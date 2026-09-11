"""The insight agent and its orchestration: real post performance in, plain
markers out — no fabricated scores, no forecast for unposted content (see
`InsightState`/`run_insight` in orchestrator.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.models import AgentRun, Brand, Insight, PlatformAccount, Post
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from worker import llm, main
from worker.orchestrator import run_insight

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)

MARKERS_REPLY = (
    '{"markers":['
    '"Posts naming a specific origin get more shares than general posts.",'
    '"The sampler post far outperformed single-product posts."'
    "]}"
)


@pytest.fixture
def prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "insight.md").write_text("Analyze {{posts_summary}}")


def scripted(reply: str) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(reply)])

    return FunctionModel(respond)


async def _a_brand_with_posts(db: AsyncSession, n_posts: int = 2) -> Brand:
    brand = Brand(
        name="Ridgeline Roasters",
        voice_guidelines="Warm, plain-spoken.",
        brand_rules_json={
            "prohibited_content": [],
            "required_elements": [],
            "tone": {"avoid_words": [], "prefer_words": []},
            "max_hashtags": 5,
        },
    )
    db.add(brand)
    await db.flush()
    account = PlatformAccount(brand_id=brand.id, platform="instagram", handle="@r")
    db.add(account)
    await db.flush()
    for i in range(n_posts):
        db.add(
            Post(
                account_id=account.id,
                external_id=f"p-{i}",
                text=f"Post {i}",
                posted_at=NOW,
                metrics_json={"likes": 100 * (i + 1), "comments": 5, "shares": 2},
            )
        )
    await db.commit()
    return brand


async def test_insight_writes_one_row_per_marker(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    brand = await _a_brand_with_posts(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(MARKERS_REPLY))

    state = await run_insight(brand.id, db)
    await db.commit()

    assert state.agents_run == ["insight"]
    markers = (await db.execute(select(Insight).order_by(Insight.id))).scalars().all()
    assert len(markers) == 2
    assert all(m.brand_id == brand.id for m in markers)


async def test_insight_writes_one_agent_runs_row_scoped_to_the_brand(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    brand = await _a_brand_with_posts(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(MARKERS_REPLY))

    await run_insight(brand.id, db)
    await db.commit()

    run = (await db.execute(select(AgentRun))).scalar_one()
    assert run.agent == "insight"
    assert run.entity_type == "brand"
    assert run.entity_id == brand.id


async def test_insight_on_a_brand_with_no_posts_raises(db: AsyncSession, prompts: None) -> None:
    """Generating "patterns" from zero data would mean inventing them —
    exactly what the honesty rule exists to prevent."""
    brand = Brand(
        name="No Posts Yet",
        voice_guidelines="x",
        brand_rules_json={
            "prohibited_content": [],
            "required_elements": [],
            "tone": {"avoid_words": [], "prefer_words": []},
            "max_hashtags": 5,
        },
    )
    db.add(brand)
    await db.commit()

    with pytest.raises(ValueError, match="no posts"):
        await run_insight(brand.id, db)


async def test_insight_on_a_missing_brand_raises(db: AsyncSession, prompts: None) -> None:
    with pytest.raises(LookupError):
        await run_insight(999999, db)


async def test_the_arq_job_runs_insight_and_commits(
    db: AsyncSession,
    worker_engine: AsyncEngine,
    prompts: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand = await _a_brand_with_posts(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(MARKERS_REPLY))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    result = await main.process_insight({"session_factory": factory, "job_try": 1}, brand.id)

    assert "insight" in result
    async with factory() as checking:
        markers = (await checking.execute(select(Insight))).scalars().all()
        assert len(markers) == 2
