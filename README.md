# SocialOps

**A multi-agent social media command center for small and mid-size businesses — built as a monolith, then migrated to AWS in six phases.**

SocialOps gives a marketing manager one dashboard where incoming comments, mentions, and uploaded assets are handled by a team of specialist AI agents, with a human approving anything before it publishes.

> **Status: pre-implementation.** This repository currently holds the project proposal and license. Phase 1 (the working local app) has not been committed yet. See [Roadmap](#roadmap) for what is coming.

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
| **Analytics** | Summarizes performance across accounts |

A human reviews and approves agent output before anything is published.

---

## Architecture

The application is **deliberately built as a stateful monolith first**, then migrated step by step so that each cloud concept — compute, containers, managed data services, decoupled messaging, orchestration, observability, automation — is exercised against a real workload rather than a toy example.

### Tech stack

| Layer | Technology |
| --- | --- |
| Front end | React / Next.js dashboard — container → S3 + CloudFront |
| Application | FastAPI (Python) REST API, containerized |
| Agent workers | Separate containers behind SQS, autoscaled on queue depth |
| Relational data | PostgreSQL — local → Amazon RDS (Multi-AZ) |
| Object storage | Local disk → EBS → Amazon S3 with lifecycle policies |
| Messaging | Amazon SQS (with dead-letter queue) |
| Cache / agent state | Amazon ElastiCache (Redis) |
| AI | Amazon Bedrock (vision + text), Amazon Rekognition |
| Orchestration | AWS Step Functions |
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
| **1. Working local app** | Monolithic FastAPI + React app, local Postgres, local file storage, agents running in-process via Docker Compose | Baseline architecture, local dev parity |
| **2. Platform setup & lift-and-shift** | AWS account, IAM roles, VPC with public/private subnets, security groups; deploy the monolith as-is to an EC2 instance with Postgres and files on the same box | IaaS, networking, IAM, least privilege |
| **3. Containerize & deploy** | Dockerize API, front end, and agent workers; push to ECR; run on ECS (Fargate) behind an Application Load Balancer | Containers, image registry, managed container runtime, load balancing |
| **4. Decouple state** | Postgres → RDS, files → S3, agent state and sessions → ElastiCache, work items → SQS; app containers become stateless | Managed data services, object storage, caching, message queues, stateless design |
| **5. Orchestrate & expose** | Split into services (API, orchestrator, triage workers, media workers); autoscale on SQS queue depth; expose via API Gateway + ALB with HTTPS, Route 53, and WAF; agent hand-offs coordinated by Step Functions | Service decomposition, autoscaling, API management, edge security, workflow orchestration |
| **6. Observe & automate** | CloudWatch dashboards, alarms, and structured logging; X-Ray tracing across agents; Terraform for all infrastructure; GitHub Actions CI/CD; k6 load tests; cost dashboard | Observability, IaC, CI/CD, load testing, FinOps |

---

## Target user

A marketing manager at a small business, or a boutique agency account manager running 3–5 client brand accounts. Not a developer — they live in a dashboard, review agent output, and approve work.

## Desired outcomes

Once fully deployed, SocialOps should absorb engagement spikes with no human intervention, cut time-to-first-response on customer comments from hours to minutes, and let one marketing manager run multiple accounts with agents doing the first pass.

Architecturally, the system should be:

- fully stateless at the compute layer,
- scaled out and in automatically on queue depth,
- able to survive an AZ failure, and
- redeployable from scratch through IaC and CI/CD.

## Definition of success

**Technical**

- The same application runs correctly at every phase of the flow.
- After Phase 4, the app containers hold no state.
- Replaying a 2,000-comment viral-post dump triggers visible worker scale-out; the queue drains within a target window, with failures landing in the DLQ.
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
| `LICENSE` | MIT License |

## License

Released under the [MIT License](LICENSE).
