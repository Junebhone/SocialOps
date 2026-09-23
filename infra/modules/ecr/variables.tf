variable "repository_names" {
  description = "One repository per image, e.g. socialops/api."
  type        = set(string)
}

variable "untagged_expiry_days" {
  description = "Days before an untagged image (a superseded build layer) is expired."
  type        = number
  default     = 7
}
