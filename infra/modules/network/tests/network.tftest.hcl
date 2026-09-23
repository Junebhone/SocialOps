mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b", "us-east-1c"] }
  }

  mock_data "aws_region" {
    defaults = { region = "us-east-1" }
  }
}

variables {
  name       = "test"
  cidr_block = "10.99.0.0/16"
  az_count   = 2
}

run "single_nat_is_shared_by_every_private_subnet" {
  command = plan

  variables {
    single_nat_gateway = true
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 1 && length(aws_route.private_nat) == 2
    error_message = "One NAT gateway should serve both private route tables."
  }
}

run "one_nat_per_az_when_not_single" {
  command = plan

  variables {
    single_nat_gateway = false
  }

  assert {
    condition     = length(aws_nat_gateway.this) == 2
    error_message = "Expected a NAT gateway in each AZ."
  }
}

run "subnets_do_not_overlap_and_stay_private" {
  command = plan

  variables {
    single_nat_gateway = true
  }

  assert {
    condition     = aws_subnet.public[*].cidr_block == ["10.99.0.0/24", "10.99.1.0/24"]
    error_message = "Public subnets should be the first two /24s."
  }

  assert {
    condition     = aws_subnet.private[*].cidr_block == ["10.99.16.0/20", "10.99.32.0/20"]
    error_message = "Private subnets should be /20s above the public range."
  }

  assert {
    condition     = alltrue([for s in aws_subnet.public : s.map_public_ip_on_launch == false])
    error_message = "Nothing launched into a public subnet should get a public IP by default."
  }
}

run "rejects_small_vpc" {
  command = plan

  variables {
    cidr_block         = "10.99.0.0/20"
    single_nat_gateway = true
  }

  expect_failures = [var.cidr_block]
}
