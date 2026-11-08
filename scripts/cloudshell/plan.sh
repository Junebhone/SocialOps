#!/usr/bin/env bash
# Read-only: plans infra/bootstrap and infra/stack (dev) from AWS CloudShell.
# Nothing is applied. Prints only resource actions, no values.
export PATH="$HOME/bin:$PATH" AWS_PAGER="" TF_PLUGIN_CACHE_DIR="$HOME/.tfcache"
export TF_VAR_alert_email="${ALERT_EMAIL:?set ALERT_EMAIL first}"
mkdir -p "$TF_PLUGIN_CACHE_DIR"
B="socialops-tfstate-$(aws sts get-caller-identity --query Account --output text)"
PAT='^Plan:|No changes|Error|will be (created|updated|destroyed)|must be replaced'
rm -rf ~/so/infra/bootstrap/.terraform ~/so/infra/stack/.terraform
df -h ~ | tail -1
cd ~/so && git pull -q && git log --oneline -1

echo "=== BOOTSTRAP"
cd ~/so/infra/bootstrap
terraform init -input=false -backend-config="bucket=$B" > ~/init-bootstrap.txt 2>&1 || tail -5 ~/init-bootstrap.txt
terraform plan -input=false -no-color > ~/plan-bootstrap.txt 2>&1
grep -E "$PAT" ~/plan-bootstrap.txt

echo "=== STACK DEV"
cd ~/so/infra/stack
terraform init -input=false -backend-config="bucket=$B" > ~/init-stack.txt 2>&1 || tail -5 ~/init-stack.txt
terraform workspace select dev > /dev/null
echo "workspace: $(terraform workspace show)"
terraform plan -input=false -no-color -var-file=env/dev.tfvars > ~/plan-dev.txt 2>&1
grep -E "$PAT" ~/plan-dev.txt
