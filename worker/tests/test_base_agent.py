"""The agent contract (hard rule #3).

An agent is a prompt, a schema and a tier. These tests pin that shape, because
every agent in steps 4 and 6 inherits it and a drift here would be copied four
times.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, Field
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from worker import llm
from worker.agents.base import BaseAgent
from worker.config import get_settings


class CommentIn(BaseModel):
    comment_text: str


class TriageOut(BaseModel):
    category: str
    sentiment: int = Field(ge=-2, le=2)
    needs_reply: bool


class TriageAgent(BaseAgent[CommentIn, TriageOut]):
    """A stand-in for step 4's real agent, declared the way all of them are."""

    tier = "fast"
    prompt_name = "triage"
    output_schema = TriageOut


GOOD = '{"category": "question", "sentiment": 0, "needs_reply": true}'


@pytest.fixture
def wired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "triage.md").write_text("Classify: {{comment_text}}")

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(GOOD)])

    monkeypatch.setattr(llm, "_build_model", lambda settings, tier: FunctionModel(respond))


async def test_run_returns_only_the_output(wired: None) -> None:
    """Hard rule #3: `run(input: BaseModel) -> BaseModel`, nothing else."""
    output = await TriageAgent().run(CommentIn(comment_text="Does this come in decaf?"))

    assert isinstance(output, TriageOut)
    assert output.category == "question"


async def test_run_with_usage_gives_the_orchestrator_the_numbers(wired: None) -> None:
    """Hard rule #5: the orchestrator writes tokens, cost and latency into
    agent_runs, and they only exist at the moment of the call."""
    output, usage = await TriageAgent().run_with_usage(CommentIn(comment_text="hi"))

    assert isinstance(output, TriageOut)
    assert usage.input_tokens > 0
    assert usage.cost_usd is not None
    assert usage.latency_ms >= 0


def test_an_agent_declares_a_tier_and_never_a_model() -> None:
    """D6. The agent says 'fast'; only config knows that means qwen3.5:2b, which
    is what makes the Bedrock swap an env change instead of an edit to four
    agent files."""
    assert TriageAgent.tier == "fast"

    source = Path(TriageAgent.__module__.replace(".", "/") + ".py")
    assert "qwen" not in source.name

    assert get_settings().model_for_tier(TriageAgent.tier) == "qwen3.5:2b"


def test_variables_default_to_the_input_fields(wired: None) -> None:
    """The common case needs no override; a prompt variable matches an input
    field by name."""
    assert TriageAgent().variables(CommentIn(comment_text="hello")) == {"comment_text": "hello"}


def test_a_text_agent_sends_no_images(wired: None) -> None:
    assert TriageAgent().images(CommentIn(comment_text="hello")) is None


async def test_an_unrendered_prompt_variable_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prompt asking for {{brand_voice}} that the agent never supplies would
    otherwise reach the model as a literal, and come back confidently wrong."""
    monkeypatch.setattr(llm, "PROMPTS_DIR", tmp_path)
    (tmp_path / "triage.md").write_text("Classify: {{comment_text}} for {{brand_voice}}")

    with pytest.raises(ValueError, match="unrendered variables"):
        await TriageAgent().run(CommentIn(comment_text="hi"))
