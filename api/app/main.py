"""FastAPI application entry point.

Phase 1 scope: the app is stateless (hard rule #2). No module-level mutable
state, no in-RAM sessions, no caches — anything that must survive a request goes
to Postgres or Redis.

The database engine is the one piece of long-lived mutable state the process
needs (it owns a connection pool), so it is built in the lifespan and reached
through `request.state` rather than being a module global.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db import create_engine_and_sessionmaker
from app.logging import configure_logging, request_id_middleware
from app.routers import brands, comments, ingest, platform_accounts, posts, reply_drafts

configure_logging()


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


class Health(BaseModel):
    status: str
    version: str
    llm_provider: str


@app.get("/health", response_model=Health)
async def health() -> Health:
    """Liveness probe. Reads config so a misconfigured container fails visibly.

    Deliberately does not touch the database: this answers "is the process up",
    and Compose uses it to gate dependent services.
    """
    settings = get_settings()
    return Health(status="ok", version=app.version, llm_provider=settings.llm_provider)
