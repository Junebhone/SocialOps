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

output "ci_plan_role_arn" {
  description = "Role the Terraform workflow assumes to plan. Set as the AWS_PLAN_ROLE_ARN repository variable."
  value       = aws_iam_role.ci_plan.arn
}

output "ci_ecr_push_role_arn" {
  description = "Role the CI workflow assumes to push images from main. Set as the AWS_ECR_PUSH_ROLE_ARN repository variable."
  value       = aws_iam_role.ci_ecr_push.arn
}

output "github_variables_commands" {
  description = "Paste into a shell to connect the GitHub workflows to this account. These are repository variables, not secrets: nothing here grants access by itself."
  value       = <<-EOT
    gh variable set AWS_REGION            --repo ${var.github_repository} --body "${local.region}"
    gh variable set TF_STATE_BUCKET       --repo ${var.github_repository} --body "${aws_s3_bucket.state.id}"
    gh variable set AWS_PLAN_ROLE_ARN     --repo ${var.github_repository} --body "${aws_iam_role.ci_plan.arn}"
    gh variable set AWS_ECR_PUSH_ROLE_ARN --repo ${var.github_repository} --body "${aws_iam_role.ci_ecr_push.arn}"
  EOT
}
