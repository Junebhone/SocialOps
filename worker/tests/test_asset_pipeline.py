"""The asset pipeline, end to end, against a scripted model.

Same shape as `test_orchestrator.py`, for the same reason: the graph is where
routing, persistence and the audit trail meet, so a bug here is invisible in the
agent tests and only shows up as strange rows after an upload.

No test reaches a real model — `ALLOW_MODEL_REQUESTS = False` in conftest makes
that an error rather than a slow surprise (hard rule #10).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from app.models import AgentRun, Asset, Brand, ContentDraft
from PIL import Image
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from worker import llm, storage
from worker.orchestrator import run_asset

MEDIA = (
    '{"description":"A kraft coffee bag on a wooden table.",'
    '"detected_text":["RIDGELINE ROASTERS"],'
    '"brand_check":{"passes":true,"issues":[]}}'
)
MEDIA_FAILS = (
    '{"description":"A serum bottle beside a glass of wine.",'
    '"detected_text":[],'
    '"brand_check":{"passes":false,"issues":["Shows alcohol: a glass of wine is in frame."]}}'
)


def _content(hashtags: int = 2) -> str:
    tags = ", ".join(f'"tag{n}"' for n in range(hashtags))
    return (
        '{"drafts":['
        f'{{"platform":"x","text":"Short one.","hashtags":[{tags}]}},'
        f'{{"platform":"instagram","text":"Longer one.","hashtags":[{tags}]}},'
        '{"platform":"linkedin","text":"Business one.","hashtags":[]}'
        "]}"
    )


BRAND_RULES: dict[str, Any] = {
    "prohibited_content": ["competitor logos", "alcohol"],
    "required_elements": ["product visible", "logo visible"],
    "tone": {"avoid_words": ["cheap", "guys"], "prefer_words": ["small-batch", "crafted"]},
    "max_hashtags": 5,
}


@pytest.fixture
def prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "media.md").write_text(
        "Prohibited {{prohibited_content}} required {{required_elements}}"
    )
    (tmp_path / "content.md").write_text(
        "Voice {{brand_voice}} image {{description}} text {{detected_text}} "
        "avoid {{avoid_words}} prefer {{prefer_words}} max {{max_hashtags}}"
    )


@pytest.fixture
def disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Point the worker's storage at a temp directory for the whole test."""
    backend = storage.LocalDiskStorage(tmp_path / "storage")
    monkeypatch.setattr("worker.orchestrator.get_storage", lambda: backend)
    return backend


def scripted(media: str = MEDIA, content: str | None = None) -> object:
    """A model that answers media first, then content."""
    calls = {"n": 0}
    body = content if content is not None else _content()

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        return ModelResponse(parts=[TextPart(media if calls["n"] == 1 else body)])

    return FunctionModel(respond)


def a_png(width: int = 800, height: int = 600) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 120, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


async def _an_asset(db: AsyncSession, backend: Any, rules: dict[str, Any] | None = None) -> Asset:
    brand = Brand(
        name="Ridgeline Roasters",
        voice_guidelines="Warm, plain-spoken.",
        brand_rules_json=rules if rules is not None else BRAND_RULES,
    )
    db.add(brand)
    await db.flush()

    key = storage.new_key(brand.id, "bag.png")
    await backend.put(key, a_png())
    asset = Asset(brand_id=brand.id, filename="bag.png", storage_key=key, mime="image/png")
    db.add(asset)
    await db.commit()
    return asset


async def test_an_upload_gets_an_analysis_and_three_drafts(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 6's demo criterion: upload one photo, get three platform drafts."""
    asset = await _an_asset(db, disk)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted())

    state = await run_asset(asset.id, db)
    await db.commit()

    assert state.agents_run == ["media", "content"]

    reloaded = await db.get(Asset, asset.id)
    assert reloaded is not None
    assert reloaded.analysis_json is not None
    assert reloaded.analysis_json["brand_check"]["passes"] is True

    drafts = (await db.execute(select(ContentDraft).order_by(ContentDraft.id))).scalars().all()
    assert sorted(draft.platform for draft in drafts) == ["instagram", "linkedin", "x"]
    assert all(draft.status == "pending" for draft in drafts)


async def test_every_agent_call_writes_one_audit_row(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hard rule #5 and D7's joinability, on the asset path this time: the runs
    must point back at the asset, not at a comment."""
    asset = await _an_asset(db, disk)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted())

    await run_asset(asset.id, db)
    await db.commit()

    runs = (await db.execute(select(AgentRun).order_by(AgentRun.id))).scalars().all()
    assert [run.agent for run in runs] == ["media", "content"]
    for run in runs:
        assert run.entity_type == "asset"
        assert run.entity_id == asset.id
        assert run.brand_id > 0
        assert run.cost_usd is not None  # ollama is 0, never NULL (D15)


async def test_the_content_draft_points_at_the_run_that_produced_it(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provenance: the Agents page has to be able to answer 'which run wrote
    this caption', and content_drafts.agent_run_id is the only link."""
    asset = await _an_asset(db, disk)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted())

    await run_asset(asset.id, db)
    await db.commit()

    content_run = (
        await db.execute(select(AgentRun).where(AgentRun.agent == "content"))
    ).scalar_one()
    drafts = (await db.execute(select(ContentDraft))).scalars().all()
    assert {draft.agent_run_id for draft in drafts} == {content_run.id}


async def test_a_failing_brand_check_still_produces_drafts(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliberate. A failing check is information for the human reviewing the
    Content page, not a reason to withhold the copy — they fix the photo and
    keep the captions."""
    asset = await _an_asset(db, disk)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(media=MEDIA_FAILS))

    state = await run_asset(asset.id, db)
    await db.commit()

    assert state.analysis is not None
    assert state.analysis.brand_check.passes is False
    assert len((await db.execute(select(ContentDraft))).scalars().all()) == 3


async def test_hashtags_are_trimmed_to_the_brand_rule(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """max_hashtags is a brand rule (D16) and the prompt asks for it, but a 9B
    model overshoots often enough that an unenforced limit is not a rule.

    The stored draft obeys the brand; the agent_runs row still holds what the
    model actually returned, so the audit trail is not rewritten.
    """
    rules = {**BRAND_RULES, "max_hashtags": 2}
    asset = await _an_asset(db, disk, rules=rules)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted(content=_content(hashtags=7)))

    await run_asset(asset.id, db)
    await db.commit()

    drafts = (await db.execute(select(ContentDraft))).scalars().all()
    assert all(len(draft.hashtags_json) <= 2 for draft in drafts)

    run = (await db.execute(select(AgentRun).where(AgentRun.agent == "content"))).scalar_one()
    assert run.output_json is not None
    assert len(run.output_json["drafts"][0]["hashtags"]) == 7


async def test_rerunning_a_finished_asset_changes_nothing(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """arq retries, and step 9's Retry button re-enqueues by hand. Without the
    guard a second run pays for another vision call and shows the reviewer six
    drafts for one photo."""
    asset = await _an_asset(db, disk)
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted())
    await run_asset(asset.id, db)
    await db.commit()

    await run_asset(asset.id, db)
    await db.commit()

    assert len((await db.execute(select(ContentDraft))).scalars().all()) == 3
    assert len((await db.execute(select(AgentRun))).scalars().all()) == 2


async def test_a_missing_asset_fails_loudly(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(llm, "_build_model", lambda s, t: scripted())

    with pytest.raises(LookupError):
        await run_asset(999999, db)


async def test_the_brand_rules_reach_the_media_prompt(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D16: one column, four consumers. If the rules never arrive, the brand
    check is the model inventing rules and then passing them."""
    asset = await _an_asset(db, disk)
    seen: list[str] = []

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(str(getattr(messages[-1].parts[0], "content", "")))
        return ModelResponse(parts=[TextPart(MEDIA if len(seen) == 1 else _content())])

    monkeypatch.setattr(llm, "_build_model", lambda s, t: FunctionModel(capture))
    await run_asset(asset.id, db)

    assert "competitor logos, alcohol" in seen[0]
    assert "product visible, logo visible" in seen[0]
    # And the content prompt gets tone + max_hashtags from the same column.
    assert "cheap, guys" in seen[1]
    assert "small-batch, crafted" in seen[1]


async def test_a_brand_with_no_rules_does_not_send_an_empty_list(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'Prohibited content: ' with nothing after it is a blank a 9B model fills
    by inventing rules to check against."""
    asset = await _an_asset(db, disk, rules={})
    seen: list[str] = []

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(str(getattr(messages[-1].parts[0], "content", "")))
        return ModelResponse(parts=[TextPart(MEDIA if len(seen) == 1 else _content())])

    monkeypatch.setattr(llm, "_build_model", lambda s, t: FunctionModel(capture))
    await run_asset(asset.id, db)

    assert "Prohibited none" in seen[0]


async def test_the_image_is_sent_as_an_attachment_not_as_prompt_text(
    db: AsyncSession, prompts: None, disk: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default `variables()` would render several hundred kilobytes of JPEG
    into the prompt, and the model then answers from the noise."""
    asset = await _an_asset(db, disk)
    parts: list[Any] = []

    def capture(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if not parts:
            parts.extend(messages[-1].parts)
            return ModelResponse(parts=[TextPart(MEDIA)])
        return ModelResponse(parts=[TextPart(_content())])

    monkeypatch.setattr(llm, "_build_model", lambda s, t: FunctionModel(capture))
    await run_asset(asset.id, db)

    # UserPromptPart.content is the list `complete()` built: the rendered prompt
    # followed by the attachments.
    content = parts[0].content
    assert isinstance(content, list)

    text, *attachments = content
    assert isinstance(text, str)
    # The instruction, and nothing else. If `variables()` had leaked the image
    # in, this would be hundreds of kilobytes of binary.
    assert len(text) < 500
    assert "PNG" not in text

    assert [attachment.media_type for attachment in attachments] == ["image/jpeg"]
    assert attachments[0].data[:2] == b"\xff\xd8"  # JPEG magic
