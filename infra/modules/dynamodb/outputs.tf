output "sessions_table_name" {
  value = aws_dynamodb_table.chat_sessions.name
}

output "messages_table_name" {
  value = aws_dynamodb_table.chat_messages.name
}

output "table_arns" {
  value = [
    aws_dynamodb_table.chat_sessions.arn,
    aws_dynamodb_table.chat_messages.arn,
  ]
}
