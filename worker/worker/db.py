"""Database access for the worker.

The models themselves are the api package's (D24) — one definition of the schema,
copied into this image at build time. Only the engine is built here.

The worker's session lifetime is a job, not a request, so the factory is created
once in `on_startup` and handed to jobs through the arq context rather than being
a module global.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from worker.config import get_settings


def create_engine_and_sessionmaker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Mirrors the api's factory, including why expire_on_commit is off.

    With the default, commit expires every loaded attribute and the next read is
    implicit IO — which cannot work under async and surfaces as a greenlet error
    partway through a node.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One session per job, rolled back if the job raises.

    A job that fails must leave nothing half-written: arq will retry it, and a
    partial write from attempt one would be double-counted by attempt two.
    """
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except (Exception, asyncio.CancelledError):
            # A cancelled job (arq's `job_timeout`, via `asyncio.wait_for`)
            # raises `CancelledError`, a `BaseException` since Python 3.8 —
            # missed by a bare `except Exception`, same gap as the two failure
            # writers this session eventually rolls back for.
            await session.rollback()
            raise
