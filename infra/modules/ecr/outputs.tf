output "repository_urls" {
  description = "Repository URL by name, e.g. socialops/api => 123456789012.dkr.ecr.us-east-1.amazonaws.com/socialops/api."
  value       = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "repository_arns" {
  description = "Repository ARN by name. CI's push role is scoped to these."
  value       = { for k, r in aws_ecr_repository.this : k => r.arn }
}
