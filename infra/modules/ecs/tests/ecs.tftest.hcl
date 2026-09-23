mock_provider "aws" {
  mock_data "aws_region" {
    defaults = { region = "us-east-1" }
  }
}

variables {
  name                    = "test"
  private_subnet_ids      = ["subnet-a", "subnet-b"]
  task_security_group_ids = { web = "sg-web", api = "sg-api", worker = "sg-worker" }
  execution_role_arn      = "arn:aws:iam::123456789012:role/exec"
  task_role_arns          = { api = "arn:aws:iam::123456789012:role/api", worker = "arn:aws:iam::123456789012:role/worker" }
  target_group_arns       = { web = "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/web/1", api = "arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/api/1" }
  database_url_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:db-AbCdEf"
  log_retention_days      = 7

  images = {
    api    = "registry.example/socialops/api:abc1234"
    worker = "registry.example/socialops/worker:abc1234"
    web    = "registry.example/socialops/web:abc1234"
  }

  app_environment = {
    REDIS_URL       = "rediss://cache.example:6379/0"
    STORAGE_BACKEND = "s3"
  }

  web_environment = {
    NEXT_PUBLIC_API_URL = "http://alb.example:8000"
  }

  services = {
    api    = { cpu = 256, memory = 512, desired_count = 2 }
    worker = { cpu = 512, memory = 1024, desired_count = 1 }
    web    = { cpu = 1024, memory = 2048, desired_count = 1 }
  }
}

run "services_are_private_and_wired_to_the_right_load_balancer" {
  command = plan

  assert {
    condition = alltrue([
      for s in aws_ecs_service.this : s.network_configuration[0].assign_public_ip == false
    ])
    error_message = "Tasks run in private subnets with no public IP."
  }

  assert {
    condition     = length(aws_ecs_service.this["worker"].load_balancer) == 0
    error_message = "The worker takes no inbound traffic and must not join a target group."
  }

  assert {
    condition     = one(aws_ecs_service.this["api"].load_balancer).container_port == 8000
    error_message = "The api service should register container port 8000."
  }

  assert {
    condition     = aws_ecs_service.this["api"].desired_count == 2
    error_message = "desired_count should come from the services map."
  }
}

run "database_url_is_a_secret_not_an_env_var" {
  command = plan

  assert {
    condition     = !contains([for e in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].environment : e.name], "DATABASE_URL")
    error_message = "DATABASE_URL must be injected from Secrets Manager, never as a plain environment variable."
  }

  assert {
    condition     = jsondecode(aws_ecs_task_definition.api.container_definitions)[0].secrets[0].name == "DATABASE_URL"
    error_message = "The api task should receive DATABASE_URL as a secret."
  }

  assert {
    condition     = jsondecode(aws_ecs_task_definition.migrate.container_definitions)[0].command == ["alembic", "upgrade", "head"]
    error_message = "The migrate task should run Alembic and nothing else."
  }
}

run "api_runs_without_reload" {
  command = plan

  assert {
    condition     = !contains(jsondecode(aws_ecs_task_definition.api.container_definitions)[0].command, "--reload")
    error_message = "--reload is a dev convenience; the image's default command must be overridden on ECS."
  }
}

run "rejects_non_fargate_cpu" {
  command = plan

  variables {
    services = {
      api    = { cpu = 300, memory = 512, desired_count = 1 }
      worker = { cpu = 512, memory = 1024, desired_count = 1 }
      web    = { cpu = 1024, memory = 2048, desired_count = 1 }
    }
  }

  expect_failures = [var.services]
}
