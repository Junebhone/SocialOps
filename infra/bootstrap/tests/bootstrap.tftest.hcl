mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }

  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }

  mock_data "aws_region" {
    defaults = { region = "us-east-1" }
  }

  mock_data "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" }
  }

  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
}

run "state_bucket_is_private_versioned_and_named_per_account" {
  command = plan

  assert {
    condition     = aws_s3_bucket.state.bucket == "socialops-tfstate-123456789012"
    error_message = "The state bucket name must carry the account ID so it is globally unique."
  }

  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled"
    error_message = "State must be versioned so a bad apply can be rolled back."
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.state.block_public_acls,
      aws_s3_bucket_public_access_block.state.block_public_policy,
      aws_s3_bucket_public_access_block.state.ignore_public_acls,
      aws_s3_bucket_public_access_block.state.restrict_public_buckets,
    ])
    error_message = "State contains the database password; the bucket must block all public access."
  }
}

run "lock_table_matches_what_the_s3_backend_expects" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.lock.name == "socialops-tflock" && aws_dynamodb_table.lock.hash_key == "LockID"
    error_message = "infra/stack/backend.tf names socialops-tflock, and the S3 backend requires a LockID string key."
  }
}

run "one_repository_per_service" {
  command = plan

  assert {
    condition     = keys(module.ecr.repository_urls) == ["socialops/api", "socialops/web", "socialops/worker"]
    error_message = "Expected ECR repositories for api, web and worker."
  }
}

run "creates_the_github_oidc_provider_by_default" {
  command = plan

  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 1
    error_message = "A fresh account needs the GitHub OIDC provider created."
  }

  assert {
    condition     = aws_iam_role.ci_plan.name == "socialops-ci-plan" && aws_iam_role.ci_ecr_push.name == "socialops-ci-ecr-push"
    error_message = "The workflows and infra/README.md refer to these role names."
  }
}

run "reuses_an_existing_github_oidc_provider" {
  command = plan

  variables {
    create_github_oidc_provider = false
  }

  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 0
    error_message = "An account can only have one GitHub OIDC provider; it must be looked up, not created."
  }
}

run "rejects_a_repository_that_is_not_owner_slash_name" {
  command = plan

  variables {
    github_repository = "SocialOps"
  }

  expect_failures = [var.github_repository]
}
