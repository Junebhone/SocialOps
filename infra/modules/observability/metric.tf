# Counts API responses with status 5xx from the JSON request logs.
#
# app/logging.py writes exactly one line per request. A response the app
# returned is logged as event "request" with its status_code; an unhandled
# exception is logged as event "request.failed" with status_code 500, because
# that is what Starlette sends the client. Matching on status_code alone counts
# both, and each failed request once.
#
# Health checks and every other non-request line have no status_code >= 500,
# so they never match. No line, no data point: the alarm treats missing data
# as not breaching.
resource "aws_cloudwatch_log_metric_filter" "api_5xx" {
  name           = "${var.name}-api-5xx"
  log_group_name = var.api_log_group_name
  pattern        = "{ $.status_code >= 500 }"

  metric_transformation {
    name      = "Api5xxCount"
    namespace = var.metric_namespace
    value     = "1"
    unit      = "Count"
  }
}
