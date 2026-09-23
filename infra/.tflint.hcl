# tflint for every Terraform directory under infra/. Run from infra/:
#
#   tflint --init
#   tflint --recursive --config "$(pwd)/.tflint.hcl"
#
# The plugin version is pinned for the same reason the providers are: the same
# commit should produce the same lint result on every machine and in CI.

config {
  # Evaluate local module calls with the caller's values, so a bad instance
  # type in env/*.tfvars is caught where it is used.
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "aws" {
  enabled = true
  version = "0.49.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

# Every variable and output carries a description; keep it that way.
rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_documented_outputs" {
  enabled = true
}

rule "terraform_naming_convention" {
  enabled = true
}
