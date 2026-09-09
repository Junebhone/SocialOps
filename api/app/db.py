"""Database engine and session wiring.

Hard rule #2 forbids module-level mutable state, and an Engine is mutable — it
owns a connection pool. So this module exposes only a pure factory; the engine
itself is built in the app's lifespan and reached through `request.state`.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings


def create_engine_and_sessionmaker(
    settings: Settings | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Build an engine and a session factory. Holds no state of its own.

    `expire_on_commit=False` is required rather than stylistic: with the default,
    commit expires every loaded attribute, and the next read — during
    `response_model` serialization — becomes implicit IO, which cannot work under
    async and surfaces as a greenlet error just before the response is written.
    """
    settings = settings or get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, from the lifespan-owned factory.

    This dependency owns rollback and close only — it must never commit. A yield
    dependency's exit code runs after the response has been sent, so a commit
    that failed here could not change a 201 the client already received. Routes
    commit; this cleans up.
    """
    factory: async_sessionmaker[AsyncSession] = request.state.sessionmaker
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            # Re-raising is mandatory: swallowing here would turn a failed
            # request into a silent 200 and leak the session.
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]
