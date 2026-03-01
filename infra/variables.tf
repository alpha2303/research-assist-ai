# ── General ───────────────────────────────────────────────────────────────────

variable "project_name" {
  description = "Project name used as prefix for all resources."
  type        = string
  default     = "research-assist"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region to deploy resources to."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile to use."
  type        = string
  default     = "default"
}

# ── Networking ────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

# ── RDS ───────────────────────────────────────────────────────────────────────

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "research_assist"
}

variable "db_username" {
  description = "Database master username."
  type        = string
  default     = "research_admin"
}

variable "db_password" {
  description = "Database master password."
  type        = string
  sensitive   = true
}

# ── ElastiCache ───────────────────────────────────────────────────────────────

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"
}

# ── ECS ───────────────────────────────────────────────────────────────────────

variable "backend_cpu" {
  description = "CPU units for backend task (1024 = 1 vCPU)."
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Memory (MiB) for backend task."
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  description = "CPU units for Celery worker task."
  type        = number
  default     = 512
}

variable "worker_memory" {
  description = "Memory (MiB) for Celery worker task."
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Desired number of backend service tasks."
  type        = number
  default     = 1
}
