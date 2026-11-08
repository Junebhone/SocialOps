# Dashboard (Member 3): errors, ECS and database resource usage, ALB traffic.
# Built with jsonencode from resource attributes so names are never hard-coded.

variable "cluster_name" {
  description = "ECS cluster name, from module.ecs.cluster_name."
  type        = string
}

variable "service_names" {
  description = "ECS service name per service, from module.ecs.service_names."
  type        = map(string)
}

variable "alb_arn" {
  description = "ARN of the load balancer, from module.alb.arn."
  type        = string
}

variable "target_group_arns" {
  description = "Target group ARN per service, from module.alb.target_group_arns."
  type        = map(string)
}

variable "db_instance_identifier" {
  description = "RDS instance identifier, from module.database.instance_identifier."
  type        = string
}

data "aws_region" "current" {}

locals {
  # CloudWatch dimensions use the ARN suffix: "app/<name>/<id>" and "targetgroup/<name>/<id>".
  alb_dimension = split("loadbalancer/", var.alb_arn)[1]
  api_tg_dim    = "targetgroup/${split("targetgroup/", var.target_group_arns["api"])[1]}"
  region        = data.aws_region.current.region
  services      = sort(keys(var.service_names))
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = var.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title   = "API 5xx responses (Sum per 60 s)"
          region  = local.region
          view    = "timeSeries"
          stat    = "Sum"
          period  = 60
          metrics = [[var.metric_namespace, aws_cloudwatch_log_metric_filter.api_5xx.metric_transformation[0].name]]
          annotations = {
            alarms = [aws_cloudwatch_metric_alarm.api_5xx.arn]
          }
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "ALB requests and 5xx"
          region = local.region
          view   = "timeSeries"
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", local.alb_dimension],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", local.alb_dimension],
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", local.alb_dimension],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "ECS CPU utilization (%)"
          region = local.region
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [for s in local.services :
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.cluster_name, "ServiceName", var.service_names[s]]
          ]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "ECS memory utilization (%)"
          region = local.region
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [for s in local.services :
            ["AWS/ECS", "MemoryUtilization", "ClusterName", var.cluster_name, "ServiceName", var.service_names[s]]
          ]
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6
        properties = {
          title   = "ALB target response time (API, s)"
          region  = local.region
          view    = "timeSeries"
          stat    = "Average"
          period  = 60
          metrics = [["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", local.alb_dimension, "TargetGroup", local.api_tg_dim]]
        }
      },
      {
        type = "metric", x = 12, y = 12, width = 12, height = 6
        properties = {
          title   = "RDS CPU utilization (%)"
          region  = local.region
          view    = "timeSeries"
          stat    = "Average"
          period  = 60
          metrics = [["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.db_instance_identifier]]
        }
      },
    ]
  })
}
