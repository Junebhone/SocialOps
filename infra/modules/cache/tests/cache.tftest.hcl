mock_provider "aws" {}

variables {
  name               = "test"
  subnet_ids         = ["subnet-a", "subnet-b"]
  security_group_ids = ["sg-cache"]
  node_type          = "cache.t4g.micro"
}

run "single_node_has_no_failover" {
  command = plan

  variables {
    num_cache_clusters = 1
  }

  assert {
    condition     = aws_elasticache_replication_group.this.automatic_failover_enabled == false
    error_message = "A single node has nothing to fail over to; AWS rejects failover here."
  }

  assert {
    condition     = aws_elasticache_replication_group.this.transit_encryption_enabled == true
    error_message = "Redis must require TLS in every environment."
  }
}

run "replicas_fail_over_across_azs" {
  command = plan

  variables {
    num_cache_clusters = 2
  }

  assert {
    condition = alltrue([
      aws_elasticache_replication_group.this.automatic_failover_enabled,
      aws_elasticache_replication_group.this.multi_az_enabled,
    ])
    error_message = "With a replica, failover and Multi-AZ should both be on."
  }
}

run "rejects_uppercase_id" {
  command = plan

  variables {
    name               = "SocialOps-Dev"
    num_cache_clusters = 1
  }

  expect_failures = [var.name]
}
