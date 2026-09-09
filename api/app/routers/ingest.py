"""Comment ingestion and queue visibility.

Ingest is idempotent (D9): running `make replay` twice inserts nothing the second
time and enqueues nothing, so a repeated 2,000-comment dump costs zero extra
model calls rather than two wasted hours.
"""

import csv
import io
import time

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import AwareDatetime, BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.db import SessionDep
from app.models import Comment, FailedJob, PlatformAccount, Post

router = APIRouter(tags=["ingest"])


class IncomingComment(BaseModel):
    """One row of a dump. Shaped by what a platform export actually gives you."""

    external_id: str = Field(min_length=1, max_length=128)
    post_external_id: str
    account_handle: str
    author: str
    text: str
    # No default: comments.created_at is the platform's timestamp and the column
    # has no server default, so a missing value must fail here rather than at insert.
    created_at: AwareDatetime


class IngestResult(BaseModel):
    inserted: int
    skipped: int
    enqueued: int


async def _resolve_posts(session: SessionDep) -> dict[tuple[str, str], int]:
    """Map (account_handle, post_external_id) -> post id.

    Resolved in one query rather than per comment: at 2,000 comments the
    round-trips dominate everything else in this endpoint.
    """
    rows = await session.execute(
        select(PlatformAccount.handle, Post.external_id, Post.id).join(
            Post, Post.account_id == PlatformAccount.id
        )
    )
    return {(handle, external_id): post_id for handle, external_id, post_id in rows}


def _parse_csv(raw: bytes) -> list[IncomingComment]:
    reader = csv.DictReader(io.StringIO(raw.decode()))
    return [IncomingComment(**row) for row in reader]


async def _read_payload(request: Request) -> list[IncomingComment]:
    """Accept a JSON array, a CSV upload, or a raw CSV body.

    Content-type branching rather than two typed parameters: declaring an
    `UploadFile` alongside a JSON body makes FastAPI treat the whole endpoint as
    multipart, and the JSON array then never binds — which is a 422 on the happy
    path that `make replay` uses.
    """
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(status_code=422, detail="Expected a 'file' part")
        return _parse_csv(await upload.read())

    if "csv" in content_type:
        return _parse_csv(await request.body())

    try:
        rows = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Body is not valid JSON") from exc
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="Expected a JSON array of comments")
    try:
        return [IncomingComment(**row) for row in rows]
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc


@router.post(
    "/ingest/comments",
    response_model=IngestResult,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/IncomingComment"},
                    }
                },
                "text/csv": {"schema": {"type": "string"}},
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                },
            }
        }
    },
)
async def ingest_comments(request: Request, session: SessionDep) -> IngestResult:
    """Insert new comments and enqueue one job per NEW comment.

    Idempotent: replaying the same dump inserts nothing the second time.
    """
    payload = await _read_payload(request)
    if not payload:
        raise HTTPException(status_code=422, detail="Provide a JSON array or a CSV file")

    posts = await _resolve_posts(session)

    inserted_ids: list[int] = []
    skipped = 0
    for comment in payload:
        post_id = posts.get((comment.account_handle, comment.post_external_id))
        if post_id is None:
            # An unknown post is a data problem, not a transient one; retrying
            # would not help, so it is counted rather than raised.
            skipped += 1
            continue

        # D9. ON CONFLICT on exactly the (post_id, external_id) unique constraint,
        # so a replayed dump is a no-op instead of a duplicate charge.
        statement = (
            insert(Comment)
            .values(
                post_id=post_id,
                external_id=comment.external_id,
                author=comment.author,
                text=comment.text,
                created_at=comment.created_at,
            )
            .on_conflict_do_nothing(index_elements=["post_id", "external_id"])
            .returning(Comment.id)
        )
        new_id = (await session.execute(statement)).scalar_one_or_none()
        if new_id is None:
            skipped += 1
        else:
            inserted_ids.append(new_id)

    await session.commit()

    enqueued = await _enqueue(inserted_ids)
    return IngestResult(inserted=len(inserted_ids), skipped=skipped, enqueued=enqueued)


async def _enqueue(comment_ids: list[int], attempt: str = "") -> int:
    """One job per comment, keyed by comment id.

    The job key is what stops a re-enqueue double-charging: arq returns None for
    a job id that already exists, so the same comment cannot be queued twice
    even if this endpoint is called concurrently (D9).

    `attempt` exists because that same key blocks legitimate retries. arq keeps a
    finished job's key for an hour, so a comment whose job died is refused
    re-entry for an hour — which is exactly what happened when the database ran
    out of disk mid-replay and 124 jobs were lost. A retry is a genuinely new
    attempt and gets its own key; the dedupe still holds within one attempt.
    """
    if not comment_ids:
        return 0

    settings = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        enqueued = 0
        for comment_id in comment_ids:
            job = await redis.enqueue_job(
                "process_comment", comment_id, _job_id=f"comment-{comment_id}{attempt}"
            )
            enqueued += job is not None
        return enqueued
    finally:
        await redis.aclose()


class RequeueResult(BaseModel):
    requeued: int


@router.post("/queue/requeue", response_model=RequeueResult)
async def requeue_unprocessed(session: SessionDep) -> RequeueResult:
    """Re-enqueue every comment still sitting at `new`.

    Ingest only enqueues comments it actually inserted (D9), which is right: it
    is what stops a replayed dump re-spending model calls. But it means a job
    lost to a worker outage is never retried — the comment stays `new` forever
    and the queue looks healthy. This is the recovery path, and it is what
    step 9's Retry button calls.

    Idempotent for the same reason ingest is: the job key is derived from the
    comment id, so a comment already queued is not queued twice.
    """
    stuck = (
        (await session.execute(select(Comment.id).where(Comment.status == "new")))
        .scalars()
        .all()
    )
    attempt = f"-retry-{int(time.time())}"
    return RequeueResult(requeued=await _enqueue(list(stuck), attempt=attempt))


class QueueStats(BaseModel):
    queued: int
    running: int
    failed: int


@router.get("/queue/stats", response_model=QueueStats)
async def queue_stats(session: SessionDep) -> QueueStats:
    """Live queue depth for the top bar, polled every 2s.

    Read straight from Redis and the DLQ table. D18 dropped the idea of sampling
    this into a table every 10s — that existed only to feed a chart D1 cut, and
    it would have put a permanent background writer inside the worker whose
    latency step 9 measures.
    """
    settings = get_settings()
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        queued = int(await redis.zcard("arq:queue") or 0)
        # arq writes one `in-progress` key per job it has picked up.
        running = len(await redis.keys("arq:in-progress:*"))
    finally:
        await redis.aclose()

    failed = int(await session.scalar(select(func.count()).select_from(FailedJob)) or 0)

    return QueueStats(queued=queued, running=running, failed=failed)
