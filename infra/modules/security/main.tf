# Every security group in one module, so the rules that reference each other
# (alb -> web, api/worker -> db) resolve without a dependency cycle between
# the modules that own the resources.
#
# The shape mirrors docker-compose.yml: the browser reaches web and api, only
# api and worker reach Postgres and Redis, and the worker accepts no inbound
# traffic at all.
#
# Rules are separate aws_vpc_security_group_*_rule resources rather than inline
# blocks. Inline rules and standalone rules fight over the same group, and a
# standalone rule can be added later (Module 5 monitoring, a bastion) without
# rewriting the group.

locals {
  alb_listener_ports = toset([80, var.api_listener_port])

  alb_ingress = {
    for pair in setproduct(var.allowed_ingress_cidrs, local.alb_listener_ports) :
    "${pair[0]}:${pair[1]}" => { cidr = pair[0], port = pair[1] }
  }
}

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "Public ALB: HTTP for the web app and the API listener."
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-alb" }
}

resource "aws_security_group" "web" {
  name        = "${var.name}-web"
  description = "Next.js tasks: reachable only from the ALB."
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-web" }
}

resource "aws_security_group" "api" {
  name        = "${var.name}-api"
  description = "FastAPI tasks: reachable only from the ALB."
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-api" }
}

resource "aws_security_group" "worker" {
  name        = "${var.name}-worker"
  description = "arq worker tasks: no inbound traffic."
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-worker" }
}

resource "aws_security_group" "db" {
  name        = "${var.name}-db"
  description = "RDS PostgreSQL: api and worker only."
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-db" }
}

resource "aws_security_group" "cache" {
  name        = "${var.name}-cache"
  description = "ElastiCache Redis: api and worker only."
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-cache" }
}

# --- ALB ---------------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "alb_from_clients" {
  for_each = local.alb_ingress

  security_group_id = aws_security_group.alb.id
  description       = "Clients to ALB listener ${each.value.port}"
  cidr_ipv4         = each.value.cidr
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
}

resource "aws_vpc_security_group_egress_rule" "alb_to_web" {
  security_group_id            = aws_security_group.alb.id
  description                  = "ALB to web tasks"
  referenced_security_group_id = aws_security_group.web.id
  ip_protocol                  = "tcp"
  from_port                    = var.web_port
  to_port                      = var.web_port
}

resource "aws_vpc_security_group_egress_rule" "alb_to_api" {
  security_group_id            = aws_security_group.alb.id
  description                  = "ALB to api tasks"
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = var.api_port
  to_port                      = var.api_port
}

# --- Tasks -------------------------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "web_from_alb" {
  security_group_id            = aws_security_group.web.id
  description                  = "ALB to Next.js"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = var.web_port
  to_port                      = var.web_port
}

resource "aws_vpc_security_group_ingress_rule" "api_from_alb" {
  security_group_id            = aws_security_group.api.id
  description                  = "ALB to FastAPI"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = var.api_port
  to_port                      = var.api_port
}

# Tasks need outbound HTTPS for ECR pulls, CloudWatch Logs, Secrets Manager,
# S3, SQS and Bedrock, and the web task fetches Google Fonts at build time.
# Egress is open on every port rather than just 443 so the data-store rules
# below stay the only thing to reason about for 5432 and 6379.
resource "aws_vpc_security_group_egress_rule" "task_all" {
  for_each = {
    web    = aws_security_group.web.id
    api    = aws_security_group.api.id
    worker = aws_security_group.worker.id
  }

  security_group_id = each.value
  description       = "${each.key} tasks outbound"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# --- Data stores -------------------------------------------------------------
# No egress rules: security groups are stateful, so replies are allowed, and
# neither Postgres nor Redis initiates connections.

resource "aws_vpc_security_group_ingress_rule" "db_from_tasks" {
  for_each = {
    api    = aws_security_group.api.id
    worker = aws_security_group.worker.id
  }

  security_group_id            = aws_security_group.db.id
  description                  = "${each.key} to PostgreSQL"
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = var.db_port
  to_port                      = var.db_port
}

resource "aws_vpc_security_group_ingress_rule" "cache_from_tasks" {
  for_each = {
    api    = aws_security_group.api.id
    worker = aws_security_group.worker.id
  }

  security_group_id            = aws_security_group.cache.id
  description                  = "${each.key} to Redis"
  referenced_security_group_id = each.value
  ip_protocol                  = "tcp"
  from_port                    = var.cache_port
  to_port                      = var.cache_port
}
