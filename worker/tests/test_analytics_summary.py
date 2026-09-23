"""The analytics agent's weekly summary: SQL numbers in, a short plain-English
paragraph out, and a Monday schedule that asks for each week exactly once
(see `run_analytics_summary` in orchestrator.py and `enqueue_due_summaries` in
main.py)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from app.models import AgentRun, AnalyticsSummary, Brand, Comment, PlatformAccount, Post
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from worker import llm, main
from worker.orchestrator import QUIET_WEEK, run_analytics_summary

WEEK_END = date(2026, 9, 20)  # a Sunday
IN_THE_WEEK = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)

SUMMARY_REPLY = '{"summary":"Ridgeline Roasters had 3 comments this week, mostly questions."}'


@pytest.fixture
def prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Captures every rendered prompt, so a test can check what the model saw."""
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "analytics.md").write_text("{{brand_name}} | {{period}} | {{stats}}")
    return []


def scripted(reply: str, seen: list[str]) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(str(messages))
        return ModelResponse(parts=[TextPart(reply)])

    return FunctionModel(respond)


async def _a_brand(db: AsyncSession, name: str = "Ridgeline Roasters") -> Brand:
    brand = Brand(
        name=name,
        voice_guidelines="Warm, plain-spoken.",
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


async def _comments(db: AsyncSession, brand: Brand, *rows: dict[str, Any]) -> None:
    account = PlatformAccount(brand_id=brand.id, platform="instagram", handle=f"@b{brand.id}")
    db.add(account)
    await db.flush()
    post = Post(
        account_id=account.id,
        external_id=f"p-{brand.id}",
        text="New roast.",
        posted_at=IN_THE_WEEK,
        metrics_json={},
    )
    db.add(post)
    await db.flush()
    for i, row in enumerate(rows):
        db.add(
            Comment(
                post_id=post.id,
                external_id=f"c-{i}",
                author="@rae",
                text="Hi",
                created_at=row.pop("created_at", IN_THE_WEEK),
                status="triaged",
                **row,
            )
        )
    await db.commit()


# --- run_analytics_summary ------------------------------------------------


async def test_a_week_with_comments_is_summarized_by_the_agent(
    db: AsyncSession, prompts: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    brand = await _a_brand(db)
    await _comments(
        db,
        brand,
        {"category": "question", "sentiment": 1},
        {"category": "question", "sentiment": 0},
        {"category": "complaint", "sentiment": -1},
    )
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(SUMMARY_REPLY, prompts))

    state = await run_analytics_summary(brand.id, db, period_end=WEEK_END)
    await db.commit()

    assert state.agents_run == ["analytics"]
    summary = (await db.execute(select(AnalyticsSummary))).scalar_one()
    assert summary.period_start == date(2026, 9, 14)
    assert summary.period_end == WEEK_END
    assert summary.text.startswith("Ridgeline Roasters had 3 comments")
    assert summary.stats_json["comments_triaged"] == 3
    assert summary.stats_json["by_category"] == {"question": 2, "complaint": 1}
    assert summary.agent_run_id is not None


async def test_the_model_is_given_the_sql_numbers(
    db: AsyncSession, prompts: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model restates numbers; it never computes them (ADR-0005)."""
    brand = await _a_brand(db)
    await _comments(db, brand, {"category": "praise", "sentiment": 2})
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(SUMMARY_REPLY, prompts))

    await run_analytics_summary(brand.id, db, period_end=WEEK_END)

    assert "comments triaged: 1" in prompts[0]
    assert "average sentiment: +2.00" in prompts[0]
    assert "replies published: 0" in prompts[0]


async def test_the_agent_run_is_audited_against_the_brand(
    db: AsyncSession, prompts: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    brand = await _a_brand(db)
    await _comments(db, brand, {"category": "praise", "sentiment": 2})
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(SUMMARY_REPLY, prompts))

    await run_analytics_summary(brand.id, db, period_end=WEEK_END)
    await db.commit()

    run = (await db.execute(select(AgentRun))).scalar_one()
    assert (run.agent, run.entity_type, run.entity_id) == ("analytics", "brand", brand.id)


async def test_a_quiet_week_is_written_without_calling_a_model(
    db: AsyncSession, prompts: list[str]
) -> None:
    """Nothing to describe means nothing for a model to invent. No
    `_build_model` patch here: `ALLOW_MODEL_REQUESTS = False` would raise if
    this path tried to call one."""
    brand = await _a_brand(db)
    # Outside the week: must not count.
    await _comments(
        db,
        brand,
        {"category": "praise", "sentiment": 2, "created_at": IN_THE_WEEK + timedelta(days=30)},
    )

    state = await run_analytics_summary(brand.id, db, period_end=WEEK_END)
    await db.commit()

    assert state.agents_run == []
    summary = (await db.execute(select(AnalyticsSummary))).scalar_one()
    assert summary.text == QUIET_WEEK
    assert summary.agent_run_id is None
    assert (await db.execute(select(AgentRun))).first() is None


async def test_a_missing_brand_raises(db: AsyncSession, prompts: list[str]) -> None:
    with pytest.raises(LookupError):
        await run_analytics_summary(999999, db)


async def test_the_arq_job_runs_and_commits(
    db: AsyncSession,
    worker_engine: AsyncEngine,
    prompts: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    brand = await _a_brand(db)
    await _comments(db, brand, {"category": "question", "sentiment": 1})
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(SUMMARY_REPLY, prompts))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    result = await main.process_analytics_summary(
        {"session_factory": factory, "job_try": 1}, brand.id, WEEK_END.isoformat()
    )

    assert "analytics" in result
    async with factory() as checking:
        summary = (await checking.execute(select(AnalyticsSummary))).scalar_one()
        assert summary.period_end == WEEK_END


# --- the Monday schedule ----------------------------------------------------


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 9, 21), date(2026, 9, 20)),  # Monday -> yesterday
        (date(2026, 9, 23), date(2026, 9, 20)),  # Wednesday -> last Sunday
        (date(2026, 9, 27), date(2026, 9, 20)),  # Sunday -> a week ago; this week is not over
    ],
)
def test_last_completed_sunday(today: date, expected: date) -> None:
    assert main.last_completed_sunday(today) == expected


class FakeRedis:
    """Honours arq's job-key dedupe, which is half of the schedule's idempotency."""

    def __init__(self) -> None:
        self.jobs: dict[str, tuple[Any, ...]] = {}

    async def enqueue_job(self, function: str, *args: Any, _job_id: str) -> object | None:
        if _job_id in self.jobs:
            return None
        self.jobs[_job_id] = (function, *args)
        return SimpleNamespace(job_id=_job_id)


async def test_the_schedule_enqueues_last_week_once_per_brand(
    db: AsyncSession, worker_engine: AsyncEngine
) -> None:
    await _a_brand(db, "Ridgeline Roasters")
    await _a_brand(db, "Fieldnote Skin")
    redis = FakeRedis()
    ctx = {"session_factory": async_sessionmaker(worker_engine), "redis": redis}

    assert await main.enqueue_due_summaries(ctx) == 2
    assert await main.enqueue_due_summaries(ctx) == 0  # still queued: arq refuses the key
    assert {job[0] for job in redis.jobs.values()} == {"process_analytics_summary"}


async def test_the_schedule_skips_a_week_already_summarized(
    db: AsyncSession, worker_engine: AsyncEngine
) -> None:
    brand = await _a_brand(db)
    factory = async_sessionmaker(worker_engine)
    async with factory() as session:
        week_end = main.last_completed_sunday(await main.today_in(session, brand.timezone))
    db.add(
        AnalyticsSummary(
            brand_id=brand.id,
            period_start=week_end - timedelta(days=6),
            period_end=week_end,
            text=QUIET_WEEK,
            stats_json={},
        )
    )
    await db.commit()

    assert await main.enqueue_due_summaries({"session_factory": factory, "redis": FakeRedis()}) == 0
