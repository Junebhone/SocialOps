output "web_url" {
  description = "The dashboard."
  value       = module.alb.web_url
}

output "api_url" {
  description = "The API as the browser sees it (NEXT_PUBLIC_API_URL)."
  value       = module.alb.api_url
}

output "images" {
  description = "Exact image references this environment runs."
  value       = local.images
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = module.ecs.cluster_name
}

output "ecs_service_names" {
  description = "ECS service name per service."
  value       = module.ecs.service_names
}

output "database_url_secret_arn" {
  description = "Secrets Manager ARN holding DATABASE_URL."
  value       = module.database.database_url_secret_arn
}

output "assets_bucket" {
  description = "S3 bucket for uploads (STORAGE_ROOT)."
  value       = module.storage.bucket_name
}

output "queue_urls" {
  description = "SQS job queue and its dead-letter queue."
  value = {
    jobs = module.queue.queue_url
    dlq  = module.queue.dlq_url
  }
}

output "nat_gateway_count" {
  description = "NAT gateways this environment pays for (the largest fixed cost here)."
  value       = module.network.nat_gateway_count
}

# Everything `aws ecs run-task` needs to run the migration, so the command in
# infra/README.md can be pasted without looking anything up.
output "migrate_command" {
  description = "Run Alembic migrations as a one-off Fargate task."
  value = join(" ", [
    "aws ecs run-task",
    "--region ${var.aws_region}",
    "--cluster ${module.ecs.cluster_name}",
    "--launch-type FARGATE",
    "--task-definition ${module.ecs.migrate_task_family}",
    "--network-configuration 'awsvpcConfiguration={subnets=[${join(",", module.network.private_subnet_ids)}],securityGroups=[${module.security.task_security_group_ids.api}],assignPublicIp=DISABLED}'",
  ])
}
