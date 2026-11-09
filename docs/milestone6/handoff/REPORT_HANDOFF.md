# Handoff: the one-page written analysis (Milestone 6)

Give this file to Claude and ask: **"Write the one-page Milestone 6 analysis as a PDF from this brief."**

## The assignment (verbatim requirement)

Written analysis, **1 page**. Explain:
1. What your logs and dashboard monitor, and how your metric counts HTTP 5xx errors.
2. What triggers your alert and where the notification is delivered.
3. Which resources Terraform manages and any exceptions.
4. How your pipeline deploys changes, checks application health, and automatically rolls back a failed deployment.

Worth 8 of 50 points. Graded on whether the four topics are clearly explained.

## Output requirements

- **Exactly one page**, US Letter, PDF. Verify the page count before finishing.
- Title line, then **four short sections** with these exact headings: **Monitoring**, **Alert conditions**, **Terraform coverage**, **Deploy and rollback**.
- Body about 9.5 to 10 pt, readable. Inline code (`like this`) for names, patterns and metric names.
- Plain prose, no bullets needed. No screenshots (they go in the artifacts). No secrets, no email addresses, no account IDs.
- Use only the facts below. Do not invent numbers. A working draft already exists at `docs/milestone6/Milestone6_Analysis.md`
  (with a generator `build_analysis_pdf.py`); improve wording if useful, keep the facts.

## Facts to use

### 1. Monitoring
- The API (FastAPI, structlog) writes **one JSON log line per request**: `request_id`, `method`, `path`, `status_code`, `duration_ms`, `level`, `timestamp`. ECS ships stdout to CloudWatch Logs group `/ecs/socialops-dev/api`.
- A **metric filter** with pattern `{ $.status_code >= 500 }` adds **1** to custom metric `Api5xxCount` (namespace `SocialOps/dev`, unit Count) for every matching line.
- An **unhandled exception** is logged as `request.failed` with `status_code=500`, so crashes are counted too, each request once. Health checks and other lines never match. No matching line means no data point.
- Dashboard `socialops-dev` shows: API 5xx per 60 s with the alarm threshold line, ALB `RequestCount`, `HTTPCode_Target_5XX_Count` and `HTTPCode_ELB_5XX_Count`, API `TargetResponseTime`, ECS CPU and memory for api, web and worker, RDS CPU, and the alarm state.
- Controlled test: `GET /debug/error` (a deliberate 500, switched on only for the demo) at 2026-11-08 23:52:15 UTC, request id `25af8b47971440e3b4dfafd12437869e`, found by request id as exactly one JSON line; `Api5xxCount` = 1 in the 23:52 UTC minute.

### 2. Alert conditions
- Alarm `socialops-dev-api-5xx`: **Sum of `Api5xxCount` ≥ 1 within one 60-second period**, 1 of 1 datapoints, **missing data treated as not breaching** (a quiet minute publishes no data point, so silence means healthy).
- Both the **ALARM** and the return-to-**OK** transitions publish to SNS topic `socialops-dev-alerts`, which **emails the team**. The email subscription is confirmed once by a person.
- Observed: the alarm email arrived about a minute after the controlled request (inbox 17:53 local = 23:53 UTC). A separate burst took the alarm to ALARM at 00:10:04 UTC and back to OK at 00:16:04 UTC; an email was sent for each.

### 3. Terraform coverage
- Terraform (workspace `dev`, remote state in S3 with locking) manages: VPC and networking, security groups, ALB with HTTPS and ACM certificate, Route 53 records, ECS cluster and the `api`, `web`, `worker` services and task definitions, RDS Postgres (private), ElastiCache Redis, S3 assets bucket, SQS queue, IAM roles, ECR repositories, log groups, the metric filter, alarm, SNS topic and subscription, the dashboard, and the SSM parameter that switches the error route.
- **Exceptions, with reasons:** the state bucket and lock table plus the CI/OIDC roles live in a separate **bootstrap** stack (needed before Terraform can run); the Route 53 hosted zone (the registrar's nameservers depend on it); the budget `SocialOps-Budget` (a cost guard kept outside the stack it protects); Bedrock model access (granted in the console); the one-time click that confirms the SNS email subscription; leftover **Milestone 5** resources in us-east-2.
- The ECS services use `ignore_changes = [task_definition]` and the SSM parameter uses `ignore_changes = [value]`, so pipeline deploys and the demo switch are not reported as drift.
- **Live `terraform plan` with refresh on, run after three pipeline deploys: "No changes. Your infrastructure matches the configuration."**

### 4. Deploy and rollback
- Deployment branch: **`main`**. Every push runs lint and tests, builds the three images tagged with the commit SHA, then the **deploy** job.
- The deploy job assumes a **main-only OIDC role with least privilege (no stored AWS keys)**, then: records the running task-definition revisions (the rollback target); registers new revisions that change only the image tag; runs the database migration as a one-off ECS task and stops before touching any service if it fails; updates the three services and waits for stability; then **health-checks** `https://api.socialops.website/health/ready` (must return `"status":"ok"`) and the web URL (200) up to 10 times 15 s apart, and confirms every running task is on the new revision.
- If any check fails the job **restores the recorded revisions, waits for stability, re-runs the health check to prove the old version is serving, and fails the run** so it shows red.
- **How this differs from the ECS circuit breaker:** the circuit breaker only rolls back tasks that never start or never pass their container health check. It cannot see a deployment that starts, stays up and is broken (for example `/health/ready` returning 503). The pipeline's health check and rollback catch that case.
- Proof: good run 42529005106 (commit `9f643ee`, about 7.5 min); failed deploy 42535888765 (commit `1e89ac9`): readiness returned 503 on all 10 tries, the job restored `api:3`, `worker:3`, `web:2`, re-verified `{"status":"ok","database":true,"redis":true}` and went red; revert run 42537260649 (commit `5594ccb`) green.
- Security and cost controls stayed in place: private RDS, S3 public access blocked and access through IAM roles, secrets in Secrets Manager, budget alert, no state files or credentials in git.

## Checklist before returning the PDF
- [ ] One page. [ ] Four sections with the exact headings. [ ] All numbers match this file. [ ] No emails, secrets or account IDs.
