# dev: cheapest shape that still exercises every component. Disposable data,
# one NAT gateway, single-AZ database, one Redis node, one task per service.

environment = "dev"
aws_region  = "us-east-1"
disposable  = true

vpc_cidr           = "10.10.0.0/16"
single_nat_gateway = true

# No auth in Phase 1. Replace with your team's addresses (e.g. "203.0.113.7/32")
# before running apply. Plan does not care.
allowed_ingress_cidrs = ["0.0.0.0/0"]

db_instance_class        = "db.t4g.micro"
db_multi_az              = false
db_backup_retention_days = 1

cache_node_type = "cache.t4g.micro"
cache_num_nodes = 1

services = {
  api    = { cpu = 256, memory = 512, desired_count = 1 }
  worker = { cpu = 512, memory = 1024, desired_count = 1 }
  web    = { cpu = 1024, memory = 2048, desired_count = 1 } # next build runs at start
}

# The full git SHA to deploy. CI pushes every merge to main under its SHA;
# deploy a new build by changing this line in a PR. 8d183a3 is the merge of
# PR #4, the first build CI pushed to ECR.
image_tag = "8d183a315eb18fff3e5745a40297c8e13b7dcf6d"

# The config.py contract for models (tier -> model, D6). Ollama is the local
# default and does not run on AWS, so AWS environments use Bedrock. Current
# Claude models on Bedrock are called through a cross-region inference profile,
# hence the us. prefix; the worker role allows both profiles and base models.
llm_provider     = "bedrock"
llm_model_fast   = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
llm_model_text   = "us.anthropic.claude-sonnet-5-v1:0"
llm_model_vision = "us.anthropic.claude-sonnet-5-v1:0"

log_retention_days = 7
