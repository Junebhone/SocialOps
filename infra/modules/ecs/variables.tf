variable "name" {
  description = "Prefix for every resource name, e.g. socialops-dev."
  type        = string
}

variable "private_subnet_ids" {
  description = "Subnets the tasks run in. Private: tasks get no public IP."
  type        = list(string)
}

variable "task_security_group_ids" {
  description = "Security group per service (modules/security)."
  type = object({
    web    = string
    api    = string
    worker = string
  })
}

variable "execution_role_arn" {
  description = "Role ECS uses to start tasks (modules/iam)."
  type        = string
}

variable "task_role_arns" {
  description = "Runtime role per service (modules/iam). web has none."
  type = object({
    api    = string
    worker = string
  })
}

variable "images" {
  description = "Full image reference per service, repository:tag. The migrate task reuses the api image."
  type = object({
    api    = string
    worker = string
    web    = string
  })
}

variable "app_environment" {
  description = "Plain environment variables for the api, worker and migrate containers. The config.py contract (CLAUDE.md hard rule #1), minus DATABASE_URL, which is injected from Secrets Manager."
  type        = map(string)
}

variable "database_url_secret_arn" {
  description = "Secrets Manager ARN injected as DATABASE_URL."
  type        = string
}

variable "web_environment" {
  description = "Environment variables for the web container."
  type        = map(string)
}

variable "services" {
  description = "Fargate size and task count per service. cpu in CPU units (1024 = 1 vCPU), memory in MiB."
  type = map(object({
    cpu           = number
    memory        = number
    desired_count = number
  }))

  validation {
    condition     = alltrue([for k in ["api", "worker", "web"] : contains(keys(var.services), k)])
    error_message = "services must define api, worker and web."
  }

  validation {
    condition     = alltrue([for s in values(var.services) : contains([256, 512, 1024, 2048, 4096], s.cpu)])
    error_message = "Each service's cpu must be a Fargate size: 256, 512, 1024, 2048 or 4096."
  }
}

variable "target_group_arns" {
  description = "ALB target group per load-balanced service (modules/alb)."
  type = object({
    web = string
    api = string
  })
}

variable "api_port" {
  description = "Port the FastAPI container listens on."
  type        = number
  default     = 8000
}

variable "web_port" {
  description = "Port the Next.js container listens on."
  type        = number
  default     = 3000
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for every service."
  type        = number
}

variable "container_insights" {
  description = "Enable CloudWatch Container Insights on the cluster. Costs per metric; worth it where you debug."
  type        = bool
  default     = false
}
