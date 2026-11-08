output "api_5xx_metric_name" {
  description = "Metric the 5xx filter publishes. alarms.tf and dashboard.tf read it."
  value       = aws_cloudwatch_log_metric_filter.api_5xx.metric_transformation[0].name
}

output "metric_namespace" {
  description = "Namespace of the custom metrics."
  value       = aws_cloudwatch_log_metric_filter.api_5xx.metric_transformation[0].namespace
}

output "api_5xx_filter_name" {
  description = "Name of the metric filter on the API log group."
  value       = aws_cloudwatch_log_metric_filter.api_5xx.name
}

output "alerts_topic_arn" {
  description = "SNS topic the alarm notifies."
  value       = aws_sns_topic.alerts.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name."
  value       = aws_cloudwatch_dashboard.this.dashboard_name
}
