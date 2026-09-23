#!/usr/bin/env bash
# Every Terraform check that needs no AWS account: formatting, validation,
# lint, and the mocked-provider tests for both environments.
#
# `make tf-check` runs this locally and CI runs the same script on every pull
# request, so "it passed on my machine" and "it passed in CI" mean the same
# thing. Needs terraform and tflint on PATH (versions in .terraform-version and
# infra/.tflint.hcl).
set -euo pipefail

cd "$(dirname "$0")/../infra"

export TF_IN_AUTOMATION=1
export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-$HOME/.terraform.d/plugin-cache}"
mkdir -p "$TF_PLUGIN_CACHE_DIR"

ENVIRONMENTS=(dev staging)
TFLINT_CONFIG="$(pwd)/.tflint.hcl"

step() { printf '\n==> %s\n' "$*"; }

# Run a command quietly: one summary line when it passes, the whole output
# when it fails, so a CI log shows exactly which assertion broke.
check() {
  local label=$1 out
  shift
  if out=$("$@" 2>&1); then
    printf '  %-22s %s\n' "$label" "$(printf '%s\n' "$out" | grep -v '^$' | tail -1)"
  else
    printf '  %-22s FAILED\n%s\n' "$label" "$out"
    return 1
  fi
}

step "terraform fmt"
terraform fmt -check -recursive -diff

step "terraform init + validate"
for dir in stack bootstrap modules/*/; do
  dir="${dir%/}"
  check "$dir (init)" terraform -chdir="$dir" init -backend=false -input=false -no-color
  check "$dir" terraform -chdir="$dir" validate -no-color
done

step "tflint"
tflint --init --config "$TFLINT_CONFIG" >/dev/null
tflint --recursive --config "$TFLINT_CONFIG" --format compact
# The recursive pass cannot see tfvars values; this pass checks each
# environment's instance types and sizes where they are used.
for env in "${ENVIRONMENTS[@]}"; do
  printf '  stack with env/%s.tfvars\n' "$env"
  tflint --chdir=stack --config "$TFLINT_CONFIG" --var-file="env/$env.tfvars" --format compact
done

step "terraform test (mocked AWS provider, no credentials)"
for env in "${ENVIRONMENTS[@]}"; do
  check "stack [$env]" terraform -chdir=stack test -no-color -var-file="env/$env.tfvars"
done
for dir in bootstrap modules/*/; do
  dir="${dir%/}"
  [ -d "$dir/tests" ] || continue
  check "$dir" terraform -chdir="$dir" test -no-color
done

step "all Terraform checks passed"
