output "dns_name" {
  description = "Public DNS name of the ALB."
  value       = aws_lb.this.dns_name
}

output "arn" {
  description = "ARN of the ALB."
  value       = aws_lb.this.arn
}

output "web_url" {
  description = "Where the dashboard is served."
  value       = "http://${aws_lb.this.dns_name}"
}

output "api_url" {
  description = "The API as the browser sees it. Becomes NEXT_PUBLIC_API_URL."
  value       = "http://${aws_lb.this.dns_name}:${var.api_listener_port}"
}

# The target groups are handed to ECS services. An ECS service cannot attach
# to a target group that no listener uses yet ("target group does not have an
# associated load balancer"), so these outputs wait for the listeners.
output "target_group_arns" {
  description = "Target group per load-balanced service: web and api."
  value = {
    web = aws_lb_target_group.web.arn
    api = aws_lb_target_group.api.arn
  }

  depends_on = [aws_lb_listener.web, aws_lb_listener.api]
}
