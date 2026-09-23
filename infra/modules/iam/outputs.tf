output "execution_role_arn" {
  description = "Role ECS uses to start tasks: image pull, logs, DATABASE_URL secret."
  value       = aws_iam_role.execution.arn
}

output "task_role_arns" {
  description = "Runtime role per service. web has none: it calls no AWS API."
  value = {
    api    = aws_iam_role.api.arn
    worker = aws_iam_role.worker.arn
  }
}
