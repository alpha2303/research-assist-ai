# ── Outputs ───────────────────────────────────────────────────────────────────

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.ecs.alb_dns_name
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.redis_endpoint
}

output "s3_bucket_name" {
  description = "S3 bucket for document storage"
  value       = module.s3.bucket_name
}

output "ecr_backend_url" {
  description = "ECR repository URL for backend image"
  value       = module.ecs.ecr_backend_url
}

output "ecr_worker_url" {
  description = "ECR repository URL for worker image"
  value       = module.ecs.ecr_worker_url
}

output "dynamodb_sessions_table" {
  description = "DynamoDB chat sessions table name"
  value       = module.dynamodb.sessions_table_name
}

output "dynamodb_messages_table" {
  description = "DynamoDB chat messages table name"
  value       = module.dynamodb.messages_table_name
}
