# Screenshot checklist

Save into `docs/milestone6/evidence/` with these names. Never capture secrets (no Secrets Manager values, no
`.env`, no tfvars, no access keys). Crop out personal email addresses if the repo copy will be public; the
originals for grading can stay uncropped. Region: us-east-1 (N. Virginia). Slide numbers refer to
`Milestone6_SocialOps.pptx`.

| # | File | What to capture | Where | Who | Slide |
|---|---|---|---|---|---|
| 1 | `dashboard.png` | Whole dashboard `socialops-dev`: 5xx graph with the threshold line, ALB, ECS CPU and memory (api, web, worker), response time, RDS CPU, alarm state. Time range covering the test (last 1 h). | CloudWatch > Dashboards > socialops-dev | Tan | 5 |
| 2 | `alarm-policy.png` | Alarm `socialops-dev-api-5xx`: metric `SocialOps/dev` `Api5xxCount`, Sum, 60 s, >= 1, missing data = not breaching, actions to `socialops-dev-alerts` for ALARM and OK. | CloudWatch > Alarms > socialops-dev-api-5xx (Details and Actions) | Tan | 6 |
| 3 | `alert-email.png` | The ALARM email, open, sender, subject and alarm description visible. | Team alert inbox | Tan | 6 |
| 4 | `alert-emails-list.png` | Inbox list showing ALARM, OK, ALARM (17:43, 17:51, 17:53) so the return-to-OK email is shown. | Team alert inbox | Tan | 6 |
| 5 | `metric-filter.png` | Metric filter: pattern `{ $.status_code >= 500 }`, namespace `SocialOps/dev`, metric `Api5xxCount`, value 1. | CloudWatch > Log groups > /ecs/socialops-dev/api > Metric filters | Tan | 4 |
| 6 | `metric-rise.png` | `Api5xxCount` rising by 1 for the controlled request. | CloudWatch > Metrics > SocialOps/dev | Zainab | 4 |
| 7 | `json-log-line.png` | The JSON log line found by `request_id` (status_code 500, path /debug/error). | CloudWatch Logs Insights or log events | Zainab | 3 |
| 8 | `sns-confirmed.png` | SNS topic `socialops-dev-alerts`, email subscription status Confirmed. | SNS > Topics > socialops-dev-alerts > Subscriptions | Tan | 6 |
| 9 | `pipeline-good.png` | Run 42529005106 (green): job list and summary with rollback target and new revisions. | https://github.com/Junebhone/SocialOps/actions/runs/42529005106 | Tan | 8 |
| 10 | `pipeline-failed-rollback.png` | Run 42535888765 (red): health check failing 10/10, the "Roll back" step, summary "ROLLED BACK". | https://github.com/Junebhone/SocialOps/actions/runs/42535888765 | Tan | 9 |
| 11 | `pipeline-revert.png` | Run 42537260649 (green) after the revert. | https://github.com/Junebhone/SocialOps/actions/runs/42537260649 | Tan | 9 |
| 12 | `health-after-rollback.png` | Terminal: `curl https://api.socialops.website/health/ready` returning ok. | Terminal | Tan | 9 |
| 13 | `terraform-plan.png` | `terraform plan` (refresh on) ending "No changes. Your infrastructure matches the configuration." Workspace dev visible. | Terminal | Dan | 7 |
| 14 | `live-app.png` | https://app.socialops.website loaded (padlock visible) plus the API health JSON. | Browser | Tan | 2 |
| 15 | `security-controls.png` | Optional: RDS "Publicly accessible: No", Budget `SocialOps-Budget`. | RDS console, Billing > Budgets | Tan | 10 |

Before the video: error route switch must be `false`
(`aws ssm get-parameter --name /socialops-dev/enable-error-route --query Parameter.Value --output text`),
alarm state `OK`, nobody sending test requests.
