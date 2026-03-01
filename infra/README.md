# Infrastructure — Terraform

This directory contains the Terraform configuration for deploying `research-assist-ai` to AWS.

## Architecture

| Component       | AWS Service                  | Purpose                            |
| --------------- | ---------------------------- | ---------------------------------- |
| Networking      | VPC, subnets, NAT Gateway   | Isolated network with public/private subnets |
| Backend API     | ECS Fargate + ALB            | Containerised FastAPI service      |
| Celery Worker   | ECS Fargate                  | Async document processing          |
| Database        | RDS PostgreSQL 16 (pgvector) | Document chunks, embeddings        |
| Chat Storage    | DynamoDB                     | Chat sessions and messages         |
| Object Storage  | S3                           | PDF document files                 |
| Cache / Broker  | ElastiCache Redis 7          | Celery message broker              |
| Embeddings      | Amazon Bedrock (Titan)       | Vector embedding generation        |
| LLM             | Amazon Bedrock (Nova)        | Conversational AI                  |
| Monitoring      | CloudWatch Alarms            | ALB 5xx, ECS CPU alarms           |

## Directory Structure

```
infra/
├── main.tf                   # Root module — providers, module calls
├── variables.tf              # Root input variables
├── outputs.tf                # Root outputs
├── environments/
│   └── dev.tfvars            # Dev environment variable values
└── modules/
    ├── vpc/                  # VPC, subnets, NAT, routes
    ├── s3/                   # Document storage bucket
    ├── dynamodb/             # Chat tables
    ├── rds/                  # PostgreSQL + pgvector
    ├── elasticache/          # Redis for Celery
    ├── iam/                  # ECS execution & task roles
    ├── ecs/                  # ECS cluster, services, ALB, ECR
    └── cloudwatch/           # Alarms
```

## Prerequisites

1. **AWS CLI** configured with credentials (`aws configure`)
2. **Terraform ≥ 1.7** installed
3. **Docker** running locally (for building images)

## Getting Started

### 1. Initialise Terraform

```bash
cd infra
terraform init
```

### 2. Create your variables file

Copy the example and fill in values:

```bash
cp environments/dev.tfvars my.tfvars
# Edit my.tfvars — at minimum set db_password
```

### 3. Plan

```bash
terraform plan -var-file=my.tfvars
```

Review the plan carefully. Expected resources: ~40 AWS resources.

### 4. Apply

```bash
terraform apply -var-file=my.tfvars
```

### 5. Build and deploy containers

After `terraform apply` completes:

```bash
cd ..
chmod +x scripts/deploy.sh
./scripts/deploy.sh dev
```

This will:
- Login to ECR
- Build backend and worker Docker images
- Push to ECR
- Run Alembic database migrations
- Force a new ECS deployment

### 6. Verify

```bash
# Get ALB DNS name
terraform output alb_dns_name

# Test health endpoint
curl http://<alb-dns>/health
```

## Environment Configuration

### State Backend (Recommended for teams)

Uncomment the `backend "s3"` block in `main.tf` and create the S3 bucket + DynamoDB lock table:

```bash
aws s3 mb s3://research-assist-terraform-state
aws dynamodb create-table \
  --table-name research-assist-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### Secrets Management

Sensitive values (e.g. `db_password`) should not be committed to version control.

Options:
- Pass via CLI: `terraform apply -var="db_password=..."` 
- Use environment variables: `export TF_VAR_db_password=...`
- Use AWS Secrets Manager or SSM Parameter Store and reference in task definitions

## Tear Down

```bash
terraform destroy -var-file=my.tfvars
```

> **Warning**: This will delete all AWS resources including the database. Ensure you have backups.

## Cost Estimate (Dev)

Using `dev.tfvars` defaults (t4g.micro instances, single-AZ NAT):

| Resource        | ~Monthly Cost |
| --------------- | ------------- |
| NAT Gateway     | $32           |
| RDS (t4g.micro) | $13           |
| ElastiCache     | $12           |
| ECS Fargate     | $15           |
| ALB             | $16           |
| S3 / DynamoDB   | < $1          |
| **Total**       | **~$90/mo**   |

Costs vary by region and usage. Use the [AWS Pricing Calculator](https://calculator.aws/) for precise estimates.
