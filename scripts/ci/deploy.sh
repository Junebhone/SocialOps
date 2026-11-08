#!/usr/bin/env bash
# Deploy helpers for the "deploy" job in .github/workflows/ci.yml.
#
# Usage: deploy.sh <record|check_images|register|migrate|update|verify|rollback>
#
# Inputs (environment): CLUSTER, REGION, IMAGE_TAG (the commit SHA), ECR_PREFIX,
# API_URL, WEB_URL, plus the state the earlier subcommands leave in
# $STATE_DIR (default .deploy-state): prev-<svc> and new-<svc> hold task
# definition ARNs. Nothing here prints a secret: task definitions reference
# Secrets Manager by ARN only.
set -euo pipefail

CLUSTER="${CLUSTER:-socialops-dev}"
REGION="${REGION:-us-east-1}"
ECR_PREFIX="${ECR_PREFIX:-socialops}"
API_URL="${API_URL:-https://api.socialops.website}"
WEB_URL="${WEB_URL:-https://app.socialops.website}"
STATE_DIR="${STATE_DIR:-.deploy-state}"
SERVICES=(api worker web)
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"

mkdir -p "$STATE_DIR"
export AWS_DEFAULT_REGION="$REGION" AWS_PAGER=""

summary() { echo "$*" >> "$SUMMARY"; }
revision() { echo "${1##*/}"; }

registry() {
  echo "$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${REGION}.amazonaws.com"
}

# The repository holding the image for a task family. migrate reuses the api image.
image_for() {
  local svc="$1" repo="$1"
  [ "$svc" = migrate ] && repo=api
  echo "$(registry)/${ECR_PREFIX}/${repo}:${IMAGE_TAG}"
}

# 1. Remember what is running now. This is the rollback target.
record() {
  summary "### Rollback target (running before this deploy)"
  for svc in "${SERVICES[@]}"; do
    td=$(aws ecs describe-services --cluster "$CLUSTER" --services "$svc" \
           --query 'services[0].taskDefinition' --output text)
    echo "$td" > "$STATE_DIR/prev-$svc"
    summary "- \`$svc\`: \`$(revision "$td")\`"
  done
}

# 2. The new image must exist before anything changes.
check_images() {
  for svc in api worker web; do
    aws ecr describe-images --repository-name "${ECR_PREFIX}/${svc}" \
      --image-ids "imageTag=${IMAGE_TAG}" >/dev/null \
      || { echo "::error::image ${ECR_PREFIX}/${svc}:${IMAGE_TAG} not in ECR"; exit 1; }
  done
}

# Register a copy of the family's current task definition with a new image.
# Only the image changes; everything else (env, secrets, roles, sizing) is
# carried over, which is why Terraform sees no drift.
register_one() {
  local family="$1" svc="$2" current
  current=$(aws ecs describe-task-definition --task-definition "$family" \
              --query taskDefinition --output json)
  echo "$current" | jq --arg svc "$svc" --arg img "$(image_for "$svc")" '
      del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
          .compatibilities, .registeredAt, .registeredBy, .deregisteredAt)
      | .containerDefinitions |= map(if .name == $svc then .image = $img else . end)' \
    > "$STATE_DIR/$svc.json"
  aws ecs register-task-definition --cli-input-json "file://$STATE_DIR/$svc.json" \
    --query taskDefinition.taskDefinitionArn --output text > "$STATE_DIR/new-$svc"
}

register() {
  summary "### New task definition revisions (image tag \`${IMAGE_TAG}\`)"
  for svc in "${SERVICES[@]}" migrate; do
    register_one "${CLUSTER}-${svc}" "$svc"
    summary "- \`$svc\`: \`$(revision "$(cat "$STATE_DIR/new-$svc")")\`"
  done
}

# 3. Migrations first, on the new image, before any service sees the new code.
migrate() {
  local net task exit_code
  net=$(aws ecs describe-services --cluster "$CLUSTER" --services api \
          --query 'services[0].networkConfiguration' --output json)
  task=$(aws ecs run-task --cluster "$CLUSTER" --launch-type FARGATE \
           --task-definition "$(cat "$STATE_DIR/new-migrate")" \
           --network-configuration "$net" \
           --query 'tasks[0].taskArn' --output text)
  echo "migrate task: $task"
  aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$task"
  exit_code=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$task" \
                --query 'tasks[0].containers[0].exitCode' --output text)
  summary "### Migration"
  if [ "$exit_code" != "0" ]; then
    summary "Migration task exited with code \`$exit_code\`. No service was changed."
    local id="${task##*/}"
    aws logs get-log-events --log-group-name "/ecs/${CLUSTER}/migrate" \
      --log-stream-name "ecs/migrate/${id}" --query 'events[].message' --output text || true
    exit 1
  fi
  summary "Migration task exited 0."
}

# 4. Point each service at its new revision and wait for ECS to settle.
update() {
  for svc in "${SERVICES[@]}"; do
    aws ecs update-service --cluster "$CLUSTER" --service "$svc" \
      --task-definition "$(cat "$STATE_DIR/new-$svc")" >/dev/null
  done
  aws ecs wait services-stable --cluster "$CLUSTER" --services "${SERVICES[@]}"
}

# 5. Health over the public HTTPS URLs, with retries. The web root answers 307
# (redirect), so follow redirects and require 200 at the end.
health() {
  local tries="${1:-10}" delay="${2:-15}" i api web
  for i in $(seq 1 "$tries"); do
    api=$(curl -fsS --max-time 10 "$API_URL/health/ready" 2>/dev/null || true)
    web=$(curl -sS -L --max-time 10 -o /dev/null -w '%{http_code}' "$WEB_URL" 2>/dev/null || true)
    echo "try $i/$tries: api=${api:-none} web=${web:-none}"
    if echo "$api" | jq -e '.status == "ok"' >/dev/null 2>&1 && [ "$web" = "200" ]; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

# Every running task must be on the revision we expect: proves the new (or,
# after a rollback, the old) version is the one serving.
running_on() {
  local prefix="$1" svc want tds
  for svc in "${SERVICES[@]}"; do
    want=$(cat "$STATE_DIR/$prefix-$svc")
    tds=$(aws ecs list-tasks --cluster "$CLUSTER" --service-name "$svc" --desired-status RUNNING \
            --query 'taskArns' --output text | xargs -r aws ecs describe-tasks --cluster "$CLUSTER" \
            --query 'tasks[].taskDefinitionArn' --output text --tasks)
    [ -n "$tds" ] || { echo "$svc: no running tasks"; return 1; }
    for td in $tds; do
      [ "$td" = "$want" ] || { echo "$svc runs $(revision "$td"), expected $(revision "$want")"; return 1; }
    done
    echo "$svc runs $(revision "$want")"
  done
}

verify() {
  summary "### Health check"
  if health 10 15 && running_on new; then
    summary "Healthy on the new revisions: $(for s in "${SERVICES[@]}"; do printf '%s ' "$(revision "$(cat "$STATE_DIR/new-$s")")"; done)"
  else
    summary "Health check FAILED after deploy."
    return 1
  fi
}

# Automatic rollback: back to the recorded revisions, then prove the old
# version answers. The ECS circuit breaker only catches tasks that never start;
# this catches a deployment that starts, stays up, and is unhealthy.
rollback() {
  for svc in "${SERVICES[@]}"; do
    aws ecs update-service --cluster "$CLUSTER" --service "$svc" \
      --task-definition "$(cat "$STATE_DIR/prev-$svc")" >/dev/null
  done
  aws ecs wait services-stable --cluster "$CLUSTER" --services "${SERVICES[@]}"
  summary "### Rollback"
  if health 10 15 && running_on prev; then
    summary "ROLLED BACK to $(for s in "${SERVICES[@]}"; do printf '%s=%s ' "$s" "$(revision "$(cat "$STATE_DIR/prev-$s")")"; done)"
    summary "Old version verified: health check passed."
  else
    summary "ROLLBACK FAILED to verify healthy. Manual action needed."
  fi
  exit 1  # the run must show red either way
}

"${1:?subcommand required}"
