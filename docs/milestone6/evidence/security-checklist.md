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
| Error route switch (SSM `/socialops-dev/enable-error-route`) | was `true` during testing; set back to `false` 2026-11-09 00:14 UTC, `GET /debug/error` returns 404 afterwards (`route-off.png`). Re-verify before recording. |
| us-east-2 Milestone 5 RDS `socialops-db` | still `available` (cost); not touched, decision pending |

Member 2 cross-check (`member2-evidence.pdf`): RDS PubliclyAccessible False with storage encryption enabled (`rds-private-cli.png`,
`rds-config.png`); Block Public Access all four settings True on the assets and tfstate buckets (`s3-public-block.png`);
API task uses IAM task role `socialops-dev-api-task`, DATABASE_URL injected from Secrets Manager; only `.env.example` is tracked in git
and `.gitignore` excludes `.env`, `.terraform/`, `*.tfstate` (`git-no-secrets.png`). Matches our own CloudShell checks above.
