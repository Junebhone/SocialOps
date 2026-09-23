# ADR-0006: Terraform layout, environments and CI for AWS (Module 3)

Date: 2026-09-23
Status: accepted

## Context
Module 3 asks for the whole AWS target architecture as Terraform, two
environments as workspaces with remote state and locking, a CI pipeline that
posts `terraform plan` on every pull request, and pinned versions with a
documented apply order. The app it deploys is the Phase 1 compose stack,
unchanged ([D2](../DECISIONS.md)). Applying is optional, so the design has to
be verifiable without an AWS bill, and mostly without an AWS account.

## Decision

**Two roots.** `infra/bootstrap` holds what exists once per account: the state
bucket, the lock table, ECR, and the CI roles. It keeps local state, because
it creates the bucket. `infra/stack` holds one full environment and composes
ten local modules.

**Workspaces select the state and tfvars select the values.** A guard ties the
two together. `terraform.workspace` must equal `var.environment`, checked as a
precondition on the first data source, so a mismatched pair stops before
anything is read. The `default` workspace is refused.

**Plan in CI, apply by hand.** GitHub Actions authenticates with OIDC. The
plan role is read-only apart from the lock files, and the push role can only
push to ECR from `main`. No workflow can apply.

**Promote an image, never rebuild it.** CI pushes each merge to `main` once,
tagged with the full commit SHA, into immutable ECR repositories. An
environment deploys a build when a pull request changes `image_tag` in its
tfvars.

**Verify without AWS.** `terraform test` plans every module and both
environments against a mocked provider. That plan, together with `fmt`,
`validate` and `tflint` checking each environment's tfvars, is
`scripts/tf-check.sh`, which both `make tf-check` and CI run.

Smaller choices, each explained next to the code:

- Locking uses both `use_lockfile` and the DynamoDB table. The brief names the
  table; Terraform 1.16 deprecates it (`infra/stack/backend.tf`).
- `DATABASE_URL` is one Secrets Manager secret holding the full URL, so
  `config.py` is unchanged (`modules/database`).
- ALB and container health checks use `/health`, not `/health/ready`. ECS
  replaces tasks that fail them, which would turn a database blip into the
  restart loop [D28](../DECISIONS.md) warns about (`modules/alb`).
- The browser calls the API directly, so the ALB has a second listener on
  port 8000 rather than path routing the API's routes do not support
  (`modules/alb`).
- The web task runs `next build` at start, because `NEXT_PUBLIC_API_URL` is
  inlined at build time (`modules/ecs`).

## Alternatives considered
- **A directory per environment (or Terragrunt).** This is more robust to a
  wrong `-var-file` than workspaces. The brief asks for workspaces, and the
  guard closes the one hole that workspaces leave.
- **Registry modules (terraform-aws-modules).** They would have meant less
  code, but each wraps hundreds of options, and the brief asks for modules
  written for this architecture. Local modules also mean no third-party
  module version to pin.
- **Terraform Cloud for state and plans.** It would put another account and
  service in the path. The brief names an S3 backend.
- **Applying from CI on merge.** That needs a role that can change everything,
  triggered by any merge, for an environment nobody asked to have running.
  Plans are the deliverable, and applying stays deliberate.
- **GHCR instead of ECR.** It would need no AWS setup, but ECS would pull
  across the internet with separate credentials. ECR sits beside the
  execution role that already exists.
- **Access keys in GitHub secrets.** These are long-lived and must be
  rotated. OIDC issues one-hour credentials scoped to the repo and trigger.

## Consequences
- **The deliverable costs nothing.** `terraform plan`, `make tf-check` and CI
  are free. Bootstrap costs cents. An applied dev is about $5 a day and
  staging about $12 (`infra/README.md`).
- **Applying today proves infrastructure, not a running app.** `S3Storage`,
  the Bedrock `case` in `worker/llm.py`, and an SQS consumer are app changes
  for later modules. Until they land, the tasks fail config validation at
  start, loudly and on purpose.
- **Promoting to staging is a one-line PR with a plan comment.** This is
  also the seam a later module automates.
- **CI's plan jobs need a one-time human step.** Someone applies bootstrap and
  runs `make tf-plan` once per environment to create the workspaces. Until
  then they report "skipped" rather than failing.
- **The database password is in Terraform state.** The state bucket is
  encrypted, private and TLS-only. Write-only arguments are the upgrade.
