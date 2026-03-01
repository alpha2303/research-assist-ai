"""Initialize DynamoDB tables for chat sessions and messages.

This script creates the required DynamoDB tables with appropriate indexes.
Safe to run multiple times (idempotent - tables are created only if they don't exist).

Usage:
    python scripts/init_dynamodb.py
    
Environment Variables Required:
    - AWS_PROFILE: AWS profile name (default: "default")
    - AWS_REGION: AWS region (default: "us-east-1")
    - DYNAMODB_ENDPOINT_URL: Optional, for LocalStack (e.g., "http://localhost:4566")
"""

import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import boto3
from botocore.exceptions import ClientError
from app.core.config import get_settings


def create_chat_sessions_table(dynamodb_resource):
    """Create chat_sessions table.
    
    Schema:
        PK: chat_id (String) - UUID of chat session
        SK: project_id (String) - UUID of parent project
        Attributes:
            - title (String)
            - created_at (String) - ISO 8601 timestamp
            - updated_at (String) - ISO 8601 timestamp
            - message_count (Number) - count of messages in chat
            - running_summary (String) - accumulated conversation summary
            - summary_through_index (Number) - last message index included in summary
    
    Indexes:
        - GSI: project_id-updated_at-index (for listing chats in a project)
    """
    settings = get_settings()
    table_name = settings.dynamodb_chat_sessions_table
    
    try:
        table = dynamodb_resource.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'chat_id', 'KeyType': 'HASH'},  # Partition key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'chat_id', 'AttributeType': 'S'},
                {'AttributeName': 'project_id', 'AttributeType': 'S'},
                {'AttributeName': 'updated_at', 'AttributeType': 'S'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'project_id-updated_at-index',
                    'KeySchema': [
                        {'AttributeName': 'project_id', 'KeyType': 'HASH'},
                        {'AttributeName': 'updated_at', 'KeyType': 'RANGE'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5,
                    },
                },
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5,
            },
        )
        
        # Wait for table to be created
        table.wait_until_exists()
        print(f"✅ Created table: {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"ℹ️  Table already exists: {table_name}")
        else:
            raise


def create_chat_messages_table(dynamodb_resource):
    """Create chat_messages table.
    
    Schema:
        PK: chat_id (String) - UUID of parent chat session
        SK: message_id (String) - UUID of message (allows sorting by creation)
        Attributes:
            - sender (String) - "user" or "assistant"
            - content (String) - message text
            - timestamp (String) - ISO 8601 timestamp
            - token_count (Number) - token count (for assistant messages)
            - sources (List) - list of source references (for assistant messages)
                [{document_id, document_title, chunk_index, page_number, similarity_score}]
            - message_index (Number) - sequential index within chat (0, 1, 2, ...)
    
    Note: SK (message_id) is a UUID v7 or timestamp-prefixed UUID to maintain
    chronological order when querying by chat_id.
    """
    settings = get_settings()
    table_name = settings.dynamodb_chat_messages_table
    
    try:
        table = dynamodb_resource.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'chat_id', 'KeyType': 'HASH'},  # Partition key
                {'AttributeName': 'message_id', 'KeyType': 'RANGE'},  # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'chat_id', 'AttributeType': 'S'},
                {'AttributeName': 'message_id', 'AttributeType': 'S'},
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5,
            },
        )
        
        # Wait for table to be created
        table.wait_until_exists()
        print(f"✅ Created table: {table_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"ℹ️  Table already exists: {table_name}")
        else:
            raise


def main():
    """Initialize all DynamoDB tables."""
    print("🚀 Initializing DynamoDB tables for Research Assist AI...\n")
    
    settings = get_settings()
    
    # Configure DynamoDB resource
    endpoint_url = settings.dynamodb_endpoint_url
    if endpoint_url:
        print(f"Using LocalStack endpoint: {endpoint_url}")
    else:
        print(f"Using AWS DynamoDB in region: {settings.aws_region}")
    
    dynamodb = boto3.resource(
        'dynamodb',
        endpoint_url=endpoint_url,
        region_name=settings.aws_region,
    )
    
    print()
    
    # Create tables
    create_chat_sessions_table(dynamodb)
    create_chat_messages_table(dynamodb)
    
    print("\n✨ DynamoDB initialization complete!")
    print("\nCreated tables:")
    print(f"  • {settings.dynamodb_chat_sessions_table}")
    print(f"  • {settings.dynamodb_chat_messages_table}")
    

if __name__ == "__main__":
    main()
