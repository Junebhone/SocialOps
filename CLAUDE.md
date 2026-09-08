# SocialOps — Claude Code Rules (Phase 1: Working Local Demo)

> Every non-obvious decision below is explained in **[docs/DECISIONS.md](docs/DECISIONS.md)**.
> If a rule here looks arbitrary, the reasoning is there. Read it before proposing a change.

## What this project is
Multi-agent social media command center for small businesses. An orchestrator routes
incoming work (comments, uploaded media) to specialist agents: triage, response, content,
media. A human approves everything before it "publishes". Phase 1 runs fully local via
Docker Compose. Later phases migrate to AWS (EC2 → ECS → RDS/S3/SQS → Step Functions →
CloudWatch/Terraform). Every design decision must keep that migration cheap.

## Stack (do not substitute without asking)
- Front end: Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui
- API: FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, uvicorn
- Worker: Python, `pydantic-graph` for the orchestrator, `arq` on Redis for the job queue
- LLM access: **Pydantic AI** only. Default provider is Ollama. Never hardcode a provider.
- Data: PostgreSQL 16, Redis 7
- Files: local `./storage` volume behind a `StorageBackend` interface
- Dev: Docker Compose (services: postgres, redis, api, worker, web)
- Synthetic data only. No live social platform APIs.

## Repo layout
```
socialops/
  docker-compose.yml   .env.example   Makefile   README.md
  api/        app/{main.py, config.py, db.py, models/, schemas/, routers/, services/}  alembic/  tests/
  worker/     worker/{main.py, orchestrator.py, agents/, llm.py, storage.py, eval.py}  tests/
  web/        Next.js app
  data/       seed.py  viral_post_dump.json  comments_small.json  eval.json  sample_images/
  docs/       DECISIONS.md  PROMPTS.md  START-HERE.md  SETUP.md  eval.md  decisions/
  infra/      (empty in Phase 1 — Terraform later)
```

## Hard rules
1. Config only via environment variables read in one place (`config.py`). Required:
   `DATABASE_URL`, `REDIS_URL`, `STORAGE_BACKEND`, `STORAGE_ROOT`, `LLM_PROVIDER`,
   `LLM_MODEL_FAST`, `LLM_MODEL_TEXT`, `LLM_MODEL_VISION`, `OLLAMA_BASE_URL`.
   No `localhost` in code.
2. API is stateless. No in-memory caches, no module-level mutable state, no sessions in RAM.
3. Every agent extends `BaseAgent` with `run(input: BaseModel) -> BaseModel`. Agents never
   touch the queue or the DB directly; the orchestrator does. Every agent declares a
   `tier: Literal["fast","standard","vision"]`; `config.py` maps tier → model. **Agents never
   name a model.**
4. Every LLM call goes through `worker/llm.py::complete()`. It builds a Pydantic AI `Agent`
   for the caller's tier, uses `PromptedOutput` with the caller's schema, times the call,
   and returns `(parsed, usage)` where usage has `input_tokens`, `output_tokens`,
   `cost_usd`, `latency_ms`. Pydantic AI owns validation and retries (`retries=3`).
   There is exactly one place a model is called; do not call `Agent.run()` anywhere else.
5. Every agent invocation writes one `agent_runs` row (agent, entity_type, entity_id,
   brand_id, output_json, status, tokens, cost_usd, latency_ms, error). This is the audit
   trail and the cost dashboard, so `entity_type`/`entity_id` must always be joinable back
   to the row that caused the run.
6. Prompts live in `worker/agents/prompts/*.md`, loaded at runtime. Not inline strings.
   Prompts must be model-agnostic: no provider-specific features. Assume the weakest model
   (a 2B local model). Ask for strict JSON matching a schema shown in the prompt — the
   prompt is the whole contract, because `PromptedOutput` means there is no hidden tool
   schema. Strip markdown fences before parsing; small Qwen models emit them.
7. Failed jobs retry 3x with backoff, then land in `failed_jobs` (our DLQ). Never swallow errors.
   `arq` owns retries. Do not add a second retry or durability layer.
8. Structured JSON logging (`structlog`) from day one, one log line per request/job with
   `request_id`/`job_id`.
9. Storage access only through `StorageBackend` (`put`, `get`, `url`, `delete`). Phase 1
   implementation is `LocalDiskStorage`. S3 comes later; don't write it now.
10. Tests: `pytest` for api and worker. Agents are unit-tested with Pydantic AI's `TestModel`
    / `FunctionModel` via `Agent.override(model=...)`. Set `models.ALLOW_MODEL_REQUESTS = False`
    in `conftest.py`. No test may call a real model.
11. Do not add dependencies beyond the stack above without stating why in the PR summary.
12. Do not build auth, billing, or live platform integrations. Out of scope for Phase 1.

## Data model (minimum — extend only if a feature needs it)
```
brands(id, name, voice_guidelines, brand_rules_json)
platform_accounts(id, brand_id, platform, handle)
posts(id, account_id, external_id, text, posted_at, metrics_json)
comments(id, post_id, external_id, author, text, created_at, category, sentiment,
         needs_reply, status)                          UNIQUE(post_id, external_id)
reply_drafts(id, comment_id, text, agent_run_id, status[pending|approved|rejected|published],
             final_text, approved_by, approved_at)
outbox(id, reply_draft_id, payload_json, created_at, sent_at)
assets(id, brand_id, filename, storage_key, mime, analysis_json)
content_drafts(id, asset_id, platform, text, hashtags_json, agent_run_id, status)
agent_runs(id, agent, entity_type, entity_id, brand_id, output_json, status, input_tokens,
           output_tokens, cost_usd NULL, latency_ms, error, created_at)
                                                        INDEX(entity_type, entity_id)
failed_jobs(id, job_type, payload_json, error, attempts, created_at)
```

`brand_rules_json` shape — one column, three consumers (media checks the first two, content
respects `max_hashtags` and `tone`, response uses `tone.avoid_words`):
```json
{
  "prohibited_content": ["competitor logos", "alcohol", "unaccompanied minors"],
  "required_elements": ["product visible", "logo visible"],
  "tone": { "avoid_words": ["cheap", "guys"], "prefer_words": ["small-batch", "crafted"] },
  "max_hashtags": 5
}
```

`cost_usd` is nullable and encodes three states: `0` when the provider is Ollama,
the value from `RunUsage.cost` when priced, `NULL` when the model cannot be priced.
Render `NULL` as `—`, never as `$0.00`.

## Agents and their contracts
- **triage** (`fast`): comment text → `{category: question|complaint|praise|spam|other,
  sentiment: -2..2 (int), needs_reply: bool, urgency: low|med|high}`
- **response** (`standard`): comment + brand voice → `{reply_text, tone, confidence}`
- **content** (`standard`): asset analysis + brand → `[{platform, text, hashtags[]}]` for
  x, instagram, linkedin
- **media** (`vision`): image → `{description, detected_text[],
  brand_check: {passes: bool, issues[]}}`

Sentiment is a 5-point integer, not a float: small models do not produce calibrated
continuous scores, and five buckets are hand-labelable for the eval set.

*(An analytics agent is out of scope for Phase 1 — see D1.)*

## Orchestration
`worker/orchestrator.py` is a `pydantic-graph` graph, one typed node per step:

- comment path: `ingest → triage → (needs_reply ? response : end) → persist`
- asset path: `ingest → media → content → persist`

Nodes call agents; nodes write `agent_runs`. Agents contain no graph types. Do **not** use
Pydantic AI sub-agents or agent delegation for routing — routing is an `if`, not a model
decision. Do **not** add a durable-execution layer (Temporal, DBOS, Prefect, Restate);
`arq` owns retries. Approval is not a paused run: the graph persists the draft and ends.

## Workflow expectations
- Work in small steps. After each step: run `make test`, run `make lint`, show me a diff
  summary and the exact commands you ran.
- Before creating a file, check whether it exists. Prefer editing.
- When a step is ambiguous, ask one question, then proceed. Don't stall.
- Keep the README's "Run it" section accurate after every change.
- Commit after each completed step with a conventional-commit message.
- If a decision contradicts `docs/DECISIONS.md`, say so before writing code.

## Commands
```
make up        # docker compose up --build
make down
make migrate   # alembic upgrade head
make seed      # python data/seed.py
make test      # pytest api worker
make lint      # ruff + mypy (python), eslint (web)
make models    # pull the two Ollama models
make replay    # POST comments_small.json to /ingest/comments (300 comments)
make replay-full  # POST viral_post_dump.json (2,000 comments — unattended, ~1h+)
make eval      # score the 50 labeled comments in data/eval.json
```

## Local models (Ollama)
Two models, not three: `qwen3.5:9b` is multimodal, so `standard` and `vision` are the same
model and only two are ever resident (~9.3 GB).

```
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
LLM_MODEL_FAST=qwen3.5:2b       # 2.7 GB — triage
LLM_MODEL_TEXT=qwen3.5:9b       # 6.6 GB — response, content
LLM_MODEL_VISION=qwen3.5:9b     # same model, vision-capable
```

Set on the **host**, not in the container (Ollama runs on the host):
```
OLLAMA_MAX_LOADED_MODELS=2
OLLAMA_KEEP_ALIVE=30m
```
Without these, Ollama tries to hold three models and evicts unpredictably mid-replay.
Cap Docker Desktop's memory explicitly; 16 GB total is workable but not generous.

Pass thinking-off options for Qwen on classification calls. Cost for Ollama is recorded as 0.

## UI design brief
- Audience: a marketing manager, not a developer. Dense but calm.
- Layout: left sidebar (Inbox, Content, Agents), top bar with live queue stats and a
  brand selector.
- `brand_id` is a required query param on every list endpoint and lives in the URL, never
  in a session — the API is stateless and a shared link must resolve to the same view.
- Palette: neutral grays + one accent; sentiment/urgency colors only on badges.
- Typography: Inter, 14px base, generous row height in tables.
- Every list is scannable: badge, title, one-line preview, actions on hover.
- No marketing hero sections, no gradients, no emoji in UI, no placeholder lorem ipsum.
- Loading and empty states for every list. Errors shown inline, never as alert().

## Skills and tools available in this repo
- Use the `agent-prompts` skill whenever creating or editing files in worker/agents/prompts/.
- Use `frontend-design` for any page or component work in web/.
- Use `tdd` when implementing anything in api/ or worker/ that has logic.
- Use Context7 (MCP) to check Pydantic AI, `pydantic-graph`, `arq`, SQLAlchemy, and Next.js
  APIs before writing code against them. Do not guess method signatures.
- Never read or print the contents of .env.
