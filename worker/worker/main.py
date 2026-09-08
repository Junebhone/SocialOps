"""arq worker entry point.

Step 0 wires the queue and nothing else. The orchestrator graph, the agents, and the
job functions arrive in step 4; `ping` exists so the worker has a registered function
and the container has something to prove it is connected to Redis.

`max_tries = 3` here is the only retry mechanism in the system (hard rule #7, D12).
"""

from typing import Any

import structlog
from arq.connections import RedisSettings

from worker.config import get_settings
from worker.logging import bind_job_context, configure_logging

configure_logging()

log = structlog.get_logger()


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job. Every line it logs carries job_id (hard rule #8)."""
    bind_job_context(ctx)
    log.info("ping")
    return "pong"


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    log.info(
        "worker.startup",
        llm_provider=settings.llm_provider,
        model_fast=settings.model_for_tier("fast"),
        model_standard=settings.model_for_tier("standard"),
    )


class WorkerSettings:
    """Consumed by `arq worker.main.WorkerSettings`."""

    functions = [ping]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
    job_timeout = 300
