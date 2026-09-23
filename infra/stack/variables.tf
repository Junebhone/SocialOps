# --- Identity ----------------------------------------------------------------

variable "project" {
  description = "Prefix for every resource name."
  type        = string
  default     = "socialops"
}

variable "environment" {
  description = "Environment name. Set in env/<name>.tfvars."
  type        = string

  validation {
    condition     = contains(["dev", "staging"], var.environment)
    error_message = "environment must be dev or staging."
  }
}

variable "aws_region" {
  description = "Region for everything in this stack. us-east-1 has the widest Bedrock model coverage."
  type        = string
  default     = "us-east-1"
}

variable "allowed_account_ids" {
  description = "If non-empty, the AWS provider refuses to run against any other account."
  type        = list(string)
  default     = []
}

variable "disposable" {
  description = "true where the data can be thrown away (dev): destroy skips the final DB snapshot, empties the uploads bucket, deletes secrets immediately, and turns deletion protection off."
  type        = bool
}

# --- Network -----------------------------------------------------------------

variable "vpc_cidr" {
  description = "VPC range. Different per environment so they can be peered later."
  type        = string
}

variable "az_count" {
  description = "Availability zones to spread across."
  type        = number
  default     = 2
}

variable "single_nat_gateway" {
  description = "One NAT gateway for the whole VPC (cheaper) or one per AZ (survives an AZ outage)."
  type        = bool
}

variable "allowed_ingress_cidrs" {
  description = "Who can reach the ALB. There is no auth in Phase 1 (CLAUDE.md rule 12): narrow this to your team's addresses before any apply."
  type        = list(string)
}

# --- Data --------------------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
}

variable "db_multi_az" {
  description = "Keep an RDS standby in a second AZ."
  type        = bool
}

variable "db_backup_retention_days" {
  description = "Days of automated RDS backups."
  type        = number
}

variable "cache_node_type" {
  description = "ElastiCache node type."
  type        = string
}

variable "cache_num_nodes" {
  description = "1 = single node; 2+ = primary plus replicas with automatic failover."
  type        = number
}

# --- Compute -----------------------------------------------------------------

variable "services" {
  description = "Fargate size and task count for api, worker and web."
  type = map(object({
    cpu           = number
    memory        = number
    desired_count = number
  }))
}

variable "image_tag" {
  description = "Image tag to deploy: the git SHA CI pushed. Deploying a new build is a PR that changes this line."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{7,40}$", var.image_tag))
    error_message = "image_tag must be a git SHA (7-40 lowercase hex characters). ECR tags are immutable, so a moving tag like latest cannot be pushed twice."
  }
}

variable "ecr_repository_prefix" {
  description = "ECR repositories are <prefix>/api, <prefix>/worker, <prefix>/web (created by infra/bootstrap)."
  type        = string
  default     = "socialops"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention."
  type        = number
}

variable "container_insights" {
  description = "CloudWatch Container Insights on the ECS cluster."
  type        = bool
  default     = false
}

# --- LLM (the config.py contract) --------------------------------------------

variable "llm_provider" {
  description = "LLM_PROVIDER. Validated against the same allowlist as config.py (D21)."
  type        = string
  default     = "bedrock"

  validation {
    condition     = contains(["ollama", "bedrock"], var.llm_provider)
    error_message = "llm_provider must be ollama or bedrock, matching LLMProvider in worker/worker/config.py."
  }
}

variable "llm_model_fast" {
  description = "LLM_MODEL_FAST: the triage tier."
  type        = string
  default     = "anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "llm_model_text" {
  description = "LLM_MODEL_TEXT: the response and content tier."
  type        = string
  default     = "anthropic.claude-sonnet-5-v1:0"
}

variable "llm_model_vision" {
  description = "LLM_MODEL_VISION: the media tier."
  type        = string
  default     = "anthropic.claude-sonnet-5-v1:0"
}

variable "ollama_base_url" {
  description = "OLLAMA_BASE_URL. config.py requires it even when the provider is bedrock, so it is passed empty rather than omitted. Set it only if you run Ollama on a host the VPC can reach."
  type        = string
  default     = ""
}
