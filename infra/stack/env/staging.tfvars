# staging: production-shaped. Everything survives the loss of one AZ, data is
# protected from destroy, and every service runs two tasks so a rolling deploy
# never drops to zero. Roughly 3-4x the cost of dev, almost all of it NAT
# gateways, the Multi-AZ database and the Redis replica.

environment = "staging"
aws_region  = "us-east-1"
disposable  = false

vpc_cidr           = "10.20.0.0/16"
single_nat_gateway = false

# No auth in Phase 1. Replace with your team's addresses before running apply.
allowed_ingress_cidrs = ["0.0.0.0/0"]

db_instance_class        = "db.t4g.small"
db_multi_az              = true
db_backup_retention_days = 7

cache_node_type = "cache.t4g.small"
cache_num_nodes = 2

services = {
  api    = { cpu = 512, memory = 1024, desired_count = 2 }
  worker = { cpu = 512, memory = 1024, desired_count = 2 }
  web    = { cpu = 1024, memory = 2048, desired_count = 2 }
}

# Promote a build by copying the SHA dev has been running into this line.
image_tag = "8d183a315eb18fff3e5745a40297c8e13b7dcf6d"

# The config.py contract for models (tier -> model, D6). Ollama is the local
# default and does not run on AWS, so AWS environments use Bedrock. Current
# Claude models on Bedrock are called through a cross-region inference profile,
# hence the us. prefix; the worker role allows both profiles and base models.
llm_provider     = "bedrock"
llm_model_fast   = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
llm_model_text   = "us.anthropic.claude-sonnet-5-v1:0"
llm_model_vision = "us.anthropic.claude-sonnet-5-v1:0"

log_retention_days = 30
container_insights = true
