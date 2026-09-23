# SQS job queue and its dead-letter queue: the target for the arq -> SQS move.
#
# Nothing consumes this yet. arq on ElastiCache is still the queue and the only
# retry layer (CLAUDE.md hard rule #7). It is provisioned now because the brief
# asks for the full target architecture, and because the worker's IAM role and
# SQS_QUEUE_URL can then be wired once rather than in the same change that
# swaps the queue library.
#
# The redrive count matches arq's max_tries, and the DLQ plays the role
# failed_jobs plays today, so the swap keeps the behaviour D12 settled.

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = var.dlq_retention_seconds
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "this" {
  name                       = var.name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = var.message_retention_seconds
  receive_wait_time_seconds  = 20 # long polling: fewer empty receives, lower cost
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

# Only this queue may dead-letter into the DLQ.
resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  queue_url = aws_sqs_queue.dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.this.arn]
  })
}

data "aws_iam_policy_document" "tls_only" {
  for_each = {
    main = aws_sqs_queue.this.arn
    dlq  = aws_sqs_queue.dlq.arn
  }

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["sqs:*"]
    resources = [each.value]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_sqs_queue_policy" "tls_only" {
  for_each = {
    main = aws_sqs_queue.this.id
    dlq  = aws_sqs_queue.dlq.id
  }

  queue_url = each.value
  policy    = data.aws_iam_policy_document.tls_only[each.key].json
}
