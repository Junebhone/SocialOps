"""Shared test fixtures.

Config is required-by-default (`app.config`), so the environment must be
populated before anything imports the app. Compose already sets these for the
container; setting them here keeps the suite runnable anywhere.

Tests run against a separate `<database>_test` database so `make test` can never
disturb seeded demo data or a running replay. The schema is built by running the
real `alembic upgrade head` rather than `Base.metadata.create_all`, which means
"tests pass" also proves "make migrate works".
"""

import os
import subprocess
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://socialops:socialops@postgres:5432/socialops",
    "REDIS_URL": "redis://redis:6379/0",
    "STORAGE_BACKEND": "local",
    "STORAGE_ROOT": "/app/storage",
    "LLM_PROVIDER": "ollama",
    "LLM_MODEL_FAST": "qwen3.5:2b",
    "LLM_MODEL_TEXT": "qwen3.5:9b",
    "LLM_MODEL_VISION": "qwen3.5:9b",
    "OLLAMA_BASE_URL": "http://host.docker.internal:11434",
}

for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)

# Hard rule #10's `models.ALLOW_MODEL_REQUESTS = False` guard lives in the
# WORKER's conftest, not here: pydantic-ai is a worker dependency and the API
# never calls a model. Importing it here to set a flag would add the very
# dependency the rule guards.

from app.db import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


def _test_database_url() -> str:
    """Derived from DATABASE_URL, so there is still exactly one URL in the env."""
    url = make_url(os.environ["DATABASE_URL"])
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """A throwaway database, built by the migration that ships."""
    admin_url = make_url(os.environ["DATABASE_URL"]).set(database="postgres")
    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT.
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    name = make_url(_test_database_url()).database
    async with admin.connect() as conn:
        # FORCE: DROP fails if any connection to it is still open.
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd="/app",
        env={**os.environ, "DATABASE_URL": _test_database_url()},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

    eng = create_async_engine(_test_database_url())
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _clean_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """Isolate every test. TRUNCATE is faster than recreating the schema."""
    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as db_session:
        yield db_session


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """An HTTP client bound to the test database.

    httpx's ASGITransport does not run the app's lifespan, so `request.state`
    has no sessionmaker. Overriding the dependency is what makes this work — and
    is why no `asgi-lifespan` dependency is needed.
    """

    async def _override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db_session:
            try:
                yield db_session
            except Exception:
                await db_session.rollback()
                raise

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
