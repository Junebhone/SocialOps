"""Structured JSON logging for the API (CLAUDE.md hard rule #8).

One JSON line per request, every line carrying `request_id`. The id is bound to a
context variable rather than passed around, so anything logged deeper in the stack
inherits it without threading an argument through every call.

Step 10 extends this (job correlation across the queue); the rule says day one, so
the shape is here from the start.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response


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


log = structlog.get_logger()


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Bind a request id, emit exactly one log line per request, echo the id back.

    An inbound `X-Request-ID` is honoured so a request can be traced from the web
    app through the API and into the job it enqueues.
    """
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception(
            "request.failed",
            method=request.method,
            path=request.url.path,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        raise

    log.info(
        "request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    response.headers["X-Request-ID"] = request_id
    return response
