# Switch for GET /debug/error (the controlled 5xx used in the Milestone 6 demo).
#
# The services ignore task_definition changes (pipeline deploys must not be
# drift), so an environment variable could never be flipped on a running service.
# The API reads this parameter at request time instead. Terraform creates it as
# "false" and ignores later edits, so toggling it never shows up in a plan:
#
#   aws ssm put-parameter --name /<name>/enable-error-route --value true  --overwrite
#   aws ssm put-parameter --name /<name>/enable-error-route --value false --overwrite
resource "aws_ssm_parameter" "error_route" {
  name        = "/${local.name}/enable-error-route"
  type        = "String"
  value       = "false"
  description = "true makes GET /debug/error return a deliberate 500. Keep false except during a demo."

  lifecycle {
    ignore_changes = [value]
  }
}
