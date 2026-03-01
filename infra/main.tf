/**
 * Research Assist AI — AWS Infrastructure
 *
 * Root Terraform configuration.  Orchestrates all modules and manages the
 * remote state backend.
 *
 * Usage:
 *   cd infra
 *   terraform init
 *   terraform plan -var-file="environments/dev.tfvars"
 *   terraform apply -var-file="environments/dev.tfvars"
 */

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — uncomment after bootstrapping the S3 bucket & DynamoDB table.
  # backend "s3" {
  #   bucket         = "research-assist-terraform-state"
  #   key            = "state/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "research-assist-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  default_tags {
    tags = {
      Project     = "research-assist-ai"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ── Data sources ─────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── Modules ──────────────────────────────────────────────────────────────────

module "vpc" {
  source = "./modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
}

module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
}

module "dynamodb" {
  source = "./modules/dynamodb"

  project_name = var.project_name
  environment  = var.environment
}

module "rds" {
  source = "./modules/rds"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  db_instance_class  = var.db_instance_class
  db_name            = var.db_name
  db_username        = var.db_username
  db_password        = var.db_password
  app_security_group_id = module.ecs.ecs_tasks_security_group_id
}

module "elasticache" {
  source = "./modules/elasticache"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  app_security_group_id = module.ecs.ecs_tasks_security_group_id
  node_type          = var.redis_node_type
}

module "iam" {
  source = "./modules/iam"

  project_name          = var.project_name
  environment           = var.environment
  aws_region            = var.aws_region
  account_id            = data.aws_caller_identity.current.account_id
  s3_bucket_arn         = module.s3.bucket_arn
  dynamodb_table_arns   = module.dynamodb.table_arns
}

module "ecs" {
  source = "./modules/ecs"

  project_name          = var.project_name
  environment           = var.environment
  aws_region            = var.aws_region
  vpc_id                = module.vpc.vpc_id
  public_subnet_ids     = module.vpc.public_subnet_ids
  private_subnet_ids    = module.vpc.private_subnet_ids
  ecs_task_role_arn     = module.iam.ecs_task_role_arn
  ecs_execution_role_arn = module.iam.ecs_execution_role_arn
  database_url          = module.rds.connection_url
  redis_url             = module.elasticache.redis_url
  s3_bucket_name        = module.s3.bucket_name
  dynamodb_sessions_table = module.dynamodb.sessions_table_name
  dynamodb_messages_table = module.dynamodb.messages_table_name
  backend_cpu           = var.backend_cpu
  backend_memory        = var.backend_memory
  worker_cpu            = var.worker_cpu
  worker_memory         = var.worker_memory
  desired_count         = var.desired_count
}

module "cloudwatch" {
  source = "./modules/cloudwatch"

  project_name       = var.project_name
  environment        = var.environment
  ecs_cluster_name   = module.ecs.cluster_name
  ecs_service_name   = module.ecs.service_name
  alb_arn_suffix     = module.ecs.alb_arn_suffix
  target_group_arn_suffix = module.ecs.target_group_arn_suffix
}
