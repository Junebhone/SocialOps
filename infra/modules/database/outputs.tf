output "address" {
  description = "Hostname of the RDS instance."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Port of the RDS instance."
  value       = aws_db_instance.this.port
}

output "instance_identifier" {
  description = "RDS instance identifier."
  value       = aws_db_instance.this.identifier
}

output "database_url_secret_arn" {
  description = "ARN of the Secrets Manager secret holding DATABASE_URL. ECS injects it; nothing else should read it."
  value       = aws_secretsmanager_secret.database_url.arn
}
