"""What happens when things break: the audit row, the retries, and the DLQ.

Hard rules #5 and #7 meet here. Both were partly unenforced — a failed agent
invocation wrote no `agent_runs` row at all, so `status` and `error` were
columns nothing could produce, and `worker/main.py`'s "dead-letter only on the
last attempt" had no coverage anywhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from app.models import AgentRun, Brand, Comment, FailedJob, PlatformAccount, Post
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from worker import llm, main
from worker.orchestrator import run_comment

TRIAGE_REPLY = '{"category":"question","sentiment":0,"needs_reply":true,"urgency":"low"}'


@pytest.fixture
def prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "triage.md").write_text("Classify: {{comment_text}}")
    (tmp_path / "response.md").write_text(
        "Voice {{brand_voice}} avoid {{avoid_words}} reply to {{comment_text}}"
    )


async def _a_comment(db: AsyncSession) -> Comment:
    from datetime import UTC, datetime

    now = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    brand = Brand(
        name="Ridgeline Roasters",
        voice_guidelines="Warm, plain-spoken.",
        brand_rules_json={"prohibited_content": [], "required_elements": [],
                          "tone": {"avoid_words": [], "prefer_words": []}, "max_hashtags": 5},
    )
    db.add(brand)
    await db.flush()
    account = PlatformAccount(brand_id=brand.id, platform="instagram", handle="@r")
    db.add(account)
    await db.flush()
    post = Post(account_id=account.id, external_id="p-1", text="hi", posted_at=now,
                metrics_json={})
    db.add(post)
    await db.flush()
    comment = Comment(post_id=post.id, external_id="c-1", author="@rae",
                      text="Do you ship to Canada?", created_at=now)
    db.add(comment)
    await db.commit()
    return comment


def _explodes_on_call(which: int) -> FunctionModel:
    """A model that answers normally until the `which`-th call, then raises."""
    calls = {"n": 0}

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == which:
            raise RuntimeError("ollama connection reset")
        return ModelResponse(parts=[TextPart(TRIAGE_REPLY)])

    return FunctionModel(respond)


# --- hard rule #5: every INVOCATION writes a row ---------------------------


async def test_a_failed_agent_call_writes_an_error_row(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug. `status="ok"` was the only value ever written, so a failed call
    left no trace — and `agent_runs.status`/`error`, plus the Agents page filter
    built on them, described a state nothing could produce."""
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: _explodes_on_call(1))

    with pytest.raises(Exception, match="ollama connection reset"):
        await run_comment(comment.id, db)
    await db.commit()

    run = (await db.execute(select(AgentRun))).scalar_one()
    assert run.agent == "triage"
    assert run.status == "error"
    assert "ollama connection reset" in (run.error or "")
    assert run.output_json is None
    # NULL, not 0: the call may have spent tokens before it died and we do not
    # know how many. "Unknown" is a different fact from "free" (D15).
    assert run.cost_usd is None


async def test_the_error_row_is_joinable_back_to_the_comment(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D7's second question — 'which runs failed' — needs the same
    entity_type/entity_id a successful run carries."""
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: _explodes_on_call(1))

    with pytest.raises(Exception, match="ollama"):
        await run_comment(comment.id, db)
    await db.commit()

    run = (await db.execute(select(AgentRun))).scalar_one()
    assert run.entity_type == "comment"
    assert run.entity_id == comment.id
    assert run.brand_id > 0


async def test_a_failure_on_the_second_agent_is_attributed_to_that_agent(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Triage succeeds, response dies. The trail has to say which one broke."""
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: _explodes_on_call(2))

    with pytest.raises(Exception, match="ollama"):
        await run_comment(comment.id, db)
    await db.commit()

    runs = (await db.execute(select(AgentRun).order_by(AgentRun.id))).scalars().all()
    assert [(r.agent, r.status) for r in runs] == [("triage", "ok"), ("response", "error")]


async def test_the_failure_row_survives_the_jobs_rollback(
    db: AsyncSession, worker_engine: AsyncEngine, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reason it is written on its own session.

    `session_scope` rolls the job's session back so arq can retry from a clean
    slate. A row added to that session would be discarded with everything else,
    which is how the error path managed to look like it was recording something.
    """
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: _explodes_on_call(1))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    async with factory() as job_session:
        with pytest.raises(Exception, match="ollama"):
            await run_comment(comment.id, job_session, audit_factory=factory)
        await job_session.rollback()

    async with factory() as checking:
        run = (await checking.execute(select(AgentRun))).scalar_one()
        assert run.status == "error"


# --- hard rule #7: three attempts, then the DLQ ----------------------------


class _Ctx(dict[str, Any]):
    """The arq job context, with the attempt number under test."""


def _ctx(factory: async_sessionmaker[AsyncSession], job_try: int) -> _Ctx:
    return _Ctx(session_factory=factory, job_id=f"job-{job_try}", job_try=job_try)


async def test_an_early_attempt_does_not_dead_letter(
    db: AsyncSession, worker_engine: AsyncEngine, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """arq owns the retries (hard rule #7). Writing a `failed_jobs` row per
    attempt would put three rows in the DLQ for one comment and make the Agents
    page report three times the real number of broken jobs."""
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: _explodes_on_call(1))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    for attempt in (1, 2):
        with pytest.raises(Exception, match="ollama"):
            await main.process_comment(_ctx(factory, attempt), comment.id)

    async with factory() as checking:
        assert (await checking.execute(select(FailedJob))).scalars().all() == []


async def test_the_final_attempt_dead_letters_with_a_replayable_payload(
    db: AsyncSession, worker_engine: AsyncEngine, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The payload has to be enough to re-enqueue — the Retry button reads
    exactly this row."""
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: _explodes_on_call(1))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    with pytest.raises(Exception, match="ollama"):
        await main.process_comment(_ctx(factory, main.MAX_TRIES), comment.id)

    async with factory() as checking:
        job = (await checking.execute(select(FailedJob))).scalar_one()
        assert job.job_type == "process_comment"
        assert job.payload_json == {"comment_id": comment.id}
        assert job.attempts == main.MAX_TRIES
        assert "ollama connection reset" in job.error


async def test_a_dead_lettered_comment_is_marked_failed(
    db: AsyncSession, worker_engine: AsyncEngine, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otherwise it stays at `new` and reads in the Inbox as one the pipeline
    has not reached yet — indistinguishable from a queue that is merely behind,
    which is the wrong thing to believe while debugging a stalled replay."""
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: _explodes_on_call(1))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    with pytest.raises(Exception, match="ollama"):
        await main.process_comment(_ctx(factory, main.MAX_TRIES), comment.id)

    async with factory() as checking:
        reloaded = await checking.get(Comment, comment.id)
        assert reloaded is not None and reloaded.status == "failed"


async def test_an_asset_job_dead_letters_the_same_way(
    db: AsyncSession, worker_engine: AsyncEngine, prompts: None
) -> None:
    """Both job types share one failure path, which is what keeps the DLQ and
    the Retry button uniform across the two pipelines."""
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    with pytest.raises(LookupError):
        await main.process_asset(_ctx(factory, main.MAX_TRIES), 999999)

    async with factory() as checking:
        job = (await checking.execute(select(FailedJob))).scalar_one()
        assert job.job_type == "process_asset"
        assert job.payload_json == {"asset_id": 999999}
