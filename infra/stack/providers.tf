provider "aws" {
  region = var.aws_region

  # Optional tripwire: when set, the provider refuses to plan against any other
  # account, so a stale AWS_PROFILE cannot put dev into the wrong account.
  allowed_account_ids = length(var.allowed_account_ids) > 0 ? var.allowed_account_ids : null

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "SocialOps"
    }
  }
}
