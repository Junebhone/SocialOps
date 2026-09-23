variable "repository_names" {
  description = "One repository per image, e.g. socialops/api."
  type        = set(string)
}

variable "keep_tagged_images" {
  description = "How many tagged images to keep per repository. Older ones are expired."
  type        = number
  default     = 30
}

variable "untagged_expiry_days" {
  description = "Days before an untagged image (a superseded build layer) is expired."
  type        = number
  default     = 7
}
