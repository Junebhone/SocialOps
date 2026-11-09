# Brief for Claude Design: a 2-slide deck (SocialOps, Milestone 6)

Build a **two-slide** PowerPoint, 16:9. It is shown at the start or end of a 15-minute demo video, so it must read
from across a room: big type, few words, one idea per block. **Exactly two slides. No more.**

- **Slide 1:** "What we built": the system, how we watch it, how it deploys itself, with proof.
- **Slide 2:** "Who built what": the team contribution slide (5 members).

Audience: three university instructors grading a cloud computing course (EDS 6348, University of Houston, Group 5).
They want to see **observability** (logs, metric, dashboard, alert) and **automation** (Terraform, CI/CD, health check,
automatic rollback). Tone: confident, plain, factual. Do not oversell. Every number below is real and verified.

Hard rules: no secrets, no email addresses, no AWS account IDs, no access keys anywhere on a slide. Use only the facts
in this file. Do not invent metrics, names, logos or screenshots. Do not add a third slide, an agenda slide, or a
"thank you" slide.

---

## Context in one paragraph

SocialOps is a multi-agent social media command center for small businesses (Next.js web app, FastAPI API, Python
worker). It runs on AWS in us-east-1 on ECS Fargate behind an HTTPS load balancer. In Milestone 6 the team made it
**observable** (JSON logs, a log-based metric that counts HTTP 5xx, a dashboard, an email alarm) and **automated its
deployment** (everything in Terraform; a GitHub Actions pipeline that deploys on every push to `main`, health-checks the
live site, and rolls back automatically if the new version is unhealthy).

Live URLs (these can appear on the slide):
- Web app: https://app.socialops.website
- API health: https://api.socialops.website/health/ready → `{"status":"ok","database":true,"redis":true}`
- Repo: https://github.com/Junebhone/SocialOps (deployment branch: `main`)

---

## SLIDE 1: "SocialOps: observable and self-deploying"

Layout idea: a title bar, then **one clean left-to-right flow diagram across the top**, then **three columns** underneath
(Observe, Alert, Automate), then a thin **proof strip** at the bottom. Keep it airy. Icons are fine if simple.

### Title
SocialOps: observable and self-deploying
Subtitle: Milestone 6 · EDS 6348 Intro to Cloud Computing · Group 5

### Diagram (one flow, two rows)
Row 1, **deploy path**: GitHub Actions → ECR (images tagged by commit SHA) → ECS Fargate (api · web · worker) → ALB with HTTPS → Users
Row 2, **monitor path**: CloudWatch Logs (JSON, one line per request) → Metric filter `Api5xxCount` → Alarm → SNS → Team email
Connect "ECS Fargate" down to "CloudWatch Logs" with a short arrow labelled "stdout".
Small satellite chips under ECS: RDS Postgres (private) · Redis · S3 · SQS · Secrets Manager.
Everything is managed by Terraform (a thin footer label: "Terraform: dev workspace, remote state with locking").

### Column 1: OBSERVE
- One JSON log line per request (`request_id`, `status_code`, `duration_ms`)
- Metric filter `{ $.status_code >= 500 }` counts 1 per match
- Metric: `Api5xxCount` in `SocialOps/dev`
- Dashboard `socialops-dev`: 5xx with threshold line, ALB requests and 5xx, ECS CPU and memory (api, web, worker), API response time, RDS CPU, alarm state

### Column 2: ALERT
- Alarm `socialops-dev-api-5xx`: Sum ≥ 1 in 60 s, missing data = not breaching
- ALARM **and** OK both publish to SNS, which emails the team
- Verified live: a controlled 5xx (request `25af8b47…869e`) made the count 1 and the alarm email arrived about a minute later

### Column 3: AUTOMATE
- Every push to `main`: lint and test → build images → deploy → health check
- Deploy role uses OIDC: no stored AWS keys
- Health check: API `/health/ready` must say `ok`, web must return 200, running tasks must be on the new revision
- Failure → automatic rollback to the recorded revisions, verified, run goes red
- `terraform plan` (refresh on) after three deploys: **No changes**

### Proof strip (bottom, small, one line each, maybe as 3 pills)
- ✅ Good deploy: run 42529005106 · commit 9f643ee · ~7.5 min
- ⛔→↩ Failed deploy rolled back: run 42535888765 · commit 1e89ac9 · health check failed 10/10, old revision restored and re-verified
- ✅ Revert deploy: run 42537260649 · commit 5594ccb

Optional visual: a small row of 2 to 3 real screenshots (see "Images" below). If space is tight, skip images and keep the
diagram. Readability beats decoration.

One sentence worth giving prominence (pull-quote style, e.g. under the diagram):
**"The ECS circuit breaker catches tasks that never start. Our pipeline also catches a deployment that starts but is unhealthy."**

---

## SLIDE 2: "Team contributions"

Title: Team contributions
Subtitle: Five roles, one working system

Layout idea: a clean **5-row table or five horizontal cards**. Columns: **Member · Role · What they delivered · Evidence**.
Give each member one accent color. Keep each "delivered" cell to **2 to 3 short bullets**. The slide must still be readable.

| Member | Role | What they delivered | Evidence |
|---|---|---|---|
| **Member 1: Dan** | Platform and Terraform | HTTPS end to end (ACM wildcard certificate, Route 53, ALB listeners) · Terraform for the whole stack, remote state, services set to ignore pipeline task-definition changes · Live plan shows no changes | Certificate issued, ECS services running, live HTTPS app, `terraform plan`: No changes |
| **Member 2: Zainab** | Logging and error metric | JSON request logs, unhandled exceptions logged as 500 · Log-based metric `Api5xxCount` · Controlled error route, off by default · Ran the controlled 5xx test and the security checklist | Request ID, JSON log entry, metric rise, security checks |
| **Member 3: Thanoj Aila (Tan)** | Dashboard and alerting | CloudWatch dashboard (errors, CPU, memory, ALB, RDS) · Alarm (Sum ≥ 1 in 60 s) with SNS email for ALARM and OK · SSM switch so the error route flips on and off without a redeploy | Dashboard, alarm policy, received alert emails |
| **Member 4: Thanoj Aila (Tan)** | CI/CD and rollback | Deploy pipeline: build, migrate, deploy, health check, automatic rollback · Least-privilege OIDC deploy role, no stored keys · Proved a good deploy, a failed deploy that rolled back, and a revert | 3 pipeline runs with commit SHAs |
| **Member 5: Thanoj Aila (Tan)** | Analysis, slides, artifacts | One-page written analysis · Slides, recording script and artifact pack · Evidence collected and organized for submission | Analysis PDF, evidence folder |

Footer line: "Repository: github.com/Junebhone/SocialOps · deployment branch: main"

> Note for the human: the names for Members 3, 4 and 5 are set to Thanoj Aila (Tan) because that is who did the work. If the
> team prefers other names on those rows, replace only the name column. Do not change anything else.

Design note for slide 2: do not make Members 1 and 2 look smaller or less important. Equal-weight rows.

---

## Style direction

- Clean, modern, light background, one accent color plus a neutral gray. Dark text. Plenty of white space.
- Font: a clear sans-serif (Inter, Segoe UI, or Calibri). Titles 36 to 44 pt, body at least 18 pt, proof-strip at least 14 pt.
- Diagram: rounded rectangles, thin arrows, consistent spacing, two rows. Use color to separate the **deploy path**
  (one color) from the **monitor path** (another color).
- Status pills use green for success, amber for the rollback event.
- Everything must be editable PowerPoint shapes and text, not flattened images.

## Images you may use (optional, real, already in the repo)

All under `docs/milestone6/evidence/` in the repo. Best two to three for slide 1:
- `dashboard-top.png`: the dashboard with the alarm threshold line
- `alert-email-alarm.png`: a received alarm email
- `pipeline-failed-rollback.png`: the health check failing then the "Roll back" step

Do not crop out or alter content. Do not use screenshots that show personal email addresses.

## Facts cheat sheet (use these exact values)

- Region: us-east-1. Compute: ECS Fargate, services `api`, `web`, `worker`. Data: RDS Postgres (private), Redis, S3, SQS. Secrets: Secrets Manager.
- Metric: namespace `SocialOps/dev`, name `Api5xxCount`, filter `{ $.status_code >= 500 }`, value 1 per match.
- Alarm: `socialops-dev-api-5xx`, Sum, 60 s, ≥ 1, missing data not breaching, notifies via SNS topic `socialops-dev-alerts` on ALARM and OK.
- Controlled 5xx: request at 2026-11-08 23:52:15 UTC, request id `25af8b47971440e3b4dfafd12437869e`, metric = 1 at 23:52 UTC.
- Pipeline file: `.github/workflows/ci.yml`; logic in `scripts/ci/deploy.sh`.
- Runs: good 42529005106 (`9f643ee`), failed + rollback 42535888765 (`1e89ac9`), revert 42537260649 (`5594ccb`).
- Rollback restored `api:3`, `worker:3`, `web:2`; live API afterwards answered `{"status":"ok","database":true,"redis":true}`.
- Security and cost controls kept: RDS private, S3 public access blocked, access through IAM roles, secrets in Secrets Manager, budget alert `SocialOps-Budget`, no state files or secrets in git.
- Terraform exceptions (managed outside the main stack): state bucket and lock table (bootstrap), budget, Bedrock model access, the SNS email-confirmation click, leftover Milestone 5 resources in us-east-2.

## Deliverable

A `.pptx` with exactly two slides, named `Milestone6_Showcase.pptx`. After building it, check: two slides only, no text cut off,
no emails or secrets, names spelled as above, all numbers match this file.
