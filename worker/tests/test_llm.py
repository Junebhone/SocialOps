"""The single choke point every model call passes through.

No test here reaches a real model: `ALLOW_MODEL_REQUESTS = False` in conftest
makes that an error rather than a slow surprise (hard rule #10).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from worker import llm
from worker.config import get_settings
from worker.llm import Usage, complete, extract_json, render_prompt


class Triage(BaseModel):
    category: str
    sentiment: int = Field(ge=-2, le=2)
    needs_reply: bool


@pytest.fixture
def prompt_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "triage.md").write_text("Classify this comment: {{comment_text}}")
    return tmp_path


# --- fence stripping -------------------------------------------------------
# Qwen at 2B does all of these. Each one is an otherwise-correct answer that
# would fail validation and burn a retry.


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"a": 1}\n```', '{"a": 1}'),
        ('```JSON\n{"a": 1}\n```', '{"a": 1}'),
        ('Here is the JSON:\n```json\n{"a": 1}\n```', '{"a": 1}'),
        ('Sure! {"a": 1}', '{"a": 1}'),
        ('```json\n[{"a": 1}]\n```', '[{"a": 1}]'),
        ('  \n {"a": 1}  \n ', '{"a": 1}'),
    ],
)
def test_extract_json_recovers_the_payload(raw: str, expected: str) -> None:
    assert extract_json(raw) == expected


def test_extract_json_leaves_unrecoverable_text_alone() -> None:
    """Better to hand the raw text to the validator, which produces a retry with
    a useful message, than to invent a payload."""
    assert extract_json("I cannot answer that.") == "I cannot answer that."


def test_extract_json_keeps_nested_braces_intact() -> None:
    raw = '```json\n{"brand_check": {"passes": false, "issues": ["no logo"]}}\n```'

    assert extract_json(raw) == '{"brand_check": {"passes": false, "issues": ["no logo"]}}'


# --- prompt rendering ------------------------------------------------------


def test_render_prompt_substitutes_variables(prompt_dir: Path) -> None:
    assert render_prompt("triage", {"comment_text": "Does this come in decaf?"}) == (
        "Classify this comment: Does this come in decaf?"
    )


def test_render_prompt_rejects_an_unrendered_variable(prompt_dir: Path) -> None:
    """Sending a literal '{{comment_text}}' to a model gets a confident answer to
    the wrong question, which is far harder to notice than a crash."""
    with pytest.raises(ValueError, match="unrendered variables"):
        render_prompt("triage", {})


def test_render_prompt_reports_a_missing_file(prompt_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        render_prompt("nonexistent", {})


# --- the call itself -------------------------------------------------------


GOOD = '{"category": "question", "sentiment": 0, "needs_reply": true}'


def _responder(text: str) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(text)])

    return FunctionModel(respond)


async def _run_against(
    model: FunctionModel, monkeypatch: pytest.MonkeyPatch
) -> tuple[Triage, Usage]:
    """Swap only the model, exactly as Agent.override(model=...) would.

    `complete()` constructs its own Agent per call, so there is no instance to
    override from out here. Patching the model factory keeps every other part of
    the real code path under test: PromptedOutput, retries=3, the fence-stripping
    capability, usage capture and cost normalisation.
    """
    monkeypatch.setattr(llm, "_build_model", lambda settings, tier: model)
    return await complete(
        prompt_name="triage",
        variables={"comment_text": "Does this come in decaf?"},
        schema=Triage,
        tier="fast",
    )


async def test_a_fenced_response_still_parses(
    prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The end-to-end version of the stripper: the model returns fenced JSON and
    complete() returns a validated object anyway."""
    fenced = '```json\n{"category": "question", "sentiment": 0, "needs_reply": true}\n```'

    output, _usage = await _run_against(_responder(fenced), monkeypatch)

    assert output.category == "question"
    assert output.needs_reply is True


async def test_a_bad_response_is_retried_and_then_succeeds(
    prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pydantic AI owns the retry loop (hard rule #4). This proves it is wired:
    the first response violates the schema, the second does not."""
    attempts: list[int] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        attempts.append(1)
        if len(attempts) == 1:
            # sentiment out of range — valid JSON, invalid contract.
            # valid JSON, invalid contract
            bad = '{"category": "question", "sentiment": 9, "needs_reply": true}'
            return ModelResponse(parts=[TextPart(bad)])
        return ModelResponse(parts=[TextPart(GOOD)])

    output, _usage = await _run_against(FunctionModel(respond), monkeypatch)

    assert len(attempts) == 2
    assert output.sentiment == 0


async def test_usage_is_recorded(prompt_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard rule #5's numbers come from here; if they are not captured at the
    call, they do not exist."""
    good = '{"category": "praise", "sentiment": 2, "needs_reply": false}'

    _output, usage = await _run_against(_responder(good), monkeypatch)

    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
    assert usage.latency_ms >= 0


async def test_cost_is_zero_for_ollama_not_none(
    prompt_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D15. Ollama runs on hardware we own, so its calls are genuinely free —
    which is a different fact from 'we could not price this', and the Agents page
    renders the two differently."""
    good = '{"category": "praise", "sentiment": 2, "needs_reply": false}'

    _output, usage = await _run_against(_responder(good), monkeypatch)

    assert usage.cost_usd == Decimal(0)
    assert usage.cost_usd is not None


# --- thinking control (D23) ------------------------------------------------


@pytest.mark.parametrize("tier", ["fast", "standard", "vision"])
def test_thinking_is_disabled_on_every_ollama_tier(tier: str) -> None:
    """D23. Qwen does not stop thinking on its own: measured against Ollama, both
    2b and 9b spend the whole output budget reasoning and return an empty
    message. Leaving this off for any tier breaks that tier's agent completely.
    """
    settings = get_settings()

    resolved = llm._model_settings(settings, tier)  # type: ignore[arg-type]

    assert resolved is not None
    assert resolved.get("openai_reasoning_effort") == "none"


def test_thinking_control_is_not_applied_to_other_providers() -> None:
    """It is an Ollama workaround, not a policy. Bedrock decides per model."""
    settings = get_settings().model_copy(update={"llm_provider": "bedrock"})

    assert llm._model_settings(settings, "fast") is None
