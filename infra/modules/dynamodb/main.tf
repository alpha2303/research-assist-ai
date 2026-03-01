/**
 * DynamoDB Module — chat storage tables.
 *
 * Tables:
 *   - chat_sessions: partition key = chat_id, GSI on project_id
 *   - chat_messages: partition key = chat_id, sort key = timestamp
 */

resource "aws_dynamodb_table" "chat_sessions" {
  name         = "${var.project_name}-chat-sessions-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chat_id"

  attribute {
    name = "chat_id"
    type = "S"
  }

  attribute {
    name = "project_id"
    type = "S"
  }

  global_secondary_index {
    name            = "project_id-index"
    hash_key        = "project_id"
    projection_type = "ALL"
  }

  tags = { Name = "${var.project_name}-chat-sessions-${var.environment}" }
}

resource "aws_dynamodb_table" "chat_messages" {
  name         = "${var.project_name}-chat-messages-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "chat_id"
  range_key    = "timestamp"

  attribute {
    name = "chat_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = { Name = "${var.project_name}-chat-messages-${var.environment}" }
}
