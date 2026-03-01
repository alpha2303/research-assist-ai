variable "project_name" { type = string }
variable "environment" { type = string }
variable "aws_region" { type = string }
variable "account_id" { type = string }
variable "s3_bucket_arn" { type = string }
variable "dynamodb_table_arns" { type = list(string) }
