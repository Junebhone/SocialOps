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

variable "github_immutable_subject_prefix" {
  description = "The OIDC subject prefix GitHub sends when the repository uses immutable subject claims: repo:<owner>@<owner-id>/<repo>@<repo-id>. Find it with: gh api repos/<owner>/<repo>/actions/oidc/customization/sub (field sub_claim_prefix). Empty string if the repository uses the plain repo:<owner>/<repo> form only."
  type        = string
  default     = "repo:Junebhone@86924620/SocialOps@1361594975"

  validation {
    condition     = var.github_immutable_subject_prefix == "" || can(regex("^repo:[^/]+@[0-9]+/[^/]+@[0-9]+$", var.github_immutable_subject_prefix))
    error_message = "github_immutable_subject_prefix must look like repo:owner@123/name@456, or be empty."
  }
}

variable "create_github_oidc_provider" {
  description = "An AWS account can hold only one OIDC provider for token.actions.githubusercontent.com. Set false if yours already has one and it will be looked up instead."
  type        = bool
  default     = true
}
