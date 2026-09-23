output "primary_endpoint_address" {
  description = "Hostname of the primary node."
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "redis_url" {
  description = "REDIS_URL for the api and worker. rediss:// because transit encryption is on. Not a secret: there is no AUTH token, and the security group is the access control."
  value       = "rediss://${aws_elasticache_replication_group.this.primary_endpoint_address}:6379/0"
}
