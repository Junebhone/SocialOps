# ADR-0001: LLM provider strategy

Date: 2026-09-08
Status: superseded by ADR-0002

## Context
Student project; must be $0 in Phase 1 and migrate to AWS Bedrock in Phase 4+. Provider APIs differ.

## Decision
All model calls go through LiteLLM behind `worker/llm.py::complete()`. Phase 1 default is Ollama with Qwen3.6 8B (text) and Qwen3-VL 8B (vision). Prompts are written for the weakest model and are provider-agnostic. Provider is chosen only by env vars.

## Alternatives considered
- Direct provider SDKs — rejected, would need a rewrite at each phase.
- Paid API from day one — rejected, no budget and no learning value.

## Consequences
Lower draft quality in dev; robust JSON handling required; switching to Bedrock Haiku/Sonnet later is a one-line env change plus an eval run.

## Superseded
ADR-0002 replaces LiteLLM with Pydantic AI. The *strategy* in this ADR still holds — one
provider-agnostic call layer, prompts written for the weakest model, provider chosen by env var
only — but the implementation named here (`litellm.completion`) is no longer used.
