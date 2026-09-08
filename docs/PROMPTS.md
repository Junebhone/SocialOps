# SocialOps — Claude Code Prompt Sequence (Phase 1)

Run these in order, one per session or one per `/clear`. Each prompt assumes the previous one is
committed. `CLAUDE.md` must be in the repo root.

**Read [DECISIONS.md](DECISIONS.md) first.** These prompts encode 19 decisions; if a step looks
arbitrary, the reasoning is there. If Claude's output contradicts the log, that's a bug in the step.

Scope per [D1](DECISIONS.md): steps 0–7 and 9–10 ship. Step 8 is cut down to a plain table — no
analytics agent, no charts.

---

## 0. Bootstrap
```
Read CLAUDE.md and docs/DECISIONS.md. Create the repo skeleton exactly as laid out there:
docker-compose.yml with postgres, redis, api, worker, web services; .env.example with every
required variable including LLM_MODEL_FAST/TEXT/VISION; Makefile with all listed targets;
api/ and worker/ as installable Python packages with pyproject.toml (ruff, mypy, pytest
configured); web/ as a fresh Next.js 15 TypeScript app with Tailwind and shadcn/ui
initialized; empty data/ and infra/ folders with .gitkeep.

Dependencies: pydantic-ai and pydantic-graph in worker/. No litellm, no langgraph.
Use context7 to check the current pydantic-ai package name and import paths before writing
pyproject.toml.

Add a README "Run it" section. Do not implement features yet. Run `make up` and confirm all
five containers start and /health on the API returns 200. Commit.
```

## 1. Data model + migrations
```
Implement the data model from CLAUDE.md as SQLAlchemy 2 async models in api/app/models/,
matching Pydantic schemas in api/app/schemas/, and an initial Alembic migration.

Pay attention to these, they are deliberate (see DECISIONS.md D3, D7, D8, D9, D15):
- comments has external_id with UNIQUE(post_id, external_id)
- comments.sentiment is a SmallInteger in -2..2, not a float
- reply_drafts status is pending|approved|rejected|published, plus approved_by and approved_at.
  There is no "edited" status; a non-null final_text is what records an edit.
- outbox(id, reply_draft_id, payload_json, created_at, sent_at)
- agent_runs uses entity_type + entity_id (indexed together) and a denormalized brand_id,
  not an opaque input_ref. cost_usd is NULLABLE.

Add api/app/db.py with an async session factory reading DATABASE_URL. Add CRUD routers for
brands, platform_accounts, and posts (list/get/create). Write tests that spin up the models
against the compose Postgres, including one that proves the comments unique constraint
rejects a duplicate. Run make migrate, make test. Commit.
```

## 2. Synthetic data
```
Create data/seed.py that inserts 2 brands (one coffee roaster, one skincare DTC brand) with
realistic voice_guidelines and brand_rules_json, 3 platform_accounts each, 10 posts each with
plausible metrics_json.

brand_rules_json must match the shape in CLAUDE.md exactly:
{"prohibited_content": [...], "required_elements": [...],
 "tone": {"avoid_words": [...], "prefer_words": [...]}, "max_hashtags": 5}

Create data/comments_small.json (300 comments) and data/viral_post_dump.json (2,000 comments)
using Faker plus hand-written templates so the mix is roughly 40% questions, 25% praise,
20% complaints, 10% spam, 5% other, with some non-English and some emoji-only. Every comment
needs a stable external_id so replaying is idempotent. Include at least one deliberately
malformed comment in the 2,000-comment dump so step 9 has something for the DLQ.

Also create data/eval.json: 50 of those comments, hand-labeled with the correct category,
sentiment (-2..2 integer), and needs_reply. This is the eval set (D5) — label them carefully,
it is the only evidence that the small triage model is good enough.

Include 5 royalty-free sample product images in data/sample_images/ (generate simple PNGs with
Pillow if needed). Wire make seed. Commit.
```

## 3. LLM layer + BaseAgent
```
Use context7 to check the pydantic-ai API before writing this — Agent, PromptedOutput,
OllamaProvider, RunUsage, and Agent.override. Do not guess.

Implement worker/llm.py::complete(prompt_name, variables, schema: type[BaseModel],
tier: Literal["fast","standard","vision"], images: list[bytes] | None = None).

It loads the prompt from worker/agents/prompts/{prompt_name}.md, renders {{variables}},
builds a pydantic-ai Agent for the model that config.py maps that tier to, uses
PromptedOutput with `schema`, sets retries=3, and returns (parsed, Usage).

Usage has input_tokens, output_tokens, cost_usd, latency_ms:
- cost_usd is 0 when LLM_PROVIDER is ollama, RunUsage.cost when priced, None otherwise (D15)
- latency_ms is measured here; pydantic-ai does not provide it

Strip markdown code fences and any leading prose before parsing — small Qwen models emit them
and PromptedOutput will not do it for you. This ships with a test.

For Ollama+Qwen pass the option that disables thinking on fast-tier calls.

Implement worker/agents/base.py::BaseAgent with a `tier` class attribute. Agents never name a
model. Set pydantic_ai.models.ALLOW_MODEL_REQUESTS = False in conftest.py and test with
TestModel / FunctionModel via Agent.override — there is no hand-rolled FakeLLM.

Write tests for: retry on bad JSON, fence stripping, usage recording, and cost_usd being 0
for ollama rather than None. Commit.
```

## 4. Queue + orchestrator + triage/response agents
```
Implement the arq worker in worker/main.py with Redis from REDIS_URL.

Implement worker/orchestrator.py as a pydantic-graph graph, one typed node per step:
ingest_comment → triage → (needs_reply ? response : end) → persist. Each node calls one agent
and writes an agent_runs row with entity_type="comment" and the comment's id and brand_id.

Use context7 to check the pydantic-graph API. Do not use pydantic-ai sub-agents or agent
delegation for the branch — routing is an `if`, not a model decision (D12). Do not add any
durable-execution layer; arq owns retries.

Implement TriageAgent (tier="fast") and ResponseAgent (tier="standard") with prompts in
prompts/triage.md and prompts/response.md following the contracts in CLAUDE.md. Use the
agent-prompts skill. Sentiment is an integer -2..2.

Add POST /ingest/comments to the API that accepts a JSON array or CSV upload, inserts comments
with ON CONFLICT DO NOTHING on (post_id, external_id), enqueues one job per NEW comment with a
job key derived from the comment id, and returns {inserted, skipped}. Running it twice must
insert nothing the second time and enqueue nothing.

Add retry with backoff and a failed_jobs insert after 3 failures. Add GET /queue/stats
returning queued, running, failed counts.

Run make replay and show me the resulting comments and reply_drafts. Commit.
```

## 4.5. Eval runner
```
Implement worker/eval.py: load data/eval.json, run TriageAgent over all 50 comments against
the current LLM_PROVIDER and fast-tier model, and report category accuracy, needs_reply
accuracy, sentiment mean absolute error, p50 latency, and cost per 100 comments.

Print a markdown table row matching the columns in docs/eval.md and append it to that file.
Wire `make eval`. Run it against qwen3.5:2b and then against qwen3.5:9b by overriding
LLM_MODEL_FAST, and record both rows.

If the 2b model is more than a few points behind the 9b on category accuracy, say so plainly —
that is the signal to promote triage to the standard tier and accept a slower drain (D4).
Commit.
```

## 5. Inbox UI + approvals
```
In web/, build the Inbox page: table of comments with category, sentiment badge (5 levels),
urgency, and the draft reply. Row actions: Approve, Edit (inline textarea), Reject. Add a
checkbox column and an "Approve selected" button — batch approval is a stated demo criterion.

API endpoints:
- PATCH /reply_drafts/{id} for status and final_text, setting approved_by and approved_at
- PATCH /reply_drafts/bulk taking {ids: [], status} for the batch path
- GET /comments with filters (brand, category, status)

brand_id is a REQUIRED query param on every list endpoint and lives in the URL, never in a
session — the API is stateless (D17). Put a brand selector in the top bar.

Approving writes an outbox row. Add an arq cron job in the worker that drains outbox every
30s, marks sent_at, and flips the reply_draft to published. There is no real platform; the
outbox IS the publish step, and it is what makes the approval loop visibly close (D3).

Add a top bar showing live queue stats polled every 2s from /queue/stats.

Use the frontend-design skill. shadcn Table, Badge, Button, Textarea, Checkbox. Loading and
empty states for every list; errors inline, never alert(). Commit.
```

## 6. Storage + media + content agents
```
Implement worker/storage.py with StorageBackend and LocalDiskStorage (root from STORAGE_ROOT).

Add POST /assets (multipart upload) that stores the file and enqueues a media job.

Implement MediaAgent (tier="vision": description, detected_text, brand_check against
brand_rules_json's prohibited_content and required_elements) and ContentAgent
(tier="standard": three platform drafts respecting tone and max_hashtags) with their prompts.
Note both tiers resolve to qwen3.5:9b — it is multimodal, so this is one model, not two (D19).

Orchestrator path as a second pydantic-graph graph: asset → media → content → persist
content_drafts. Downscale images to max 1024px before sending to the model.

Write tests with TestModel/FunctionModel. Commit.
```

## 7. Content UI
```
Build the Content page: drag-and-drop upload (react-dropzone), then a card per asset showing
the image, the media analysis, brand-check pass/fail with issues, and three side-by-side
platform drafts with approve/edit/reject. Add GET /assets and GET /content_drafts endpoints,
both scoped by the required brand_id query param. Use the frontend-design skill. Commit.
```

## 8. Agents page
```
Build the Agents page: a table of agent_runs showing agent, entity_type/entity_id, tokens,
cost, latency, and status, filterable by brand and agent, plus a per-agent totals row.
Render a NULL cost_usd as "—", never as $0.00 (D15).

Add GET /agent_runs with brand_id, agent, and status filters.

No analytics agent, no charts, no queue-depth sampling table — all cut in D1 and D18. If you
think a chart belongs here, say so before building it.

Commit.
```

## 9. Load replay + DLQ
```
Stop the web container to free memory, then run make replay-full. This is unattended and will
take roughly 1.5–2 hours on one 16 GB machine; do not sit and watch it.

Confirm the queue stats climb and drain, and that the intentionally malformed comment from the
dump lands in failed_jobs. Add a Failed Jobs panel on the Agents page with a Retry button
(re-enqueue).

Measure and record in README: total wall time, per-agent p50/p95 latency, total tokens, and
the replay of 300 for comparison. These measured numbers replace the estimates in the README's
success criteria. Commit.
```

## 10. Hardening + demo
```
Add structlog JSON logging with request_id/job_id across api and worker. Add a docker-compose
healthcheck for every service.

Write scripts/demo.sh that: resets the DB (make down && make up && make migrate && make seed),
uploads one sample image, runs the small replay, and prints URLs for each page. Note that the
image upload loads the vision-capable model — since standard and vision are the same model,
this does not evict anything (D19).

Write docs/architecture-phase1.md. Generate the Mermaid diagram from the pydantic-graph graph
definition rather than hand-drawing it — that is why the graph exists (D12). Add container and
data-flow diagrams alongside it.

Update README "Run it" and add a "Switching LLM provider" section showing the env changes for
Ollama and Bedrock, referencing ADR-0002.

Run make lint and make test; fix everything. Commit and tag v0.1-phase1.
```

---

## Useful follow-up prompts

- `Run make eval against the current LLM_PROVIDER and print category accuracy, needs_reply accuracy, and sentiment MAE. Append the row to docs/eval.md.`
- `The response agent drafts are too generic. Rewrite prompts/response.md to use brand voice_guidelines and tone.avoid_words with two few-shot examples per brand pulled from the DB, then re-run make replay.`
- `Show me every place a hostname, port, or model name is hardcoded and move it to config.`
- `Review the last three commits against CLAUDE.md hard rules and docs/DECISIONS.md, and list any violations.`
- `Triage accuracy on qwen3.5:2b is below the 9b baseline. Promote triage to the standard tier, re-run make eval, and update D4 in docs/DECISIONS.md with the new drain estimate.`
