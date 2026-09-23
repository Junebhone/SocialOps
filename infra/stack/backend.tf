# Remote state in the bucket infra/bootstrap creates.
#
# The bucket name contains the AWS account ID, and a backend block cannot read
# variables, so it is supplied at init instead of written here:
#
#   terraform init -backend-config="bucket=socialops-tfstate-<account-id>"
#
# (infra/bootstrap prints that exact command as an output.)
#
# One state file per workspace. With workspace_key_prefix = "env", the dev
# workspace's state is at env/dev/socialops/terraform.tfstate and staging's at
# env/staging/socialops/terraform.tfstate. The default workspace is refused
# (see the guard in main.tf), so nothing is ever written to the bare key.
terraform {
  backend "s3" {
    key = "socialops/terraform.tfstate"
    # The state bucket's region: infra/bootstrap's aws_region. Moving to
    # another region means changing it there, here, and in env/*.tfvars.
    region               = "us-east-1"
    workspace_key_prefix = "env"
    encrypt              = true

    # Two locks. S3-native locking (use_lockfile) is Terraform's current
    # mechanism. The DynamoDB table is what the Module 3 brief asks for;
    # Terraform 1.16 still honours it but prints a deprecation warning on
    # init. Remove this line, and the table in infra/bootstrap, once the brief
    # no longer needs it.
    use_lockfile   = true
    dynamodb_table = "socialops-tflock"
  }
}
