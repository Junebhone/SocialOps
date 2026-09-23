# Three roles, split by who needs what:
#
#   execution  - used by ECS itself, before the app starts: pull the image,
#                create the log stream, read the DATABASE_URL secret.
#   api task   - the API at runtime: S3 for uploads, SQS to enqueue.
#   worker task- the worker at runtime: S3, SQS to consume, Bedrock to call a
#                model.
#
# The api role has no Bedrock access on purpose. The API never calls a model
# (worker/llm.py::complete() is the only place one is called, hard rule #4),
# so a model call from the API should fail on IAM before it can cost money.
# The web task gets no task role: it calls no AWS API at all.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = data.aws_region.current.region
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    # Confused-deputy guard: only ECS acting for this account may assume it.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

# --- Execution role ----------------------------------------------------------

resource "aws_iam_role" "execution" {
  name               = "${var.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    sid       = "ReadDatabaseUrl"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.database_url_secret_arn]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "read-database-url"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# --- Shared statements -------------------------------------------------------

data "aws_iam_policy_document" "assets_rw" {
  statement {
    sid       = "ListAssets"
    actions   = ["s3:ListBucket"]
    resources = [var.assets_bucket_arn]
  }

  statement {
    sid       = "ReadWriteAssets"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.assets_bucket_arn}/*"]
  }
}

# --- API task role -----------------------------------------------------------

resource "aws_iam_role" "api" {
  name               = "${var.name}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "api" {
  source_policy_documents = [data.aws_iam_policy_document.assets_rw.json]

  statement {
    sid       = "EnqueueJobs"
    actions   = ["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl"]
    resources = [var.queue_arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "api-runtime"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

# --- Worker task role --------------------------------------------------------

resource "aws_iam_role" "worker" {
  name               = "${var.name}-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "worker" {
  source_policy_documents = [data.aws_iam_policy_document.assets_rw.json]

  statement {
    sid = "ConsumeJobs"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:ChangeMessageVisibility",
      "sqs:SendMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
    ]
    resources = [var.queue_arn]
  }

  # LLM_PROVIDER=bedrock. Pydantic AI's Bedrock model uses the Converse API,
  # which is authorised by the InvokeModel actions. Foundation models are
  # matched in every region because cross-region inference profiles route a
  # call to whichever region has capacity.
  statement {
    sid = "InvokeModels"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:${local.partition}:bedrock:*::foundation-model/*",
      "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:inference-profile/*",
    ]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "worker-runtime"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}
