# ADR-0002: LLM access via Pydantic AI

Date: 2026-09-08
Status: accepted

Supersedes ADR-0001.

## Context
ADR-0001 routed every model call through `litellm.completion` behind `worker/llm.py::complete()`,
which also hand-rolled JSON enforcement and a 3-retry loop. Pydantic AI does all of that natively —
structured output via `output_type`, validation, retry-on-failure, and provider abstraction — in a
codebase that is already Pydantic v2 end to end with agent contracts that are already Pydantic
models.

## Decision
Remove LiteLLM. Model access is Pydantic AI: native `OllamaProvider` in Phase 1, native
`BedrockProvider` from Phase 4.

`worker/llm.py::complete()` survives as a thin choke point. It builds a Pydantic AI `Agent` for the
caller's tier, applies `PromptedOutput` with the caller's schema, times the call, writes the
`agent_runs` row, and returns `(parsed, usage)`. Exactly one place calls a model.

Three tiers — `fast`, `standard`, `vision` — map to `LLM_MODEL_FAST`, `LLM_MODEL_TEXT`,
`LLM_MODEL_VISION`. Agents declare a tier and never name a model.

## Alternatives considered
- **Keep `litellm.completion` and use Pydantic AI only to define agents** — two frameworks, two
  retry loops, no benefit.
- **Pydantic AI's `LiteLLMProvider`** — it is a compatibility-layer client for a LiteLLM *proxy
  server* (`api_base` + `api_key`), not the `litellm.completion` Python call. Keeping LiteLLM this
  way means a sixth container in `docker-compose.yml`: one more service to be down mid-demo.
- **Delete `complete()` and let agents own their own `Agent`** — hard rule #5 (one `agent_runs` row
  per invocation) and hard rule #10 (no test calls a real model) both need a single choke point.

## Consequences
Easier: the Phase 4 Bedrock switch is genuinely a provider + model-name change, and tiers map onto
Haiku/Sonnet without touching agent code. Testing improves — Pydantic AI ships `TestModel`,
`FunctionModel`, `Agent.override()`, and a global `models.ALLOW_MODEL_REQUESTS = False`, which turns
"no test may call a real model" from a convention into something the suite enforces, replacing the
hand-rolled `FakeLLM`.

Harder: output extraction uses `PromptedOutput` (schema in the prompt, validated text) rather than
tool calling, because Qwen at 2B through Ollama's OpenAI-compatibility layer is not a safe bet for
reliable tool calls. That mode is less strictly enforced, so the retry loop and a markdown-fence
stripper carry real weight. Both are required, and the stripper ships with a test.

`RunUsage.cost` is `Decimal | None` — `None`, not zero, when a model cannot be priced. `cost_usd` is
therefore nullable and encodes three states (`0` for Ollama, the `Decimal` when priced, `NULL`
otherwise) so a Phase 4 dashboard cannot report Bedrock as free because a price lookup missed.
