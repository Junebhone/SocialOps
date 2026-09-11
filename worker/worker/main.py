"""arq worker entry point.

Two job types, one shape: `process_comment` and `process_asset`. Each owns a
session, runs its orchestrator graph, and — only after arq has exhausted its
retries — records the failure in `failed_jobs`.

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
from worker.orchestrator import run_asset, run_comment, run_ideation, run_insight

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
            # The factory goes in so an agent failure can be recorded on a
            # session that outlives this one's rollback (hard rule #5).
            state = await run_comment(comment_id, session, audit_factory=factory)
        return f"comment {comment_id} processed by {', '.join(state.agents_run)}"
    except (Exception, asyncio.CancelledError) as exc:
        # arq's `job_timeout` cancels this coroutine via `asyncio.wait_for`,
        # raising `CancelledError` (a `BaseException` since Python 3.8) — a
        # bare `except Exception` misses it, so a timeout used to skip the
        # DLQ entirely (hard rule #7). Always re-raised below.
        await _handle_failure(ctx, "process_comment", {"comment_id": comment_id}, exc)
        raise


async def process_asset(ctx: dict[str, Any], asset_id: int) -> str:
    """Run one uploaded image through the asset graph.

    Deliberately the same shape as `process_comment`, down to the failure
    handling. Two job types that differ only in which graph they call is what
    keeps the DLQ, the Retry button and step 9's measurements uniform across
    both paths instead of needing a second version of each.
    """
    bind_job_context(ctx)
    factory = ctx["session_factory"]

    try:
        async with session_scope(factory) as session:
            state = await run_asset(asset_id, session, audit_factory=factory)
        return f"asset {asset_id} processed by {', '.join(state.agents_run)}"
    except (Exception, asyncio.CancelledError) as exc:
        await _handle_failure(ctx, "process_asset", {"asset_id": asset_id}, exc)
        raise


async def process_ideation(ctx: dict[str, Any], brand_id: int) -> str:
    """Run one ideation call for a brand, triggered on demand (a "Generate
    Ideas" click), not by a queued comment or asset row.

    Same shape as `process_comment`/`process_asset` down to the failure
    handling, deliberately: one DLQ, one Retry button, one place a timeout is
    handled, regardless of which of the three jobs it was.
    """
    bind_job_context(ctx)
    factory = ctx["session_factory"]

    try:
        async with session_scope(factory) as session:
            state = await run_ideation(brand_id, session, audit_factory=factory)
        return f"ideation for brand {brand_id} processed by {', '.join(state.agents_run)}"
    except (Exception, asyncio.CancelledError) as exc:
        await _handle_failure(ctx, "process_ideation", {"brand_id": brand_id}, exc)
        raise


async def process_insight(ctx: dict[str, Any], brand_id: int) -> str:
    """Run one insight call for a brand, triggered on demand (a "Generate
    insights" click). Same shape as `process_ideation`."""
    bind_job_context(ctx)
    factory = ctx["session_factory"]

    try:
        async with session_scope(factory) as session:
            state = await run_insight(brand_id, session, audit_factory=factory)
        return f"insight for brand {brand_id} processed by {', '.join(state.agents_run)}"
    except (Exception, asyncio.CancelledError) as exc:
        await _handle_failure(ctx, "process_insight", {"brand_id": brand_id}, exc)
        raise


async def _handle_failure(
    ctx: dict[str, Any],
    job_type: str,
    payload: dict[str, Any],
    exc: Exception | asyncio.CancelledError,
) -> None:
    """Log every attempt; dead-letter only the last one.

    Writing a `failed_jobs` row per attempt would put three rows in the DLQ for
    one comment and make the Agents page's failed count triple the real number
    of broken jobs.
    """
    attempt = int(ctx.get("job_try", 1))
    log.error("job.failed", job_type=job_type, attempt=attempt, error=str(exc), **payload)
    if attempt >= MAX_TRIES:
        await _record_failure(ctx["session_factory"], job_type, payload, exc, attempt)


async def _record_failure(
    factory: Any,
    job_type: str,
    payload: dict[str, Any],
    exc: Exception | asyncio.CancelledError,
    attempts: int,
) -> None:
    """The DLQ (hard rule #7). Payload must be enough to re-enqueue: the Failed
    Jobs panel has a Retry button that reads exactly this row.

    Also marks the comment `failed`. Without it a dead-lettered comment stays at
    `new` and reads in the Inbox as one the pipeline simply has not reached yet
    — indistinguishable from a queue that is merely behind, which is the wrong
    thing to believe while debugging a stalled replay. `CommentStatus` has
    carried the value since step 1; nothing set it until now.
    """
    async with session_scope(factory) as session:
        session.add(
            FailedJob(
                job_type=job_type,
                payload_json=payload,
                error=f"{type(exc).__name__}: {exc}",
                attempts=attempts,
            )
        )
        comment_id = payload.get("comment_id")
        if comment_id is not None:
            comment = await session.get(Comment, comment_id)
            if comment is not None:
                comment.status = "failed"

    log.error("job.dead_lettered", job_type=job_type, attempts=attempts, **payload)


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
            (await session.execute(select(Outbox).where(Outbox.sent_at.is_(None)))).scalars().all()
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
    functions = [
        process_comment,
        process_asset,
        process_ideation,
        process_insight,
        drain_outbox,
        ping,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
    # A comment needs one fast call and sometimes one standard call; an asset
    # needs a vision call and a standard call. 300s leaves room for a cold model
    # load on the first job after an idle gap, which is the slowest thing either
    # path can hit.
    job_timeout = 300
    # One slot, not two. This used to be two — the second reserved for
    # drain_outbox, back when it ran as an arq cron job counted against this
    # same limit. It no longer does: `_outbox_loop` drains it on a plain
    # asyncio timer outside arq's scheduling entirely (see that function's own
    # docstring), so nothing here needs a second slot for it any more — that
    # reasoning was never updated when the outbox loop moved off arq.
    #
    # Measured, not assumed: at two slots, an asset job and an insight job
    # started running "concurrently" from arq's point of view, but Ollama
    # serializes requests per model, so the second one just sat blocked on the
    # HTTP call for its entire `job_timeout` window with zero real progress —
    # both timed out together, and the one that hit a slow-to-cancel state
    # landed as a hard `TimeoutError` instead of a clean `CancelledError`,
    # which arq does not auto-retry (it removes the job from its queue
    # outright on that path — see arq's `run_job`/`finish_job`, where only a
    # clean `CancelledError` takes the "will be run again" branch). One slot
    # makes that collision structurally impossible: only one job — and so only
    # one Ollama call — runs at a time, matching what Ollama already enforces
    # anyway.
    max_jobs = 1
