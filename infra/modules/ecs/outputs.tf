output "cluster_name" {
  description = "Name of the ECS cluster."
  value       = aws_ecs_cluster.this.name
}

output "service_names" {
  description = "ECS service name per service."
  value       = { for k, s in aws_ecs_service.this : k => s.name }
}

output "task_definition_arns" {
  description = "Task definition ARN (with revision) per service, plus migrate."
  value = {
    api     = aws_ecs_task_definition.api.arn
    worker  = aws_ecs_task_definition.worker.arn
    web     = aws_ecs_task_definition.web.arn
    migrate = aws_ecs_task_definition.migrate.arn
  }
}

output "migrate_task_family" {
  description = "Task definition family for the one-off migration task."
  value       = aws_ecs_task_definition.migrate.family
}

output "log_group_names" {
  description = "CloudWatch log group per service."
  value       = { for k, g in aws_cloudwatch_log_group.this : k => g.name }
}
