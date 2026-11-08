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

TODO. Controlled failure prepared but not yet run: branch `m6/demo-bad-deploy` (local) makes `/health/ready`
return 503 on ECS Fargate only (`AWS_EXECUTION_ENV` set), liveness `/health` still passes so the ECS circuit
breaker does not trip. Expected: deploy, health check fails, "ROLLED BACK" in the job summary, old revisions
verified serving, run red. Then revert (third, green run) and re-run `terraform plan`.

Note: `/health/ready` is not used by the ALB or container health checks (they use `/health`), which is why
this failure is invisible to the circuit breaker and only the pipeline health check catches it.
