variable "name" {
  description = "Resource name prefix, e.g. socialops-dev."
  type        = string
}

variable "api_log_group_name" {
  description = "The API service's CloudWatch log group, from module.ecs.log_group_names[\"api\"]."
  type        = string
}

variable "metric_namespace" {
  description = "CloudWatch namespace for this environment's custom metrics, e.g. SocialOps/dev. One namespace per environment keeps dev and staging counts apart without a dimension the logs do not carry."
  type        = string
}
