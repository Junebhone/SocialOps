# SocialOps
Multi-agent social media command center for SMBs. Orchestrator routes comments/assets to triage, response, content, media, and analytics agents with human approval. Built as a monolith, then migrated to AWS in six phases: EC2 → ECS/Fargate → RDS/S3/SQS/ElastiCache → Step Functions → CloudWatch + Terraform + CI/CD.
