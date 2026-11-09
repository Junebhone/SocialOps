# Handoff: the artifact pack and submission index (Milestone 6)

Give this file to Claude and ask: **"Build the Milestone 6 submission index from this brief."** The output is a clean, one to two page
**Submission Index** (PDF or Word) that the instructors can follow, plus a short **Canvas submission note** (plain text, under 120 words).

## What the assignment requires as artifacts

- Live HTTPS application URL (no login needed, so no test account).
- Repository link containing the Terraform files and the pipeline workflow file, **including the demonstrated branch and commit SHA**.
- Screenshots of the dashboard, the alert policy, and a received alert.
- The log-based metric definition showing how HTTP 5xx errors are counted.
- `terraform plan` output showing no changes.
- Pipeline logs or run links showing (a) a successful build, deploy and health check, and (b) a failed deployment or health check followed by automatic rollback and verification.
- Terraform exceptions clearly explained (in the written analysis).
- The video is uploaded to OneDrive and shared with the three instructors; the OneDrive link is submitted in Canvas. The video is **not** uploaded to Canvas.

## What to produce

A table with one row per artifact: **Artifact · Where to find it (link or path) · What it proves**. Then the Canvas note. No secrets, no email addresses, no account IDs.

Use these rows and values (all verified):

| Artifact | Where | What it proves |
|---|---|---|
| Live web app | https://app.socialops.website | HTTPS app is live |
| Live API health | https://api.socialops.website/health/ready returns `{"status":"ok","database":true,"redis":true}` | API, database and Redis healthy |
| Repository | https://github.com/Junebhone/SocialOps, deployment branch `main` | All code, Terraform and workflow |
| Terraform | `infra/stack`, `infra/modules/*` (incl. `observability`), `infra/bootstrap` | Infrastructure as code |
| Pipeline workflow | `.github/workflows/ci.yml` and `scripts/ci/deploy.sh` | Build, deploy, health check, rollback |
| Log-based metric definition | `infra/modules/observability/metric.tf` (`{ $.status_code >= 500 }` → `SocialOps/dev` `Api5xxCount`, value 1) and `docs/milestone6/evidence/metric-filter.png` | How 5xx is counted |
| Alarm and SNS definition | `infra/modules/observability/alarms.tf`, `evidence/alarm-details.png`, `alarm-actions.png`, `alarm-graph.png` | Alert policy |
| Dashboard | `infra/modules/observability/dashboard.tf`, `evidence/dashboard-top.png`, `dashboard-bottom.png` | Error counts and resource usage |
| Received alerts | `evidence/alert-email-alarm.png`, `evidence/alert-email-ok.png` | A real ALARM and OK email arrived |
| Controlled 5xx | `evidence/controlled-error-request.png`, `json-log-line.png`, `json-log-line-query.png`, `metric-rise.png`, `route-off.png` | Request id `25af8b47971440e3b4dfafd12437869e`, one JSON line, metric = 1 at 23:52 UTC, route switched off after |
| Terraform plan, no changes | `evidence/terraform-plan-after-deploy.txt`, `evidence/terraform-plan.png` | Refresh-on plan: No changes |
| Pipeline run (a): success | https://github.com/Junebhone/SocialOps/actions/runs/42529005106 · commit `9f643eee8a07ed15fe2b7777dfbccc0e1abbd933` · `evidence/pipeline-good.png` | Build, deploy, health check |
| Pipeline run (b): failed then rolled back | https://github.com/Junebhone/SocialOps/actions/runs/42535888765 · commit `1e89ac939f9d4c225611a89064ab7d4848bd9845` · `evidence/pipeline-failed-rollback.png` | Health check failed 10/10, rollback to `api:3` `worker:3` `web:2`, verified |
| Revert run (green) | https://github.com/Junebhone/SocialOps/actions/runs/42537260649 · commit `5594ccb53ec4f7cebcc26bbe0a016bbaa0c74669` · `evidence/pipeline-revert.png` | Back to normal |
| Security and cost controls | `evidence/security-checklist.md`, `rds-private-cli.png`, `rds-config.png`, `s3-public-block.png`, `git-no-secrets.png` | Controls stayed in place |
| HTTPS certificate | `evidence/acm-issued.png` | ACM wildcard certificate issued |
| Written analysis | `docs/milestone6/Milestone6_Analysis.pdf` | One-page analysis |
| Slides | `docs/milestone6/Milestone6_SocialOps.pptx` (full deck) and the 2-slide showcase | Presentation |
| Demo video | OneDrive link: **[paste after upload]** | 15-minute demo |

All `evidence/...` and `docs/...` paths are in the repository under `docs/milestone6/`.

## Rules for the output
- Replace "[paste after upload]" only with the real link; if you do not have it, leave the bracket visible.
- Keep it to two pages at most. Group rows under four headings: **Live system**, **Code and Terraform**, **Evidence**, **Deliverables**.
- Do not add claims that are not in the table.

## Canvas submission note (draft, edit lightly)
"Group 5, Milestone 6. Demo video (OneDrive, shared with the instructional team): [link]. Repository: https://github.com/Junebhone/SocialOps (deployment branch main; demonstrated commits 9f643ee good deploy, 1e89ac9 failed deploy with automatic rollback, 5594ccb revert). Live app: https://app.socialops.website. Written analysis and the evidence index are in the repository under docs/milestone6/."
