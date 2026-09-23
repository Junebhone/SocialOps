output "alb_security_group_id" {
  description = "Security group for the ALB."
  value       = aws_security_group.alb.id
}

output "task_security_group_ids" {
  description = "Security group per ECS service: web, api, worker."
  value = {
    web    = aws_security_group.web.id
    api    = aws_security_group.api.id
    worker = aws_security_group.worker.id
  }
}

output "db_security_group_id" {
  description = "Security group for RDS."
  value       = aws_security_group.db.id
}

output "cache_security_group_id" {
  description = "Security group for ElastiCache."
  value       = aws_security_group.cache.id
}
