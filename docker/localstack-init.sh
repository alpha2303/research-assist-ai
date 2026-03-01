#!/bin/bash
# LocalStack initialization script
# Runs automatically on container startup via /etc/localstack/init/ready.d/
# Creates S3 buckets and DynamoDB tables needed for local development.

set -euo pipefail

echo "==> Initializing LocalStack resources..."

# ── S3 Bucket ─────────────────────────────────────────────────────────────────

BUCKET_NAME="research-assist-documents-dev"

if awslocal s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
  echo "  S3 bucket already exists: ${BUCKET_NAME}"
else
  awslocal s3 mb "s3://${BUCKET_NAME}"
  echo "  Created S3 bucket: ${BUCKET_NAME}"
fi

# ── DynamoDB Tables ───────────────────────────────────────────────────────────

SESSIONS_TABLE="research-assist-chat-sessions-dev"
MESSAGES_TABLE="research-assist-chat-messages-dev"

# Chat sessions table
if awslocal dynamodb describe-table --table-name "${SESSIONS_TABLE}" >/dev/null 2>&1; then
  echo "  DynamoDB table already exists: ${SESSIONS_TABLE}"
else
  awslocal dynamodb create-table \
    --table-name "${SESSIONS_TABLE}" \
    --key-schema AttributeName=chat_id,KeyType=HASH \
    --attribute-definitions \
      AttributeName=chat_id,AttributeType=S \
      AttributeName=project_id,AttributeType=S \
      AttributeName=updated_at,AttributeType=S \
    --global-secondary-indexes '[{
      "IndexName": "project_id-updated_at-index",
      "KeySchema": [
        {"AttributeName": "project_id", "KeyType": "HASH"},
        {"AttributeName": "updated_at", "KeyType": "RANGE"}
      ],
      "Projection": {"ProjectionType": "ALL"},
      "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
    }]' \
    --billing-mode PROVISIONED \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
  echo "  Created DynamoDB table: ${SESSIONS_TABLE}"
fi

# Chat messages table
if awslocal dynamodb describe-table --table-name "${MESSAGES_TABLE}" >/dev/null 2>&1; then
  echo "  DynamoDB table already exists: ${MESSAGES_TABLE}"
else
  awslocal dynamodb create-table \
    --table-name "${MESSAGES_TABLE}" \
    --key-schema \
      AttributeName=chat_id,KeyType=HASH \
      AttributeName=message_id,KeyType=RANGE \
    --attribute-definitions \
      AttributeName=chat_id,AttributeType=S \
      AttributeName=message_id,AttributeType=S \
    --billing-mode PROVISIONED \
    --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
  echo "  Created DynamoDB table: ${MESSAGES_TABLE}"
fi

echo "==> LocalStack initialization complete."
