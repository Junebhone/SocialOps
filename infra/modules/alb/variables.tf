variable "name" {
  description = "Prefix for resource names, e.g. socialops-dev. At most 28 characters: target group names append -web/-api and AWS caps them at 32."
  type        = string

  validation {
    condition     = length(var.name) <= 28
    error_message = "name must be at most 28 characters."
  }
}

variable "vpc_id" {
  description = "VPC for the target groups."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnets the ALB sits in (at least two AZs)."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group for the ALB (modules/security)."
  type        = string
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
  description = "Public port for the API listener."
  type        = number
  default     = 8000
}

variable "web_health_path" {
  description = "Health check path for the web target group. /inbox is what the compose healthcheck probes."
  type        = string
  default     = "/inbox"
}

variable "api_health_path" {
  description = "Health check path for the api target group. Liveness, not readiness: see the note in main.tf."
  type        = string
  default     = "/health"
}

variable "deletion_protection" {
  description = "Refuse to delete the ALB until this is switched off."
  type        = bool
  default     = false
}
