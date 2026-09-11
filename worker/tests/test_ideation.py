"""The ideation agent and its orchestration: no graph, one agent call, one
`content_ideas` row per proposed idea (see `IdeationState` in orchestrator.py
for why there is no pydantic-graph here)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.models import AgentRun, Brand, ContentIdea, Insight
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from worker import llm, main, orchestrator
from worker.orchestrator import run_ideation

IDEAS_REPLY = (
    '{"ideas":['
    '{"text":"Film the morning roast.","source_signal":"Behind-the-scenes angle"},'
    '{"text":"Post the winter sampler box.","source_signal":"Seasonal tie-in"}'
    "]}"
)


@pytest.fixture
def prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "ideation.md").write_text(
        "Voice {{brand_voice}} signals {{trend_signals}} insights {{past_insights}}"
    )


@pytest.fixture
def trends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    trends_file = tmp_path / "trends.json"
    trends_file.write_text(
        json.dumps({"Ridgeline Roasters": ["Behind-the-scenes angle", "Seasonal tie-in"]})
    )
    monkeypatch.setattr(orchestrator, "TRENDS_PATH", trends_file)


def scripted(reply: str) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(reply)])

    return FunctionModel(respond)


async def _a_brand(db: AsyncSession, name: str = "Ridgeline Roasters") -> Brand:
    brand = Brand(
        name=name,
        voice_guidelines="Warm, plain-spoken coffee roastery.",
        brand_rules_json={
            "prohibited_content": [],
            "required_elements": [],
            "tone": {"avoid_words": [], "prefer_words": []},
            "max_hashtags": 5,
        },
    )
    db.add(brand)
    await db.commit()
    return brand


async def test_ideation_writes_one_content_idea_row_per_idea(
    db: AsyncSession, prompts: None, trends: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    brand = await _a_brand(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(IDEAS_REPLY))

    state = await run_ideation(brand.id, db)
    await db.commit()

    assert state.agents_run == ["ideation"]
    ideas = (await db.execute(select(ContentIdea).order_by(ContentIdea.id))).scalars().all()
    assert [i.text for i in ideas] == ["Film the morning roast.", "Post the winter sampler box."]
    assert all(i.brand_id == brand.id for i in ideas)
    assert all(i.status == "proposed" for i in ideas)
    assert ideas[0].source_signal == "Behind-the-scenes angle"


async def test_ideation_writes_one_agent_runs_row_scoped_to_the_brand(
    db: AsyncSession, prompts: None, trends: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    brand = await _a_brand(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(IDEAS_REPLY))

    await run_ideation(brand.id, db)
    await db.commit()

    run = (await db.execute(select(AgentRun))).scalar_one()
    assert run.agent == "ideation"
    assert run.entity_type == "brand"
    assert run.entity_id == brand.id
    assert run.status == "ok"

    ideas = (await db.execute(select(ContentIdea))).scalars().all()
    assert all(i.agent_run_id == run.id for i in ideas)


async def test_ideation_on_a_brand_with_no_seeded_trends_still_runs(
    db: AsyncSession, prompts: None, trends: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A brand missing from trends.json renders "none", the same convention
    `_rule_list` uses for an unset brand rule — it does not fail the job."""
    brand = await _a_brand(db, name="Some New Brand")
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(IDEAS_REPLY))

    state = await run_ideation(brand.id, db)
    await db.commit()

    assert state.agents_run == ["ideation"]


async def test_ideation_on_a_missing_brand_raises(db: AsyncSession, prompts: None) -> None:
    with pytest.raises(LookupError):
        await run_ideation(999999, db)


async def test_ideation_uses_real_insights_as_context(
    db: AsyncSession, prompts: None, trends: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The feedback loop: once the Insight Agent has written a marker for this
    brand, the next ideation call must actually see it, not the "none"
    placeholder — otherwise the loop only exists on paper."""
    brand = await _a_brand(db)
    db.add(Insight(brand_id=brand.id, text="Posts naming an ingredient percentage do well."))
    await db.commit()

    seen_prompts: list[str] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen_prompts.append(str(messages[-1].parts[-1].content))  # type: ignore[union-attr]
        return ModelResponse(parts=[TextPart(IDEAS_REPLY)])

    monkeypatch.setattr(llm, "_build_model", lambda s, t: FunctionModel(respond))

    await run_ideation(brand.id, db)
    await db.commit()

    assert any("Posts naming an ingredient percentage do well." in p for p in seen_prompts)


async def test_the_arq_job_runs_ideation_and_commits(
    db: AsyncSession,
    worker_engine: AsyncEngine,
    prompts: None,
    trends: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`process_ideation` is the arq entry point — same shape as
    `process_comment`/`process_asset`: own session, commits on success."""
    brand = await _a_brand(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(IDEAS_REPLY))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    result = await main.process_ideation({"session_factory": factory, "job_try": 1}, brand.id)

    assert "ideation" in result
    async with factory() as checking:
        ideas = (await checking.execute(select(ContentIdea))).scalars().all()
        assert len(ideas) == 2
