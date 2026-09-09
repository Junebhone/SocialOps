"""Shared worker test fixtures.

Two jobs: populate the required environment before `worker.config` is imported, and
slam the door on real model calls. `ALLOW_MODEL_REQUESTS = False` makes hard rule #10
("no test may call a real model") something the suite enforces rather than something
we promise — any accidental live request raises instead of quietly hitting Ollama.
"""

import os

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

from pydantic_ai import models  # noqa: E402

models.ALLOW_MODEL_REQUESTS = False


from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _worker_test_database_url() -> str:
    """A database of this worker's own, separate from the api suite's.

    Both suites can run at once (`make test` runs them back to back, but nothing
    stops them overlapping), and two suites dropping and creating the same
    database is a race that fails intermittently and looks like flakiness.
    """
    url = make_url(os.environ["DATABASE_URL"])
    return url.set(database=f"{url.database}_worker_test").render_as_string(hide_password=False)


@pytest.fixture(scope="session")
async def worker_engine() -> AsyncIterator[AsyncEngine]:
    """Schema built with create_all, not alembic.

    The api suite already proves the migration and the models describe the same
    schema; repeating that here would only be slower. What these tests need is a
    real Postgres with the real constraints.
    """
    from app.models import Base

    admin_url = make_url(os.environ["DATABASE_URL"]).set(database="postgres")
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    name = make_url(_worker_test_database_url()).database
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()

    engine = create_async_engine(_worker_test_database_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(worker_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    from app.models import Base

    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    async with worker_engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    factory = async_sessionmaker(worker_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
