#!/usr/bin/env bash
#
# deploy.sh — Build, push, and deploy the application to AWS ECS.
#
# Usage:
#   ./deploy.sh [dev|staging|prod]
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Docker running
#   - Terraform outputs available (run `terraform output` in infra/)
#
set -euo pipefail

ENV="${1:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT="research-assist"

echo "==> Deploying ${PROJECT} to ${ENV} in ${AWS_REGION}"

# ── Step 1: Get Terraform outputs ─────────────────────────────────────────

cd "$(dirname "$0")/../infra"

ECR_BACKEND=$(terraform output -raw ecr_backend_url 2>/dev/null || echo "")
ECR_WORKER=$(terraform output -raw ecr_worker_url 2>/dev/null || echo "")
ECS_CLUSTER="${PROJECT}-${ENV}"
BACKEND_SERVICE="${PROJECT}-${ENV}-backend"
WORKER_SERVICE="${PROJECT}-${ENV}-worker"

if [ -z "$ECR_BACKEND" ] || [ -z "$ECR_WORKER" ]; then
  echo "ERROR: Could not read ECR URLs from Terraform. Run 'terraform apply' first."
  exit 1
fi

# ── Step 2: Authenticate Docker with ECR ──────────────────────────────────

echo "==> Logging in to ECR..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ── Step 3: Build and push images ─────────────────────────────────────────

cd "$(dirname "$0")/../backend"

echo "==> Building backend image..."
docker build -f Dockerfile.prod -t "${ECR_BACKEND}:latest" .

echo "==> Pushing backend image..."
docker push "${ECR_BACKEND}:latest"

echo "==> Building worker image..."
docker build -f Dockerfile.prod -t "${ECR_WORKER}:latest" .

echo "==> Pushing worker image..."
docker push "${ECR_WORKER}:latest"

# ── Step 4: Run database migrations ───────────────────────────────────────

echo "==> Running Alembic migrations..."
# This runs the migration as a one-off ECS task.
# For simplicity, we use the backend image with a migration command.
aws ecs run-task \
  --cluster "${ECS_CLUSTER}" \
  --task-definition "${PROJECT}-${ENV}-backend" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$(terraform output -json private_subnet_ids | jq -r 'join(",")' 2>/dev/null || echo "")],securityGroups=[],assignPublicIp=DISABLED}" \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": ["alembic", "upgrade", "head"]
    }]
  }' \
  --region "${AWS_REGION}" \
  --no-cli-pager \
  > /dev/null

echo "==> Migration task submitted."

# ── Step 5: Force new deployment ──────────────────────────────────────────

echo "==> Updating ECS backend service..."
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "${BACKEND_SERVICE}" \
  --force-new-deployment \
  --region "${AWS_REGION}" \
  --no-cli-pager \
  > /dev/null

echo "==> Updating ECS worker service..."
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "${WORKER_SERVICE}" \
  --force-new-deployment \
  --region "${AWS_REGION}" \
  --no-cli-pager \
  > /dev/null

echo ""
echo "==> Deployment initiated for ${ENV}."
echo "    Monitor progress in the AWS ECS console or with:"
echo "    aws ecs describe-services --cluster ${ECS_CLUSTER} --services ${BACKEND_SERVICE} ${WORKER_SERVICE}"
