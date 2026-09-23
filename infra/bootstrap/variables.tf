variable "project" {
  description = "Prefix for every resource name. Must match var.project in infra/stack."
  type        = string
  default     = "socialops"
}

variable "aws_region" {
  description = "Region for the state bucket, lock table and ECR. Must match the region in infra/stack/backend.tf."
  type        = string
  default     = "us-east-1"
}
