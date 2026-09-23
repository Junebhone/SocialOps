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

variable "github_repository" {
  description = "owner/name of the GitHub repository whose workflows may assume the CI roles."
  type        = string
  default     = "Junebhone/SocialOps"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must look like owner/name."
  }
}

variable "create_github_oidc_provider" {
  description = "An AWS account can hold only one OIDC provider for token.actions.githubusercontent.com. Set false if yours already has one and it will be looked up instead."
  type        = bool
  default     = true
}
