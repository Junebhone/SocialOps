#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="us-east-2"
SECRET_ID="socialops/prod/database-url"

export NEXT_PUBLIC_API_URL="http://18.227.185.45:8000"
export ECR_REGISTRY="518668548718.dkr.ecr.us-east-2.amazonaws.com"
export IMAGE_TAG="${IMAGE_TAG:-v2}"

echo "Retrieving DATABASE_URL from AWS Secrets Manager..."

DATABASE_URL="$(
  sudo docker run --rm amazon/aws-cli \
    secretsmanager get-secret-value \
    --secret-id "$SECRET_ID" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text
)"

if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: DATABASE_URL secret was empty."
  exit 1
fi

echo "Secret retrieved successfully."

sudo env \
  DATABASE_URL="$DATABASE_URL" \
  NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
  ECR_REGISTRY="$ECR_REGISTRY" \
  IMAGE_TAG="$IMAGE_TAG" \
  docker compose \
    --env-file /dev/null \
    -f docker-compose.yml \
    -f docker-compose.registry.yml \
    -f docker-compose.cloud.yml \
    up -d --no-build

sudo env \
  DATABASE_URL="$DATABASE_URL" \
  NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
  ECR_REGISTRY="$ECR_REGISTRY" \
  IMAGE_TAG="$IMAGE_TAG" \
  docker compose \
    --env-file /dev/null \
    -f docker-compose.yml \
    -f docker-compose.registry.yml \
    -f docker-compose.cloud.yml \
    ps

unset DATABASE_URL
