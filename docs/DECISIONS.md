# SocialOps — Technical Decision Log

Running record of every non-obvious technical decision for Phase 1, with the reasoning.

**Status key:** `SETTLED` = agreed, safe to build on · `OPEN` = still being decided · `SUPERSEDED` = replaced by a later entry.

This log is the *narrative*. Load-bearing decisions get promoted to numbered ADRs in
[docs/decisions/](decisions/) using [0000-template.md](decisions/0000-template.md). Where an
entry contradicts `CLAUDE.md`, the **Touches** line names what has to change; none of those
edits have been applied yet.

---

## D1 — Cut line for Phase 1 · `SETTLED (on a stated assumption)`

**Assumption, not a fact.** No deadline was given across three requests, and the team position is
unresolved — five people nominally, but the demo is being built solo. This entry therefore proceeds
on the assumption of **an effectively solo build with roughly four weeks**. If either turns out to
be wrong, this is the first entry to revisit; nothing else in this log depends on it.

**Decision — what ships:**

| Steps | Status | Note |
|---|---|---|
| 0–5 | **Core** | Skeleton, data model, seed data, LLM layer, queue + orchestrator, Inbox + approvals |
| 6 | **Core** | Storage, media agent, content agent |
| 7 | **Core, stripped** | Content page: upload, analysis, three drafts, approve/reject. No polish. |
| 8 | **Cut to a table** | Drop `AnalyticsAgent`, the Recharts dashboard, and `GET /analytics/{brand_id}`. Keep a plain Agents page listing `agent_runs` (agent, tokens, cost, latency) and `failed_jobs`. |
| 9–10 | **Core** | Load replay, DLQ panel, structlog, healthchecks, `demo.sh`, architecture doc |

**Why this cut and not the obvious one:** an earlier draft cut steps 7 and 8 together as "the second
copy of the same machinery." That was wrong. *"Upload one product photo and watch three
platform-specific drafts appear"* is a stated demo criterion and the most visually striking thing in
the product — cutting it to preserve a sentiment chart inverts the value. The genuinely cuttable
work is the analytics **dashboard**: `AnalyticsAgent` is the one agent whose output is a paragraph
of prose nobody reads on stage, and Recharts is a day of layout work. The Agents page survives
because it is the payoff for hard rule #5 — the audit trail and cost-per-agent story is the thing
that makes this look like engineering rather than a demo.

**Steps 9 and 10 are explicitly not cuttable.** The load replay, the DLQ, and the architecture
diagram are what an examiner actually watches, and they are the bridge into Phase 2.

**Two seed brands are kept** (D17). It is ~30 lines of seed data and it is what makes the brand
selector and per-brand cost real rather than decorative.

**Touches:** `docs/START-HERE.md` §7 (the A/B/C/D split assumes five parallel builders and is now
fiction) · step 8 in `PROMPTS.md` · `README.md` success criteria.

---

## D2 — Phase 1 is stateless; the roadmap gets reworded, not the code · `SETTLED`

**Decision:** Keep `CLAUDE.md` hard rule #2 (stateless API, no in-RAM sessions, separate worker
container, Redis queue from day one). Rewrite the phase narrative in `README.md` and the proposal
so Phases 2–4 are described as **re-platforming**, not re-architecting.

**Why:** The proposal promises a *"stateful monolith"* in Phase 1 with *"agents running in-process,"*
then sells Phase 3 as "containerize the workers" and Phase 4 as "make the containers stateless."
But `CLAUDE.md` already builds separate containers, a queue, and a stateless API — so Phases 3 and 4
would have nothing left to do. Two ways to resolve it: build deliberately bad architecture so there
is something to fix later, or tell the truth about what the later phases are. Writing throwaway
statefulness is real work that produces nothing, and shared mutable state across a team is a
reliable source of bugs. Honest framing is cheaper and defensible.

**Consequences:** Phases 2–4 become "same app, better infrastructure": EC2 → ECS/Fargate, local
Postgres → RDS, local disk → S3, Redis → ElastiCache, arq → SQS. That is still a genuine migration
story, but it must be *stated* as one. The current docs promise a re-architecture the code will not
perform, and that gap is exactly what an examiner will find.

**Touches:** `README.md` roadmap table · the proposal's phase-mapping table · a new ADR.

---

## D3 — The approval loop actually closes · `SETTLED`

**Decision:** Add `approved_by` (free text — there is no auth in Phase 1), `approved_at`, and a
`published` status to `reply_drafts`. Add an `outbox` table that the worker drains on a timer.
Drop the `edited` status.

**Why:** The product's one-line pitch is *"a human approves everything before it publishes,"* and
"approve a batch of agent-drafted replies" is a stated demo criterion. But the schema had no
`published` state, no approver, and no timestamp, and none of the 11 build steps contained a publish
action — so clicking Approve would have left the row at `approved` forever. The outbox is ~40 lines,
makes the loop visibly close on stage, and is the exact seam a real platform integration plugs into
if the live-API stretch goal is ever attempted. `edited` was redundant: a non-null `final_text`
already records that a human changed the draft, and `edited` vs `approved` left "was this
sent?" ambiguous.

**Touches:** `CLAUDE.md` data model · step 5 in `PROMPTS.md`.

---

## D4 — Demo on 300 comments, publish the 2,000 · `SETTLED`

**Decision:** `make replay` (300 comments) is the demo path. The 2,000-comment `replay-full` is an
unattended run whose wall time, p50/p95 latency, and token totals are recorded in the README.
Triage moves to a small fast model; the 8B model is reserved for response drafting.

**Why:** Arithmetic. On Apple Silicon with an 8–9B model at q4, a triage call is roughly 2s and a
response call roughly 3.5s. 2,000 comments with the specified category mix is ~2,000 triage calls
and ~1,300 response calls ≈ **2.4 hours serialized**, and one laptop running an 8B model is
memory-bandwidth-bound, so concurrency will not rescue it. Step 9 asks you to *watch* the queue
climb and drain; nobody will. Splitting the models is the real win: triage is a bounded
classification task that a 1.7B model handles, turning the triage leg from ~66 minutes to ~13.

**Consequences:** The README's "queue drains within a target window" finally gets a number. Model
splitting creates a hard dependency on D5 — you now need evidence the small model did not lose
accuracy.

**Touches:** `README.md` success criteria · `Makefile` · steps 4 and 9 in `PROMPTS.md`.

---

## D5 — The eval harness gets built · `SETTLED`

**Decision:** Hand-label 50 comments into `data/eval.json` as part of step 2. Add `worker/eval.py`
as a new step 4.5.

**Why:** `make eval`, `docs/eval.md`, and the weekly ritual in START-HERE all reference
`data/eval.json` and `worker.eval` — and **no build step creates either one**. `CLAUDE.md` never
mentions eval at all. It was a phantom. It also matters more than it looks: with prompts being
edited on branches, eval is the only thing that catches a prompt change quietly destroying
accuracy, and it is the only evidence that would justify ADR-0001's claim that switching to Bedrock
is "a one-line env change plus an eval run." D4's model split makes it load-bearing.

**Alternative rejected:** Cutting eval entirely. Acceptable — but then the `Makefile` target and
`docs/eval.md` must be deleted too. A documented ritual nobody can perform is worse than no ritual.

**Touches:** `PROMPTS.md` steps 2 and 4.5 · `CLAUDE.md` commands list.

---

## D6 — Model tiers, not model names · `SETTLED`

**Decision:** Three env vars — `LLM_MODEL_FAST`, `LLM_MODEL_TEXT`, `LLM_MODEL_VISION`. `BaseAgent`
carries a `tier` class attribute (`fast` | `standard` | `vision`); `config.py` maps tier → model.
Agents never name a model.

**Why:** D4's model split broke `CLAUDE.md` hard rule #1, which permits only `LLM_MODEL_TEXT` and
`LLM_MODEL_VISION`. Tiers generalise: on Bedrock the same split is Haiku for triage, Sonnet for
drafting. This is what actually makes ADR-0001's "one-line env change" true. It also gives the cost
dashboard a free axis — spend per tier.

**Alternative rejected:** A per-agent JSON map (`LLM_MODEL_MAP={"triage":...}`). More flexible than
this project will ever need, and it turns a typo into a runtime crash.

**Touches:** `CLAUDE.md` hard rule #1 · `.env.example` · step 3 in `PROMPTS.md`.

---

## D7 — `agent_runs.input_ref` becomes a real, joinable reference · `SETTLED`

**Decision:** Replace the opaque `input_ref` string with `entity_type` + `entity_id`, indexed
together. Denormalize `brand_id` onto `agent_runs`.

**Why:** Hard rule #5 makes `agent_runs` the audit trail and cost dashboard, but never defined
`input_ref`'s format. An opaque `"comment:123"` cannot be joined, which kills the two questions that
make the dashboard worth building: *what did this one comment cost end-to-end,* and *which comments
failed.* Two indexed columns keep one row shape for every agent and survive new entity types without
a migration. `brand_id` is denormalized because per-brand cost otherwise needs a four-table join,
and that chart belongs on the Agents page.

**Alternative rejected:** Nullable per-type FKs (`comment_id`, `asset_id`, …) — a migration every
time an agent learns a new input type.

**Touches:** `CLAUDE.md` data model and hard rule #5.

---

## D8 — Sentiment is an ordinal, not a float · `SETTLED`

**Decision:** `sentiment` becomes a 5-point integer, `-2..2`, replacing the continuous `-1..1`.

**Why:** Small models do not produce calibrated continuous scores — they emit whatever numbers
appeared in the prompt's examples, clustered on `0.8` / `-0.5` / `0.0`. D4 moved triage to a much
smaller model, making this worse. Nothing downstream needs the precision: the UI renders a badge,
and `sentiment_trend` only needs something averageable, which `AVG()` over integers still gives.
Decisively, it makes D5's eval set gradeable — a human cannot hand-label a float, but five buckets
they can, which turns "sentiment accuracy" into a real number.

**Touches:** `CLAUDE.md` triage contract and data model · `prompts/triage.md`.

---

## D9 — Ingest is idempotent; approval is batchable · `SETTLED`

**Decision:** Add `external_id` to `comments` with a unique index on `(post_id, external_id)` and
`ON CONFLICT DO NOTHING`. `POST /ingest/comments` returns `{inserted, skipped}`. Derive the arq job
key from the comment id. Add `PATCH /reply_drafts/bulk` taking `{ids[], status}`, plus a checkbox
column in the Inbox.

**Why:** `posts` had `external_id`; `comments` did not, and nothing enforced uniqueness — so running
`make replay` twice inserted every comment twice and re-spent every LLM call. D4 makes replaying
deliberate and repeated, so a duplicated 2,000-comment run is ~2 wasted hours and a corrupted
analytics chart. The job key stops a re-enqueue double-charging. Batch approval is separate but
adjacent: *"approve a batch of agent-drafted replies"* is a stated demo criterion, yet step 5 only
specified per-row actions — and approving 40 rows one at a time on stage is a bad look.

**Touches:** `CLAUDE.md` data model · steps 4 and 5 in `PROMPTS.md`.

---

## D10 — LangGraph, contained · `SUPERSEDED by D11 and D12`

**Decision (as agreed, now replaced):** Keep LangGraph but confine it to `orchestrator.py` behind a
single `run_comment_job(comment_id)` entry point, with no LangGraph types in `worker/agents/`, and
the checkpointer **off**.

**Why it was scoped that way:** The graph is a two-node chain with one conditional — an `if`
statement wearing a dependency. The one real argument for keeping it was that the graph object maps
1:1 onto the Phase 5 Step Functions state machine and makes a good diagram. The checkpointer had to
be off because arq already owns retries, and two retry mechanisms on one job means double-charged
LLM calls and confusing DLQ entries.

---

## D11 — Pydantic AI replaces LangGraph · `SETTLED`

**Decision:** Use [Pydantic AI](https://pydantic.dev/docs/ai/overview/) instead of LangGraph.

**Why:** User decision. It fits the stack — the project is already Pydantic v2 end to end, agent
output contracts are already Pydantic models, and Pydantic AI's `output_type` + validation-retry
loop is precisely what `CLAUDE.md` hard rule #4 describes building by hand.

**What was verified** (via Context7 against `/pydantic/pydantic-ai`):

- Native `OllamaProvider` / `OllamaModel` (`base_url` must end in `/v1`) and a native
  `BedrockProvider` — Phase 1 and Phase 4 are both first-class.
- `RunUsage` exposes `input_tokens`, `output_tokens`, `requests`, `tool_calls`, and
  `cost: Decimal | None`, priced by `genai-prices`. **It returns `None`, not `0`, when a model
  cannot be priced** — deliberately, so "unknown" stays distinct from "free". No `latency_ms`; we
  time it ourselves.
- Built-in `TestModel` and `FunctionModel` plus `Agent.override(model=...)` and the
  `models.ALLOW_MODEL_REQUESTS = False` guard — a better implementation of hard rule #10 than the
  hand-rolled `FakeLLM`, and the global guard makes "no test may call a real model" enforceable
  rather than aspirational.
- Output modes are selectable: `ToolOutput` (default, needs reliable tool calling), `NativeOutput`
  (needs provider structured-output support), `PromptedOutput` (schema in the prompt — the
  documented fallback for weak models).
- A `LiteLLMProvider` exists, but it is a **compatibility-layer client for a LiteLLM proxy server**
  (`api_base` + `api_key`) — *not* the `litellm.completion` Python call that hard rule #4 mandates.

**Scope check.** An earlier draft of this entry claimed Pydantic AI does not cover orchestration and
so could not replace LangGraph. That was wrong. Verified against the docs, its scope includes
`pydantic-graph` (typed, graph-based workflows), sub-agents for multi-agent coordination, durable
execution via Temporal / DBOS / Prefect / Restate, and human-in-the-loop approval through *deferred
tools*. It covers everything LangGraph was doing here, which makes the swap sound — see D12.

**Consequences:** Pydantic AI overlaps `worker/llm.py` and LiteLLM (hard rule #4), which now
describes a retry-and-validate loop the framework already implements. Resolved by D13 (LiteLLM is
cut) and D12 (`pydantic-graph` takes the orchestration role).

**Touches:** `CLAUDE.md` stack list and hard rules #3, #4, #10 · `ADR-0001` (its "all model calls go
through LiteLLM" decision is in question) · steps 3 and 4 in `PROMPTS.md` · `pyproject.toml`
dependencies (hard rule #11 requires stating the swap).

---

## D12 — `pydantic-graph` orchestrates; no durable-execution layer · `SETTLED`

**Decision:** Orchestration is a `pydantic-graph` graph in `worker/orchestrator.py` — one typed node
per step, `ingest → triage → (needs_reply ? response : end) → persist`, with Pydantic AI agents
called inside the nodes. **No durable execution layer** (no Temporal, DBOS, Prefect, or Restate).

**Why:** LangGraph is a fine library but oversized for a linear chain with one branch, and pulling in
a second framework family is a dependency paid for twice in a codebase that is already Pydantic v2
end to end, with agent contracts that are already Pydantic models. Against a plain ~15-line async
function, the graph costs roughly 45 extra lines and buys three things: typed state passed between
nodes, a structure that absorbs the media path (`asset → media → content`) without reshaping, and
**auto-generated Mermaid from the graph definition** — which is a step 10 deliverable that would
otherwise be hand-drawn and left to rot. It also translates directly into the Phase 5 Step Functions
state machine, making that migration a translation rather than a rewrite.

**Why no durable execution:** `arq` on Redis already owns retries and the DLQ (hard rule #7). Each
durable-execution option drags in a whole new infrastructure component, and two retry mechanisms on
one job means double-charged LLM calls and DLQ entries nobody can explain.

**Rejected — human-in-the-loop primitives.** Both LangGraph's `interrupt()` and Pydantic AI's
deferred tools would model the approval gate as a paused run. They are the strongest argument for
either framework and they still do not fit: approval arrives days later over a separate HTTP
request, so pausing a live run would require durably checkpointed state and fights hard rule #2's
stateless API. The run persists the draft and ends; approval is D3's outbox.

**Rejected — Pydantic AI sub-agents / agent delegation.** Having the triage agent call the response
agent as a tool puts routing inside a model call: a 1.7B model would decide control flow,
nondeterministically and unauditably, and the nested call breaks hard rule #5's one-row-per-
invocation. The routing rule is `if needs_reply`. It stays an `if`.

**Touches:** `CLAUDE.md` stack list (LangGraph → `pydantic-graph`) · step 4 in `PROMPTS.md` ·
step 10's Mermaid diagram becomes generated, not hand-drawn · `pyproject.toml`.

---

## D13 — LiteLLM is cut; Pydantic AI owns provider abstraction · `SETTLED`

**Decision:** Remove LiteLLM. Model access is Pydantic AI's native `OllamaProvider` in Phase 1 and
native `BedrockProvider` from Phase 4. `worker/llm.py::complete()` survives as a **thin choke
point**: it builds the `Agent` from the caller's tier (D6), times the call, writes the `agent_runs`
row, and returns `(parsed, usage)`.

**Why:** LiteLLM's only job in this design was provider-agnosticism, and Pydantic AI does that
natively with both targets first-class. Hard rule #4 — wrap `litellm.completion`, enforce JSON via
Pydantic, retry up to 3 times — now describes work the framework already performs, so keeping
LiteLLM means maintaining a second implementation of it.

Pydantic AI's `LiteLLMProvider` does not preserve the rule: it is a compatibility-layer client for a
**LiteLLM proxy server** (`api_base` + `api_key`), not the `litellm.completion` Python call. Keeping
LiteLLM therefore means a sixth container in `docker-compose.yml` — one more service to be down
mid-demo.

**Why `complete()` still exists:** hard rule #5 (one `agent_runs` row per invocation) and hard rule
#10 (every agent testable without a real model) both depend on there being exactly one place every
call passes through. The choke point survives; only its internals change.

**Rejected:** keeping `litellm.completion` under a hand-rolled wrapper with Pydantic AI used only for
agent definitions — two frameworks, two retry loops, no benefit.

**Consequence for testing:** Pydantic AI ships `TestModel`, `FunctionModel`, `Agent.override()`, and
a global `models.ALLOW_MODEL_REQUESTS = False`. That replaces the hand-rolled `FakeLLM`, and the
global guard turns "no test may call a real model" from a convention into something the suite
enforces.

**Touches:** `CLAUDE.md` stack list and hard rules #4 and #10 · **`ADR-0001` must be superseded by a
new ADR-0002** — it currently records "all model calls go through LiteLLM" as *accepted*, and that
is now false · `pyproject.toml` · step 3 in `PROMPTS.md`.

---

## D14 — `PromptedOutput`, configured per tier · `SETTLED`

**Decision:** Pydantic AI agents use `PromptedOutput` — the JSON schema goes in the prompt, the
response text is validated, and the model retries on failure. The mode is set per tier (D6) so
Phase 4 on Bedrock can switch to `NativeOutput` without touching agent code.

**Why:** `ToolOutput` (the default) depends on reliable tool calling, which is not a safe bet for
Qwen at 1.7B through Ollama's OpenAI-compatibility layer; when it degrades, the symptom is a retry
storm with no obvious cause. `NativeOutput` needs provider-side structured-output support and
carries documented restrictions alongside function tools.

Decisively, hard rule #6 already mandates this without naming it: *"prompts must be model-agnostic,
no provider-specific features, assume the weakest model, ask for strict JSON matching a schema shown
in the prompt."* That is a description of `PromptedOutput`. It also keeps
`worker/agents/prompts/*.md` the single source of truth for every agent contract — under
`ToolOutput`, half the contract lives in a generated tool schema you cannot see, which makes prompt
debugging guesswork and muddies the `agent-prompts` skill's job.

**Known cost:** schema adherence is not strictly enforced, so the retry loop and a markdown-fence
stripper carry more weight. `PROMPTS.md` already anticipates this in its follow-up prompts
("Qwen is returning markdown fences around JSON") — that stripper is required, not optional, and
ships with a test.

**Touches:** step 3 in `PROMPTS.md` · the `agent-prompts` skill's conventions.

---

## D15 — `cost_usd` is nullable and encodes three states · `SETTLED`

**Decision:** `agent_runs.cost_usd` becomes nullable. Write `0` when the provider is Ollama, the
`Decimal` from `RunUsage.cost` when `genai-prices` priced the call, and `NULL` otherwise. The
dashboard renders `NULL` as `—`, never `$0.00`.

**Why:** `CLAUDE.md` says "cost for Ollama is recorded as 0", but Pydantic AI deliberately returns
`cost: Decimal | None` and uses `None` — not zero — when a model cannot be priced, precisely so
"unknown" stays distinguishable from "free". There are genuinely three states here: free because we
own the hardware, priced, and unpriceable. Collapsing them to `0` costs nothing today and produces a
Phase 4 cost dashboard that confidently reports Bedrock as free whenever a price lookup misses.

**Touches:** `CLAUDE.md` data model and the Ollama note · step 3 in `PROMPTS.md`.

---

## D16 — `brand_rules_json` gets a defined shape · `SETTLED`

**Decision:** One shape, three consumers:

```json
{
  "prohibited_content": ["competitor logos", "alcohol", "unaccompanied minors"],
  "required_elements": ["product visible", "logo visible"],
  "tone": { "avoid_words": ["cheap", "guys"], "prefer_words": ["small-batch", "crafted"] },
  "max_hashtags": 5
}
```

**Why:** `CLAUDE.md` requires the media agent to return
`brand_check: {passes: bool, issues: []}` checked against `brand_rules_json` — but never defined
what that column holds, which makes the contract unimplementable and the prompt unwritable. Every
value here is a short natural-language string an 8B vision model can actually check against an image
description and detected text, rather than a rule engine it would have to reason about.

The shape is deliberately shared: the **media** agent checks `prohibited_content` and
`required_elements`; the **content** agent respects `max_hashtags` and `tone`; the **response**
agent uses `tone.avoid_words`. One column, no per-agent config sprawl.

**Touches:** `CLAUDE.md` data model and the media agent contract · step 2 (seed data) and step 6 in
`PROMPTS.md`.

---

## D17 — Brand scoping without auth · `SETTLED`

**Decision:** `brand_id` is a required query parameter on every list endpoint. The web app keeps the
selected brand in the URL, with a brand selector in the top bar. Two brands are seeded.

**Why:** Auth is explicitly out of scope (hard rule #12), but the product's premise is one manager
running 3–5 client accounts, so "which brand am I looking at" has to be answered somehow. Putting it
in the URL rather than a session keeps hard rule #2 intact — the API stays stateless, and a
bookmarked or shared link resolves to the same view. Making it *required* rather than optional
avoids the failure mode where an unscoped query quietly returns another brand's comments, which
would be the demo's worst moment.

**Amended in step 9 — two operational endpoints are outside this.** `/queue/stats` and
`/failed_jobs` are not brand-scoped, and cannot usefully be. `failed_jobs` has no `brand_id`
column, and giving it one would mean resolving a payload back to a brand for a row that exists
precisely *because* its payload could not be resolved. Both describe the machine rather than a
client's content, so neither can leak one brand's comments into another's view, which is the
failure this entry exists to prevent. The Failed Jobs panel is labelled "all brands" so the scope
is never in question. `/brands` was always outside it, for the obvious reason.

**Touches:** `CLAUDE.md` API notes · steps 5, 7 and 8 in `PROMPTS.md` · `README.md`.

---

## D18 — No queue-depth sampling table · `SETTLED`

**Decision:** Drop the "sample `/queue/stats` into a small in-DB table every 10s" mechanism from
step 8. Live queue stats come from `GET /queue/stats`, polled by the top bar.

**Why:** It existed only to feed the "queue depth over the last hour" chart, and D1 cut that chart.
`CLAUDE.md` says to extend the data model only if a feature needs it, and no surviving feature needs
it. It would also have added a permanently-running background writer to a worker whose job is
supposed to be draining a queue — a small but real source of noise in the load-replay numbers that
step 9 asks you to measure.

**Touches:** step 8 in `PROMPTS.md` · `CLAUDE.md` data model (no new table).

---

## D19 — Model residency is configured, not left to Ollama's defaults · `SETTLED`

**Decision:** Set `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=30m` on the host, and cap
Docker Desktop's memory explicitly. The models themselves are chosen in D20; because `standard` and
`vision` resolve to the same multimodal model, only **two** are ever resident (~9.3 GB).

**The workload never needs all three at once.** The two paths are disjoint:

| Path | Models | Weights | Frequency |
|---|---|---|---|
| Comment | `fast` → `standard` | ~9.3 GB | 300–2,000× per replay |
| Asset | `vision` → `standard` | ~9.3 GB (same two) | once per upload |

The dev machine has 16 GB. The comment path's 6.4 GB fits comfortably alongside Docker and macOS,
and that is the path that runs thousands of times. **16 GB is sufficient for the main path** — an
earlier draft of this entry claimed otherwise by summing all three models as if they were
co-resident, which the workload does not require.

**The actual risk:** left at Ollama's default of 3, a stray third model — an experiment, an old tag
still cached, a teammate's `ollama run` — gets held alongside the two the pipeline needs, hits memory
pressure, and evicts unpredictably. What it evicts may be the model the next comment job needs,
turning a 0.6s triage call into a 6.6 GB reload mid-drain and corrupting the latency numbers step 9
asks you to measure. Capping at 2 makes residency **deterministic**: the two models stay pinned for
the whole run. The long keep-alive stops them being dropped during idle gaps between demo steps.

D20 removes most of this risk at the source by collapsing `vision` onto `standard`. The cap remains
because it costs nothing and the failure it prevents is silent.

**Disk, not just memory.** Docker Desktop's virtual disk defaults to 8 GB on this machine, and
that is not enough. Measured during step 6: images plus build cache reached ~4.3 GB, the Postgres
volume and an orphaned `node_modules` volume took another 1.6 GB, and the remainder went to WAL
during a replay. Postgres then hit `PANIC: could not write to file
"pg_logical/replorigin_checkpoint.tmp": No space left on device`, aborted the checkpointer, and
**failed to restart** — recovery itself needs to write. Nothing else reported a problem: the API's
Compose healthcheck stayed green because `/health` deliberately does not touch the database, so
`docker compose ps` showed four healthy services and every endpoint returning 500.

Raise the virtual disk limit to 32 GB and check `docker system df` before a long run.
`make prune` reclaims what is safe to reclaim — dangling images and build cache, both rebuild
artefacts. It deliberately does **not** run `docker volume prune`: that removes every volume no
container references, which on this machine included an unrelated project's MySQL database.

**The churn is self-inflicted, and now handled.** `make up` builds, so every `make reset` orphans
the previous three images — measured at ~2 GB per reset, which means three resets fill the default
disk on their own. This surfaced a second time during step 9's measured replay: free space fell
from 2.7 GB to 328 MB in ten minutes, and it was image churn from one `make reset`, not the replay.
`reset` now prunes dangling images after building.

This is also a live risk for step 9: `replay-full` is 2,000 comments and roughly 10× the WAL of the
300-comment run that filled the disk.

**Touches:** `.env.example` · `docs/START-HERE.md` §0 prerequisites · `README.md` "Run it" ·
step 10's healthchecks (a green API on a dead database is the thing to fix there).

---

## D20 — Model selection: `qwen3.5:2b` + `qwen3.5:9b` · `SETTLED`

**Decision:**

| Tier | Model | Size | Used by |
|---|---|---|---|
| `fast` | `qwen3.5:2b` | 2.7 GB | triage |
| `standard` | `qwen3.5:9b` | 6.6 GB | response, content |
| `vision` | `qwen3.5:9b` | *(same model)* | media |

**The model `CLAUDE.md` specified does not exist.** `qwen3.6:8b` is not a real tag — qwen3.6 ships
only in 27b and 35b. `make models` would have failed on the first day of the project. This was found
by checking the Ollama library, not by reasoning.

**Why `qwen3.5:9b` for both text and vision:** it is multimodal — text and image input in one
6.6 GB model, tools, thinking, 256K context. That collapses the `standard` and `vision` tiers onto a
single model, so the pipeline goes from three resident models to two and D19's eviction problem
mostly disappears rather than being managed. The D6 tier abstraction is unaffected: three tiers,
two models, and Phase 4 can still point them at three different Bedrock models.

**Why not bigger.** 27B-class models were considered and rejected on arithmetic, not preference:

| Candidate | Size | Verdict |
|---|---|---|
| `qwen3.8:27b` | ~17 GB | Exceeds total RAM. Would swap to disk on every call. |
| `qwen3.6:27b` | ~17 GB | Same. |
| `qwen3.5:27b` | 17 GB | Same. |
| `qwen3-vl:8b` | 6.1 GB | Viable, but a *third* model when `qwen3.5:9b` already does vision. |

A model that swaps to disk is slower than a smaller model that does not, by a wide margin. On a
16 GB machine, "which model fits alongside Docker" dominates "which model scores higher".

**Why `qwen3.5:2b` and not `qwen3:1.7b`:** same family as `standard`, so one prompt style works
across both tiers and eval results are comparable. 1.3 GB is a fair price for that consistency.
`qwen3.5:0.8b` (1.0 GB) is the fallback if memory gets tight, at real risk to JSON adherence under
`PromptedOutput` (D14).

**Verified on 2026-09-08.** Both tags pulled cleanly and matched the listed sizes (2.7 GB / 6.6 GB,
8.7 GB on disk after layer sharing). `qwen3.5:9b` was smoke-tested on a generated PNG and correctly
described it, so the multimodal claim holds and the `standard` / `vision` collapse is sound.

Also observed: the model emits a `Thinking...` block by default. Thinking must be explicitly
disabled on `fast`-tier classification calls, or every triage call pays for reasoning tokens that
are discarded — this is why `CLAUDE.md` calls for it, and step 3 must actually implement it.

**Touches:** `CLAUDE.md` local models section · `Makefile` · `.env.example` · `docs/eval.md` ·
`docs/START-HERE.md`.

---

## D21 — `LLM_PROVIDER` is validated against an allowlist · `SETTLED`

**Decision:** `config.py` types `llm_provider` as a named alias,
`LLMProvider = Literal["ollama", "bedrock"]`, rather than a bare `str`.

**Why:** The stack rule says *"never hardcode a provider"*, and a reviewer flagged the
`Literal` as naming providers in code. The rule is about which provider *runs* — that is still
chosen only by the `LLM_PROVIDER` environment variable, so ADR-0002's "one-line env change"
holds. What the `Literal` adds is a typo-catcher: `LLM_PROVIDER=olama` fails at container start
with a message naming the field, instead of an hour into a replay on the first model call.

The alias is named rather than inline so `worker/llm.py` can `match` on it exhaustively. Adding
a third provider is then a two-file edit in which **mypy names the second file** — the model
factory that has not handled the new case. A bare `str` makes it a one-file edit that compiles
fine and crashes at runtime. The cost of the allowlist is one line; the cost of removing it is
a silent failure mode in the exact place Phase 4 does its work.

**Alternative rejected:** widening to `str` and validating inside `llm.py`. It moves the error
from startup to first use, which is the wrong direction for a config error.

**Touches:** `api/app/config.py` · `worker/worker/config.py` · step 3 in `PROMPTS.md`.

---

## D22 — One `config.py` per service, and only the worker maps tiers · `SETTLED`

**Decision:** `api/app/config.py` and `worker/worker/config.py` both exist. The tier → model map
(D6) lives **only** in the worker's. The API declares the `LLM_MODEL_*` variables as required but
never resolves a tier.

**Why:** Hard rule #1 says config is read in *one place*, and `CLAUDE.md`'s repo layout lists
`config.py` only under `api/app/`. But the API and the worker are separate containers and
separate installable packages, so a single shared module would need a third package on the
`PYTHONPATH` of both images — real packaging work in service of a literal reading. The rule's
target is scattered `os.environ` calls and hostnames written into code; one reader per service
satisfies that.

The tier map is different: it is the specific thing D6 exists to centralise, and duplicating it
would give the project two answers to "what does `fast` mean". The worker is the only service
that calls a model, so it owns the map. The API still *requires* the variables, so a deployment
missing `LLM_MODEL_FAST` fails when the API starts rather than when the first job runs.

**Touches:** `CLAUDE.md` repo layout (the worker's `config.py` is not listed).

---

## D23 — Qwen's thinking is disabled on every Ollama tier, via `reasoning_effort` · `SETTLED`

**Decision:** `worker/llm.py` sends `reasoning_effort: "none"` on **every** Ollama call, not
only on classification calls. Gated on the provider, so Phase 4 Bedrock is unaffected.

**Why:** `CLAUDE.md` asks for thinking-off "on classification calls", implying the `fast` tier
only. Measured against this Ollama build, that is not enough: **both models run their entire
output budget as reasoning and return an empty message**. `qwen3.5:2b` asked to classify one
comment returned `finish_reason: length` with `content: ''`, and `qwen3.5:9b` did the same on a
two-sentence drafting prompt. Given a 2,000-token budget, 2b produced 2,000 tokens of thinking
and still no answer. Restricting the fix to `fast` would leave the response, content and media
agents failing on every call.

**Three mechanisms were tested; only one works through the endpoint Pydantic AI uses:**

| Mechanism | Result |
|---|---|
| `{"think": false}` in the request body | Works on Ollama's native `/api/chat`; **silently ignored** on the OpenAI-compatible `/v1`, which is what `OllamaModel` talks to |
| Qwen's `/no_think` prompt directive | Ignored. Would also have violated hard rule #6 by putting a model-specific token in a prompt |
| `reasoning_effort: "none"` | **Works.** OpenAI-standard, Ollama maps it through, and Pydantic AI exposes it as `openai_reasoning_effort` |

`PARAMETER think false` in a Modelfile was also tried: `ollama create` rejects it as an unknown
parameter, so this cannot be pushed down into a model variant and kept out of the code.

**Consequences:** `CLAUDE.md`'s "Pass thinking-off options for Qwen on classification calls"
understates it — the line should read *all* calls. Measured after the fix: triage on 2b is
**~850 ms** and a response draft on 9b is **~3.4 s**, against D4's estimates of ~2 s and ~3.5 s.
Triage is more than twice as fast as assumed, which makes D4's drain arithmetic conservative.

**Revisit when:** the eval set (D5) exists and can measure whether thinking actually buys
accuracy on the drafting tiers. It is off now because it demonstrably prevented any output at
all, not because it was judged unhelpful.

**Touches:** `CLAUDE.md` local-models note · `worker/llm.py` · D4's latency estimates.

---

## D24 — The api package owns the shared schema; the worker copies it · `SETTLED (written up late)`

**Decision:** SQLAlchemy models are defined once, in `api/app/models/`. The worker's Dockerfile
copies `api/app` to `/opt/api/app` and puts it on `PYTHONPATH`; `worker/worker/db.py` builds only
an engine. The worker does not define, and does not migrate, any table.

**Why:** The orchestrator writes `comments`, `reply_drafts`, `agent_runs` and `content_drafts`, so
it needs the models. The alternatives were a duplicate set of model classes in the worker, or a
third installable package on both images' `PYTHONPATH`. Duplication is the worse of the two by a
wide margin: two definitions of `comments` drift, and the definition that drifts silently is the
one only a replay exercises — you find out an hour into an unattended 2,000-comment run. A shared
package is defensible but is real packaging work (a third `pyproject.toml`, a third build stage,
a version to keep in step) in service of a boundary that does not exist yet. Copying is one
`COPY` line and it is honest about what is happening: the api is the schema's owner.

**Consequence:** Alembic lives only in the api, so `make migrate` has exactly one place to run
from. The copy is baked into the image rather than bind-mounted, so the worker still runs on ECS
in Phase 3 where there are no host mounts; compose additionally mounts it read-only for dev
hot-reload.

**Bookkeeping.** This entry is written up after the fact. `worker/Dockerfile`,
`docker-compose.yml` and `worker/worker/db.py` have cited "D24" since step 4 for a decision that
was never recorded here — the reasoning was in the code comments and nowhere else.
`docs/eval.md` also cited D24, but for something different (the fast-vs-standard tier trade-off);
that arithmetic is D4's, and the reference has been corrected.

**Touches:** `CLAUDE.md` repo layout (the worker's use of `app.models` is not shown there).

---

## D25 — Storage is one async interface, owned by the api package · `SETTLED`

**Decision:** `StorageBackend` and `LocalDiskStorage` live in `api/app/storage.py` and reach the
worker through D24's copy. `worker/worker/storage.py` re-exports them and adds `get_storage()`,
which resolves the *worker's* own `STORAGE_BACKEND` / `STORAGE_ROOT` (D22). The four methods are
hard rule #9's exactly: `put`, `get`, `url`, `delete`. Three are `async`; `url` is not.

**Why here and not `worker/storage.py` alone,** which is where `CLAUDE.md`'s layout and step 6 both
put it: both services touch the same bytes. The API writes an upload, the worker reads it back to
send to the vision model. Two implementations of "what does a `storage_key` mean on disk" is the
same drift D24 rejected for models, except worse — the media path runs once per demo, so a
mismatch is found on stage rather than in a replay.

**Why async when local disk does not need it:** the entire purpose of the interface is that Phase 4
changes no call sites. S3 is network I/O. A sync interface today means editing every caller later,
which is precisely the cost hard rule #9 exists to avoid. `LocalDiskStorage` uses
`asyncio.to_thread` — stdlib, no new dependency. `url()` stays sync because neither backend does
I/O to produce one; presigning is local computation.

**Two consequences worth naming:**

* `url()` returns an API route (`/assets/file/<key>`) under local disk, because a directory has no
  address a browser can reach. That is the one place the storage layer knows an API route exists,
  and the constant is shared with the router so they cannot drift. In Phase 4 it returns a
  presigned URL and the route stops being called. The web app never learns which backend it is —
  it renders whatever `url` the API gave it.
* The FastAPI dependency (`StorageDep`) is deliberately **not** in `app/storage.py`. The worker
  imports that module and has no FastAPI, so a `from fastapi import Depends` at its top would break
  the worker at import. Framework wiring lives in `app/routers/params.py`; the backend stays plain.

**Touches:** `CLAUDE.md` repo layout and hard rule #9 · step 6 in `PROMPTS.md`.

---

## D26 — The content agent's contract is enforced twice, in two different ways · `SETTLED`

**Decision:** "One draft per platform" is a Pydantic validator on `ContentOutput`, so a wrong shape
is **retried**. "No more than `max_hashtags`" is a trim at persist time, so an overshoot is
**clamped**. The `agent_runs` row keeps the model's raw output either way.

**Why not both the same way:** they are different kinds of wrong. A response with two Instagram
captions and no LinkedIn one is *malformed* — the Content page puts three drafts side by side and
would render a blank column — and a malformed response is exactly what Pydantic AI's retry loop
(`retries=3`, hard rule #4) exists to fix, with the validation error handed back to the model as
the correction. Seven hashtags where the brand allows five is *correct output that breaks a
brand rule*: the captions are fine, and burning two more 9B calls to re-roll them would cost
seconds of demo time to fix something a slice fixes for free.

**Why clamping is not silent data loss:** hard rule #5 already requires the full model output in
`agent_runs.output_json`, so the audit trail shows what was actually returned while the stored
draft obeys the brand. The trim is logged with the returned and kept counts. Reviewers see the
draft; the Agents page can still show the model overshooting, which is the signal that
`prompts/content.md` needs work.

**Rejected — enforcing `max_hashtags` in the schema.** It is per-brand (D16), so it cannot be a
static `Field` constraint, and threading a runtime limit into the output model to make the
framework retry on it would turn one brand's stricter rule into a retry storm on a 9B model.

**Touches:** step 6 in `PROMPTS.md` · the `agent-prompts` skill (the content contract).

---

## D27 — Ingest rejects rows, not batches; a malformed row skips the retries · `SETTLED`

**Decision:** `POST /ingest/comments` validates each row independently. Rows that fail are written
to `failed_jobs` with `job_type="ingest_comment"` and the original payload; the rest are inserted
and enqueued. The response gains a `rejected` count. A rejected row does **not** go through arq's
three attempts.

**Why — this was a bug, not a refinement.** Validation ran inside one `try`, so a single
unparseable row returned `422` for the whole payload. `data/viral_post_dump.json` contains exactly
one such row by design (`created_at: "not-a-timestamp"`, index 1447), and the generator that placed
it says in a comment that *"the other 1,999 must still process, which is the point"*. They did not.
Posting the real file returned HTTP 422 and inserted **zero** comments, enqueued zero jobs, and
dead-lettered nothing — so step 9's unattended 1.5–2 hour `replay-full` would have finished in the
first second against an empty database, and the DLQ evidence it exists to produce would never have
appeared. Confirmed against the file before the fix.

**Why straight to the DLQ instead of three retries:** hard rule #7 sends *failed jobs* to
`failed_jobs` after three attempts, and that is right for a transient failure — a model timeout, a
dropped connection. A date that is not a date is permanent. Retrying it twice more costs two
round trips to produce the identical error, and it is the kind of thing that makes a DLQ entry read
`attempts: 3` when nothing was ever retried. The rule's real requirement is *never swallow errors*,
and recording it satisfies that.

**Why `job_type="ingest_comment"` and not `"process_comment"`:** it never became a job. Labelling it
as one would make the Retry button re-enqueue a comment id that does not exist, which fails and
lands straight back in the DLQ — a button that looks like it works and quietly cannot.

**Consequence — Retry dispatches on job type.** `process_comment` and `process_asset` are
re-enqueued with a fresh attempt suffix (arq holds a finished job's key for an hour, so without one
the retry inside that hour is silently refused and the button appears dead). `ingest_comment`
re-validates the stored row instead, which normally fails again and says why. That is deliberate:
Retry re-runs the same operation and reports the same reason rather than pretending, and it
succeeds only if someone actually fixed the payload.

**Rejected — keeping the 422 and documenting "clean your dumps first".** The dump is ours, the bad
row is ours, and it is there specifically to exercise this path.

**Touches:** step 9 in `PROMPTS.md` · `CLAUDE.md` hard rule #7 (the "3x then DLQ" line describes
*job* failures, not parse failures) · `README.md`.

---

## D28 — Liveness and readiness are different questions · `SETTLED`

**Decision:** `/health` stays a pure liveness probe and touches nothing external. A new
`/health/ready` pings Postgres and Redis and returns `503` naming whichever is down. The Compose
healthcheck for `api` points at **readiness**. `worker` and `web` get healthchecks too — the worker
via `arq --check`, which reads arq's own Redis heartbeat.

**Why:** measured, during step 6. Docker's virtual disk filled, Postgres hit
`PANIC: could not write to file` and failed to restart — and `docker compose ps` went on reporting
the API as **healthy**, because the healthcheck asked `/health`, which by design answers "is this
process up" and nothing else. Four green services and every endpoint returning 500. The time lost
went into reading a CORS error in the browser console, because a 500 raised above the CORS
middleware arrives at the browser with no `Access-Control-Allow-Origin` header and therefore looks
like a front-end configuration problem. Nothing in the stack said "the database is gone".

**Why not simply point `/health` at the database.** A liveness probe that fails when a dependency
is down is asking to be restarted for someone else's outage, which turns a database blip into a
restart loop and, under an orchestrator, takes the whole service down at exactly the wrong moment.
The two probes answer different questions and Kubernetes in Phase 3 will want both by name.

**Why `arq --check` and not `pgrep arq`:** a process check stays green through a worker wedged on a
model call that never returns, which is the failure actually worth catching on this service. arq
writes a health record to Redis on an interval and `--check` exits non-zero when it is stale.

**Consequence:** `scripts/demo.sh` waits on `/health/ready`, so it cannot proceed into a replay
against a database that is not there.

**Touches:** `docker-compose.yml` · `api/app/main.py` · D19 (this is the fix its Touches line
called for) · step 10 in `PROMPTS.md`.

---

## D29 — The idempotency guard needs a row lock, not just a read · `SETTLED`

**Decision:** `Ingest` selects the comment `FOR UPDATE OF comments`, and `reply_drafts` gains
`UNIQUE(comment_id)`.

**Why — found by the load replay, which is what step 9 is for.** A clean 300-comment run produced
**301 triage runs**: comment 242 was triaged, drafted, and then triaged and drafted *again*
sixteen minutes later, and both attempts committed. The result was two `reply_drafts` rows for one
comment, and `GET /comments/242` then returned **500** — that endpoint reads the draft with
`scalar_one_or_none()`, and `CommentWithDraft.draft` is singular, so the code had always assumed
one draft per comment without anything enforcing it. The Inbox listed the comment twice for the
same reason.

The guard added in step 4 (`if comment.status in COMPLETED_STATUSES: return End`) is
**check-then-act**. It closes the common case — a retry that starts after the first attempt
committed — and nothing more. Two attempts whose transactions overlap both read `new`, and both
proceed. D9's job key prevents a *duplicate enqueue*; it does not prevent a retry from overlapping
the attempt it is retrying.

**Why both fixes and not one.** The row lock is the correctness fix: the second transaction blocks
at the SELECT, and by the time it reads, the status is `drafted`, so it exits having spent **no
model calls**. The constraint alone would let it triage and draft all over again — paying for both
calls — before failing on the insert. But the constraint still earns its place as the backstop: it
is what turns this class of race from a silent duplicate that 500s an endpoint into a failed job
with a visible error, and it makes an assumption the API already relied on into something the
database guarantees. The concurrency test asserts **two model calls, not four**, which is what
separates the two.

`of=Comment` locks only the comment row. Locking the brand join too would serialise every job in a
replay behind a single brand row.

**Rate observed:** 1 in 300. Small enough to be invisible in the demo, large enough that
`replay-full` at 2,000 comments would be expected to produce several.

**Touches:** `worker/orchestrator.py` · `api/app/models/draft.py` · a new migration ·
`CLAUDE.md` data model (`reply_drafts` is now one-per-comment by constraint).

---

## D30 — Retry where a job can be re-queued; Discard where it cannot · `SETTLED`

**Decision:** `POST /failed_jobs/{id}/retry` accepts only `process_comment` and `process_asset`.
`POST /failed_jobs/{id}/discard` clears any row. `GET /failed_jobs` reports `retryable` per row and
the panel labels its one button from that. `attempts` is never incremented by a human action.

**Why — found by using it.** The first version offered Retry on every row, and for an
`ingest_comment` row it re-validated the stored payload. That payload is stored and immutable, so
the validation could never pass: every press returned the same 422 and incremented `attempts`. The
malformed row from `viral_post_dump.json` reached **`attempts: 7`** on a real screen, entirely from
button presses, next to a documented rule that says three attempts and then the DLQ. A counter that
records how many times someone pressed a button that cannot work is not information, and the code
comment defending it — *"it succeeds only if someone actually fixed the payload, which is the case
it exists for"* — described a case unreachable from the UI.

**Why Discard is the right affordance.** The DLQ is a list of work that still needs attention. For
a malformed input row the attention it needs is a person reading the reason and fixing the source
data, which happens nowhere near this panel; re-running is not part of the remedy. So the action
that belongs on the row is the one that says "seen, and dealt with elsewhere". The refused Retry
now names the remedy rather than just declining.

**Why Discard is not restricted to unretryable rows.** An operator who has decided a dead comment
job is not worth chasing should not have to press Retry first to get rid of it.

**Why `retryable` is on the wire.** The rule lives in one place. Deriving it in the browser from a
second copy of the job-type list is how the two drift, and the drift would show up as a button that
promises something the API refuses.

**Touches:** step 9 in `PROMPTS.md` (the panel has two actions, not one) · D27, which introduced
the `ingest_comment` job type.

---

## Standing assumptions

| # | Assumption | Revisit when |
|---|---|---|
| 1 | Effectively a solo build, roughly four weeks (D1) | A deadline is set, or teammates start committing |
| 2 | Qwen via Ollama needs prompted JSON, not tool calling (D14) | The eval set (D5) shows `ToolOutput` is reliable |

Resolved: the `qwen3.5` tags resolve and `qwen3.5:9b` is multimodal — both verified by pulling and
smoke-testing on 2026-09-08 (D20).

No open questions remain.

---

## Applied

All of the above is now reflected in the repo:

| File | What changed |
|---|---|
| `CLAUDE.md` | Stack, hard rules 1/3/4/5/6/7/10, data model, agent contracts, orchestration section, commands, local models, UI brief |
| `docs/decisions/0001-*` | Status → superseded by ADR-0002 |
| `docs/decisions/0002-*` | **New** — LLM access via Pydantic AI |
| `docs/decisions/0003-*` | **New** — orchestration via `pydantic-graph` |
| `docs/PROMPTS.md` | Steps 0–10 rewritten; new step 4.5 (eval runner); step 8 cut to a table |
| `docs/START-HERE.md` | §0 prerequisites (RAM, Docker cap, Ollama vars), §1 models, §5 now points here, §7 solo build |
| `docs/SETUP.md` | Context7 row, tdd row, agent-prompts snippet, team hygiene, repo skeleton |
| `docs/eval.md` | Tier column, sentiment MAE, both models, rationale |
| `README.md` | Status, agent table, architecture framing, stack table, roadmap, success criteria, repo contents, "Run it" |
| `Makefile` | `models` target pulls `qwen3.5:2b` + `qwen3.5:9b` |
| `.claude/agents/tester.md` | `FakeLLM` → `TestModel`/`FunctionModel`, idempotency + fence-stripping coverage |
| `.claude/skills/agent-prompts/SKILL.md` | 2B target, `PromptedOutput` note, ordinal sentiment throughout |

`.env.example` is listed separately — see the note at the end of this file.

---

## `.env.example` — must be edited by hand

The repo's own permission rules deny writes to anything matching `.env*`, so this file could not be
updated automatically. Replace its LLM block with:

```
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1

# Three tiers, two models: qwen3.5:9b is multimodal, so standard and vision are
# the same model and only two are ever resident (~9.3 GB). See D19 / D20.
LLM_MODEL_FAST=qwen3.5:2b
LLM_MODEL_TEXT=qwen3.5:9b
LLM_MODEL_VISION=qwen3.5:9b
```

Two things to check while you are in there:

1. `OLLAMA_BASE_URL` needs the **`/v1` suffix** — Pydantic AI's `OllamaProvider` talks to Ollama's
   OpenAI-compatible endpoint. The old value (`http://host.docker.internal:11434`) will not work.
2. `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_KEEP_ALIVE` do **not** belong in this file. Ollama runs on
   the host, not in a container, so they go in your host shell profile:
   ```
   export OLLAMA_MAX_LOADED_MODELS=2
   export OLLAMA_KEEP_ALIVE=30m
   ```
