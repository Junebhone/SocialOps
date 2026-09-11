# ADR-0004: Lighter local models for constrained RAM

Date: 2026-09-11
Status: accepted

## Context
D20 (see [DECISIONS.md](../DECISIONS.md#d20--model-selection-qwen35-2b--qwen35-9b--settled))
sized `qwen3.5:2b` + `qwen3.5:9b` (~9.3 GB resident) against a 16 GB dev machine. The machine
actually available for this build has materially less headroom, so a smaller pair is needed on
the same two-model, tiered shape (D6, D19, D20) — one `fast` model, one multimodal model serving
both `standard` and `vision`.

## Decision
Add `qwen3:0.6b` (`fast`, 523 MB) and `qwen2.5vl:3b` (`standard` + `vision`, 3.2 GB; multimodal) as
an **opt-in alternative** pair, documented alongside — not replacing — D20's default. Total
resident if opted into: ~3.7 GB, a 60% cut from D20's ~9.3 GB. `OLLAMA_MAX_LOADED_MODELS=2` (D19)
is unchanged either way.

## Alternatives considered
- **`qwen3:4b` (text) + `qwen2.5vl:3b` (vision) as separate models, alongside `qwen3:0.6b`** — better
  text quality, but reintroduces the 3-resident-model eviction problem D19 exists to eliminate.
- **Gemma 3** (`gemma3:1b` + `gemma3:4b`, ~4.1 GB) — comparable RAM, and drops the need for D23's
  thinking-off workaround entirely (Gemma 3 has no hidden reasoning mode). Rejected only because
  every prompt in `worker/agents/prompts/*.md` is tuned against Qwen's `PromptedOutput` behavior;
  switching families means re-verifying strict-JSON adherence from zero, not a same-harness eval
  re-run.
- **Gemma 4 `e2b`** (`qwen3:0.6b` + `gemma4:e2b-it-qat`, ~4.8 GB) — bigger than the chosen option
  despite the "E2B" name (Gemma 4's matryoshka architecture doesn't shrink disk size in proportion
  to the effective-param label), and five months old with no track record against this stack's
  exact call pattern.
- **Keep D20's `qwen3.5:2b` / `qwen3.5:9b`** — the better choice on quality alone, not viable on
  the available RAM.

## Consequences
Everything in D14 (`PromptedOutput`) and D23 (`reasoning_effort: "none"`) carries over unchanged —
same model family, same endpoint, same thinking-off mechanism. The two-row `docs/eval.md` table
needs to be re-run against the new tags before this can be trusted the way D20's numbers are
trusted (D20 was pull-verified and smoke-tested on 2026-09-08; this entry is not yet). If the eval
shows the smaller `standard` model losing meaningful accuracy against D20's baseline, `worker/agents/prompts/response.md`
and `content.md` may need retuning before relying on this pair for real drafting quality — not just
the JSON-shape retries `PromptedOutput` already covers.

Revisit this ADR — and prefer D20's pair, or the rejected Option B/C above — once more RAM is
available; nothing here argues the smaller pair is qualitatively better, only that it fits.

Full comparison table and reasoning: [DECISIONS.md § D31](../DECISIONS.md#d31--model-selection-revisited-for-constrained-ram-qwen306b--qwen25vl3b--settled-revisit-when-ram-increases).
