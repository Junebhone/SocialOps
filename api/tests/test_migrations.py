"""The migration and the models must describe the same schema.

The most common step-1 regression is editing a model and forgetting to generate
the migration. Nothing else in the suite would catch it: the tests build their
database from `alembic upgrade head`, so a drifted model would simply never be
exercised.
"""

import os
import subprocess
from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base
from tests.conftest import _test_database_url


async def test_upgrade_head_leaves_no_model_drift(engine: AsyncEngine) -> None:
    def _diff(sync_conn: Connection) -> list[Any]:
        return compare_metadata(MigrationContext.configure(sync_conn), Base.metadata)

    async with engine.connect() as conn:
        assert await conn.run_sync(_diff) == []


def test_downgrade_to_base_then_upgrade_round_trips() -> None:
    """Proves downgrade() is not a stub, so `make reset` can rebuild from empty."""
    env = {**os.environ, "DATABASE_URL": _test_database_url()}
    for command in (["alembic", "downgrade", "base"], ["alembic", "upgrade", "head"]):
        result = subprocess.run(
            command, cwd="/app", env=env, capture_output=True, text=True, timeout=120
        )
        assert result.returncode == 0, result.stderr


async def test_constraint_names_follow_the_naming_convention(engine: AsyncEngine) -> None:
    """Deterministic names are what let a Phase 2+ migration drop a constraint.

    Left to Postgres these would be `comments_pkey` and friends, and renaming
    them later needs a hand-written migration.
    """

    def _names(sync_conn: Connection) -> set[str]:
        inspector = inspect(sync_conn)
        found = {inspector.get_pk_constraint("comments")["name"]}
        found |= {c["name"] for c in inspector.get_unique_constraints("comments")}
        found |= {c["name"] for c in inspector.get_foreign_keys("comments")}
        found |= {c["name"] for c in inspector.get_check_constraints("comments")}
        return {name for name in found if name}

    async with engine.connect() as conn:
        names = await conn.run_sync(_names)

    assert {
        "pk_comments",
        "uq_comments_post_id_external_id",
        "fk_comments_post_id_posts",
        "ck_comments_sentiment_range",
    } <= names


async def test_the_agent_runs_entity_index_is_composite(engine: AsyncEngine) -> None:
    """D7: 'what did this comment cost end to end' must be one index lookup."""

    def _indexes(sync_conn: Connection) -> list[list[str | None]]:
        return [
            list(index["column_names"]) for index in inspect(sync_conn).get_indexes("agent_runs")
        ]

    async with engine.connect() as conn:
        indexes = await conn.run_sync(_indexes)

    assert ["entity_type", "entity_id"] in indexes
