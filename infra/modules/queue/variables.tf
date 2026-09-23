variable "name" {
  description = "Queue name. The dead-letter queue is this with -dlq appended."
  type        = string
}

variable "max_receive_count" {
  description = "Deliveries before a message moves to the DLQ. 3 mirrors arq's max_tries in worker/worker/main.py."
  type        = number
  default     = 3
}

variable "visibility_timeout_seconds" {
  description = "Must exceed the longest job. arq's job_timeout is 300s; 330 leaves room to delete the message after."
  type        = number
  default     = 330
}

variable "message_retention_seconds" {
  description = "How long an unconsumed job waits in the main queue."
  type        = number
  default     = 345600 # 4 days
}

variable "dlq_retention_seconds" {
  description = "How long a dead-lettered job waits. The maximum, so nobody loses a failure to a long weekend."
  type        = number
  default     = 1209600 # 14 days
}
