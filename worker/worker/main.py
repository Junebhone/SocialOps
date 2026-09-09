"""arq worker entry point.

One job type in step 4: `process_comment`. It owns a session, runs the
orchestrator graph, and — only after arq has exhausted its retries — records the
failure in `failed_jobs`.

`max_tries = 3` is the only retry mechanism in the system (hard rule #7, D12).
There is deliberately no second one: two retry layers on one job means
double-charged model calls and DLQ entries nobody can explain.
"""

from typing import Any

import structlog
from app.models import FailedJob
from arq.connections import RedisSettings

from worker.config import get_settings
from worker.db import create_engine_and_sessionmaker, session_scope
from worker.logging import bind_job_context, configure_logging
from worker.orchestrator import run_comment

configure_logging()

log = structlog.get_logger()

MAX_TRIES = 3


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
    log.info(
        "worker.startup",
        llm_provider=settings.llm_provider,
        model_fast=settings.model_for_tier("fast"),
        model_standard=settings.model_for_tier("standard"),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


class WorkerSettings:
    """Consumed by `arq worker.main.WorkerSettings`."""

    functions = [process_comment, ping]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
    # A comment needs one fast call and sometimes one standard call. 300s leaves
    # room for a cold model load on the first job after an idle gap.
    job_timeout = 300
    # One at a time. The machine is memory-bandwidth-bound on a 9B model, so
    # concurrency buys nothing and makes the latency numbers step 9 measures
    # meaningless (D4).
    max_jobs = 1
