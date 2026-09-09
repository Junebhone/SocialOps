"""Alembic environment, wired for an async engine and for app.config.

Two things here are deliberate:

1. The database URL comes from `app.config`, never from `alembic.ini`. Hard rule
   #1 says config is read in one place; a `sqlalchemy.url` line in the ini would
   be a second place, and it would drift from what the containers actually use.
2. The URL is injected into a copy of the config SECTION DICT rather than via
   `config.set_main_option()`. ConfigParser applies pyformat interpolation to
   values set that way, so a percent-encoded character in a password raises
   `ValueError: invalid interpolation syntax`. Harmless in Compose, guaranteed
   to bite on the move to RDS.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing the models package is what registers every table on Base.metadata.
# If a model is missing from its __init__, autogenerate diffs a half-empty
# MetaData against a populated database and emits DROP TABLE.
from app.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def _database_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it against a database."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = dict(config.get_section(config.config_ini_section, {}))
    configuration["sqlalchemy.url"] = _database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        # The engine lives and dies inside asyncio.run(), so a pooled connection
        # would outlive the loop that created it.
        poolclass=pool.NullPool,
    )

    # .connect(), not .begin() — context.begin_transaction() opens the transaction.
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
