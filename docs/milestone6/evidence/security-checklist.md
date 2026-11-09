# Security and cost controls (checked from CloudShell, account 518668548718)

| Control | Result |
|---|---|
| RDS `socialops-dev` publicly accessible | False |
| RDS security group ingress CIDRs | none (empty) |
| S3 assets bucket public access block (`socialops-dev-assets-518668548718`) | BlockPublicAcls, BlockPublicPolicy, RestrictPublicBuckets all True |
| Secrets in Secrets Manager | `socialops/dev/database-url` (names only checked) |
| Budget alert | `SocialOps-Budget` present |
| IAM users with long-lived keys named socialops | none |
| CI access | OIDC roles only (`socialops-ci-plan`, `socialops-ci-ecr-push`, `socialops-ci-deploy`), no stored keys |
| tfstate / keys / `.env` / secret patterns in git history (main) | none found |
| Team email in git | not committed (GitHub repo variable `ALERT_EMAIL`, sensitive Terraform variable) |
| Error route switch (SSM `/socialops-dev/enable-error-route`) | found `true` at check time (left on after testing); must be `false` before recording |
| us-east-2 Milestone 5 RDS `socialops-db` | still `available` (cost); not touched, decision pending |
