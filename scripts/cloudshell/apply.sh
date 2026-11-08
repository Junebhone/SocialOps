#!/usr/bin/env bash
# Applies the reviewed Milestone 6 changes from AWS CloudShell.
# Each root is planned to a file, the plan's counts must match what was reviewed,
# and only then is that exact plan file applied. Any other count aborts.
set -uo pipefail
export PATH="$HOME/bin:$PATH" AWS_PAGER="" TF_PLUGIN_CACHE_DIR="/tmp/tfcache" TMPDIR="/tmp"
export TF_VAR_alert_email="${ALERT_EMAIL:?set ALERT_EMAIL first}"
mkdir -p "$TF_PLUGIN_CACHE_DIR"
B="socialops-tfstate-$(aws sts get-caller-identity --query Account --output text)"
cd ~/so && git pull -q && git log --oneline -1

run_root() { # dir expected-plan-line [extra plan args...]
  local dir="$1" want="$2"; shift 2
  cd "$dir" || exit 1
  terraform init -input=false -backend-config="bucket=$B" > /tmp/init.txt 2>&1 || { tail -5 /tmp/init.txt; exit 1; }
  [ "$dir" = ~/so/infra/stack ] && terraform workspace select dev > /dev/null
  terraform plan -input=false -no-color -out=/tmp/tfplan "$@" > /tmp/plan.txt 2>&1 || { tail -20 /tmp/plan.txt; exit 1; }
  local got; got=$(grep -E '^Plan:' /tmp/plan.txt)
  echo "plan: $got"
  if [ "$got" != "$want" ]; then echo "ABORT: expected '$want'"; exit 1; fi
  terraform apply -input=false -no-color /tmp/tfplan 2>&1 | grep -E "Apply complete|Error|Creation complete|Modifications complete|Destruction complete" 
}

echo "=== BOOTSTRAP"
run_root ~/so/infra/bootstrap "Plan: 2 to add, 0 to change, 0 to destroy."
terraform output -raw ci_deploy_role_arn; echo

echo "=== STACK DEV"
run_root ~/so/infra/stack "Plan: 9 to add, 1 to change, 3 to destroy." -var-file=env/dev.tfvars
echo "=== SNS subscription"
aws sns list-subscriptions-by-topic --topic-arn "$(terraform output -raw alerts_topic_arn 2>/dev/null || aws sns list-topics --query "Topics[?contains(TopicArn,'socialops-dev-alerts')].TopicArn" --output text)" --query 'Subscriptions[].[Protocol,SubscriptionArn]' --output text
