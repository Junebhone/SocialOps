variable "name" {
  description = "Prefix for every resource name, e.g. socialops-dev."
  type        = string
}

variable "cidr_block" {
  description = "VPC CIDR. Give each environment its own range so they can be peered later without renumbering."
  type        = string

  validation {
    condition     = can(cidrhost(var.cidr_block, 0)) && tonumber(split("/", var.cidr_block)[1]) <= 16
    error_message = "cidr_block must be a valid IPv4 CIDR of /16 or larger; the subnet maths below carves /24s and /20s out of it."
  }
}

variable "az_count" {
  description = "How many availability zones to spread subnets across. RDS and the ALB both need at least two."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "single_nat_gateway" {
  description = "One shared NAT gateway (cheap, one AZ is a single point of failure) or one per AZ."
  type        = bool
}
