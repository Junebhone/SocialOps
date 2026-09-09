"""arq worker entry point.

One job type in step 4: `process_comment`. It owns a session, runs the
orchestrator graph, and — only after arq has exhausted its retries — records the
failure in `failed_jobs`.

`max_tries = 3` is the only retry mechanism in the system (hard rule #7, D12).
There is deliberately no second one: two retry layers on one job means
double-charged model calls and DLQ entries nobody can explain.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from app.models import Comment, FailedJob, Outbox, ReplyDraft
from arq.connections import RedisSettings
from sqlalchemy import select

from worker.config import get_settings
from worker.db import create_engine_and_sessionmaker, session_scope
from worker.logging import bind_job_context, configure_logging
from worker.orchestrator import run_comment

configure_logging()

log = structlog.get_logger()

MAX_TRIES = 3

# D3: the outbox IS the publish step, so this interval is the delay between a
# human clicking Approve and the loop visibly closing.
OUTBOX_INTERVAL_SECONDS = 30


async def process_comment(ctx: dict[str, Any], comment_id: int) -> str:
    """Run one comment through the orchestrator graph.

    Raises on failure so arq retries. On the final attempt the failure is also
    written to `failed_jobs` first — that write uses its own session, because the
    job's session has been rolled back by then and anything added to it would be
    discarded with it.
    """
    bind_job_context(ctx)
    factory = ctx["session_factory"]

    try:
        async with session_scope(factory) as session:
            state = await run_comment(comment_id, session)
        return f"comment {comment_id} processed by {', '.join(state.agents_run)}"
    except Exception as exc:
        attempt = int(ctx.get("job_try", 1))
        log.error(
            "job.failed",
            job_type="process_comment",
            comment_id=comment_id,
            attempt=attempt,
            error=str(exc),
        )
        if attempt >= MAX_TRIES:
            await _record_failure(factory, comment_id, exc, attempt)
        raise


async def _record_failure(
    factory: Any, comment_id: int, exc: Exception, attempts: int
) -> None:
    """The DLQ (hard rule #7). Payload must be enough to re-enqueue: step 9 adds
    a Retry button that reads exactly this row."""
    async with session_scope(factory) as session:
        session.add(
            FailedJob(
                job_type="process_comment",
                payload_json={"comment_id": comment_id},
                error=f"{type(exc).__name__}: {exc}",
                attempts=attempts,
            )
        )
    log.error("job.dead_lettered", comment_id=comment_id, attempts=attempts)


async def drain_outbox(ctx: dict[str, Any]) -> str:
    """Publish approved replies (D3).

    There is no real platform in Phase 1, so "publishing" means stamping
    `sent_at` and flipping the draft to `published`. That is deliberately the
    whole step: it is what makes the approval loop visibly close on stage, and
    it is the exact seam a live platform integration would replace.
    """
    bind_job_context(ctx)
    factory = ctx["session_factory"]
    sent = 0

    async with session_scope(factory) as session:
        pending = (
            (await session.execute(select(Outbox).where(Outbox.sent_at.is_(None))))
            .scalars()
            .all()
        )
        for row in pending:
            row.sent_at = datetime.now(UTC)
            draft = await session.get(ReplyDraft, row.reply_draft_id)
            if draft is not None:
                draft.status = "published"
                comment = await session.get(Comment, draft.comment_id)
                if comment is not None:
                    comment.status = "replied"
            sent += 1

    if sent:
        log.info("outbox.drained", published=sent)
    return f"published {sent}"


async def _outbox_loop(ctx: dict[str, Any]) -> None:
    """Drain the outbox every 30s, independent of the job queue.

    This is deliberately NOT an arq cron job, which is what step 5 asks for and
    what the first implementation used. arq's queue is a Redis sorted set scored
    by enqueue time, so a cron job scheduled now sorts BEHIND every comment job
    already queued: during a 300-comment replay the drain waited behind 261 jobs
    and never ran. A human clicking Approve saw nothing publish. Raising
    max_jobs does not fix it — the job is not slot-starved, it is queue-ordered.

    A plain periodic task sidesteps queue ordering entirely. It is not a second
    retry or durability layer (hard rule #7): it schedules no jobs and retries
    nothing. arq still owns every job retry in the system.
    """
    while True:
        await asyncio.sleep(OUTBOX_INTERVAL_SECONDS)
        try:
            await drain_outbox(ctx)
        except Exception:
            # A failed drain must not kill the loop; the rows stay unsent and
            # the next tick picks them up.
            log.exception("outbox.drain_failed")


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job, kept so the queue can be exercised without a model."""
    bind_job_context(ctx)
    log.info("ping")
    return "pong"


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    engine, factory = create_engine_and_sessionmaker()
    ctx["engine"] = engine
    ctx["session_factory"] = factory
    ctx["outbox_task"] = asyncio.create_task(_outbox_loop(ctx))
    log.info(
        "worker.startup",
        llm_provider=settings.llm_provider,
        model_fast=settings.model_for_tier("fast"),
        model_standard=settings.model_for_tier("standard"),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    task = ctx.get("outbox_task")
    if task is not None:
        task.cancel()
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


class WorkerSettings:
    """Consumed by `arq worker.main.WorkerSettings`."""

    # drain_outbox stays registered so it can also be triggered by hand, but the
    # periodic run is the asyncio loop started in `startup`, not a cron job.
    functions = [process_comment, drain_outbox, ping]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
    # A comment needs one fast call and sometimes one standard call. 300s leaves
    # room for a cold model load on the first job after an idle gap.
    job_timeout = 300
    # Two slots, not one. One is the honest setting for LLM work — the machine
    # is memory-bandwidth-bound on a 9B model, so concurrency buys no throughput
    # and muddies the latency numbers step 9 measures (D4). But arq counts cron
    # jobs against the same limit, so at one slot the outbox drain never gets
    # scheduled while a replay is running: a human clicks Approve and nothing
    # publishes until the queue empties. The second slot exists for that
    # millisecond-long database job, not for throughput. Ollama serializes
    # requests per model anyway, so two comment jobs overlapping does not double
    # the model thrashing.
    max_jobs = 2
