mock_provider "aws" {}

variables {
  repository_names = ["socialops/api", "socialops/worker"]
}

run "tags_are_immutable_and_images_scanned" {
  command = plan

  assert {
    condition     = alltrue([for r in aws_ecr_repository.this : r.image_tag_mutability == "IMMUTABLE"])
    error_message = "A git SHA tag must only ever point at one image."
  }

  assert {
    condition     = alltrue([for r in aws_ecr_repository.this : r.image_scanning_configuration[0].scan_on_push])
    error_message = "Every push should be scanned for known CVEs."
  }

  assert {
    condition     = length(jsondecode(aws_ecr_lifecycle_policy.this["socialops/api"].policy).rules) == 2
    error_message = "Each repository should expire untagged images and cap tagged ones."
  }
}
