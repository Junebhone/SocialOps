variable "name" {
  description = "Prefix for every role name, e.g. socialops-dev."
  type        = string
}

variable "database_url_secret_arn" {
  description = "The DATABASE_URL secret. Only the execution role reads it, to inject it at task start."
  type        = string
}

variable "assets_bucket_arn" {
  description = "The uploads bucket (modules/storage)."
  type        = string
}

variable "queue_arn" {
  description = "The SQS job queue (modules/queue)."
  type        = string
}

variable "error_route_parameter_arn" {
  description = "ARN of the SSM parameter that switches GET /debug/error. The API role may read it. Null grants nothing."
  type        = string
  default     = null
}
