# AWS Deployment Guide — Research Assist AI

Step-by-step instructions to deploy and run the Research Assist AI application on AWS.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Local Development Setup](#3-local-development-setup)
4. [AWS Infrastructure Provisioning](#4-aws-infrastructure-provisioning)
5. [Building and Pushing Docker Images](#5-building-and-pushing-docker-images)
6. [Database Migrations](#6-database-migrations)
7. [Deploying to ECS](#7-deploying-to-ecs)
8. [Automated Deployment (deploy.sh)](#8-automated-deployment-deploysh)
9. [Post-Deployment Verification](#9-post-deployment-verification)
10. [HTTPS Setup](#10-https-setup)
11. [Terraform Remote State (Teams)](#11-terraform-remote-state-teams)
12. [Monitoring and Alarms](#12-monitoring-and-alarms)
13. [Environment Variables Reference](#13-environment-variables-reference)
14. [Terraform Variables Reference](#14-terraform-variables-reference)
15. [Cost Estimates](#15-cost-estimates)
16. [Troubleshooting](#16-troubleshooting)
17. [Tearing Down Infrastructure](#17-tearing-down-infrastructure)

---

## 1. Architecture Overview

The application runs on AWS using the following services:

| Component        | AWS Service                  | Purpose                                  |
| ---------------- | ---------------------------- | ---------------------------------------- |
| Networking       | VPC, subnets, NAT Gateway   | Isolated network with public/private subnets |
| Backend API      | ECS Fargate + ALB            | Containerised FastAPI service (port 8000) |
| Celery Worker    | ECS Fargate                  | Async document processing                |
| Database         | RDS PostgreSQL 16 (pgvector) | Document chunks, vector embeddings       |
| Chat Storage     | DynamoDB                     | Chat sessions and messages (2 tables)    |
| Document Storage | S3                           | PDF document files                       |
| Cache / Broker   | ElastiCache Redis 7          | Celery message broker                    |
| Embeddings       | Amazon Bedrock (Titan V2)    | Vector embedding generation              |
| LLM              | Amazon Bedrock (Nova)        | Conversational AI (Micro/Lite/Pro)       |
| Monitoring       | CloudWatch Alarms            | ALB 5xx rate, ECS CPU utilisation        |

**Network topology:**
- ALB sits in **public subnets** (receives HTTP/HTTPS traffic)
- ECS tasks (backend + worker), RDS, and ElastiCache run in **private subnets**
- NAT Gateway allows outbound internet access from private subnets (for ECR image pulls, Bedrock API calls)

---

## 2. Prerequisites

Before deploying, ensure the following tools are installed and configured:

### 2.1 Required Tools

| Tool          | Version    | Install                                              |
| ------------- | ---------- | ---------------------------------------------------- |
| AWS CLI       | v2+        | https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html |
| Terraform     | ≥ 1.7      | https://developer.hashicorp.com/terraform/install     |
| Docker        | Latest     | https://docs.docker.com/get-docker/                  |
| jq            | Latest     | https://jqlang.github.io/jq/download/                |
| Git           | Latest     | https://git-scm.com/                                  |

### 2.2 AWS Account Setup

1. **Configure AWS CLI credentials:**

   ```bash
   aws configure
   # Enter: AWS Access Key ID, Secret Access Key, Default region (us-east-1), Output format (json)
   ```

2. **Enable Bedrock model access** — In the AWS Console:
   - Navigate to **Amazon Bedrock** → **Model access**
   - Request access to the following foundation models:
     - `amazon.titan-embed-text-v2:0` (embeddings)
     - `amazon.nova-micro-v1:0` (LLM)
     - `amazon.nova-lite-v1:0` (LLM)
     - `amazon.nova-pro-v1:0` (LLM)
   - Wait for access to be granted (usually instant for Amazon models)

3. **Verify your identity:**

   ```bash
   aws sts get-caller-identity
   ```

### 2.3 Required IAM Permissions

The IAM user/role running Terraform needs permissions to create:
- VPC, subnets, NAT Gateway, Internet Gateway, route tables
- ECS clusters, services, task definitions, ECR repositories
- RDS instances, subnet groups, parameter groups
- ElastiCache clusters, subnet groups
- DynamoDB tables
- S3 buckets
- IAM roles and policies
- CloudWatch alarms
- Application Load Balancers, target groups, listeners
- Security groups

> **Tip:** For initial setup, use an IAM user with `AdministratorAccess`. Scope down permissions for production CI/CD pipelines.

---

## 3. Local Development Setup

Before deploying to AWS, verify everything works locally using Docker Compose.

### 3.1 Start Local Services

```bash
# From the project root
docker-compose up -d
```

This starts:
- **PostgreSQL 16** with pgvector extension (`localhost:5432`)
- **Redis 7** (`localhost:6379`)
- **LocalStack** — local DynamoDB + S3 (`localhost:4566`)
- **Backend** — FastAPI with hot-reload (`localhost:8000`)
- **Celery Worker** — async document processing

### 3.2 Initialise Local DynamoDB Tables

```bash
cd backend
python scripts/init_dynamodb.py
```

### 3.3 Run Database Migrations

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/research_assist" \
  alembic upgrade head
```

### 3.4 Start Frontend (separately)

```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

### 3.5 Verify

```bash
curl http://localhost:8000/health
```

---

## 4. AWS Infrastructure Provisioning

All infrastructure is defined as Terraform modules in the `infra/` directory.

### 4.1 Initialise Terraform

```bash
cd infra
terraform init
```

This downloads the AWS provider (~5.0) and initialises the module tree.

### 4.2 Configure Variables

Copy the environment-specific variables file and customise:

```bash
# For development
cp environments/dev.tfvars my-dev.tfvars

# For production
cp environments/prod.tfvars my-prod.tfvars
```

**At minimum, set the database password.** Edit the file:

```hcl
# my-dev.tfvars
project_name    = "research-assist"
environment     = "dev"
aws_region      = "us-east-1"
aws_profile     = "default"

vpc_cidr          = "10.0.0.0/16"

db_instance_class = "db.t4g.micro"
db_name           = "research_assist"
db_username       = "research_admin"
db_password       = "YOUR_SECURE_PASSWORD_HERE"   # <-- CHANGE THIS

redis_node_type   = "cache.t4g.micro"

backend_cpu       = 512
backend_memory    = 1024
worker_cpu        = 512
worker_memory     = 1024
desired_count     = 1
```

> **Security:** Never commit `db_password` to version control. Instead, use one of:
> - CLI flag: `terraform apply -var="db_password=MySecurePass123!"`
> - Environment variable: `export TF_VAR_db_password="MySecurePass123!"`
> - AWS Secrets Manager (advanced)

### 4.3 Review the Plan

```bash
terraform plan -var-file=my-dev.tfvars
```

Review the output. Expect ~40 AWS resources to be created:
- 1 VPC, subnets, NAT Gateway, Internet Gateway
- 2 ECR repositories (backend + worker)
- 1 ECS cluster, 2 task definitions, 2 services
- 1 ALB with target group and listener
- 1 RDS PostgreSQL instance with pgvector
- 2 DynamoDB tables
- 1 S3 bucket
- 1 ElastiCache Redis cluster
- IAM roles and policies
- Security groups
- CloudWatch alarms

### 4.4 Apply

```bash
terraform apply -var-file=my-dev.tfvars
```

Type `yes` when prompted. Infrastructure provisioning takes **10–15 minutes** (RDS and NAT Gateway are the slowest).

### 4.5 Note the Outputs

After `terraform apply` completes, note the outputs:

```bash
terraform output
```

Key outputs:

| Output                    | Description                            |
| ------------------------- | -------------------------------------- |
| `alb_dns_name`            | URL to access the application          |
| `ecr_backend_url`         | ECR repo URL for backend Docker image  |
| `ecr_worker_url`          | ECR repo URL for worker Docker image   |
| `rds_endpoint`            | PostgreSQL connection endpoint         |
| `redis_endpoint`          | Redis connection endpoint              |
| `s3_bucket_name`          | S3 bucket for document storage         |
| `dynamodb_sessions_table` | DynamoDB table for chat sessions       |
| `dynamodb_messages_table` | DynamoDB table for chat messages       |
| `vpc_id`                  | VPC ID                                 |

---

## 5. Building and Pushing Docker Images

### 5.1 Authenticate Docker with ECR

```bash
AWS_REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
```

### 5.2 Build and Push Backend Image

The backend uses a multi-stage Docker build (`python:3.12-alpine` with `uv` for dependency resolution):

```bash
cd backend

# Get ECR URL from Terraform
ECR_BACKEND=$(cd ../infra && terraform output -raw ecr_backend_url)

# Build
docker build -f Dockerfile.prod -t "${ECR_BACKEND}:latest" .

# Push
docker push "${ECR_BACKEND}:latest"
```

### 5.3 Build and Push Worker Image

The worker uses the same Docker image as the backend (the entrypoint is overridden in the ECS task definition):

```bash
ECR_WORKER=$(cd ../infra && terraform output -raw ecr_worker_url)

docker build -f Dockerfile.prod -t "${ECR_WORKER}:latest" .
docker push "${ECR_WORKER}:latest"
```

### 5.4 Build and Push Frontend Image (Optional)

If serving the frontend from the same infrastructure:

```bash
cd frontend

# Build with API proxy configured to /api/
docker build -f Dockerfile.prod -t "${ECR_FRONTEND}:latest" .
docker push "${ECR_FRONTEND}:latest"
```

> **Note:** The frontend `Dockerfile.prod` includes an nginx configuration that proxies `/api/` requests to the backend service on port 8000 and serves the SPA with a fallback to `index.html`.

---

## 6. Database Migrations

### 6.1 About Migrations

The backend uses Alembic for database schema management. Migrations create:
- Tables: `projects`, `documents`, `document_chunks`, `project_documents`
- pgvector extension and vector columns for embeddings
- Full-text search tsvector triggers

### 6.2 Run Migrations via ECS (Recommended)

After pushing the backend image, run migrations as a one-off ECS task:

```bash
cd infra

ECS_CLUSTER="research-assist-dev"
TASK_DEFINITION="research-assist-dev-backend"
PRIVATE_SUBNETS=$(terraform output -json private_subnet_ids | jq -r 'join(",")')

aws ecs run-task \
  --cluster "${ECS_CLUSTER}" \
  --task-definition "${TASK_DEFINITION}" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${PRIVATE_SUBNETS}],securityGroups=[],assignPublicIp=DISABLED}" \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": ["alembic", "upgrade", "head"]
    }]
  }' \
  --region us-east-1 \
  --no-cli-pager
```

### 6.3 Run Migrations Locally (Alternative)

If you have direct access to the RDS instance (e.g., via SSH tunnel or VPN):

```bash
cd backend
DATABASE_URL="postgresql://research_admin:YOUR_PASSWORD@RDS_ENDPOINT:5432/research_assist" \
  alembic upgrade head
```

> **Note:** For local migration, use the sync driver (no `+asyncpg`). The `alembic/env.py` automatically strips `+asyncpg` if present.

---

## 7. Deploying to ECS

### 7.1 Force New Deployment

After pushing new images, tell ECS to pull and deploy them:

```bash
ECS_CLUSTER="research-assist-dev"

# Update backend service
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "research-assist-dev-backend" \
  --force-new-deployment \
  --region us-east-1 \
  --no-cli-pager > /dev/null

# Update worker service
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "research-assist-dev-worker" \
  --force-new-deployment \
  --region us-east-1 \
  --no-cli-pager > /dev/null
```

### 7.2 Monitor Deployment

```bash
# Watch service events
aws ecs describe-services \
  --cluster "research-assist-dev" \
  --services "research-assist-dev-backend" "research-assist-dev-worker" \
  --query 'services[].{name:serviceName,running:runningCount,desired:desiredCount,status:status}' \
  --output table
```

ECS performs a **rolling deployment** — new tasks start before old ones stop.

---

## 8. Automated Deployment (deploy.sh)

The project includes a deployment script that automates the entire process.

### 8.1 Usage

```bash
chmod +x scripts/deploy.sh

# Deploy to dev
./scripts/deploy.sh dev

# Deploy to production
./scripts/deploy.sh prod
```

### 8.2 What the Script Does

The `scripts/deploy.sh` script performs these steps automatically:

1. **Reads Terraform outputs** — gets ECR repository URLs, cluster name, service names
2. **Authenticates Docker with ECR** — `aws ecr get-login-password`
3. **Builds and pushes Docker images** — both backend and worker images from `Dockerfile.prod`
4. **Runs Alembic migrations** — submits a one-off ECS Fargate task with `alembic upgrade head`
5. **Forces new ECS deployment** — tells both backend and worker services to pull the latest image

### 8.3 Prerequisites for deploy.sh

- AWS CLI configured with appropriate credentials
- Docker running locally
- Terraform already applied (`terraform output` must return valid values)
- Working directory must be the project root

### 8.4 Environment Variable

The script defaults to `us-east-1`. Override with:

```bash
AWS_REGION=eu-west-1 ./scripts/deploy.sh dev
```

---

## 9. Post-Deployment Verification

### 9.1 Get the Application URL

```bash
cd infra
terraform output alb_dns_name
```

### 9.2 Health Check

```bash
ALB_DNS=$(cd infra && terraform output -raw alb_dns_name)

curl http://${ALB_DNS}/health
# Expected: {"status": "healthy"}
```

### 9.3 Test API Endpoints

```bash
# List projects
curl http://${ALB_DNS}/api/v1/projects

# Create a project
curl -X POST http://${ALB_DNS}/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Project", "description": "Testing deployment"}'
```

### 9.4 Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster "research-assist-dev" \
  --services "research-assist-dev-backend" \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount,deployments:deployments[*].{status:status,running:runningCount,desired:desiredCount}}' \
  --output json
```

### 9.5 View Application Logs

```bash
# Backend logs
aws logs tail "/ecs/research-assist-dev-backend" --follow --region us-east-1

# Worker logs
aws logs tail "/ecs/research-assist-dev-worker" --follow --region us-east-1
```

---

## 10. HTTPS Setup

The ALB is created with an HTTP listener on port 80 and an HTTPS listener placeholder on port 443. To enable HTTPS:

### 10.1 Request an ACM Certificate

```bash
aws acm request-certificate \
  --domain-name yourdomain.com \
  --validation-method DNS \
  --region us-east-1
```

### 10.2 Validate the Certificate

1. Note the `CertificateArn` from the output
2. Create the DNS CNAME record provided by ACM (in Route 53 or your DNS provider)
3. Wait for validation (usually a few minutes)

### 10.3 Add HTTPS Listener

Add to the ECS module or manually via AWS Console:

```bash
ALB_ARN=$(aws elbv2 describe-load-balancers \
  --names "research-assist-dev-alb" \
  --query 'LoadBalancers[0].LoadBalancerArn' \
  --output text)

TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups \
  --names "research-assist-dev-tg" \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text)

aws elbv2 create-listener \
  --load-balancer-arn "${ALB_ARN}" \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID \
  --default-actions Type=forward,TargetGroupArn="${TARGET_GROUP_ARN}"
```

### 10.4 (Optional) HTTP→HTTPS Redirect

Modify the existing HTTP listener to redirect:

```bash
LISTENER_ARN=$(aws elbv2 describe-listeners \
  --load-balancer-arn "${ALB_ARN}" \
  --query 'Listeners[?Port==`80`].ListenerArn' \
  --output text)

aws elbv2 modify-listener \
  --listener-arn "${LISTENER_ARN}" \
  --default-actions '[{
    "Type": "redirect",
    "RedirectConfig": {
      "Protocol": "HTTPS",
      "Port": "443",
      "StatusCode": "HTTP_301"
    }
  }]'
```

### 10.5 Custom Domain (Route 53)

Create an alias record pointing your domain to the ALB:

```bash
# In Route 53, create an A record (alias) for yourdomain.com
# pointing to the ALB DNS name
```

---

## 11. Terraform Remote State (Teams)

For team environments, enable remote state storage so multiple people can apply changes safely.

### 11.1 Create State Resources

```bash
# S3 bucket for state file
aws s3 mb s3://research-assist-terraform-state --region us-east-1

# DynamoDB table for state locking
aws dynamodb create-table \
  --table-name research-assist-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### 11.2 Enable the Backend

Uncomment the `backend "s3"` block in `infra/main.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "research-assist-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "research-assist-terraform-lock"
    encrypt        = true
  }
}
```

### 11.3 Migrate State

```bash
cd infra
terraform init -migrate-state
```

Terraform will prompt to copy the local state to S3. Confirm with `yes`.

---

## 12. Monitoring and Alarms

The `cloudwatch` Terraform module creates the following alarms:

| Alarm                  | Condition                     | Action                |
| ---------------------- | ----------------------------- | --------------------- |
| ALB 5xx Error Rate     | > threshold in 5 min          | CloudWatch (SNS optional) |
| ECS CPU Utilisation    | > threshold for backend       | CloudWatch (SNS optional) |

### 12.1 View Alarms

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix "research-assist" \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue}' \
  --output table
```

### 12.2 View ECS Metrics

```bash
# Task CPU utilisation
aws cloudwatch get-metric-statistics \
  --namespace "AWS/ECS" \
  --metric-name CPUUtilization \
  --dimensions Name=ClusterName,Value=research-assist-dev Name=ServiceName,Value=research-assist-dev-backend \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --output table
```

### 12.3 Add SNS Notifications (Optional)

To receive email/SMS alerts, create an SNS topic and subscribe:

```bash
# Create topic
TOPIC_ARN=$(aws sns create-topic --name research-assist-alerts --query TopicArn --output text)

# Subscribe email
aws sns subscribe --topic-arn "${TOPIC_ARN}" --protocol email --notification-endpoint your@email.com

# Link to CloudWatch alarm (update alarm to add action)
aws cloudwatch put-metric-alarm \
  --alarm-name "research-assist-dev-alb-5xx" \
  --alarm-actions "${TOPIC_ARN}" \
  # ... (include existing alarm configuration)
```

---

## 13. Environment Variables Reference

### Backend Application (ECS Task)

These are automatically configured by Terraform and injected into ECS task definitions:

| Variable                         | Required | Description                                      | Example                                     |
| -------------------------------- | -------- | ------------------------------------------------ | ------------------------------------------- |
| `DATABASE_URL`                   | Yes      | PostgreSQL connection URL (asyncpg driver)       | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL`                      | Yes      | Redis connection URL                             | `redis://redis-host:6379/0`                 |
| `S3_BUCKET_NAME`                 | Yes      | S3 bucket name for document storage              | `research-assist-dev-documents`             |
| `DYNAMODB_CHAT_SESSIONS_TABLE`   | Yes      | DynamoDB table name for chat sessions            | `research-assist-dev-chat-sessions`         |
| `DYNAMODB_CHAT_MESSAGES_TABLE`   | Yes      | DynamoDB table name for chat messages            | `research-assist-dev-chat-messages`         |
| `AWS_REGION`                     | Yes      | AWS region for Bedrock, DynamoDB, S3             | `us-east-1`                                 |
| `ENVIRONMENT`                    | No       | Deployment environment                           | `dev`, `staging`, `prod`                    |
| `AWS_PROFILE`                    | No       | AWS CLI profile (local dev only)                 | `default`                                   |
| `DYNAMODB_ENDPOINT_URL`          | No       | Custom DynamoDB endpoint (LocalStack)            | `http://localstack:4566`                    |
| `S3_ENDPOINT_URL`                | No       | Custom S3 endpoint (LocalStack)                  | `http://localstack:4566`                    |

### Celery Worker (ECS Task)

Same as the backend except DynamoDB variables are not included (the worker doesn't directly access chat storage).

---

## 14. Terraform Variables Reference

All variables are defined in `infra/variables.tf`:

| Variable           | Type   | Default            | Description                               |
| ------------------ | ------ | ------------------ | ----------------------------------------- |
| `project_name`     | string | `research-assist`  | Prefix for all AWS resource names         |
| `environment`      | string | `dev`              | Environment name (dev/staging/prod)       |
| `aws_region`       | string | `us-east-1`        | AWS region for all resources              |
| `aws_profile`      | string | `default`          | AWS CLI named profile                     |
| `vpc_cidr`         | string | `10.0.0.0/16`      | CIDR block for the VPC                    |
| `db_instance_class`| string | `db.t4g.micro`     | RDS instance size                         |
| `db_name`          | string | `research_assist`  | PostgreSQL database name                  |
| `db_username`      | string | `research_admin`   | Database master username                  |
| `db_password`      | string | *(sensitive)*       | Database master password — **must set**   |
| `redis_node_type`  | string | `cache.t4g.micro`  | ElastiCache node type                     |
| `backend_cpu`      | number | `512`              | Backend task CPU units (1024 = 1 vCPU)    |
| `backend_memory`   | number | `1024`             | Backend task memory (MiB)                 |
| `worker_cpu`       | number | `512`              | Worker task CPU units                     |
| `worker_memory`    | number | `1024`             | Worker task memory (MiB)                  |
| `desired_count`    | number | `1`                | Number of backend + worker ECS tasks      |

### Environment Presets

**Dev** (`environments/dev.tfvars`):
- `db.t4g.micro`, `cache.t4g.micro`, 512/1024 CPU/memory, 1 task

**Prod** (`environments/prod.tfvars`):
- `db.t4g.medium`, `cache.t4g.small`, worker gets 1024/2048, 2 tasks, VPC `10.1.0.0/16`

---

## 15. Cost Estimates

### Development Environment (~$90/month)

| Resource              | ~Monthly Cost |
| --------------------- | ------------- |
| NAT Gateway           | $32           |
| RDS (db.t4g.micro)    | $13           |
| ElastiCache (t4g.micro)| $12          |
| ECS Fargate (2 tasks) | $15           |
| ALB                   | $16           |
| S3 / DynamoDB         | < $1          |
| **Total**             | **~$90/mo**   |

### Production Environment (~$200/month)

| Resource               | ~Monthly Cost |
| ---------------------- | ------------- |
| NAT Gateway            | $32           |
| RDS (db.t4g.medium)    | $50           |
| ElastiCache (t4g.small)| $25           |
| ECS Fargate (4 tasks)  | $40           |
| ALB                    | $16           |
| S3 / DynamoDB          | < $5          |
| Bedrock usage          | Variable      |
| **Total**              | **~$200/mo**  |

> Costs vary by region and usage. Bedrock charges are usage-based. Use the [AWS Pricing Calculator](https://calculator.aws/) for precise estimates.

---

## 16. Troubleshooting

### ECS Tasks Failing to Start

```bash
# Check stopped task reason
aws ecs describe-tasks \
  --cluster "research-assist-dev" \
  --tasks $(aws ecs list-tasks --cluster research-assist-dev --desired-status STOPPED --query 'taskArns[0]' --output text) \
  --query 'tasks[0].{reason:stoppedReason,container:containers[0].{reason:reason,exit:exitCode}}' \
  --output json
```

Common issues:
- **Image not found**: Verify ECR push completed successfully
- **Health check failing**: Ensure the backend `/health` endpoint responds with 200
- **Environment variables missing**: Check the ECS task definition environment section

### Database Connection Errors

- Verify the RDS instance is in the same VPC and private subnets
- Check that the ECS task security group allows outbound to RDS (port 5432)
- Confirm the `DATABASE_URL` uses the correct host, port, username, and password

### Bedrock Access Denied

- Ensure model access is enabled in the Bedrock console for your region
- Verify the ECS task IAM role has the Bedrock `InvokeModel` and `InvokeModelWithResponseStream` permissions
- Check that you're deploying to one of the regions where Bedrock models are available (e.g., `us-east-1`)

### Migration Failures

```bash
# View migration task logs
aws logs filter-log-events \
  --log-group-name "/ecs/research-assist-dev-backend" \
  --filter-pattern "alembic" \
  --start-time $(date -u -d '30 minutes ago' +%s000) \
  --output text
```

### Cannot Access ALB

- Verify the ALB security group allows inbound on port 80 (and 443 for HTTPS)
- Confirm the ALB is in public subnets with an Internet Gateway route
- Check target group health: `aws elbv2 describe-target-health --target-group-arn <ARN>`

---

## 17. Tearing Down Infrastructure

> **Warning:** This permanently deletes **all** AWS resources including the database and all stored data. Ensure you have backups before proceeding.

### 17.1 Destroy All Resources

```bash
cd infra
terraform destroy -var-file=my-dev.tfvars
```

Type `yes` to confirm. Destruction takes **5–10 minutes**.

### 17.2 Clean Up ECR Images (Optional)

ECR repositories may retain images. To delete:

```bash
# Delete all images in backend ECR repo
aws ecr batch-delete-image \
  --repository-name "research-assist-dev-backend" \
  --image-ids "$(aws ecr list-images --repository-name research-assist-dev-backend --query 'imageIds[*]' --output json)"

# Delete all images in worker ECR repo
aws ecr batch-delete-image \
  --repository-name "research-assist-dev-worker" \
  --image-ids "$(aws ecr list-images --repository-name research-assist-dev-worker --query 'imageIds[*]' --output json)"
```

### 17.3 Clean Up Remote State (If Enabled)

```bash
# Remove state bucket and lock table
aws s3 rb s3://research-assist-terraform-state --force
aws dynamodb delete-table --table-name research-assist-terraform-lock
```

---

## Quick Reference: Full Deployment from Scratch

```bash
# 1. Clone and navigate
git clone <repo-url>
cd research-assist-ai

# 2. Provision infrastructure
cd infra
terraform init
terraform apply -var-file=environments/dev.tfvars -var="db_password=YourSecurePassword123!"

# 3. Deploy application
cd ..
chmod +x scripts/deploy.sh
./scripts/deploy.sh dev

# 4. Verify
ALB_DNS=$(cd infra && terraform output -raw alb_dns_name)
curl http://${ALB_DNS}/health

# 5. Access the application
echo "Application URL: http://${ALB_DNS}"
```
