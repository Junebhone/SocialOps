variable "name" {
  description = "Prefix for every resource name, e.g. socialops-dev."
  type        = string
}

variable "vpc_id" {
  description = "VPC the security groups belong to."
  type        = string
}

variable "allowed_ingress_cidrs" {
  description = "Who may reach the ALB. Phase 1 has no auth (CLAUDE.md rule 12), so narrow this before any apply."
  type        = list(string)

  validation {
    condition     = length(var.allowed_ingress_cidrs) > 0 && alltrue([for c in var.allowed_ingress_cidrs : can(cidrhost(c, 0))])
    error_message = "allowed_ingress_cidrs must be a non-empty list of IPv4 CIDRs."
  }
}

variable "web_port" {
  description = "Port the Next.js container listens on."
  type        = number
  default     = 3000
}

variable "api_port" {
  description = "Port the FastAPI container listens on."
  type        = number
  default     = 8000
}

variable "api_listener_port" {
  description = "Port the ALB exposes the API on. The browser calls the API directly (docs/architecture-phase1.md), so it needs its own public port."
  type        = number
  default     = 8000
}

variable "db_port" {
  description = "PostgreSQL port."
  type        = number
  default     = 5432
}

variable "cache_port" {
  description = "Redis port."
  type        = number
  default     = 6379
}
