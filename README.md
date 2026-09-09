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
| `LICENSE` | MIT License |

## Run it

**Before your first run:** cap Docker Desktop's memory (Settings → Resources → **at least 4 GB**)
and set `OLLAMA_MAX_LOADED_MODELS=2` and `OLLAMA_KEEP_ALIVE=30m` on the host shell. Two models stay
resident; without the cap Ollama tries to hold three and evicts mid-replay. See
[D19](docs/DECISIONS.md).

**Give Docker Desktop at least 32 GB of virtual disk** (Settings → Resources → Virtual disk limit),
and check it with `docker system df` before a long run. The default 8 GB is not enough: images and
build cache alone take ~4 GB, and Postgres will `PANIC: could not write to file` and refuse to
restart when the volume fills. `docker builder prune -af` reclaims the most, quickest.

```bash
cp .env.example .env
make models      # pull qwen3.5:2b and qwen3.5:9b (~9.3 GB) — one time
make up          # build and start postgres, redis, api, worker, web
make migrate     # create the ten tables
make seed        # 2 brands, 6 accounts, 20 posts — re-runnable
```

Verify it:

```bash
docker compose ps                      # five containers, postgres/redis/api healthy
open http://localhost:8000/health      # {"status":"ok", ...}
open http://localhost:8000/docs        # OpenAPI
open http://localhost:3000/inbox       # comments, drafts, approvals
open http://localhost:3000/content     # uploads, analysis, platform drafts
```

`/health` answers "is the process up" and deliberately does not touch the database, so a healthy
API can still be sitting on a stopped Postgres. If every endpoint 500s while `docker compose ps`
looks fine, check `docker compose logs postgres` first.

`GET /docs` lists every endpoint. All of them except `/brands` require a
`brand_id` query parameter — the API is stateless, so scope lives in the URL and
a shared link resolves to the same view.

Drive the two pipelines:

```bash
make replay      # 300 comments -> triage -> response -> drafts in the Inbox
make eval        # triage accuracy over the 50 labeled comments

# Upload one product photo: media analysis + three platform drafts.
curl -F "file=@data/sample_images/ridgeline_beans_flatlay.png" \
     "http://localhost:8000/assets?brand_id=2"
```

The upload returns immediately with `enqueued: true`; the worker then runs
`media` and `content` against `qwen3.5:9b` and writes three `content_drafts`.
Watch it with `make logs`. On a warm model that is roughly 15–35 s end to end —
the first upload after an idle gap pays for a 6.6 GB model load on top.

The sample images in `data/sample_images/` are Pillow-drawn shapes, not
photographs (synthetic data only). The vision agent describes them accurately,
which means the brand check usually fails on "logo visible" — that is the agent
working, not a bug.

Day-to-day:

```bash
make test    # pytest in the api and worker containers
make lint    # ruff + mypy (python), eslint (web)
make logs    # follow api and worker
make down
```

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
