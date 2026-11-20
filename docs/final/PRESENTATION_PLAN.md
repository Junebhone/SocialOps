# Final presentation: plan, script, demo, Q&A

15 minutes total, setup included. Graded: Business problem 15 · Architecture and production readiness 45 · Live demo 25 · Q&A and delivery 15.
The tone to hold the whole time: **"I migrated it, I measured it, and I know exactly what I'd change for production."**

State checked 2026-11-20: ECS `socialops-dev` (us-east-1) runs api `:11`, web `:10`, worker `:11`, all rollouts completed. RDS `socialops-dev` available.

---

## Run of show (about 12 min talk, 3 min Q&A buffer)

| Time | Segment | Rubric | Slide |
|---|---|---|---|
| 0:00–0:30 | 30 s launch video plays (made with `/brag`) | Delivery | 1 |
| 0:30–2:00 | Business problem and solution | 15 | 2 |
| 2:00–3:00 | The migration journey: laptop → VM → containers → EKS → ECS + Terraform | 45 | 3 |
| 3:00–5:00 | What runs now: architecture walk-through | 45 | 4 |
| 5:00–6:00 | Three design decisions I'd defend | 45 | 5 |
| 6:00–7:30 | Production readiness: what's built vs what I'd do at full scale | 45 | 6 |
| 7:30–11:30 | Live demo (backup video ready on slide 7) | 25 | 7 |
| 11:30–12:00 | Close: one line per pain point, solved | Delivery | 8 |
| 12:00–15:00 | Q&A | 15 | — |

The 45-point section gets ~5.5 minutes, the most of any segment. The business slide is **one slide only** (rubric says so).


### Four speakers

Names are a first guess from the repo history: swap them freely, the blocks stay the same. Each block is one continuous stretch, so there are only three handoffs plus the close.

| Speaker | Slides | Time | Length | Owns in Q&A |
|---|---|---|---|---|
| **A · Bhone** | 1 Title, 2 Business | 0:00–2:00 | 2:00 | Business case, users, cost |
| **B · Zainab** | 3 Journey, 4 Architecture | 2:00–5:00 | 3:00 | Migration, data, ECS vs EKS vs Lambda, queue |
| **C · Dan** | 5 Decisions, 6 Production readiness | 5:00–7:30 | 2:30 | AZ failure, scaling, security, DR, what we'd change |
| **D · Thanoj** | 7 Live demo (drives the laptop) | 7:30–11:30 | 4:00 | CI/CD, rollback, monitoring, alarms |
| **A · Bhone** | 8 Close, then hosts Q&A | 11:30–15:00 | 0:30 + Q&A | Routes each question to its owner |

Handoff lines (say the next person's name, it reads as a team):
- A → B: "That's the why. Zainab will show how we got it to the cloud."
- B → C: "That's what runs today. Dan, which of those choices would we defend?"
- C → D: "Enough slides. Thanoj will show it running live."
- D → A: "That's the app, the alarm and the rollback, all live. Bhone will close."

During the demo: D drives one laptop the whole time, with no mouse handoffs. A sits next to it with the backup video ready and calls the switch if Bedrock stalls. B and C stand back. In Q&A, A repeats the question, names its owner, and anyone may add one sentence after.

---

## Slide-by-slide script

### 1 · Title + launch video (0:30)
The video plays without narration. Then: "SocialOps: a multi-agent command center for small-business social media, migrated from a laptop to AWS."

### 2 · Business problem and solution (1:30), one slide
Left side: the pain on-prem. Right side: what the cloud fixes.

| On-prem pain (laptop / single VM) | Cloud answer |
|---|---|
| A viral post brings 2,000 comments in an hour; one box can't absorb it, replies take hours | Queue + workers that scale out; ALB spreads traffic over 2 AZs |
| One machine = one failure: disk, power or a reboot takes the business offline | Managed RDS with backups, Fargate replaces failed tasks, health-checked deploys |
| The models need a big GPU box sitting idle most of the day | Bedrock: pay per token, no GPU to own (Ollama locally records cost 0; cloud cost is per call in `agent_runs`) |
| Every deploy is SSH plus hand edits; no audit trail | Terraform + GitHub Actions: push → test → deploy → health check → automatic rollback |
| Nobody notices a failure until a customer does | JSON logs → 5xx metric → alarm → email in about a minute |

Say: "The user is a marketing manager running three to five brands. They don't want servers. They want every comment triaged and every reply drafted before they get to their desk, and they approve everything before it goes out."

### 3 · Migration journey (1:00)
A timeline, animated left to right, one step per milestone:
1. **Local**: Docker Compose, Postgres, Redis, Ollama on a laptop.
2. **Lift-and-shift**: one EC2 VM, everything installed natively (m7i-flex.large, Elastic IP).
3. **Containerize**: multi-stage images, ECR, multi-arch (D33, D35).
4. **Decouple state**: RDS, S3 behind the `StorageBackend` interface, Secrets Manager (D25).
5. **Orchestrate**: EKS with probes, HPA, PDBs; drain test kept the app up (337/360 OK while draining both nodes).
6. **Automate**: ECS Fargate fully in Terraform, CI/CD with rollback, CloudWatch alarms.

Say: "The code barely changed. Config only comes from environment variables, storage is one interface, the API holds no state. That's why every step was a configuration change, not a rewrite."

### 4 · Architecture now (2:00)
Diagram (build it animated: request path lights up, then the async path):
Browser → Route 53 → ALB (HTTPS, ACM cert, 80→443) → ECS Fargate `web` / `api` in private subnets across 2 AZs → RDS Postgres 16, ElastiCache Redis (arq job queue) → `worker` → Bedrock (Claude Haiku for triage, Sonnet for reply/content/vision) → S3 uploads. Side: Secrets Manager, CloudWatch Logs → metric filter → alarm → SNS email. Bottom: GitHub Actions with OIDC → ECR → ECS.

Points to land:
- **Request path vs work path**: API answers fast and enqueues; the worker does the slow LLM calls. A spike grows the queue, not the latency.
- **Orchestrator** is a typed `pydantic-graph`: comment → triage → (needs reply? response) → persist. Routing is an `if`, not a model's decision: cheap and testable.
- **Human in the loop**: nothing publishes without approval; every agent call is one `agent_runs` row with tokens, cost, latency.

### 5 · Three decisions I'd defend (1:00)
Pick three, one line each (full reasoning in `docs/DECISIONS.md`):
1. **ECS over EKS for this workload** (we ran both). EKS gave us PDBs and HPA but costs a control plane and ops time; three services don't need it.
2. **Model tiers, not model names** (D6). Agents say `fast`/`standard`/`vision`; config maps that to Ollama locally and Bedrock in AWS. Switching provider is an env var.
3. **The pipeline catches what ECS can't**. The circuit breaker only rolls back tasks that never start. Our deploy checks `/health/ready` and rolls back a deploy that starts but is unhealthy. Proven: run 42535888765.

### 6 · Production readiness (1:30), the slide that earns the most points
Two columns: **Built and proven** | **Full-scale production: what I'd do**.

Strongest line: *"Production is a tfvars file away for most of this. The modules already take these switches; dev just picks the cheapest values."*

| Area | Dev today (proven) | Production |
|---|---|---|
| Availability | 1 task per service, single-AZ RDS, 1 NAT | `desired_count ≥ 2` spread over AZs, `db_multi_az = true`, NAT per AZ (`single_nat_gateway = false`), Redis replica (all existing variables) |
| Scaling | Fixed counts on ECS (HPA proven on EKS in M5) | Target tracking on CPU for api; worker scales on **queue depth** (custom metric) |
| Data safety | 1-day backups, `disposable = true` | 7–35 day backups + PITR, `deletion_protection`, cross-region snapshot copy; RPO/RTO written down |
| Security | Private DB, OIDC (no keys), Secrets Manager, S3 public-access block | Auth (Cognito/SSO), WAF on the ALB, rate limits, ingress no longer `0.0.0.0/0`, per-brand tenancy |
| Deploys | Rolling deploy + health-check rollback | Blue/green or canary (CodeDeploy), staging workspace with manual promotion, expand/contract DB migrations |
| Observability | 5xx metric, alarm, dashboard, email | SLOs (latency p95, error budget), X-Ray tracing across agents, on-call paging, queue-age alarm, LLM cost alarm |
| LLM | Bedrock, retries 3, failed jobs table | Bedrock Guardrails, prompt eval in CI (`make eval` gate), per-brand token budgets, fallback model tier |
| Cost | ~$5/day dev, budget alert | Savings Plans, Graviton, scale workers to zero overnight, S3 lifecycle |

### 7 · Live demo (4:00), see the runbook below

### 8 · Close (0:30)
"Five pains, five answers: spikes absorbed, no single box to fail, no GPU to own, deploys that roll themselves back, failures that page us in a minute. Happy to go deeper on any of it."

---

## Demo runbook (4 minutes, all on the live HTTPS URL)

Order: business value first (what the user sees), then operations (what the interviewer grades).

1. **App** `https://app.socialops.website/inbox` (padlock visible). Inbox: comments already triaged with category, sentiment and urgency badges. Open one with a drafted reply, edit a word, approve. (40 s)
2. **Content**: upload one product photo from `data/sample_images/`. The media agent checks brand rules; the content agent writes posts for X, Instagram and LinkedIn. While it runs (Bedrock calls take seconds), go to step 3. (40 s)
3. **Agents** page: every agent call with tokens, latency, cost. "This is the audit trail and the cost dashboard in one." Back to Content: the three drafts are there. (40 s)
4. **Operations** (CloudWatch dashboard tab): 5xx count, ALB, ECS CPU/memory, RDS CPU. Trigger the controlled error (SSM switch on → one `curl` → switch off), find the JSON log line by `request_id` in Logs Insights. The alarm email lands about a minute later; come back to it at the end. (60 s)
5. **Deploy and rollback**: show the GitHub Actions run 42535888765 (red on purpose: health check failed 10/10, previous revisions restored). Do not push live: a good deploy takes ~7.5 min, a bad one ~12 min. (40 s)
6. Open the alert email that just arrived. (10 s)

Commands for step 4 are in `docs/milestone6/handoff/SOLO_RUNBOOK.md` (3:00 segment).

### Before you walk in (T-30 min)
- [ ] App, API `/health/ready` and the Agents page all load from a signed-out browser.
- [ ] Do one full rehearsal of step 2 today, so you know Bedrock still answers and how long it takes.
- [ ] `/debug/error` returns 404 (route off). Alarm is OK.
- [ ] Tabs open in order: slides, app, dashboard, Logs Insights, Actions run, mail (message body only).
- [ ] AWS console signed in, CloudShell warm. No keys, account IDs or emails on screen.
- [ ] Backup video on the laptop **and** offline (no streaming), embedded on slide 7.
- [ ] Do Not Disturb on; font size up in terminals.

### If something breaks live
Say one sentence ("Bedrock is slow right now, here's the same flow recorded this morning"), switch to the backup clip, keep going. Calm recovery scores better than a perfect demo.

### Known risk
Resolved 2026-11-20: PR #24 reverted `06abd96`, and the deploy from `main` went green. A push to `main` now deploys normally (~7.5 min). Still don't push during the presentation.

---

## Q&A bank (answer in three parts: what we did · why · what production would change)

**What happens if an AZ goes down?** Dev: RDS and NAT are single-AZ, so we'd lose the database and outbound calls. Production: Multi-AZ RDS (failover in about a minute), NAT per AZ, two or more tasks per service spread across AZs. All three are existing Terraform variables.

**How does it handle the viral spike?** Ingest is idempotent (`UNIQUE(post_id, external_id)`), the API only enqueues, workers drain the queue. Production: worker autoscaling on queue depth, a queue-age alarm, Bedrock quota raised in advance.

**Why Redis/arq and not SQS?** arq owns retries with backoff and a failed-jobs table; one durability layer, not two (D12). SQS is provisioned in Terraform; moving to it is the natural production step for durability and scale-to-zero.

**Why ECS and not EKS? You did both.** Kubernetes earned its keep for PDBs and HPA (M5 drain test). For three services, ECS has no control-plane cost and less to run. EKS makes sense with many teams or services.

**Why not Lambda?** LLM calls and image analysis can run for tens of seconds and need a long-lived queue consumer; the web app is Next.js SSR. Containers kept one image for local and cloud.

**How do you deploy without downtime, and what about DB migrations?** Rolling deploy (new tasks must pass health checks before old ones stop), migration as a one-off task that fails the pipeline before services change. Production: expand/contract migrations so old and new code both work, then blue/green.

**How did you migrate the data?** Milestone 4 migration scripts with row counts before and after (`scripts/`). The data is synthetic, so for the us-east-1 move we reseeded.

**How do you know the AI output is good?** 50 hand-labelled comments in `data/eval.json`, `make eval` scores triage. A human approves every reply. Production: run eval in CI as a gate on prompt changes.

**Security?** Private subnets for DB and tasks, Secrets Manager injected at start, OIDC for CI (no stored keys), S3 public-access block, nothing secret in git. Missing for production: user auth, WAF, IP restrictions.

**Cost?** Dev about $5/day (~$150/month, `infra/README.md`). Biggest items are NAT, ALB, RDS. Bedrock is per token and recorded per call.

**What would you do differently?** Put Terraform and CI in from day one rather than milestone 3; it would have made each move cheaper still.

**How would you know if an LLM call goes wrong at 2 a.m.?** Failed jobs land in `failed_jobs` after 3 retries; production adds an alarm on that count and on Bedrock throttling.

---

## Tooling decision
- **Build it here, in Claude Code**, not on claude.ai: the deck uses real repo facts, the evidence screenshots in `docs/milestone6/evidence/`, the live AWS state and the `/brag` video, which reads the project's code. claude.ai can see none of that.
- **frontend-slides** (HTML) for the talk itself: animations, embedded videos, one file, runs offline in a browser. Export a PDF as a fallback.
- **ppt-master** only if the professor needs a `.pptx` file submitted. Not both.
- **`/brag`**: a 30-second launch video of the web app for slide 1.
