variable "bucket_name" {
  description = "Globally unique bucket name. The caller appends the account ID to guarantee that."
  type        = string
}

variable "force_destroy" {
  description = "Let terraform destroy delete a non-empty bucket. true only where uploads are disposable."
  type        = bool
  default     = false
}

variable "infrequent_access_after_days" {
  description = "Move objects to STANDARD_IA after this many days. Uploaded photos are read heavily for a week, then rarely."
  type        = number
  default     = 90
}

variable "noncurrent_version_expiry_days" {
  description = "Delete overwritten or deleted versions after this many days."
  type        = number
  default     = 30
}
