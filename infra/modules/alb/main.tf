# One public ALB, two listeners, mirroring the two ports compose publishes.
#
# The browser calls the API directly rather than through Next.js
# (docs/architecture-phase1.md), so the API needs a public address of its own.
# Path-based routing on one listener would need the API's routes under a common
# prefix, which they are not. A second listener port keeps the app unchanged:
# NEXT_PUBLIC_API_URL becomes http://<alb>:8000, exactly as it is
# http://localhost:8000 in compose.
#
# HTTP only. HTTPS needs a domain and an ACM certificate, and Route 53 plus WAF
# arrive with Phase 5 in the README roadmap.
#
# Health checks use /health (liveness), not /health/ready. ECS replaces a task
# that fails its target-group check, so a readiness check here would restart
# every API task whenever RDS blipped: the restart loop D28 warns about.
# Readiness belongs on an alarm (Module 5), not on the thing that kills tasks.

resource "aws_lb" "this" {
  name               = var.name
  internal           = false
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [var.security_group_id]

  drop_invalid_header_fields = true
  enable_deletion_protection = var.deletion_protection

  # Image uploads go through this ALB to the API. 60s is the default and
  # comfortably covers a 10 MB upload.
  idle_timeout = 60
}

resource "aws_lb_target_group" "web" {
  name        = "${var.name}-web"
  port        = var.web_port
  protocol    = "HTTP"
  target_type = "ip" # Fargate tasks register by ENI address
  vpc_id      = var.vpc_id

  deregistration_delay = 30

  health_check {
    path                = var.web_health_path
    matcher             = "200"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 5
  }
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name}-api"
  port        = var.api_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  deregistration_delay = 30

  health_check {
    path                = var.api_health_path
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "web" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.this.arn
  port              = var.api_listener_port
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
