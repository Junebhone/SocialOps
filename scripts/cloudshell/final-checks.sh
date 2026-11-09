#!/usr/bin/env bash
# Milestone 6 final checks from CloudShell: create the dashboard, prove the plan is clean
# (refresh on) after the pipeline deploys, and run the security checklist. No secrets printed.
export PATH="$HOME/bin:$PATH" AWS_PAGER="" TF_PLUGIN_CACHE_DIR="/tmp/tfcache" TMPDIR="/tmp"
export TF_VAR_alert_email="${ALERT_EMAIL:?set ALERT_EMAIL first}"
mkdir -p "$TF_PLUGIN_CACHE_DIR"
B="socialops-tfstate-$(aws sts get-caller-identity --query Account --output text)"
cd ~/so && git pull -q && git log --oneline -1
cd ~/so/infra/stack
terraform init -input=false -backend-config="bucket=$B" > /tmp/init.txt 2>&1 || { tail -5 /tmp/init.txt; exit 1; }
terraform workspace select dev > /dev/null; echo "workspace: $(terraform workspace show)"

echo "=== 1. DASHBOARD"
terraform plan -input=false -no-color -out=/tmp/tfplan -var-file=env/dev.tfvars > /tmp/plan1.txt 2>&1
L=$(grep -E '^Plan:|^No changes' /tmp/plan1.txt); echo "$L"
case "$L" in
  "Plan: 1 to add, 0 to change, 0 to destroy.") terraform apply -input=false -no-color /tmp/tfplan 2>&1 | grep -E "Apply complete|Error|Cause" ;;
  No\ changes*) echo "dashboard already exists" ;;
  *) echo "ABORT: unexpected plan"; grep -E "will be|must be" /tmp/plan1.txt; exit 1 ;;
esac

echo "=== 2. PLAN IS CLEAN? (refresh on, after 3 pipeline deploys + SSM toggles)"
terraform plan -input=false -no-color -detailed-exitcode -var-file=env/dev.tfvars > ~/terraform-plan-final.txt 2>&1
echo "exit code $? (0 = no changes, 2 = changes, 1 = error)"
grep -E '^Plan:|^No changes|^Error|will be (created|updated|destroyed)|must be replaced' ~/terraform-plan-final.txt

echo "=== 3. SECURITY CHECKLIST"
echo "RDS publicly accessible: $(aws rds describe-db-instances --query 'DBInstances[?DBInstanceIdentifier==`socialops-dev`].PubliclyAccessible' --output text)"
SG=$(aws rds describe-db-instances --query 'DBInstances[?DBInstanceIdentifier==`socialops-dev`].VpcSecurityGroups[0].VpcSecurityGroupId' --output text)
echo "RDS SG ingress CIDRs (should be empty): $(aws ec2 describe-security-groups --group-ids "$SG" --query 'SecurityGroups[0].IpPermissions[].IpRanges[].CidrIp' --output text)"
BK=$(terraform output -raw assets_bucket 2>/dev/null)
echo "S3 public access block ($BK): $(aws s3api get-public-access-block --bucket "$BK" --query 'PublicAccessBlockConfiguration.[BlockPublicAcls,BlockPublicPolicy,RestrictPublicBuckets]' --output text 2>&1 | head -1)"
echo "Secrets Manager (names only): $(aws secretsmanager list-secrets --query 'SecretList[].Name' --output text)"
echo "Budgets: $(aws budgets describe-budgets --account-id "$(aws sts get-caller-identity --query Account --output text)" --query 'Budgets[].BudgetName' --output text)"
echo "IAM users with access keys on socialops: $(aws iam list-users --query "Users[?contains(UserName,'socialops')].UserName" --output text)"
echo "error route switch: $(aws ssm get-parameter --name /socialops-dev/enable-error-route --query Parameter.Value --output text)"
echo "ECS: $(aws ecs describe-services --cluster socialops-dev --services api web worker --query 'services[].[serviceName,runningCount]' --output text | tr '\n' ' ')"
echo "=== 4. DASHBOARD EXISTS?"
aws cloudwatch list-dashboards --query 'DashboardEntries[].DashboardName' --output text
echo "us-east-2 RDS (cost, not touched): $(aws rds describe-db-instances --region us-east-2 --query 'DBInstances[].[DBInstanceIdentifier,DBInstanceStatus]' --output text)"
