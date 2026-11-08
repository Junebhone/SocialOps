# Alerting (Member 3): SNS topic, email subscription, and the 5xx alarm.
#
# The email subscription stays "PendingConfirmation" until someone clicks the
# link AWS sends. That click is the one manual step Terraform cannot do.

variable "alert_email" {
  description = "Address that receives alarm and OK notifications. Set in an uncommitted tfvars file, never in code."
  type        = string
  sensitive   = true
}

resource "aws_sns_topic" "alerts" {
  name = "${var.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Sum of 5xx responses in 60 s. A quiet minute publishes no data point, so
# missing data is "not breaching": silence means healthy, not broken.
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name}-api-5xx"
  alarm_description   = "The API returned at least one HTTP 5xx in the last 60 s (metric ${var.metric_namespace}/${aws_cloudwatch_log_metric_filter.api_5xx.metric_transformation[0].name}, counted from JSON request logs). Look at: CloudWatch dashboard ${var.name}, then the log group ${var.api_log_group_name} (search status_code >= 500; each line has a request_id)."
  namespace           = var.metric_namespace
  metric_name         = aws_cloudwatch_log_metric_filter.api_5xx.metric_transformation[0].name
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}
