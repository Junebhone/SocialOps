"""Every Redis touch the API makes, in one module.

Two routers enqueue now — `/ingest/comments` and `/assets` — and the top bar
reads queue depth. Spreading `create_pool` across three call sites would also
spread the job-key convention, and the job key is not a detail: it is the whole
idempotency mechanism (D9). A comment enqueued as `comment-41` from one place
and `comment_41` from another is queued twice and charged twice, and nothing
fails loudly when that happens.

The API never consumes a job. It only ever writes one and counts what is
waiting; the worker owns execution and retries (hard rule #7).
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

# arq's own key names. Named here so the two places that read them cannot drift.
QUEUE_KEY = "arq:queue"
IN_PROGRESS_PREFIX = "arq:in-progress:*"


@asynccontextmanager
async def redis_pool() -> AsyncIterator[ArqRedis]:
    """A pool per operation, closed on the way out.

    Not a long-lived module-level client, which hard rule #2 forbids and which
    would also outlive the event loop under the test client. These calls happen
    once per request at most, so the connection cost is not worth the state.
    """
    settings = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        yield redis
    finally:
        await redis.aclose()


async def enqueue_comments(comment_ids: list[int], attempt: str = "") -> int:
    """One job per comment, keyed by comment id. Returns how many were queued.

    The job key is what stops a re-enqueue double-charging: arq returns None for
    a job id that already exists, so the same comment cannot be queued twice
    even if ingest is called concurrently (D9).

    `attempt` exists because that same key blocks legitimate retries. arq keeps
    a finished job's key for an hour, so a comment whose job died is refused
    re-entry for an hour — which is exactly what happened when the database ran
    out of disk mid-replay and 124 jobs were lost. A retry is a genuinely new
    attempt and gets its own key; the dedupe still holds within one attempt.
    """
    if not comment_ids:
        return 0

    async with redis_pool() as redis:
        queued = 0
        for comment_id in comment_ids:
            job = await redis.enqueue_job(
                "process_comment", comment_id, _job_id=f"comment-{comment_id}{attempt}"
            )
            queued += job is not None
        return queued


async def enqueue_asset(asset_id: int, attempt: str = "") -> bool:
    """One media job per uploaded asset. Same keying rule as comments.

    It matters more per-job here than on the comment path: a duplicated asset
    job is a second vision call and a second set of three platform drafts, so
    the Content page would show six cards for one photo.
    """
    async with redis_pool() as redis:
        job = await redis.enqueue_job(
            "process_asset", asset_id, _job_id=f"asset-{asset_id}{attempt}"
        )
        return job is not None


async def enqueue_ideation(brand_id: int) -> bool:
    """One ideation job per "Generate Ideas" click.

    Different keying rule from `enqueue_comments`/`enqueue_asset` on purpose:
    those key by entity id because the entity is an immutable row that should
    be processed exactly once (D9). A brand is not that — the whole point of
    the button is to run ideation again and get a fresh batch, so the job key
    carries a random suffix rather than `brand_id` alone, or the second click
    in the same session would be silently refused as a duplicate.
    """
    async with redis_pool() as redis:
        job = await redis.enqueue_job(
            "process_ideation", brand_id, _job_id=f"ideation-{brand_id}-{uuid.uuid4().hex}"
        )
        return job is not None


async def enqueue_insight(brand_id: int) -> bool:
    """One insight job per "Generate insights" click. Same keying rule as
    `enqueue_ideation` — a random suffix, not `brand_id` alone, because a
    second click is a second real request, not a duplicate (D9 does not
    apply: there is no immutable input row being re-processed)."""
    async with redis_pool() as redis:
        job = await redis.enqueue_job(
            "process_insight", brand_id, _job_id=f"insight-{brand_id}-{uuid.uuid4().hex}"
        )
        return job is not None


async def queue_depth() -> tuple[int, int]:
    """(queued, running), read live from Redis.

    D18 dropped the idea of sampling this into a table every 10s — that existed
    only to feed a chart D1 cut, and it would have put a permanent background
    writer inside the worker whose latency step 9 measures.
    """
    async with redis_pool() as redis:
        queued = int(await redis.zcard(QUEUE_KEY) or 0)
        running = await _count_in_progress(redis)
    return queued, running


async def _count_in_progress(redis: ArqRedis) -> int:
    """Count arq's in-progress keys with SCAN, not KEYS.

    `KEYS` walks the entire keyspace and blocks Redis while it does. The top bar
    polls this every 2 seconds from every open tab, and it does so *during* the
    replay whose latency step 9 measures — so the cheap-looking call is O(all
    keys) exactly when the keyspace is largest and the measurement matters.
    SCAN is incremental and yields between batches.
    """
    running = 0
    async for _key in redis.scan_iter(match=IN_PROGRESS_PREFIX, count=500):
        running += 1
    return running
