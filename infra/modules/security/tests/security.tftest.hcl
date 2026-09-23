mock_provider "aws" {}

variables {
  name                  = "test"
  vpc_id                = "vpc-12345678"
  allowed_ingress_cidrs = ["203.0.113.0/24", "198.51.100.7/32"]
}

run "only_the_alb_faces_clients" {
  command = plan

  assert {
    condition     = length(aws_vpc_security_group_ingress_rule.alb_from_clients) == 4
    error_message = "Expected one ALB rule per client CIDR per listener port (2 x 2)."
  }

  assert {
    condition     = toset([for r in aws_vpc_security_group_ingress_rule.alb_from_clients : r.from_port]) == toset([80, 8000])
    error_message = "The ALB should accept clients on the web and API listener ports only."
  }
}

run "data_tier_accepts_only_app_security_groups" {
  command = plan

  assert {
    condition = alltrue(concat(
      [for r in aws_vpc_security_group_ingress_rule.db_from_tasks : r.cidr_ipv4 == null],
      [for r in aws_vpc_security_group_ingress_rule.cache_from_tasks : r.cidr_ipv4 == null],
    ))
    error_message = "PostgreSQL and Redis must be reachable from security groups only, never from a CIDR."
  }

  assert {
    condition     = keys(aws_vpc_security_group_ingress_rule.db_from_tasks) == ["api", "worker"]
    error_message = "Only api and worker may reach PostgreSQL."
  }

  assert {
    condition     = keys(aws_vpc_security_group_ingress_rule.cache_from_tasks) == ["api", "worker"]
    error_message = "Only api and worker may reach Redis."
  }
}

run "rejects_empty_ingress_list" {
  command = plan

  variables {
    allowed_ingress_cidrs = []
  }

  expect_failures = [var.allowed_ingress_cidrs]
}
