output "endpoint" {
  value = aws_db_instance.main.endpoint
}

output "connection_url" {
  description = "PostgreSQL connection URL for application config."
  value       = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.main.endpoint}/${var.db_name}"
  sensitive   = true
}
