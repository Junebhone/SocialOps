# Child modules declare a floor, not a pin. The exact version is pinned once, in
# the root that calls them (infra/stack), and recorded with hashes in that root's
# .terraform.lock.hcl.
terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0"
    }
  }
}
