# Milestone 6 artifact pack

Status: done = verified with real output; TODO = not yet produced. Update as evidence lands.

| Artifact | Link / path | Status |
|---|---|---|
| Live HTTPS URL (web) | https://app.socialops.website (returns 307, then 200) | done (checked 2026-11-08) |
| Live HTTPS URL (API) | https://api.socialops.website/health/ready returns `{"status":"ok","database":true,"redis":true}` | done (checked 2026-11-08) |
| Repo | https://github.com/Junebhone/SocialOps, branch `main`, demonstrated commit SHA: | TODO |
| Terraform files | `infra/stack`, `infra/modules/*` (incl. `observability`), `infra/bootstrap` | done (observability in PR #13/#14, not merged) |
| Pipeline workflow file | `.github/workflows/ci.yml`, `scripts/ci/deploy.sh` (merged, PR #15) | done |
| Log-based metric definition | `infra/modules/observability/metric.tf`; filter `{ $.status_code >= 500 }` -> `SocialOps/dev` `Api5xxCount` | merged and live; TODO `aws logs describe-metric-filters` output in evidence/ |
| Dashboard definition (JSON) | `docs/milestone6/evidence/dashboard.json` (`aws cloudwatch get-dashboard --dashboard-name socialops-dev`). Dashboard is live. | TODO export |
| Alarm definition (JSON) | `docs/milestone6/evidence/alarm.json` (`aws cloudwatch describe-alarms`) | TODO |
| Dashboard screenshot | `docs/milestone6/evidence/dashboard.png` | TODO (Tan) |
| Alert policy screenshot | `docs/milestone6/evidence/alarm-policy.png` | TODO (Tan) |
| Received alert email screenshot | `docs/milestone6/evidence/alert-email.png` | TODO (Tan) |
| Controlled 5xx demo (log line by request_id, metric rise) | `docs/milestone6/evidence/` | TODO (Zainab + Tan) |
| `terraform plan` showing no changes | `docs/milestone6/evidence/terraform-plan-after-deploy.txt` (refresh on, No changes). Dan to also show it live. | done (CloudShell run) |
| Pipeline run (a): build, deploy, health check | https://github.com/Junebhone/SocialOps/actions/runs/42529005106 , SHA 9f643eee8a07ed15fe2b7777dfbccc0e1abbd933, `evidence/pipeline.md` | done |
| Pipeline run (b): failed deploy, automatic rollback, verified | https://github.com/Junebhone/SocialOps/actions/runs/42535888765 , SHA 1e89ac939f9d4c225611a89064ab7d4848bd9845, `evidence/pipeline.md` | done |
| Plan still clean after pipeline deploy | `evidence/terraform-plan-after-deploy.txt` | done |
| Written analysis (1 page) | `docs/milestone6/Milestone6_Analysis.pdf` (draft; has TODO markers) | draft |
| Slides | `docs/milestone6/Milestone6_SocialOps.pptx` (screenshot placeholders) | draft |
| Demo video (OneDrive, shared with sdesini@, krajan@, skolanu@cougarnet.uh.edu) | link: | TODO |

| Security and cost checklist | `docs/milestone6/evidence/security-checklist.md` | done |
| Third pipeline run (revert, green) | https://github.com/Junebhone/SocialOps/actions/runs/42537260649, SHA 5594ccb53ec4f7cebcc26bbe0a016bbaa0c74669 | done |
