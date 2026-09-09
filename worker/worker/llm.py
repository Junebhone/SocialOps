"""The one place a model is called (CLAUDE.md hard rule #4).

Every agent goes through `complete()`. Nothing else in the codebase constructs a
Pydantic AI `Agent` or calls `.run()` — that is what makes hard rule #5's
one-`agent_runs`-row-per-invocation enforceable and what makes hard rule #10's
"no test may call a real model" a single seam to close.

Pydantic AI owns validation and retries. This module owns four things it does
not: resolving a tier to a model (D6), timing the call, normalising cost into
D15's three states, and repairing the one thing small local models reliably get
wrong — wrapping their JSON in markdown fences.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, assert_never

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent, ModelRequestContext, PromptedOutput, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models import Model
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.settings import ModelSettings

from worker.config import Settings, Tier, get_settings

PROMPTS_DIR = Path(__file__).parent / "agents" / "prompts"

# ```json ... ``` or ``` ... ```, anywhere in the response.
_FENCED = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
# The outermost JSON object or array, for the "Here is the JSON: {...}" case.
_BARE_JSON = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


@dataclass(frozen=True)
class Usage:
    """What `agent_runs` records for one invocation."""

    input_tokens: int
    output_tokens: int
    # D15's three states: 0 when we own the hardware, the priced value when
    # genai-prices knows the model, None when it cannot be priced. Never collapse
    # None to 0 — that reports a paid provider as free.
    cost_usd: Decimal | None
    # Measured here. Pydantic AI does not provide it.
    latency_ms: int


def extract_json(text: str) -> str:
    """Recover the JSON payload from a model response.

    `PromptedOutput` puts the schema in the prompt and validates the response
    text; it does not strip markdown. Qwen at 2B wraps JSON in fences most of
    the time and prefixes it with a sentence some of the time, and both make an
    otherwise-correct answer fail validation and burn a retry.

    Returns the input unchanged when there is nothing to repair, so a clean
    response is never mangled.
    """
    if fenced := _FENCED.search(text):
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate

    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        return stripped

    if bare := _BARE_JSON.search(stripped):
        return bare.group(1).strip()

    return stripped


class StripCodeFences(AbstractCapability[Any]):
    """Clean the response text before Pydantic AI parses it.

    A capability rather than parsing in `complete()`: this runs inside the
    agent's own loop, so validation and the retry budget still belong to
    Pydantic AI (hard rule #4) instead of being reimplemented here.
    """

    async def after_model_request(
        self,
        ctx: RunContext[Any],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        for part in response.parts:
            if isinstance(part, TextPart):
                part.content = extract_json(part.content)
        return response


def _build_model(settings: Settings, tier: Tier) -> Model:
    """Tier → model (D6). This is the only function that names a provider."""
    model_name = settings.model_for_tier(tier)

    match settings.llm_provider:
        case "ollama":
            return OllamaModel(
                model_name,
                provider=OllamaProvider(base_url=settings.ollama_openai_base_url),
            )
        case "bedrock":
            # Phase 4. Adding it here is the whole migration for this module —
            # ADR-0002's "one-line env change" is only true because the tier
            # abstraction (D6) means no agent has to change.
            raise NotImplementedError(
                "LLM_PROVIDER=bedrock is a Phase 4 target; only ollama is wired in Phase 1."
            )
        case _ as unreachable:  # pragma: no cover - mypy exhaustiveness guard
            assert_never(unreachable)


def _model_settings(settings: Settings, tier: Tier) -> ModelSettings | None:
    """Provider-specific request options.

    Qwen thinks by default, and on a classification call it does not stop: asked
    to label one comment it will spend its entire output budget reasoning and
    return an empty message with `finish_reason: length`. Not a tuning problem —
    measured against Ollama 0.x, a 2,000-token budget produced 2,000 tokens of
    thinking and no answer.

    Three ways to switch it off were tested against this Ollama build. Only the
    third works through the endpoint Pydantic AI uses:

    * `{"think": false}` in the body — Ollama honours it on its native
      `/api/chat`, and silently ignores it on the OpenAI-compatible `/v1`, which
      is what `OllamaModel` talks to.
    * Qwen's `/no_think` directive in the prompt — ignored here, and it would
      have violated hard rule #6 by putting a model-specific token in a prompt.
    * `reasoning_effort: "none"` — the OpenAI-standard field, which Ollama does
      map through. Pydantic AI exposes it as `openai_reasoning_effort`.

    Applied to EVERY Ollama tier, not just the classification one. CLAUDE.md
    asks for thinking off "on classification calls", but qwen3.5:9b was measured
    doing the same thing on a two-sentence drafting prompt, so restricting this
    to `fast` would leave the response, content and media agents failing on
    every call. Recorded as D23.

    Gated on the provider so the Phase 4 Bedrock path is unaffected — there,
    thinking is a per-model choice worth revisiting with the eval set.
    """
    if settings.llm_provider != "ollama":
        return None

    # OpenAIChatModelSettings, not the base ModelSettings: the field is
    # OpenAI-dialect and OllamaModel speaks that dialect.
    if tier == "fast":
        # temperature=0 on the classification tier. Not tuning — reproducibility.
        # At the default temperature the same 50-comment eval scored 82% and then
        # 96% on an unchanged prompt, which makes the eval unable to answer the
        # question D5 built it for: did a prompt edit help, or did the sampler.
        # Classification wants the argmax anyway; there is nothing to be creative
        # about in choosing a label.
        return OpenAIChatModelSettings(openai_reasoning_effort="none", temperature=0.0)
    return OpenAIChatModelSettings(openai_reasoning_effort="none")


def render_prompt(prompt_name: str, variables: dict[str, Any]) -> str:
    """Load `agents/prompts/<name>.md` and substitute `{{variables}}`.

    Prompts live on disk, not in string literals (hard rule #6), so a prompt
    change is a reviewable diff and `make eval` can attribute an accuracy change
    to it.
    """
    path = PROMPTS_DIR / f"{prompt_name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"No prompt at {path}")

    text = path.read_text()
    for key, value in variables.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))

    if leftover := re.findall(r"\{\{(\w+)\}\}", text):
        # Silently sending "{{comment_text}}" to a model produces a plausible
        # answer to the wrong question, which is far worse than failing here.
        raise ValueError(
            f"Prompt '{prompt_name}' has unrendered variables: {sorted(set(leftover))}"
        )

    return text


async def complete[OutputT: BaseModel](
    prompt_name: str,
    variables: dict[str, Any],
    schema: type[OutputT],
    tier: Tier,
    images: list[bytes] | None = None,
) -> tuple[OutputT, Usage]:
    """Run one model call and return the parsed output with its usage."""
    settings = get_settings()
    prompt = render_prompt(prompt_name, variables)

    agent = Agent(
        _build_model(settings, tier),
        output_type=PromptedOutput(schema),
        # Pydantic AI's own validate-and-retry loop, which is the loop hard rule
        # #4 describes. There is no second one anywhere.
        retries=3,
        capabilities=[StripCodeFences()],
        model_settings=_model_settings(settings, tier),
    )

    user_prompt: str | list[Any] = prompt
    if images:
        attachments = [BinaryContent(data=image, media_type="image/png") for image in images]
        user_prompt = [prompt, *attachments]

    started = time.perf_counter()
    result = await agent.run(user_prompt)
    latency_ms = int((time.perf_counter() - started) * 1000)

    usage = result.usage
    return result.output, Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=_cost_usd(settings, usage.cost),
        latency_ms=latency_ms,
    )


def _cost_usd(settings: Settings, reported: Decimal | None) -> Decimal | None:
    """D15. Ollama runs on hardware we already own, so its calls are genuinely
    free — 0, not None. Everything else passes through whatever genai-prices
    could determine, including None for a model it cannot price."""
    if settings.llm_provider == "ollama":
        return Decimal(0)
    return reported
