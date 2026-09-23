# How GitHub Actions gets into AWS: OpenID Connect, not access keys.
#
# Each workflow run asks GitHub for a short-lived token that names the repo and
# the trigger, and exchanges it with AWS STS for one-hour credentials. There is
# no secret stored in GitHub to leak or rotate. The trust policies below are the
# whole access-control story, so they are narrow on purpose:
#
#   ci-plan      pull requests from this repository only. Read-only across the
#                account, plus the state lock. It can see everything and change
#                nothing, which is what a plan needs.
#   ci-ecr-push  the main branch only. Push to the three ECR repositories and
#                nothing else. A pull request cannot publish an image.
#
# Neither role can apply. Applying stays a deliberate act by a person with
# their own credentials (infra/README.md).

data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  partition   = data.aws_partition.current.partition
  region      = data.aws_region.current.region
  github_host = "token.actions.githubusercontent.com"

  github_oidc_provider_arn = (
    var.create_github_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : data.aws_iam_openid_connect_provider.github[0].arn
  )
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.github_host}"
  client_id_list = ["sts.amazonaws.com"]
  # No thumbprint_list: for GitHub, AWS validates the token against its own
  # library of trusted root CAs, and a pinned thumbprint only breaks when
  # GitHub rotates its certificate.
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1

  url = "https://${local.github_host}"
}

# --- Plan role ---------------------------------------------------------------

data "aws_iam_policy_document" "ci_plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    # "pull_request" is the subject GitHub issues for pull_request events.
    # Forks never get here: GitHub does not issue OIDC tokens to fork PRs.
    condition {
      test     = "StringEquals"
      variable = "${local.github_host}:sub"
      values   = ["repo:${var.github_repository}:pull_request"]
    }
  }
}

resource "aws_iam_role" "ci_plan" {
  name                 = "${var.project}-ci-plan"
  description          = "terraform plan from GitHub Actions pull requests. Read-only."
  assume_role_policy   = data.aws_iam_policy_document.ci_plan_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "ci_plan_read_only" {
  role       = aws_iam_role.ci_plan.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "ci_plan_state" {
  statement {
    sid       = "ListState"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.state.arn]
  }

  statement {
    sid       = "ReadState"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.state.arn}/*"]
  }

  # A plan takes the state lock but never writes state. So the role can create
  # and delete lock files (use_lockfile) and nothing else in the bucket.
  statement {
    sid       = "TakeS3Lock"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/*.tflock"]
  }

  statement {
    sid       = "TakeDynamoDbLock"
    actions   = ["dynamodb:DescribeTable", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
    resources = [aws_dynamodb_table.lock.arn]
  }

  # ReadOnlyAccess deliberately omits secret values. Refreshing the
  # DATABASE_URL secret version needs one, so it is granted for this
  # project's secrets only.
  statement {
    sid       = "RefreshProjectSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:${local.partition}:secretsmanager:${local.region}:${local.account_id}:secret:${var.project}/*"]
  }
}

resource "aws_iam_role_policy" "ci_plan_state" {
  name   = "terraform-state-and-lock"
  role   = aws_iam_role.ci_plan.id
  policy = data.aws_iam_policy_document.ci_plan_state.json
}

# --- ECR push role -----------------------------------------------------------

data "aws_iam_policy_document" "ci_ecr_push_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_host}:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "ci_ecr_push" {
  name                 = "${var.project}-ci-ecr-push"
  description          = "Push images to ECR from GitHub Actions on main."
  assume_role_policy   = data.aws_iam_policy_document.ci_ecr_push_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "ci_ecr_push" {
  # Registry login. This action has no resource-level scoping.
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PushToProjectRepositories"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = values(module.ecr.repository_arns)
  }
}

resource "aws_iam_role_policy" "ci_ecr_push" {
  name   = "push-project-images"
  role   = aws_iam_role.ci_ecr_push.id
  policy = data.aws_iam_policy_document.ci_ecr_push.json
}
