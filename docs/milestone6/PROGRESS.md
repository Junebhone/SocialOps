# Milestone 6 progress (Members 3, 4, 5 — TAN)

Branch `m6/tan-obs`, stacked on `feat/m6-logging-metric` (Member 2), which is stacked on Member 1's platform branch.

## Findings (2026-11-08, via CloudShell, acct 518668548718)
- api/web/worker each 1/1 on task definition `:1`; circuit breaker enabled with rollback.
- Log groups: `/ecs/socialops-dev/{api,web,worker,migrate}`.
- ALB `socialops-dev`; target groups `socialops-dev-api`, `socialops-dev-web`; RDS `socialops-dev` (PubliclyAccessible=False).
- No SNS topics, alarms or dashboards exist yet. OIDC provider and roles `socialops-ci-plan`, `socialops-ci-ecr-push` exist. `SocialOps-Budget` exists.
- API `/health/ready` -> ok (db, redis true). Web returns 307 (redirect): pipeline health check must follow redirects (`curl -L`).
- **us-east-2: RDS `socialops-db` is `available` (running, costing money).** Reported to TAN; not touched.
- `ignore_changes = [task_definition]` is on Member 1's branch (ecs/main.tf).
- Terraform pin is `~> 1.16.0`; validated with 1.16.7.

## Trap to resolve
Member 2's `enable_error_route` is a Terraform variable (task env var). With ignore_changes on task_definition it will not reach running tasks. Proposal: SSM parameter read at request time (option a). Needs Member 2 / TAN decision.

## Done (Member 3 code, not applied)
- `infra/modules/observability/alarms.tf`: SNS topic `socialops-dev-alerts`, email subscription, alarm `socialops-dev-api-5xx` (Sum, 60 s, >=1, notBreaching, alarm+ok actions).
- `infra/modules/observability/dashboard.tf`: dashboard `socialops-dev` (5xx + alarm annotation, ALB, ECS CPU/memory x3, TargetResponseTime, RDS CPU).
- Wired in `infra/stack/main.tf`; `alert_email` variable (no default; tfvars, uncommitted).
- `terraform validate` ok; `terraform test -var-file=env/dev.tfvars`: 5 passed.

## Open
- Team email for SNS. Apply (TAN's OK). SNS confirmation click. Live 5xx/alarm/email verification and timing.
- Member 4 deploy role + workflow; Member 5 docs.
