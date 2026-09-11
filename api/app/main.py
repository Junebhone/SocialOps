"""FastAPI application entry point.

Phase 1 scope: the app is stateless (hard rule #2). No module-level mutable
state, no in-RAM sessions, no caches — anything that must survive a request goes
to Postgres or Redis.

The database engine is the one piece of long-lived mutable state the process
needs (it owns a connection pool), so it is built in the lifespan and reached
through `request.state` rather than being a module global.
"""

from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Literal, TypedDict

import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import SessionDep, create_engine_and_sessionmaker
from app.logging import configure_logging, request_id_middleware
from app.routers import (
    agent_runs,
    assets,
    brands,
    comments,
    content_drafts,
    content_ideas,
    failed_jobs,
    ingest,
    insights,
    platform_accounts,
    posts,
    reply_drafts,
)
from app.services import queue as queue_service

configure_logging()

log = structlog.get_logger()


class State(TypedDict):
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    """Own the engine for the life of the process.

    Building it here rather than at import keeps hard rule #2 intact, gives
    shutdown an ordered `dispose()`, and turns a bad DATABASE_URL into a startup
    failure instead of a 500 on the first request.
    """
    engine, sessionmaker = create_engine_and_sessionmaker()
    try:
        yield {"engine": engine, "sessionmaker": sessionmaker}
    finally:
        await engine.dispose()


app = FastAPI(title="SocialOps API", version="0.1.0", lifespan=lifespan)

# One structured JSON line per request, tagged with request_id (hard rule #8).
app.middleware("http")(request_id_middleware)

# The browser calls the API directly from the Next.js app on another origin.
# Phase 1 has no auth and no cookies, so a permissive policy costs nothing here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brands.router)
app.include_router(platform_accounts.router)
app.include_router(posts.router)
app.include_router(ingest.router)
app.include_router(comments.router)
app.include_router(reply_drafts.router)
app.include_router(assets.router)
app.include_router(content_drafts.router)
app.include_router(content_ideas.router)
app.include_router(insights.router)
app.include_router(agent_runs.router)
app.include_router(failed_jobs.router)


class Health(BaseModel):
    status: str
    version: str
    llm_provider: str


class Readiness(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    redis: bool


@app.get("/health", response_model=Health)
async def health() -> Health:
    """Liveness: is this process up and configured?

    Deliberately touches nothing external. A liveness probe that fails when a
    dependency is down asks to be restarted for someone else's outage, which
    turns a database blip into a restart loop. Use /health/ready for "can it
    actually serve".
    """
    settings = get_settings()
    return Health(status="ok", version=app.version, llm_provider=settings.llm_provider)


@app.get("/health/ready", response_model=Readiness)
async def ready(session: SessionDep, response: Response) -> Readiness:
    """Readiness: can this process serve a real request?

    This exists because of a real incident. Docker's disk filled, Postgres hit
    `PANIC: could not write to file` and refused to restart, and `docker compose
    ps` went on reporting the API as **healthy** — because the Compose
    healthcheck pointed at /health, which by design touches nothing. Four green
    services, and every endpoint returning 500. See D19.

    Returns 503 rather than raising, so the body still names which dependency is
    down. "Postgres is unreachable" and "the API is broken" need to look
    different at 2am.
    """
    database = await _can_reach(_ping_database(session))
    redis = await _can_reach(_ping_redis())

    if database and redis:
        return Readiness(status="ok", database=True, redis=True)

    response.status_code = 503
    log.warning("readiness.degraded", database=database, redis=redis)
    return Readiness(status="degraded", database=database, redis=redis)


async def _can_reach(check: Awaitable[None]) -> bool:
    """Any failure is a failure. The reason goes in the log, not the response —
    a readiness body is read by a healthcheck, not by a person."""
    try:
        await check
    except Exception:
        log.exception("readiness.check_failed")
        return False
    return True


async def _ping_database(session: AsyncSession) -> None:
    await session.execute(text("SELECT 1"))


async def _ping_redis() -> None:
    # Resolved through the module, not imported by name: the test suite's
    # autouse guard patches `app.services.queue.redis_pool`, and a
    # `from ... import redis_pool` here would bind past it and open a real
    # connection to the shared Redis from a test.
    async with queue_service.redis_pool() as redis:
        await redis.ping()
