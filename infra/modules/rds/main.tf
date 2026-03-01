/**
 * RDS Module — PostgreSQL with pgvector extension.
 *
 * Creates:
 *   - DB subnet group (private subnets)
 *   - Security group allowing app traffic on port 5432
 *   - RDS instance with pgvector via parameter group
 */

# ── Security Group ───────────────────────────────────────────────────────────

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-${var.environment}-rds-sg"
  description = "Allow PostgreSQL from ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-${var.environment}-rds-sg" }
}

# ── Subnet Group ─────────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "${var.project_name}-${var.environment}-db-subnet" }
}

# ── Parameter Group (pgvector) ───────────────────────────────────────────────

resource "aws_db_parameter_group" "pgvector" {
  name   = "${var.project_name}-${var.environment}-pgvector"
  family = "postgres16"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pgvector"
    apply_method = "pending-reboot"
  }

  tags = { Name = "${var.project_name}-${var.environment}-pgvector-params" }
}

# ── RDS Instance ─────────────────────────────────────────────────────────────

resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-${var.environment}"

  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.pgvector.name

  # Don't expose publicly
  publicly_accessible = false

  # Backups
  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # Deletion protection (disable for dev)
  deletion_protection = var.environment == "prod" ? true : false
  skip_final_snapshot = var.environment != "prod"

  tags = { Name = "${var.project_name}-${var.environment}-postgres" }
}
