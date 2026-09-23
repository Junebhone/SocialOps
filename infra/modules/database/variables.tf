variable "name" {
  description = "Prefix for every resource name, e.g. socialops-dev."
  type        = string
}

variable "secret_name" {
  description = "Secrets Manager name for the DATABASE_URL secret, e.g. socialops/dev/database-url."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets for the DB subnet group (at least two AZs)."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups attached to the instance."
  type        = list(string)
}

variable "engine_version" {
  description = "PostgreSQL major version. A major-only value lets AWS apply minor upgrades without the plan showing drift."
  type        = string
  default     = "16"
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
}

variable "allocated_storage" {
  description = "Initial storage in GiB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling in GiB. A full disk is how Phase 1 lost Postgres (D28); autoscaling is the managed answer."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Standby in a second AZ."
  type        = bool
}

variable "backup_retention_days" {
  description = "Automated backup retention. 0 disables backups."
  type        = number
}

variable "deletion_protection" {
  description = "Refuse deletes until this is switched off."
  type        = bool
}

variable "skip_final_snapshot" {
  description = "Destroy without a final snapshot. true only where the data is disposable."
  type        = bool
}

variable "apply_immediately" {
  description = "Apply modifications now instead of in the next maintenance window."
  type        = bool
  default     = false
}

variable "secret_recovery_window_days" {
  description = "Days a deleted secret can be restored. 0 deletes immediately, which lets dev be destroyed and recreated under the same name."
  type        = number
  default     = 7
}

variable "db_name" {
  description = "Database name. Matches the compose default so migrations and seeds are unchanged."
  type        = string
  default     = "socialops"
}

variable "username" {
  description = "Master username."
  type        = string
  default     = "socialops"
}
