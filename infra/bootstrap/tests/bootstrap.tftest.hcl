mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
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
