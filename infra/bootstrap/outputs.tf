output "state_bucket" {
  description = "S3 bucket holding every environment's state. Pass it to terraform init in infra/stack."
  value       = aws_s3_bucket.state.id
}

output "lock_table" {
  description = "DynamoDB table used for state locking."
  value       = aws_dynamodb_table.lock.name
}

output "ecr_repository_urls" {
  description = "Where CI pushes images, one repository per service."
  value       = module.ecr.repository_urls
}

output "stack_init_command" {
  description = "Run in infra/stack to point it at this state bucket."
  value       = "terraform init -backend-config=\"bucket=${aws_s3_bucket.state.id}\""
}
