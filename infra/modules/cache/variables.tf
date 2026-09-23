variable "name" {
  description = "Replication group ID and resource name prefix, e.g. socialops-dev. Lowercase, at most 40 characters."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,39}$", var.name))
    error_message = "name must be lowercase letters, digits and hyphens, start with a letter, and be at most 40 characters."
  }
}

variable "subnet_ids" {
  description = "Private subnets for the cache subnet group."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups attached to the cache nodes."
  type        = list(string)
}

variable "engine_version" {
  description = "Redis engine version. 7.x matches the redis:7-alpine image in docker-compose.yml."
  type        = string
  default     = "7.1"
}

variable "parameter_group_name" {
  description = "Parameter group matching engine_version."
  type        = string
  default     = "default.redis7"
}

variable "node_type" {
  description = "ElastiCache node type."
  type        = string
}

variable "num_cache_clusters" {
  description = "1 = a single node. 2 or more adds replicas with automatic failover across AZs."
  type        = number

  validation {
    condition     = var.num_cache_clusters >= 1 && var.num_cache_clusters <= 6
    error_message = "num_cache_clusters must be between 1 and 6."
  }
}

variable "snapshot_retention_limit" {
  description = "Days of daily snapshots to keep. 0 disables them."
  type        = number
  default     = 0
}

variable "apply_immediately" {
  description = "Apply modifications now instead of in the next maintenance window."
  type        = bool
  default     = false
}
