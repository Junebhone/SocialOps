# Plans the whole stack against a mocked AWS provider: no credentials, no
# account, no cost. CI runs it on every pull request, once per environment:
#
#   terraform test -var-file=env/dev.tfvars
#   terraform test -var-file=env/staging.tfvars
#
# What each module does with its inputs is tested next to the module
# (modules/*/tests). This file checks that each environment's tfvars produce
# a plan at all, reach the outputs they should, and that bad values are
# refused before anything is created.

mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b", "us-east-1c"] }
  }

  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }

  mock_data "aws_region" {
    defaults = { region = "us-east-1" }
  }

  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }

  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }

  mock_data "aws_ecr_repository" {
    defaults = { repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/socialops/mock" }
  }
}

# terraform test always runs in the default workspace, so the guard that ties
# workspace to environment is switched off here and exercised on its own below.
variables {
  require_workspace_match = false
}

run "environment_plans" {
  command = plan

  assert {
    condition     = output.nat_gateway_count == (var.single_nat_gateway ? 1 : var.az_count)
    error_message = "NAT gateway count does not follow single_nat_gateway."
  }

  assert {
    condition     = alltrue([for img in values(output.images) : endswith(img, ":${var.image_tag}")])
    error_message = "Every service must run the image_tag from this environment's tfvars."
  }

  assert {
    condition     = keys(output.ecs_service_names) == ["api", "web", "worker"]
    error_message = "Expected exactly three ECS services: api, web, worker."
  }
}

run "rejects_unknown_environment" {
  command = plan

  variables {
    environment = "prod"
  }

  expect_failures = [var.environment]
}

run "rejects_mutable_image_tag" {
  command = plan

  variables {
    image_tag = "latest"
  }

  expect_failures = [var.image_tag]
}

run "rejects_unknown_llm_provider" {
  command = plan

  variables {
    llm_provider = "openai"
  }

  expect_failures = [var.llm_provider]
}

run "refuses_workspace_that_does_not_match_environment" {
  command = plan

  variables {
    require_workspace_match = true
  }

  expect_failures = [data.aws_caller_identity.current]
}
