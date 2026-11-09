# Milestone 6 artifact pack

Status: done = verified with real output; TODO = not yet produced. Update as evidence lands.

| Artifact | Link / path | Status |
|---|---|---|
| Live HTTPS URL (web) | https://app.socialops.website (returns 307, then 200) | done; screenshot `evidence/live-app.png` |
| Live HTTPS URL (API) | https://api.socialops.website/health/ready returns `{"status":"ok","database":true,"redis":true}` | done (checked 2026-11-08) |
| Repo | https://github.com/Junebhone/SocialOps, deployment branch `main`. Demonstrated commits: good deploy `9f643eee8a07ed15fe2b7777dfbccc0e1abbd933`, failed deploy + rollback `1e89ac939f9d4c225611a89064ab7d4848bd9845`, revert `5594ccb53ec4f7cebcc26bbe0a016bbaa0c74669` | done (add the live-demo commit SHAs after recording) |
| Terraform files | `infra/stack`, `infra/modules/*` (incl. `observability`), `infra/bootstrap` | done (observability in PR #13/#14, not merged) |
| Pipeline workflow file | `.github/workflows/ci.yml`, `scripts/ci/deploy.sh` (merged, PR #15) | done |
| Log-based metric definition (screenshot `evidence/metric-filter.png`) | `infra/modules/observability/metric.tf`; filter `{ $.status_code >= 500 }` -> `SocialOps/dev` `Api5xxCount` | done; console screenshot `evidence/metric-filter.png` |
| Dashboard definition (JSON) | `docs/milestone6/evidence/dashboard.json` (`aws cloudwatch get-dashboard --dashboard-name socialops-dev`). Dashboard is live. | TODO export |
| Alarm definition (JSON) | `docs/milestone6/evidence/alarm.json` (optional; alarm is defined in `infra/modules/observability/alarms.tf` and shown in `alarm-details.png`) | optional |
| Dashboard screenshot | `docs/milestone6/evidence/dashboard-top.png`, `dashboard-bottom.png` | done |
| Alert policy screenshot | `evidence/alarm-details.png`, `alarm-actions.png`, `alarm-graph.png` | done |
| Received alert email screenshot | `evidence/alert-email-alarm.png`, `alert-email-ok.png` | done |
| Controlled 5xx demo (log line by request_id, metric rise) | `evidence/controlled-error-request.png` (HTTP 500, request_id 25af8b47971440e3b4dfafd12437869e), `json-log-line.png`, `json-log-line-query.png`, `metric-rise.png` (1 at 23:52 UTC), `route-off.png`; full pack `member2-evidence.pdf` | done |
| `terraform plan` showing no changes | `docs/milestone6/evidence/terraform-plan-after-deploy.txt` (refresh on, No changes, CloudShell) and `evidence/terraform-plan.png` (Dan, "No changes"). Dan to also show it live. | done |
| Pipeline run (a): build, deploy, health check | https://github.com/Junebhone/SocialOps/actions/runs/42529005106 , SHA 9f643eee8a07ed15fe2b7777dfbccc0e1abbd933, `evidence/pipeline.md` | done |
| Pipeline run (b): failed deploy, automatic rollback, verified | https://github.com/Junebhone/SocialOps/actions/runs/42535888765 , SHA 1e89ac939f9d4c225611a89064ab7d4848bd9845, `evidence/pipeline.md` | done |
| Plan still clean after pipeline deploy | `evidence/terraform-plan-after-deploy.txt` | done |
| Written analysis (1 page) | `docs/milestone6/Milestone6_Analysis.pdf` (no TODO markers left; team to proofread) | done |
| Slides | `docs/milestone6/Milestone6_SocialOps.pptx` (screenshot placeholders) | draft |
| Demo video (OneDrive, shared with the three instructors named in the brief) | link: | TODO |

| Security and cost checklist | `docs/milestone6/evidence/security-checklist.md` | done |
| Third pipeline run (revert, green) | https://github.com/Junebhone/SocialOps/actions/runs/42537260649, SHA 5594ccb53ec4f7cebcc26bbe0a016bbaa0c74669 | done |
| Certificate | `evidence/acm-issued.png` (*.socialops.website issued, us-east-1) | done |
| ECS services screenshot (Dan) | pending retake: the Nov 6 capture shows old revision :1 | TODO (Dan) |
