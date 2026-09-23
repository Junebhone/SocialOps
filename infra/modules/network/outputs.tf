output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnets: the ALB and NAT gateways only."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnets: Fargate tasks, RDS and ElastiCache."
  value       = aws_subnet.private[*].id
}

output "availability_zones" {
  description = "The AZs the subnets were placed in."
  value       = local.azs
}

output "nat_gateway_count" {
  description = "How many NAT gateways this environment pays for."
  value       = local.nat_count
}
