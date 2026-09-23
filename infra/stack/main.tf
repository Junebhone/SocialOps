# One copy of SocialOps: everything an environment needs, composed from
# ../modules. Which environment is decided by the workspace and the tfvars file
# together (see infra/README.md); nothing in here names dev or staging.
#
#   terraform workspace select dev
#   terraform plan -var-file=env/dev.tfvars
#
# The ECR repositories are NOT created here. They belong to the account
# (infra/bootstrap) because one image is promoted through every environment.

# Workspace guard. Plan and apply stop here, before any resource is read or
# changed, if the tfvars file and the workspace disagree: planning
# env/staging.tfvars while the dev workspace is selected would otherwise
# "update" dev's resources into staging's shape. It also keeps everything out
# of the default workspace, whose state key no environment owns.
data "aws_caller_identity" "current" {
  lifecycle {
    precondition {
      condition     = !var.require_workspace_match || terraform.workspace == var.environment
      error_message = "Workspace \"${terraform.workspace}\" does not match environment \"${var.environment}\". Run: terraform workspace select ${var.environment}   (or pass the matching env/<workspace>.tfvars)"
    }
  }
}

data "aws_ecr_repository" "this" {
  for_each = toset(["api", "worker", "web"])

  name = "${var.ecr_repository_prefix}/${each.key}"
}

locals {
  name       = "${var.project}-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id

  images = {
    for svc, repo in data.aws_ecr_repository.this : svc => "${repo.repository_url}:${var.image_tag}"
  }

  # The config.py contract (CLAUDE.md hard rule #1), filled from what this
  # stack created. DATABASE_URL is not here: it comes from Secrets Manager.
  app_environment = {
    REDIS_URL        = module.cache.redis_url
    STORAGE_BACKEND  = "s3"
    STORAGE_ROOT     = module.storage.bucket_name
    LLM_PROVIDER     = var.llm_provider
    LLM_MODEL_FAST   = var.llm_model_fast
    LLM_MODEL_TEXT   = var.llm_model_text
    LLM_MODEL_VISION = var.llm_model_vision
    OLLAMA_BASE_URL  = var.ollama_base_url
    AWS_REGION       = var.aws_region
    # Not read by config.py yet (extra="ignore" drops it). Wired now so the
    # arq -> SQS change needs a code change and no infrastructure change.
    SQS_QUEUE_URL = module.queue.queue_url
  }
}

module "network" {
  source = "../modules/network"

  name               = local.name
  cidr_block         = var.vpc_cidr
  az_count           = var.az_count
  single_nat_gateway = var.single_nat_gateway
}

module "security" {
  source = "../modules/security"

  name                  = local.name
  vpc_id                = module.network.vpc_id
  allowed_ingress_cidrs = var.allowed_ingress_cidrs
}

module "database" {
  source = "../modules/database"

  name               = local.name
  secret_name        = "${var.project}/${var.environment}/database-url"
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [module.security.db_security_group_id]

  instance_class        = var.db_instance_class
  multi_az              = var.db_multi_az
  backup_retention_days = var.db_backup_retention_days

  deletion_protection         = !var.disposable
  skip_final_snapshot         = var.disposable
  apply_immediately           = var.disposable
  secret_recovery_window_days = var.disposable ? 0 : 7
}

module "cache" {
  source = "../modules/cache"

  name               = local.name
  subnet_ids         = module.network.private_subnet_ids
  security_group_ids = [module.security.cache_security_group_id]

  node_type                = var.cache_node_type
  num_cache_clusters       = var.cache_num_nodes
  snapshot_retention_limit = var.disposable ? 0 : 3
  apply_immediately        = var.disposable
}

module "storage" {
  source = "../modules/storage"

  # Account ID suffix: bucket names are global, and two teammates bootstrapping
  # their own accounts must not collide.
  bucket_name   = "${local.name}-assets-${local.account_id}"
  force_destroy = var.disposable
}

module "queue" {
  source = "../modules/queue"

  name = "${local.name}-jobs"
}

module "iam" {
  source = "../modules/iam"

  name                    = local.name
  database_url_secret_arn = module.database.database_url_secret_arn
  assets_bucket_arn       = module.storage.bucket_arn
  queue_arn               = module.queue.queue_arn
}

module "alb" {
  source = "../modules/alb"

  name              = local.name
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  security_group_id = module.security.alb_security_group_id
}

module "ecs" {
  source = "../modules/ecs"

  name                    = local.name
  private_subnet_ids      = module.network.private_subnet_ids
  task_security_group_ids = module.security.task_security_group_ids
  execution_role_arn      = module.iam.execution_role_arn
  task_role_arns          = module.iam.task_role_arns
  target_group_arns       = module.alb.target_group_arns

  images                  = local.images
  app_environment         = local.app_environment
  database_url_secret_arn = module.database.database_url_secret_arn
  web_environment = {
    # The browser's address for the API, exactly as in compose (D17).
    NEXT_PUBLIC_API_URL     = module.alb.api_url
    NEXT_TELEMETRY_DISABLED = "1"
  }

  services           = var.services
  log_retention_days = var.log_retention_days
  container_insights = var.container_insights
}
