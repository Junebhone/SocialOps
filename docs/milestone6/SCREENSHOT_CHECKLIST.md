# Screenshot checklist

Save into `docs/milestone6/evidence/` with these names. Never capture secrets (no Secrets Manager values, no
`.env`, no tfvars, no access keys). Crop out personal email addresses if the repo copy will be public; the
originals for grading can stay uncropped. Region: us-east-1 (N. Virginia). Slide numbers refer to
`Milestone6_SocialOps.pptx`.

| # | File | What to capture | Where | Who | Slide |
|---|---|---|---|---|---|
| 1 | `dashboard-top.png`, `dashboard-bottom.png` (**DONE**, account bar cropped) | Whole dashboard `socialops-dev`: 5xx graph with the threshold line, ALB, ECS CPU and memory (api, web, worker), response time, RDS CPU, alarm state. Time range covering the test (last 1 h). | CloudWatch > Dashboards > socialops-dev | Tan | 5 |
| 2 | `alarm-policy.png` | Alarm `socialops-dev-api-5xx`: metric `SocialOps/dev` `Api5xxCount`, Sum, 60 s, >= 1, missing data = not breaching, actions to `socialops-dev-alerts` for ALARM and OK. | CloudWatch > Alarms > socialops-dev-api-5xx (Details and Actions) | Tan | 6 |
| 3 | `alert-email.png` | The ALARM email, open, sender, subject and alarm description visible. | Team alert inbox | Tan | 6 |
| 4 | `alert-emails-list.png` | Inbox list showing ALARM, OK, ALARM (17:43, 17:51, 17:53) so the return-to-OK email is shown. | Team alert inbox | Tan | 6 |
| 5 | `metric-filter.png` | Metric filter: pattern `{ $.status_code >= 500 }`, namespace `SocialOps/dev`, metric `Api5xxCount`, value 1. | CloudWatch > Log groups > /ecs/socialops-dev/api > Metric filters | Tan | 4 |
| 6 | `metric-rise.png` (done, from Zainab) | `Api5xxCount` rising by 1 for the controlled request. | CloudWatch > Metrics > SocialOps/dev | Zainab | 4 |
| 7 | `json-log-line.png` (done, from Zainab) | The JSON log line found by `request_id` (status_code 500, path /debug/error). | CloudWatch Logs Insights or log events | Zainab | 3 |
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

## Status

| # | Screenshot | Status |
|---|---|---|
| 1 | dashboard (top, bottom) | DONE |
| 2 | alarm policy (`alarm-details.png`, `alarm-actions.png`, plus `alarm-graph.png`) | DONE |
| 3 | ALARM email (`alert-email-alarm.png`) | DONE |
| 4 | OK email (`alert-email-ok.png`; inbox list shot still optional) | DONE |
| 5 | metric filter (`metric-filter.png`) | DONE |
| 6 | metric rise (`metric-rise.png`) | DONE (Zainab) |
| 7 | JSON log line by request_id (`json-log-line.png`, `json-log-line-query.png`, `controlled-error-request.png`, `route-off.png`) | DONE (Zainab) |
| 8 | SNS confirmed | TODO Tan |
| 9 | pipeline good run (`pipeline-good.png`, run #47, 9f643ee) | DONE |
| 10 | pipeline failed + rollback (`pipeline-failed-rollback.png`: health check 10/10 failing, Roll back step) | DONE; still TODO: Summary page showing "ROLLED BACK" |
| 11 | pipeline revert run (`pipeline-revert.png`, run #51, 5594ccb) | DONE |
| 12 | API health after rollback (`api-health-ready.png` from Dan shows /health/ready ok; a post-rollback terminal shot is optional) | DONE (Dan) |
| 13 | terraform plan, No changes (`terraform-plan.png`) | DONE (Dan) |
| 14 | live app (`live-app.png`, padlock visible, app.socialops.website/inbox; also `acm-issued.png` for the certificate) | DONE (Dan) |
| 15 | security controls (`rds-private-cli.png`, `rds-config.png`, `s3-public-block.png`, `git-no-secrets.png`, from Zainab's pack) | DONE (Zainab); optional budget shot still TODO |

## How to get each one

Open the AWS console in us-east-1 (N. Virginia). On a Mac, **Shift+Cmd+4** then drag selects an area; the file
lands on the Desktop. Rename it to the name in the table and copy it into `docs/milestone6/evidence/`.

1. **Dashboard** (done). If you retake it: CloudWatch > Dashboards > `socialops-dev`, choose **3h** or **1h**, scroll to
   capture the top four graphs, then the bottom row with the alarm-state widget.
2. **Alarm policy**: CloudWatch > Alarms > All alarms > `socialops-dev-api-5xx`. Capture the **Details** tab (metric,
   Sum, 60 seconds, threshold, missing data treatment) and the **Actions** tab (SNS topic for In alarm and OK).
3. **ALARM email**: open the "ALARM: socialops-dev-api-5xx" email and capture the body.
4. **Inbox list**: capture the list with the three alert emails and their times.
5. **Metric filter**: CloudWatch > Log groups > `/ecs/socialops-dev/api` > **Metric filters** tab. Capture the filter
   pattern and the metric name, namespace and value.
6. **SNS**: Simple Notification Service > Topics > `socialops-dev-alerts` > Subscriptions. Capture status **Confirmed**.
7. **Pipeline runs**: open each run URL in the table above. For the good run, capture the job list and the **Summary**
   (scroll to the rollback target and new revisions). For the red run, expand the Deploy job: the health check
   failing 10 times, the **Roll back** step, and the **Summary** line "ROLLED BACK".
8. **Health after rollback**: in a terminal run `curl https://api.socialops.website/health/ready` and capture the
   `{"status":"ok",...}` line.
9. **Live app**: open https://app.socialops.website in a browser, capture with the padlock visible.
10. **Security** (optional): RDS > Databases > `socialops-dev` > Connectivity: Publicly accessible **No**. Billing >
    Budgets: `SocialOps-Budget`.

Zainab: `metric-rise.png` (CloudWatch > Metrics > All metrics > SocialOps/dev > Api5xxCount, Sum, 1 minute) and
`json-log-line.png` (CloudWatch > Logs Insights, log group `/ecs/socialops-dev/api`, query
`fields @timestamp, @message | filter request_id = "<id>"`).
Dan: `terraform plan` with "No changes" visible.

Crop out personal usernames and emails from the AWS header or inbox before adding screenshots to the public repo.

## Dan's pack (received 2026-11-09)

Saved: `terraform-plan.png`, `api-health-ready.png`, `live-app.png`, `acm-issued.png`.

**Not saved: `ECS_Services_Running.pdf`.** It was captured on November 6 ("Last updated November 6, 2026, 23:56 UTC-6") and shows all three services on
task definition `:1`. The services now run `api:5`, `worker:5`, `web:4` after the pipeline deploys, so that screenshot contradicts the live state and
would confuse graders. Dan: retake it (ECS > Clusters > socialops-dev > Services) so it shows the current revisions, 1/1 tasks running.
