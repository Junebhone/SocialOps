output "dns_name" {
  description = "Public DNS name of the ALB."
  value       = aws_lb.this.dns_name
}

output "arn" {
  description = "ARN of the ALB."
  value       = aws_lb.this.arn
}

output "zone_id" {
  description = "Route 53 hosted zone ID of the ALB."
  value       = aws_lb.this.zone_id
}

output "web_url" {
  description = "Where the dashboard is served."
  value       = "https://${var.web_hostname}"
}

output "api_url" {
  description = "The API as the browser sees it. Becomes NEXT_PUBLIC_API_URL."
  value       = "https://${var.api_hostname}"
}

output "target_group_arns" {
  description = "Target group per load-balanced service: web and api."

  value = {
    web = aws_lb_target_group.web.arn
    api = aws_lb_target_group.api.arn
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener_rule.web,
    aws_lb_listener_rule.api,
  ]
}
