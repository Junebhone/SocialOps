# Pipeline evidence

Workflow: `.github/workflows/ci.yml` (job `deploy`), logic in `scripts/ci/deploy.sh`.
Deploy role: `socialops-ci-deploy` (OIDC, `ref:refs/heads/main` only).

## (a) Successful build, deploy and health check

- Run: https://github.com/Junebhone/SocialOps/actions/runs/42529005106
- Commit SHA: `9f643eee8a07ed15fe2b7777dfbccc0e1abbd933` (merge of PR #20), branch `main`
- Jobs: Lint and test, Image (api/web/worker), Deploy (dev): all success. Total about 7.5 min.
- Deploy job, from the log: migrate task ran; `try 1/10: api={"status":"ok","database":true,"redis":true} web=200`;
  `api runs socialops-dev-api:3`, `worker runs socialops-dev-worker:3`, `web runs socialops-dev-web:2`.
- Live after: `https://api.socialops.website/health/ready` returns `{"status":"ok","database":true,"redis":true}`; web returns 200 after redirect.

## (b) Failed deploy, automatic rollback, verification

- Run: https://github.com/Junebhone/SocialOps/actions/runs/42535888765 (conclusion: failure, as designed)
- Commit SHA: `1e89ac939f9d4c225611a89064ab7d4848bd9845` (merge of PR #21), branch `main`
- Controlled failure: on ECS Fargate only (`AWS_EXECUTION_ENV` set), `/health/ready` returned 503. Liveness
  `/health` still passed, so the ECS circuit breaker did not trip; only the pipeline health check caught it.
- Deploy job, from the log: `try 1/10 ... try 10/10: api=none web=200` (readiness 503 every try), then the
  "Roll back" step: `try 1/10: api={"status":"ok","database":true,"redis":true} web=200`,
  `api runs socialops-dev-api:3`, `worker runs socialops-dev-worker:3`, `web runs socialops-dev-web:2`
  (the revisions recorded before the deploy).
- Live after, checked independently: `https://api.socialops.website/health/ready` returned
  `{"status":"ok","database":true,"redis":true}` and the web returned 200.
- Lint, tests and all three image builds in this run were green; only the deploy job failed.

## (c) Revert (third run)

Revert of the controlled failure: PR #22.
- Run: https://github.com/Junebhone/SocialOps/actions/runs/42537260649 (success, about 7 min)
- Commit SHA: `5594ccb53ec4f7cebcc26bbe0a016bbaa0c74669`
- Deploy health check: `try 1/10: api={"status":"ok","database":true,"redis":true} web=200`;
  `api runs socialops-dev-api:5`, `worker runs socialops-dev-worker:5`, `web runs socialops-dev-web:4`.
- `terraform plan` (refresh on) afterwards: No changes. See `terraform-plan-after-deploy.txt`.

Note: `/health/ready` is not used by the ALB or container health checks (they use `/health`), which is why
this failure is invisible to the circuit breaker and only the pipeline health check catches it.

## Controlled 5xx test (Member 2)

Request: `GET https://api.socialops.website/debug/error` -> HTTP 500 at 2026-11-08 23:52:15 GMT, `x-request-id: 25af8b47971440e3b4dfafd12437869e`
(`controlled-error-request.png`). Logs Insights on `/ecs/socialops-dev/api` filtered by that request_id returned exactly 1 record, JSON with
`status_code` 500, `path` /debug/error (`json-log-line.png`). `Api5xxCount` (Sum, 1 min) = 1 at 23:52 UTC (`metric-rise.png`).
ALARM email in the inbox at 17:53 local (23:53 UTC if the inbox is US Central). Route switched off 2026-11-09 00:14 UTC; `/debug/error` returns 404 (`route-off.png`).
A second single 5xx in the 00:09 UTC minute took the alarm to ALARM at 00:10:04 and back to OK at 00:16:04 (`alert-email-alarm.png`, `alert-email-ok.png`).
