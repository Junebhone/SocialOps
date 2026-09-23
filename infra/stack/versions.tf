# Exact pins. This root is what gets planned in CI and applied by a person, so
# "the same code" must mean the same provider build on every machine. The
# hashes for each platform are in .terraform.lock.hcl, which is committed.
terraform {
  required_version = "~> 1.16.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.66.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.9.1"
    }
  }
}
