# Demo run of show (~15 min)

Rules: cameras on for every presenter. No secrets on screen (no `.env`, no tfvars, no Secrets Manager values). Controlled failures only. Upload to OneDrive, not Canvas.

Before recording: error route set ON (see Member 2's mechanism), SNS subscription confirmed, `main` quiet (no other merges), dashboard open, alarm in OK.

| Time | Who | What to say and do |
|---|---|---|
| 0:00 | Member 5 (Tan) | Open https://app.socialops.website. Show architecture slide (GitHub Actions, ECR, ECS behind ALB/HTTPS, logs, metric filter, alarm, SNS, email). Show `curl https://api.socialops.website/health/ready`. |
| 2:00 | Member 2 (Zainab) | Trigger the controlled 5xx. Note the `request_id`. Find that JSON line in CloudWatch Logs (`/ecs/socialops-dev/api`, filter `status_code >= 500`). Show `Api5xxCount` rising by 1. |
| 5:00 | Member 3 (Tan) | Dashboard `socialops-dev`: 5xx with alarm annotation, ECS CPU and memory, ALB, RDS. Alarm policy (Sum >= 1, 60 s, notBreaching). Show the received email. Allow the measured error-to-email delay [TODO seconds]; cut the wait in editing. Return to OK; error route off. |
| 8:00 | Member 1 (Dan) | `terraform -chdir=infra/stack workspace show` (dev), `terraform plan` with refresh on. Show "No changes". |
| 10:00 | Member 4 (Tan) | Push a harmless commit to `main`. Show Actions run: lint/test, build + push, deploy job (record revisions, migrate, update, health check). Show summary. |
| 13:00 | Member 4 (Tan) | Push the controlled bad commit (`/health/ready` returns 503). Show the deploy, failed health check, automatic rollback, the Roll back step showing the old revisions answering ok, run red. `curl https://api.socialops.website/health/ready` returns 200 on the old version. Explain circuit breaker vs this step. |

Editing: cut while the pipeline runs (build and `services-stable` waits take minutes) and cut the alarm-to-email wait.

After the rollback test (off camera): revert the bad commit (third, green run), re-run `terraform plan` and confirm no changes, turn the error route off.

Security checklist (Zainab runs, Tan cross-checks): RDS not public; S3 via roles; secrets in Secrets Manager; no state, keys or secrets in git (`git log -p` grep, `.gitignore`); `SocialOps-Budget` present.
