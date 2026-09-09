"""The session dependency's transaction contract.

`get_session` owns rollback and close, never commit. These are the tests that
stop someone "simplifying" it by moving the commit into the dependency, where a
failure could not change a response the client has already received.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import SessionDep, get_session
from app.main import app
from app.models import Brand
from tests.factories import BRAND_RULES


@app.post("/_test_explode", include_in_schema=False)
async def _explode(session: SessionDep) -> None:
    """A route that writes and then fails. Mounted only for these tests."""
    session.add(Brand(name="doomed", voice_guidelines="x", brand_rules_json=BRAND_RULES))
    await session.flush()
    raise RuntimeError("route failed after writing")


def _bind(factory: async_sessionmaker[AsyncSession]) -> None:
    """Point the app at the test database.

    ASGITransport does not run the lifespan, so `request.state.sessionmaker`
    does not exist; overriding the dependency is what supplies it.
    """

    async def _override() -> AsyncIterator[AsyncSession]:
        async with factory() as db_session:
            try:
                yield db_session
            except Exception:
                await db_session.rollback()
                raise

    app.dependency_overrides[get_session] = _override


async def test_a_failing_route_leaves_nothing_committed(
    session_factory: async_sessionmaker[AsyncSession], session: AsyncSession
) -> None:
    _bind(session_factory)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/_test_explode")
    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert (await session.execute(select(Brand))).scalars().all() == []


async def test_the_dependency_reraises_rather_than_swallowing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dropping the `raise` after rollback would turn a failure into a silent
    200 and leak the session."""
    _bind(session_factory)
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with pytest.raises(RuntimeError, match="route failed after writing"):
                await client.post("/_test_explode")
    finally:
        app.dependency_overrides.clear()
