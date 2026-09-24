# ECS on Fargate: one cluster, three long-running services, and a one-off
# migrate task.
#
# The images are the Phase 1 Dockerfiles, unchanged — "same images" is the
# whole point of D2. Their default commands are the dev ones (uvicorn
# --reload, next dev), so the task definitions override the command where that
# matters and nothing else:
#
#   api     uvicorn without --reload. One process per task; scale by adding
#           tasks, which the stateless API (hard rule #2) allows.
#   worker  the image's own `arq worker.main.WorkerSettings`.
#   web     `next build && next start`, run at container start. See below.
#   migrate `alembic upgrade head`, run by hand with `aws ecs run-task` before
#           the api and worker start against a new database (infra/README.md).
#
# Why web builds at start: NEXT_PUBLIC_API_URL is inlined into the browser
# bundle by `next build`, so building in CI would bake one environment's ALB
# address into an image that is supposed to be promoted between environments.
# Building at start keeps one image for dev and staging at the cost of a slow
# first boot (about two minutes). A production Dockerfile stage with a runtime
# config endpoint is the proper fix and is listed in infra/README.md.

data "aws_region" "current" {}

locals {
  region = data.aws_region.current.region

  # ECS wants [{name, value}]. A for over a map iterates in key order, so the
  # rendered JSON is stable and the plan does not show spurious diffs.
  app_env = [for k, v in var.app_environment : { name = k, value = v }]
  web_env = [for k, v in var.web_environment : { name = k, value = v }]

  app_secrets = [{ name = "DATABASE_URL", valueFrom = var.database_url_secret_arn }]

  # Alembic's env.py imports config.py, which validates every variable.
  # Migrations never touch storage, so the migrate task is given "local": it
  # needs no bucket access and no AWS_REGION, and it proves the network path
  # and the DATABASE_URL secret on its own.
  migrate_env = [
    for k, v in merge(var.app_environment, { STORAGE_BACKEND = "local", STORAGE_ROOT = "/tmp/unused" }) :
    { name = k, value = v }
  ]

  log_services = toset(["api", "worker", "web", "migrate"])

  log_config = {
    for svc in local.log_services : svc => {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.this[svc].name
        awslogs-region        = local.region
        awslogs-stream-prefix = svc
        # structlog writes one JSON line per request/job (hard rule #8). If
        # CloudWatch is slow, drop log lines rather than block the app.
        mode            = "non-blocking"
        max-buffer-size = "25m"
      }
    }
  }
}

resource "aws_ecs_cluster" "this" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = var.container_insights ? "enabled" : "disabled"
  }
}

resource "aws_cloudwatch_log_group" "this" {
  for_each = local.log_services

  name              = "/ecs/${var.name}/${each.key}"
  retention_in_days = var.log_retention_days
}

# --- Task definitions --------------------------------------------------------

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.services["api"].cpu
  memory                   = var.services["api"].memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arns.api

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64" # CI builds on amd64 runners
  }

  container_definitions = jsonencode([{
    name      = "api"
    image     = var.images.api
    essential = true
    command = [
      "uvicorn", "app.main:app",
      "--host", "0.0.0.0",
      "--port", tostring(var.api_port),
      # Only the ALB can reach this port (modules/security), so trusting its
      # X-Forwarded-For puts real client addresses in the request logs.
      "--proxy-headers", "--forwarded-allow-ips", "*",
    ]
    portMappings     = [{ containerPort = var.api_port, protocol = "tcp" }]
    environment      = local.app_env
    secrets          = local.app_secrets
    logConfiguration = local.log_config["api"]
    stopTimeout      = 30

    # Liveness, same probe as the ALB. See modules/alb for why not /health/ready.
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:${var.api_port}/health').status==200 else 1)\""]
      interval    = 15
      timeout     = 5
      retries     = 3
      startPeriod = 20
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.services["worker"].cpu
  memory                   = var.services["worker"].memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arns.worker

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name             = "worker"
    image            = var.images.worker
    essential        = true
    environment      = local.app_env
    secrets          = local.app_secrets
    logConfiguration = local.log_config["worker"]
    # Fargate's maximum, and still shorter than arq's 300s job_timeout. On a
    # deploy, a job still running after 120s is killed. arq retries it
    # (max_tries), and the orchestrator's row-lock guard (D29) makes the retry
    # produce one draft, not two.
    stopTimeout = 120

    # arq writes a heartbeat to Redis and --check fails when it goes stale.
    # Unlike a process check, that catches a worker wedged on a model call
    # that never returns (D28).
    healthCheck = {
      command     = ["CMD-SHELL", "arq --check worker.main.WorkerSettings"]
      interval    = 30
      timeout     = 10
      retries     = 3
      startPeriod = 60
    }
  }])
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${var.name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.services["web"].cpu
  memory                   = var.services["web"].memory
  execution_role_arn       = var.execution_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "web"
    image     = var.images.web
    essential = true
    command = [
      "sh", "-c",
      "npm run build && exec npm run start -- --hostname 0.0.0.0 --port ${var.web_port}",
    ]
    portMappings     = [{ containerPort = var.web_port, protocol = "tcp" }]
    environment      = local.web_env
    logConfiguration = local.log_config["web"]
    stopTimeout      = 30

    healthCheck = {
      command  = ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:${var.web_port}/inbox || exit 1"]
      interval = 30
      timeout  = 10
      retries  = 5
      # The build runs inside this window. 300 is the ECS maximum.
      startPeriod = 300
    }
  }])
}

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.name}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = var.execution_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  # The api image: Alembic lives only in the api package (D24).
  container_definitions = jsonencode([{
    name             = "migrate"
    image            = var.images.api
    essential        = true
    command          = ["alembic", "upgrade", "head"]
    environment      = local.migrate_env
    secrets          = local.app_secrets
    logConfiguration = local.log_config["migrate"]
  }])
}

# --- Services ----------------------------------------------------------------

locals {
  service_definitions = {
    api = {
      task_definition = aws_ecs_task_definition.api.arn
      security_group  = var.task_security_group_ids.api
      load_balancer   = { target_group_arn = var.target_group_arns.api, port = var.api_port }
      grace_seconds   = 60
    }
    worker = {
      task_definition = aws_ecs_task_definition.worker.arn
      security_group  = var.task_security_group_ids.worker
      load_balancer   = null
      grace_seconds   = null
    }
    web = {
      task_definition = aws_ecs_task_definition.web.arn
      security_group  = var.task_security_group_ids.web
      load_balancer   = { target_group_arn = var.target_group_arns.web, port = var.web_port }
      # The ALB must not kill the task while `next build` is still running.
      grace_seconds = 420
    }
  }
}

resource "aws_ecs_service" "this" {
  for_each = local.service_definitions

  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = each.value.task_definition
  desired_count   = var.services[each.key].desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [each.value.security_group]
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = each.value.load_balancer == null ? [] : [each.value.load_balancer]

    content {
      target_group_arn = load_balancer.value.target_group_arn
      container_name   = each.key
      container_port   = load_balancer.value.port
    }
  }

  health_check_grace_period_seconds = each.value.grace_seconds

  # A deployment whose tasks never become healthy rolls itself back instead of
  # leaving the service half-replaced.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  propagate_tags          = "SERVICE"
  enable_ecs_managed_tags = true
}
