variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "ecs_task_role_arn" { type = string }
variable "ecs_execution_role_arn" { type = string }

variable "database_url" {
  type      = string
  sensitive = true
}
variable "redis_url" { type = string }
variable "s3_bucket_name" { type = string }
variable "dynamodb_sessions_table" { type = string }
variable "dynamodb_messages_table" { type = string }

variable "backend_cpu" { type = number }
variable "backend_memory" { type = number }
variable "worker_cpu" { type = number }
variable "worker_memory" { type = number }
variable "desired_count" { type = number }
