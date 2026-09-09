"""The comment pipeline, end to end, against a scripted model.

The graph is where routing, persistence and the audit trail meet, so a bug here
is invisible in the agent tests and only shows up as strange rows after a
replay. That is exactly how the duplicate-draft bug reached the database.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.models import AgentRun, Brand, Comment, PlatformAccount, Post, ReplyDraft
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from worker import llm
from worker.orchestrator import run_comment

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)

TRIAGE_REPLY = '{"category":"question","sentiment":0,"needs_reply":true,"urgency":"low"}'
TRIAGE_SPAM = '{"category":"spam","sentiment":0,"needs_reply":false,"urgency":"low"}'
RESPONSE = '{"reply_text":"We do ship there.","tone":"factual","confidence":0.8}'


@pytest.fixture
def prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "triage.md").write_text("Classify: {{comment_text}}")
    (tmp_path / "response.md").write_text(
        "Voice {{brand_voice}} avoid {{avoid_words}} reply to {{comment_text}}"
    )


def scripted(triage: str, response: str = RESPONSE) -> object:
    """A model that answers triage first, then response."""
    calls = {"n": 0}

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        return ModelResponse(parts=[TextPart(triage if calls["n"] == 1 else response)])

    return FunctionModel(respond)


async def _a_comment(db: AsyncSession, text: str = "Do you ship to Canada?") -> Comment:
    brand = Brand(
        name="Ridgeline Roasters",
        voice_guidelines="Warm, plain-spoken.",
        brand_rules_json={
            "prohibited_content": [],
            "required_elements": [],
            "tone": {"avoid_words": ["cheap", "guys"], "prefer_words": []},
            "max_hashtags": 5,
        },
    )
    db.add(brand)
    await db.flush()
    account = PlatformAccount(brand_id=brand.id, platform="instagram", handle="@r")
    db.add(account)
    await db.flush()
    post = Post(account_id=account.id, external_id="p-1", text="hi", posted_at=NOW,
                metrics_json={})
    db.add(post)
    await db.flush()
    comment = Comment(post_id=post.id, external_id="c-1", author="@rae", text=text,
                      created_at=NOW)
    db.add(comment)
    await db.commit()
    return comment


async def test_a_comment_needing_a_reply_gets_one(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(TRIAGE_REPLY))

    state = await run_comment(comment.id, db)
    await db.commit()

    assert state.agents_run == ["triage", "response"]
    draft = (await db.execute(select(ReplyDraft))).scalar_one()
    assert draft.text == "We do ship there."
    assert draft.status == "pending"
    reloaded = await db.get(Comment, comment.id)
    assert reloaded is not None and reloaded.status == "drafted"


async def test_spam_skips_the_response_agent(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The routing rule is an `if` (D12). Spam must not cost a drafting call."""
    comment = await _a_comment(db, "FOLLOW ME FOR FREE GIVEAWAYS")
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(TRIAGE_SPAM))

    state = await run_comment(comment.id, db)
    await db.commit()

    assert state.agents_run == ["triage"]
    assert (await db.execute(select(ReplyDraft))).scalars().all() == []
    reloaded = await db.get(Comment, comment.id)
    assert reloaded is not None and reloaded.status == "replied"


async def test_every_agent_call_writes_one_audit_row(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hard rule #5, and D7's joinability: the run must point back at the
    comment that caused it."""
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(TRIAGE_REPLY))

    await run_comment(comment.id, db)
    await db.commit()

    runs = (await db.execute(select(AgentRun).order_by(AgentRun.id))).scalars().all()
    assert [run.agent for run in runs] == ["triage", "response"]
    for run in runs:
        assert run.entity_type == "comment"
        assert run.entity_id == comment.id
        assert run.brand_id > 0
        assert run.cost_usd is not None  # ollama is 0, never NULL (D15)


async def test_rerunning_a_finished_comment_changes_nothing(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug this guard was written for.

    arq retries failed jobs and step 9's Retry button re-enqueues by hand.
    Without the guard a second run produced a second triage row and a second
    draft — double-charging the model and showing a reviewer two drafts for one
    comment. Measured for real: 6 comments got two drafts after a requeue.
    """
    comment = await _a_comment(db)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(TRIAGE_REPLY))
    await run_comment(comment.id, db)
    await db.commit()

    await run_comment(comment.id, db)
    await db.commit()

    assert len((await db.execute(select(ReplyDraft))).scalars().all()) == 1
    assert len((await db.execute(select(AgentRun))).scalars().all()) == 2


async def test_a_missing_comment_fails_loudly(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Better a job that fails into the DLQ than one that silently does nothing."""
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(TRIAGE_REPLY))

    with pytest.raises(LookupError):
        await run_comment(999999, db)


async def test_the_brands_avoid_words_reach_the_response_prompt(
    db: AsyncSession, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D16: one column, three consumers. Response reads tone.avoid_words, and if
    it never arrives the prompt silently drafts without the brand's rules."""
    comment = await _a_comment(db)
    seen: list[str] = []

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(str(getattr(messages[-1].parts[-1], "content", "")))
        return ModelResponse(parts=[TextPart(TRIAGE_REPLY if len(seen) == 1 else RESPONSE)])

    monkeypatch.setattr(llm, "_build_model", lambda s, t: FunctionModel(capture))
    await run_comment(comment.id, db)

    assert "cheap, guys" in seen[1]


async def test_two_overlapping_attempts_produce_one_draft(
    db: AsyncSession, worker_engine: AsyncEngine, prompts: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bug the 300-comment replay found.

    `Ingest`'s guard was check-then-act: two attempts at the same comment could
    both read `new`, both triage it and both write a draft. It happened once in
    300 — comment 242 — and `GET /comments/242` then returned 500, because that
    endpoint reads the draft with `scalar_one_or_none()`.

    Two things close it, and this exercises both: the guard now takes a row lock
    on the comment, so the second transaction waits and then sees `drafted`; and
    `UNIQUE(comment_id)` is the backstop that turns the same race into a loud
    failure rather than a silent duplicate.
    """
    comment = await _a_comment(db)
    await db.commit()

    calls: list[str] = []

    def counting(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append("call")
        return ModelResponse(parts=[TextPart(TRIAGE_REPLY if len(calls) == 1 else RESPONSE)])

    monkeypatch.setattr(llm, "_build_model", lambda s, t: FunctionModel(counting))
    factory = async_sessionmaker(worker_engine, expire_on_commit=False)

    async def attempt() -> None:
        async with factory() as session:
            try:
                await run_comment(comment.id, session)
                await session.commit()
            except Exception:
                await session.rollback()

    await asyncio.gather(attempt(), attempt())

    async with factory() as checking:
        assert len((await checking.execute(select(ReplyDraft))).scalars().all()) == 1

    # Two model calls, not four. This is what separates the row lock from the
    # constraint: the constraint alone would let the second attempt triage and
    # draft the comment all over again — paying for both calls — before failing
    # on the insert. The lock makes it wait, see `drafted`, and stop.
    assert len(calls) == 2


async def test_the_database_refuses_a_second_draft(db: AsyncSession) -> None:
    """The backstop on its own. Even if a future change loses the lock, the
    constraint keeps `GET /comments/{id}` from 500ing."""
    comment = await _a_comment(db)
    db.add(ReplyDraft(comment_id=comment.id, text="first", status="pending"))
    await db.commit()

    db.add(ReplyDraft(comment_id=comment.id, text="second", status="pending"))
    with pytest.raises(IntegrityError):
        await db.commit()
