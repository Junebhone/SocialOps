# Container registries, shared by every environment.
#
# One image is built per commit and promoted between environments by changing
# image_tag in that environment's tfvars, never rebuilt. So the repositories
# belong to the account (infra/bootstrap), not to a workspace.
#
# IMMUTABLE tags: a git SHA can only ever point at one image. A plan that says
# "deploy abc123" then means the same bytes in dev and in staging.
#
# Tagged images are never expired automatically. ECR cannot know which SHA an
# environment's tfvars pins, so a count-based rule would eventually delete the
# image staging runs. Its next task replacement or rollback would then fail to
# pull. Old tags are deleted by hand once no tfvars file references them
# (infra/README.md, "What it costs").

resource "aws_ecr_repository" "this" {
  for_each = var.repository_names

  name                 = each.value
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after ${var.untagged_expiry_days} days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_expiry_days
        }
        action = { type = "expire" }
      },
    ]
  })
}
