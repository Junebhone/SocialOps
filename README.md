# SocialOps

**A multi-agent social media command center for small and mid-size businesses — built as a monolith, then migrated to AWS in six phases.**

SocialOps gives a marketing manager one dashboard where incoming comments, mentions, and uploaded assets are handled by a team of specialist AI agents, with a human approving anything before it publishes.

> **Status: Phase 1 in progress — steps 0–2 of 10 complete.** The Compose stack runs, the ten-table schema is migrated with CRUD endpoints, and the synthetic dataset is generated and seeded. Agents, the queue and the UI are being built step by step per [docs/PROMPTS.md](docs/PROMPTS.md).
>
> Start with **[docs/DECISIONS.md](docs/DECISIONS.md)** — every non-obvious technical decision and why. Then [docs/START-HERE.md](docs/START-HERE.md) to set up, and [docs/PROMPTS.md](docs/PROMPTS.md) to build.

---

## The problem

Small businesses running several brand accounts hit the same three walls:

- **Comments pile up unanswered**, especially after a post spikes.
- **Content is produced inconsistently** across platforms.
- **Nobody has time to analyze** what is actually working.

## The approach

An **orchestrator** receives every incoming item and routes it to the right specialist agent:

| Agent | Responsibility |
| --- | --- |
| **Triage** | Classifies incoming comments and mentions, scores sentiment |
| **Response** | Drafts replies in the brand's voice |
| **Content** | Turns one uploaded asset into platform-specific posts |
| **Media** | Analyzes images and video, checks brand guidelines |
| **Analytics** | Summarizes performance across accounts *(Phase 2+ — out of scope for Phase 1, see D1)* |

A human reviews and approves agent output before anything is published.

---

## Architecture

The application is built **correctly from the start** — stateless API, containerized worker, queue-backed ingestion — and then **re-platformed** phase by phase onto managed AWS services. Each phase swaps infrastructure underneath an app whose shape does not change: local Postgres becomes RDS, local disk becomes S3, `arq` on Redis becomes SQS, Docker Compose becomes ECS.

This is a deliberate departure from the original proposal, which described Phase 1 as a *stateful monolith* to be re-architected later. Writing throwaway statefulness is real work that produces nothing, so the migration is framed honestly as re-platforming rather than re-architecture. The reasoning is in [D2](docs/DECISIONS.md).

### Tech stack

| Layer | Technology |
| --- | --- |
| Front end | React / Next.js dashboard — container → S3 + CloudFront |
| Application | FastAPI (Python) REST API, containerized |
| Agent workers | Separate containers behind `arq`/Redis → SQS, autoscaled on queue depth |
| Relational data | PostgreSQL — local → Amazon RDS (Multi-AZ) |
| Object storage | Local disk → EBS → Amazon S3 with lifecycle policies |
| Messaging | Amazon SQS (with dead-letter queue) |
| Cache / agent state | Amazon ElastiCache (Redis) |
| AI | Pydantic AI over Ollama (local) → Amazon Bedrock (vision + text) |
| Orchestration | `pydantic-graph` (local) → AWS Step Functions |
| IaC & CI/CD | Terraform, GitHub Actions |

### How the workload maps to cloud concepts

- **Relational data** — accounts, campaigns, posts, comments, approvals, and per-agent run logs with foreign-key relationships and audit history.
- **Unstructured file processing** — uploaded product photos and video processed by the media agent; bulk comment exports (CSV/JSON) parsed by the triage agent.
- **Async / traffic spike** — a viral post produces thousands of comments in an hour; ingestion is queued and fanned out to autoscaling agent workers, with failures landing in a dead-letter queue.

---

## Roadmap

The six-phase migration path, from laptop to fully automated cloud deployment:

| Phase | What gets built | Cloud concepts exercised |
| --- | --- | --- |
| **1. Working local app** | FastAPI + Next.js, local Postgres, local file storage, a separate worker container behind a Redis queue, all via Docker Compose | Baseline architecture, local dev parity, queue-backed async |
| **2. Platform setup & lift-and-shift** | AWS account, IAM roles, VPC with public/private subnets, security groups; deploy the same containers to an EC2 instance with Postgres and files on the same box | IaaS, networking, IAM, least privilege |
| **3. Containerize & deploy** | Dockerize API, front end, and agent workers; push to ECR; run on ECS (Fargate) behind an Application Load Balancer | Containers, image registry, managed container runtime, load balancing |
| **4. Decouple state** | Postgres → RDS, files → S3, Redis → ElastiCache, `arq` → SQS, Ollama → Bedrock; every swap is an env change behind an existing interface | Managed data services, object storage, caching, message queues |
| **5. Orchestrate & expose** | Split into services (API, orchestrator, triage workers, media workers); autoscale on SQS queue depth; expose via API Gateway + ALB with HTTPS, Route 53, and WAF; agent hand-offs coordinated by Step Functions | Service decomposition, autoscaling, API management, edge security, workflow orchestration |
| **6. Observe & automate** | CloudWatch dashboards, alarms, and structured logging; X-Ray tracing across agents; Terraform for all infrastructure; GitHub Actions CI/CD; k6 load tests; cost dashboard | Observability, IaC, CI/CD, load testing, FinOps |

---

## Target user

A marketing manager at a small business, or a boutique agency account manager running 3–5 client brand accounts. Not a developer — they live in a dashboard, review agent output, and approve work.

## Desired outcomes

Once fully deployed, SocialOps should absorb engagement spikes with no human intervention, cut time-to-first-response on customer comments from hours to minutes, and let one marketing manager run multiple accounts with agents doing the first pass.

Architecturally, the system should be:

- fully stateless at the compute layer (true from Phase 1, not retrofitted),
- scaled out and in automatically on queue depth,
- able to survive an AZ failure, and
- redeployable from scratch through IaC and CI/CD.

## Definition of success

**Technical**

- The same application runs correctly at every phase of the flow.
- After Phase 4, the app containers hold no state.
- Replaying a 2,000-comment viral-post dump triggers visible worker scale-out and drains within the target window, with failures landing in the DLQ.
  - Phase 1 reference (one 16 GB laptop, sequential): **300 comments in ~15–20 min**, 2,000 unattended in ~1.5–2 h. Measured numbers replace these estimates in step 9.
  - The point of the AWS phases is that this number collapses once workers autoscale.
- Any team member can destroy and recreate the environment with `terraform apply`.
- A CI pipeline deploys on merge.

**Demo**

- Upload one product photo and watch three platform-specific drafts appear.
- Replay the comment dump and show the SQS depth spike, ECS task count rising, and the CloudWatch recovery graph.
- Approve a batch of agent-drafted replies.
- Kill a container live and show traffic keep flowing.
- Show the before/after architecture diagrams from Phase 1 to Phase 6.

## Known risk

Live social platform APIs (X, Meta, TikTok) require paid access or lengthy app review. The project is built against a **replay / synthetic data source**, and live integration is treated as a stretch goal.

---

## Repository contents

| Path | Description |
| --- | --- |
| `Project Proposal.pdf` | Full project proposal — domain, problem statement, technical fit, phase mapping, and success criteria |
| `CLAUDE.md` | Build rules: stack, hard rules, data model, agent contracts |
| `docs/DECISIONS.md` | **Every technical decision and why.** Read this first. |
| `docs/decisions/` | ADRs — numbered, one per load-bearing decision |
| `docs/START-HERE.md` | Setup, prerequisites, and the build loop |
| `docs/PROMPTS.md` | The ordered build steps |
| `docs/SETUP.md` | Claude Code tooling: skills, MCP servers, hooks, subagents |
| `docs/eval.md` | Model accuracy log — updated on every prompt or model change |
| `docs/architecture-phase1.md` | What runs, what talks to what, and both pipelines. Diagrams generated from the graph definitions. |
| `api/` | FastAPI service — stateless, owns the schema and the migrations |
| `worker/` | arq worker — the `pydantic-graph` pipelines and the four agents |
| `web/` | Next.js app — Inbox, Content, Agents |
| `data/` | Synthetic seed data, the two comment dumps, and the 50-comment eval set |
| `scripts/` | `demo.sh`, `measure.py` (replay timings), `gen_diagrams.py` |
| `infra/` | Empty in Phase 1 — Terraform lands with the AWS phases |
| `LICENSE` | MIT License |

## Run it

**Before your first run:** cap Docker Desktop's memory (Settings → Resources → **at least 4 GB**)
and set `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=30m` on the host shell. Two models stay
resident; without the cap Ollama tries to hold three and evicts mid-replay. See
[D19](docs/DECISIONS.md).

**Give Docker Desktop at least 32 GB of virtual disk** (Settings → Resources → Virtual disk limit).
The default 8 GB is not enough: images and build cache alone take ~4 GB, and every `make reset`
orphans ~2 GB more, because `make up` rebuilds. When the volume fills, Postgres hits
`PANIC: could not write to file` and refuses to restart — and the API's own healthcheck will still
say it is fine unless you are on a build with `/health/ready`. Run `make prune` to reclaim, and
check before any long run.

```bash
cp .env.example .env
make models      # pull qwen3.5:2b and qwen3.5:9b (~9.3 GB) — one time
make up          # build and start postgres, redis, api, worker, web
make migrate     # create the ten tables
make seed        # 2 brands, 6 accounts, 20 posts — re-runnable
```

Verify it:

```bash
docker compose ps                          # five containers, all five (healthy)
curl -s localhost:8000/health/ready        # {"status":"ok","database":true,"redis":true}
```

Use **`/health/ready`**, not `/health`. Liveness answers "is the process up" and touches nothing —
it stays green in front of a stopped Postgres, which is exactly how a full disk once presented as
four healthy services and every endpoint returning 500 ([D28](docs/DECISIONS.md)). Readiness pings
Postgres and Redis and returns 503 naming whichever is down.

`GET /docs` lists every endpoint. Every **list** endpoint requires a `brand_id`
query parameter — the API is stateless, so scope lives in the URL and a shared
link resolves to the same view. Three do not, and are not meant to: `/brands`,
which is the list you pick a brand from, and `/queue/stats` and `/failed_jobs`,
which are operational and have no brand to scope by.

Or run the whole demo path in one command:

```bash
make demo    # preflight, reset, seed, upload one photo, replay 300, print URLs
```

`make demo` **deletes the database volume**. Use `make demo --keep` to leave existing data alone.

Day-to-day:

```bash
make test      # pytest in the api and worker containers
make lint      # ruff + mypy (python), eslint (web)
make logs      # follow api and worker
make measure   # time a 300-comment replay, print the numbers below
make diagrams  # re-render the pipeline diagrams from the graph definitions
make prune     # reclaim Docker disk (dangling images + build cache only)
make down      # stop everything, keep the data
```

How it fits together — containers, both pipelines, the failure path, and what
Phase 2+ actually changes — is in
[docs/architecture-phase1.md](docs/architecture-phase1.md). The two pipeline
diagrams there are generated from the `pydantic-graph` definitions, not drawn.

### Open it

Three pages, all scoped by `brand_id` in the URL ([D17](docs/DECISIONS.md)). Landing on
`localhost:3000` redirects to the Inbox and picks a brand for you; the top bar has a selector.

| Page | What is on it |
| --- | --- |
| [`/inbox?brand_id=1`](http://localhost:3000/inbox?brand_id=1) | Comments with category, sentiment, urgency and the drafted reply. Hover a row for Approve / Edit / Reject, or tick several and use **Approve selected**. |
| [`/content?brand_id=1`](http://localhost:3000/content?brand_id=1) | Drop a photo in. One card per asset: the image, what the vision agent saw, the brand check, and three platform captions side by side. |
| [`/agents?brand_id=1`](http://localhost:3000/agents?brand_id=1) | Every model call — tokens, cost, p50/p95 — plus per-agent totals and the Failed Jobs panel. Click any entity link to see one comment end to end. |
| [`localhost:8000/docs`](http://localhost:8000/docs) | OpenAPI for every endpoint. |

Which brand is which id depends on seed order, so look it up rather than guessing:

```bash
curl -s localhost:8000/brands | jq -r '.[] | "\(.id)\t\(.name)"'
```

### Feed it new comments

`make replay` is **idempotent** ([D9](docs/DECISIONS.md)) — that is the point, so a repeated
2,000-comment dump costs nothing. It also means running it twice inserts nothing the second time
and you will see `{"inserted":0,"skipped":300}`. To see work happen, give it rows it has not seen.

**Write your own.** The most direct way to watch the pipeline think:

```bash
curl -X POST http://localhost:8000/ingest/comments \
  -H "Content-Type: application/json" \
  -d '[{
    "external_id": "test-001",
    "post_external_id": "post-0-0",
    "account_handle": "@ridgelineroasters",
    "author": "@you",
    "text": "Do you ship to Singapore, and how fresh are the beans on arrival?",
    "created_at": "2026-09-09T21:00:00+00:00"
  }]'
```

Returns `{"inserted":1,"skipped":0,"enqueued":1,"rejected":0}` at once; the agents finish in
15–30 s. `external_id` must be new — reusing one is a deliberate no-op. `account_handle` and
`post_external_id` must match seeded rows or the row is counted as `skipped`, which is a data
problem rather than a transient one, so it is counted rather than retried:

| Brand | `account_handle` | `post_external_id` |
| --- | --- | --- |
| Ridgeline Roasters (coffee) | `@ridgelineroasters` | `post-0-0` |
| Fieldnote Skin (skincare) | `@fieldnoteskin` | `post-1-0` |

Keep the comment on-topic for its brand. A coffee question posted under a skincare post once drew
the reply *"we do not carry coffee, only skincare formulations"* — the model being right about data
that was wrong.

**Feed more of the pre-generated dump.** `viral_post_dump.json` holds 2,000 rows and `make replay`
only uses the 300 in `comments_small.json`, so there is plenty left:

```bash
python3 -c "
import json,urllib.request
rows=json.load(open('data/viral_post_dump.json'))[100:150]
r=urllib.request.Request('http://localhost:8000/ingest/comments',
  data=json.dumps(rows).encode(),headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(r).read().decode())"
```

Change the slice to taste. At ~10 s per comment, 50 rows is roughly 8 minutes.

**CSV works too** — same six columns:

```bash
curl -X POST -H "Content-Type: text/csv" \
     --data-binary @mine.csv http://localhost:8000/ingest/comments
```

#### Where a new comment goes

| When | State | Where you can see it |
| --- | --- | --- |
| immediately | `comments` row, `status: new` | **All** tab only — no draft yet |
| ~5 s | triaged; category, sentiment, urgency set | **All** tab, badges filled, *"Waiting for the agent"* |
| ~15–30 s | `reply_drafts` row, `status: pending` | **Needs review** tab, top of the list |
| you approve | `outbox` row written | badge flips to `approved` |
| ≤30 s later | worker drains the outbox | badge flips to `published`, moves to **Published** |

The Inbox opens on **Needs review**, which filters `status = drafted`. For the first ~15 seconds a
new comment is not in that view — it is not lost, it is still being processed. Switch to **All** to
watch it move, or watch the `queued` / `running` counters in the top bar.

The Inbox sorts newest-first by the comment's own `created_at`, so anything you write with a recent
date lands at the top, above the seeded data (dated from 2026-08-01).

### Feed it a photo

```bash
BRAND=$(curl -s localhost:8000/brands | jq -r '.[0].id')
curl -sf -F "file=@data/sample_images/ridgeline_beans_flatlay.png" \
     "http://localhost:8000/assets?brand_id=$BRAND" | jq .
```

Or drag one onto the Content page. Returns `enqueued: true` at once; the worker then runs `media`
and `content` against `qwen3.5:9b` and writes three `content_drafts`. Roughly 15–35 s on a warm
model — the first upload after an idle gap also pays for a 6.6 GB model load. PNG, JPEG and WebP,
up to 10 MB.

The images in `data/sample_images/` are Pillow-drawn shapes, not photographs (synthetic data only).
The vision agent describes them accurately, which means the brand check usually fails on "logo
visible" — that is the agent working, not a bug. Drop in a real product photo for a better demo.

### Things worth trying deliberately

- **Spam.** Post `"check out my page, free followers"`. Triage should return `needs_reply: false`
  and the drafting call is **skipped entirely** — that branch is an `if`, not a model decision
  ([D12](docs/DECISIONS.md)). The Agents page will show one triage run for it and no response run.
- **Sarcasm.** *"Great, another price rise. Love that."* This is where a 2B classifier is weakest;
  `docs/eval.md` has the measured accuracy.
- **A refund demand.** Should come back `complaint / hostile / high`.
- **Batch approval.** Tick ten rows and use Approve selected, then watch them flip to `published`
  within 30 s as the outbox drains — that is the loop closing ([D3](docs/DECISIONS.md)).
- **Cost per comment.** On the Agents page, click a `comment 123` link to see every model call that
  one comment caused, which is what [D7](docs/DECISIONS.md) restructured the audit table to answer.
- **A hallucination.** Ask something the brand never told it — *"how fresh are the beans?"* drew
  *"within a week of roasting"*, a fact nobody supplied. The prompt forbids inventing facts and the
  model still did. This is what the human-approval gate is for.
- **The dead-letter queue.** Post a row with `"created_at": "not-a-date"`. That row alone is
  rejected and appears in the Failed Jobs panel with the reason; every other row in the same
  payload still processes ([D27](docs/DECISIONS.md)). The panel offers **Discard** rather than
  Retry for it, because re-running a malformed row cannot succeed ([D30](docs/DECISIONS.md)).

### Where the data comes from

All synthetic. No social platform is contacted anywhere in Phase 1.

| File | What it is |
| --- | --- |
| `data/comments_small.json` | 300 comments — the `make replay` demo path |
| `data/viral_post_dump.json` | 2,000 comments for `make replay-full`, including one deliberately malformed row |
| `data/eval.json` | 50 of them **hand-labelled** with the correct category, sentiment and `needs_reply` — the only evidence the 2B triage model is good enough |
| `data/sample_images/` | 5 Pillow-drawn PNGs |

The JSON is generated once by `data/generate_comments.py` and committed; the same seed reproduces it
byte-identically, so an `external_id` already ingested never changes meaning. Comment text is
hand-written templates rather than Faker prose — triage has to classify these, and lorem has no
category signal, so a model would be graded on noise. Faker supplies only what should genuinely
vary: names, handles, dates, order numbers. The mix targets ~40% question, 25% praise, 20%
complaint, 10% spam, 5% other.

`make seed` creates the brands, accounts and posts those comments attach to. It is re-runnable.

### Stop and restart

```bash
make down             # stop, keep the data
docker compose stop   # pause without removing containers — fastest restart
make up               # start again; data is still there
```

Closing the browser does nothing to the stack — the containers are detached and the worker keeps
draining. Ollama runs on the **host**, so `make down` does not stop it; quit it separately to
unload the ~9 GB of models.

`docker compose down -v` deletes the database volume. That is the only command here that loses data.

### If something looks wrong

```bash
docker compose ps                      # all five should say (healthy)
curl -s localhost:8000/health/ready    # names the dependency that is down
make logs                              # follow api + worker, structured JSON
docker compose logs postgres           # check here first if every endpoint 500s
make prune                             # reclaim Docker disk
```

Every log line carries a `request_id` (API) or `job_id` (worker), so one comment can be traced from
the HTTP request through to the model calls it caused.

A stuck comment — `status: new` long after ingest — usually means its job was lost. `POST
/queue/requeue` re-enqueues every comment still at `new` and every asset with no analysis:

```bash
curl -X POST localhost:8000/queue/requeue
```

### Measured

Real numbers from `make measure`, on one 16 GB Apple Silicon laptop with Ollama
on the host. These replace the estimates the success criteria used to carry.

#### replay (300 comments) — 2026-09-09

- **52.3 min** wall time, first to last recorded run
- **485** agent runs, **337,278** tokens (323,176 in / 14,102 out)
- **10.5 s per comment** end to end
- 0 dead-lettered, 0 errors

| Agent | Runs | Tokens in | Tokens out | p50 | p95 |
|---|---:|---:|---:|---:|---:|
| triage | 301 | 207,277 | 6,468 | 4,240 ms | 14,295 ms |
| response | 184 | 115,899 | 7,634 | 11,875 ms | 28,849 ms |

Cost is `$0.00` throughout: Ollama runs on hardware we already own, which is a
different fact from "we could not price it" ([D15]).

Read these as a **conservative** upper bound. The machine was compiling, linting
and running the test suite throughout — triage p50 measured 4.2 s here against
the ~850 ms [D23] recorded for an unloaded call, and 184 response calls on a
9B model is where the wall time actually goes. `replay-full` is 2,000 comments;
at this rate expect **5–6 hours**, not the "~1h+" the Makefile used to claim.
Run it with `make measure-full`, after raising the Docker disk limit.

#### What the replay found

Two things, which is what a load replay is for:

- **301 triage runs for 300 comments.** One comment was processed twice, and it
  produced a second reply draft — at which point `GET /comments/{id}` returned
  **500**, because it reads the draft with `scalar_one_or_none()`. The
  orchestrator's idempotency guard was check-then-act, so two overlapping
  attempts could both read `new`. `Ingest` now takes a row lock on the comment,
  and `reply_drafts` has `UNIQUE(comment_id)` as a backstop. Both are tested,
  including that the second attempt does not re-spend the model calls.
- **Ingest rejected the whole batch on one bad row** ([D27]). `replay-full`
  returned 422 and inserted nothing at all, which would have made the unattended
  run pointless.

[D27]: docs/DECISIONS.md

### Switching LLM provider

Nothing in `worker/agents/` names a model. Agents declare a **tier**, and
`worker/config.py` is the only place a tier becomes a model name ([D6]) — which
is what makes [ADR-0002]'s claim that Phase 4 is an env change something you can
check rather than something you have to believe.

**Ollama (Phase 1, the default).** Two models cover three tiers, because
`qwen3.5:9b` is multimodal ([D20]):

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL_FAST=qwen3.5:2b       # triage
LLM_MODEL_TEXT=qwen3.5:9b       # response, content
LLM_MODEL_VISION=qwen3.5:9b     # media — same weights as TEXT
```

**Bedrock (Phase 4).** The same three tiers, pointed at three different models:

```env
LLM_PROVIDER=bedrock
LLM_MODEL_FAST=anthropic.claude-haiku-4-5-20251001-v1:0
LLM_MODEL_TEXT=anthropic.claude-sonnet-5-v1:0
LLM_MODEL_VISION=anthropic.claude-sonnet-5-v1:0
AWS_REGION=us-east-1            # credentials via the usual AWS chain
```

`LLM_PROVIDER` is validated against an allowlist ([D21]), so a typo fails at
container start naming the field rather than an hour into a replay.

What actually has to change in the code is **one `case` in
`worker/llm.py::_build_model`** — it currently raises `NotImplementedError` for
`bedrock`, deliberately, so the gap is visible rather than implied. No agent,
no prompt, and no orchestrator node changes. Two things follow from that being
the only edit:

- `reasoning_effort: "none"` is gated on the provider ([D23]). It is an Ollama
  workaround for Qwen returning empty messages, not a policy — Bedrock decides
  thinking per model.
- Cost stops being zero. `cost_usd` is `0` for Ollama because we own the
  hardware, the priced value when `genai-prices` knows the model, and `NULL`
  when it cannot be priced ([D15]). The Agents page renders that third state as
  an em dash, never `$0.00`.

**Then run the eval.** `make eval` scores the 50 hand-labelled comments in
`data/eval.json` and appends a row to [docs/eval.md](docs/eval.md). Swapping
provider without it is a claim; with it, it is a measurement — which is the
reason the harness exists ([D5]).

[D5]: docs/DECISIONS.md
[D6]: docs/DECISIONS.md
[D15]: docs/DECISIONS.md
[D20]: docs/DECISIONS.md
[D21]: docs/DECISIONS.md
[D23]: docs/DECISIONS.md
[ADR-0002]: docs/decisions/0002-llm-access-via-pydantic-ai.md

### Ports and services

| Service | Port | Notes |
| --- | --- | --- |
| `web` | 3000 | Next.js 15 App Router, Tailwind v4, shadcn/ui |
| `api` | 8000 | FastAPI, stateless; `/health` and `/docs` |
| `postgres` | 5432 | Postgres 16 |
| `redis` | 6379 | Redis 7, arq queue |
| `worker` | — | arq worker; no published port |

Ollama runs on the **host**, not in Compose — the containers reach it at
`host.docker.internal:11434`.

## License

Released under the [MIT License](LICENSE).
