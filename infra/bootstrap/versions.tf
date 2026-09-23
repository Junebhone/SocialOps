# The bootstrap root keeps its state in a local file on purpose: it creates the
# bucket every other state file lives in, so it cannot store itself there on
# the first apply. infra/README.md shows how to move it into the bucket
# afterwards. Same exact pins as infra/stack.
terraform {
  required_version = "~> 1.16.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.66.0"
    }
  }
}
