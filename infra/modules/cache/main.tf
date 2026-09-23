# ElastiCache Redis for the arq queue.
#
# arq stays the queue and the only retry mechanism (CLAUDE.md hard rule #7);
# this is the same Redis 7 compose runs, made managed. The SQS queue in
# modules/queue is provisioned for the later arq -> SQS move and is not a
# second queue in use.
#
# A replication group rather than a single aws_elasticache_cluster because
# in-transit encryption is only available on replication groups, and because
# going from one node to a replica with failover is then a variable change.

locals {
  replicated = var.num_cache_clusters > 1
}

resource "aws_elasticache_subnet_group" "this" {
  name       = var.name
  subnet_ids = var.subnet_ids
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = var.name
  description          = "arq job queue for ${var.name}"

  engine         = "redis"
  engine_version = var.engine_version
  # The default group is deliberate: arq needs no non-default Redis settings,
  # and a custom group is one more resource to keep in step with the version.
  # tflint-ignore: aws_elasticache_replication_group_default_parameter_group
  parameter_group_name = var.parameter_group_name
  node_type            = var.node_type
  port                 = 6379

  num_cache_clusters         = var.num_cache_clusters
  automatic_failover_enabled = local.replicated
  multi_az_enabled           = local.replicated

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = var.security_group_ids

  at_rest_encryption_enabled = true
  # TLS, so the URL scheme is rediss://. arq's RedisSettings.from_dsn turns
  # that scheme into ssl=True, so no code change is needed.
  transit_encryption_enabled = true

  snapshot_retention_limit = var.snapshot_retention_limit
  apply_immediately        = var.apply_immediately
}
