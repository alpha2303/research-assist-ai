"""DynamoDB client wrapper for chat sessions and messages.

This module provides a centralized wrapper around boto3's DynamoDB resource,
including table references and connection configuration for both LocalStack
(local development) and AWS (production).
"""

import boto3
from typing import Optional
from botocore.config import Config
from app.core.config import get_settings


class DynamoDBClient:
    """Wrapper for DynamoDB operations with table references.
    
    Supports both LocalStack (local) and real AWS environments based on
    environment configuration.
    """
    
    def __init__(self):
        """Initialize DynamoDB resource and table references."""
        settings = get_settings()
        
        # Configure boto3 client
        config = Config(
            region_name=settings.aws_region,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        
        # Use endpoint_url for LocalStack, omit for real AWS
        endpoint_url = settings.dynamodb_endpoint_url if hasattr(settings, 'dynamodb_endpoint_url') else None
        
        self._resource = boto3.resource(
            'dynamodb',
            endpoint_url=endpoint_url,
            config=config
        )
        
        # Table references (lazy-loaded on first access)
        self._chat_sessions_table = None
        self._chat_messages_table = None
    
    @property
    def chat_sessions(self):
        """Get reference to chat_sessions table.
        
        Returns:
            boto3.resources.factory.dynamodb.Table: DynamoDB table resource
        """
        if self._chat_sessions_table is None:
            settings = get_settings()
            self._chat_sessions_table = self._resource.Table(
                settings.dynamodb_chat_sessions_table
            )
        return self._chat_sessions_table
    
    @property
    def chat_messages(self):
        """Get reference to chat_messages table.
        
        Returns:
            boto3.resources.factory.dynamodb.Table: DynamoDB table resource
        """
        if self._chat_messages_table is None:
            settings = get_settings()
            self._chat_messages_table = self._resource.Table(
                settings.dynamodb_chat_messages_table
            )
        return self._chat_messages_table
    
    @property
    def resource(self):
        """Get underlying boto3 DynamoDB resource.
        
        Returns:
            boto3.resources.base.ServiceResource: DynamoDB service resource
        """
        return self._resource


# Singleton instance
_dynamodb_client: Optional[DynamoDBClient] = None


def get_dynamodb_client() -> DynamoDBClient:
    """Get or create singleton DynamoDB client instance.
    
    Returns:
        DynamoDBClient: Configured DynamoDB client
    """
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = DynamoDBClient()
    return _dynamodb_client
