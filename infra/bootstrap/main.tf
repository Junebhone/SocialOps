# Everything that exists once per AWS account rather than once per
# environment. Applied by a person with admin credentials, once, before
# anything in infra/stack can be planned:
#
#   - the S3 bucket that holds every environment's Terraform state
#   - the DynamoDB table that locks it
#   - the ECR repositories, shared because one image is promoted through
#     every environment rather than rebuilt per environment

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # The account ID makes the name globally unique, so every teammate can
  # bootstrap a personal account without a naming collision.
  state_bucket = "${var.project}-tfstate-${local.account_id}"
  lock_table   = "${var.project}-tflock"
}

# --- State bucket ------------------------------------------------------------

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket

  # State is the only record of what Terraform owns. Losing it means importing
  # every resource by hand, so Terraform refuses to plan its deletion.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# State holds the database password (modules/database), so it is encrypted at
# rest here and never committed to git (.gitignore).
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Every apply writes a new version, so a corrupted or wrongly-applied state
# can be rolled back to the previous object.
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  depends_on = [aws_s3_bucket_versioning.state]
}

data "aws_iam_policy_document" "state_tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.state.arn,
      "${aws_s3_bucket.state.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state_tls_only.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}

# --- Lock table --------------------------------------------------------------
# The Module 3 brief asks for a DynamoDB lock table, so there is one. Terraform
# 1.11+ can also lock with a file in the bucket itself (use_lockfile), and has
# deprecated the DynamoDB option in its favour. infra/stack/backend.tf turns
# both on; dropping DynamoDB later is one line there and this resource.

resource "aws_dynamodb_table" "lock" {
  name         = local.lock_table
  billing_mode = "PAY_PER_REQUEST" # a handful of requests per plan: pennies
  hash_key     = "LockID"          # the attribute name the S3 backend expects

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  deletion_protection_enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

# --- Container registries ----------------------------------------------------

module "ecr" {
  source = "../modules/ecr"

  repository_names = toset([for svc in ["api", "worker", "web"] : "${var.project}/${svc}"])
}
