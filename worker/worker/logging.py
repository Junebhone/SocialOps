"""Structured JSON logging for the worker (CLAUDE.md hard rule #8).

Mirrors `api/app/logging.py`. The correlation key here is `job_id` rather than
`request_id`: arq puts the job id in the job context, and `bind_job_context` pins it
to a context variable so every line a job emits — including lines from agents and
orchestrator nodes called several frames down — carries it without being passed one.
"""

from typing import Any

import structlog


def configure_logging() -> None:
    """JSON to stdout. Docker collects stdout, so there is no file handler."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        cache_logger_on_first_use=True,
    )


def bind_job_context(ctx: dict[str, Any]) -> None:
    """Call at the top of every job function.

    `job_try` is included because arq owns retries (hard rule #7) — when a job lands
    in `failed_jobs`, the log shows which attempt it died on.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        job_id=ctx.get("job_id"),
        job_try=ctx.get("job_try"),
    )
