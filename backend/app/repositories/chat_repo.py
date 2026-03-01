"""Repository layer for chat sessions and messages in DynamoDB.

This module provides data access methods for chat-related operations,
separating database interaction from business logic.

Error handling strategy:
- Read operations that may legitimately return "not found" distinguish
  between ``ResourceNotFoundException`` (item missing — return ``None``)
  and other ``ClientError``s (service failure — let propagate so the
  router can return 503).
- Write operations let ``ClientError`` propagate so callers can react
  (e.g. return 503 or send an SSE error event).
- All caught errors are logged.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.db.dynamodb import get_dynamodb_client
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _to_iso_string(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _from_iso_string(iso_str: str) -> datetime:
    """Parse ISO 8601 string to datetime."""
    return datetime.fromisoformat(iso_str)


def _serialize_for_dynamodb(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Python types to DynamoDB-compatible types."""
    serialized = {}
    for key, value in data.items():
        if isinstance(value, float):
            serialized[key] = Decimal(str(value))
        elif isinstance(value, list):
            serialized[key] = [_serialize_for_dynamodb(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            serialized[key] = _serialize_for_dynamodb(value)
        else:
            serialized[key] = value
    return serialized


def _deserialize_from_dynamodb(data: dict[str, Any]) -> dict[str, Any]:
    """Convert DynamoDB types to Python types."""
    deserialized = {}
    for key, value in data.items():
        if isinstance(value, Decimal):
            deserialized[key] = float(value) if value % 1 else int(value)
        elif isinstance(value, list):
            deserialized[key] = [_deserialize_from_dynamodb(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            deserialized[key] = _deserialize_from_dynamodb(value)
        else:
            deserialized[key] = value
    return deserialized


class ChatRepository:
    """Repository for chat session and message operations."""
    
    def __init__(self):
        """Initialize repository with DynamoDB client."""
        self.dynamodb = get_dynamodb_client()
        self.settings = get_settings()
    
    # ========== Chat Session Operations ==========
    
    async def create_chat_session(
        self,
        project_id: str,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Create a new chat session.
        
        Args:
            project_id: ID of the parent project (UUID)
            title: Optional chat title (auto-generated if omitted)
            
        Returns:
            Created chat session data
        """
        chat_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Generate default title if not provided
        if not title:
            title = f"Chat {now.strftime('%Y-%m-%d %H:%M')}"
        
        item = {
            'chat_id': chat_id,
            'project_id': str(project_id),
            'title': title,
            'created_at': _to_iso_string(now),
            'updated_at': _to_iso_string(now),
            'message_count': 0,
            'running_summary': '',
            'summary_through_index': -1,  # -1 means no messages summarized yet
        }
        
        self.dynamodb.chat_sessions.put_item(Item=item)
        return item
    
    async def get_chat_session(self, chat_id: str) -> dict[str, Any] | None:
        """Get a chat session by ID.
        
        Args:
            chat_id: Chat session ID (UUID)
            
        Returns:
            Chat session data or None if not found
            
        Raises:
            ClientError: If DynamoDB is unreachable or returns a
                non-"not-found" error.
        """
        try:
            response = self.dynamodb.chat_sessions.get_item(
                Key={'chat_id': chat_id}
            )
            return _deserialize_from_dynamodb(response['Item']) if 'Item' in response else None
        except ClientError as exc:
            code = exc.response["Error"].get("Code", "")
            if code == "ResourceNotFoundException":
                return None
            logger.error("DynamoDB get_chat_session failed for %s: %s", chat_id, exc)
            raise
    
    async def list_chat_sessions(
        self,
        project_id: str,
        limit: int = 50,
        last_updated_at: str | None = None,
    ) -> list[dict[str, Any]]:
        """List chat sessions for a project, sorted by updated_at descending.
        
        Args:
            project_id: Project ID to filter by
            limit: Maximum number of sessions to return
            last_updated_at: For pagination - updated_at of last item from previous page
            
        Returns:
            List of chat session data (newest first)
        """
        # Query using GSI: project_id-updated_at-index
        query_kwargs = {
            'IndexName': 'project_id-updated_at-index',
            'KeyConditionExpression': Key('project_id').eq(str(project_id)),
            'ScanIndexForward': False,  # Descending order (newest first)
            'Limit': limit,
        }
        
        if last_updated_at:
            # Pagination: start after the last item from previous page
            query_kwargs['ExclusiveStartKey'] = {
                'project_id': str(project_id),
                'updated_at': last_updated_at,
            }
        
        response = self.dynamodb.chat_sessions.query(**query_kwargs)
        items = response.get('Items', [])
        return [_deserialize_from_dynamodb(item) for item in items]
    
    async def update_chat_session(
        self,
        chat_id: str,
        title: str | None = None,
        message_count: int | None = None,
        running_summary: str | None = None,
        summary_through_index: int | None = None,
    ) -> dict[str, Any] | None:
        """Update chat session fields.
        
        Args:
            chat_id: Chat session ID
            title: New title (optional)
            message_count: New message count (optional)
            running_summary: Updated summary (optional)
            summary_through_index: Updated summary index (optional)
            
        Returns:
            Updated chat session data or None if not found
        """
        update_parts = []
        expression_values = {}
        expression_names = {}
        
        # Always update updated_at
        update_parts.append('#updated_at = :updated_at')
        expression_values[':updated_at'] = _to_iso_string(datetime.now(timezone.utc))
        expression_names['#updated_at'] = 'updated_at'
        
        if title is not None:
            update_parts.append('#title = :title')
            expression_values[':title'] = title
            expression_names['#title'] = 'title'
        
        if message_count is not None:
            update_parts.append('message_count = :message_count')
            expression_values[':message_count'] = message_count
        
        if running_summary is not None:
            update_parts.append('running_summary = :running_summary')
            expression_values[':running_summary'] = running_summary
        
        if summary_through_index is not None:
            update_parts.append('summary_through_index = :summary_through_index')
            expression_values[':summary_through_index'] = summary_through_index
        
        try:
            response = self.dynamodb.chat_sessions.update_item(
                Key={'chat_id': chat_id},
                UpdateExpression='SET ' + ', '.join(update_parts),
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names,
                ReturnValues='ALL_NEW',
            )
            return _deserialize_from_dynamodb(response['Attributes'])
        except ClientError as exc:
            code = exc.response["Error"].get("Code", "")
            if code == "ResourceNotFoundException":
                return None
            logger.error("DynamoDB update_chat_session failed for %s: %s", chat_id, exc)
            raise
    
    async def delete_chat_session(self, chat_id: str) -> bool:
        """Delete a chat session.
        
        Note: This does NOT delete associated messages. 
        Call delete_chat_messages() first for cascade delete.
        
        Args:
            chat_id: Chat session ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            self.dynamodb.chat_sessions.delete_item(Key={'chat_id': chat_id})
            return True
        except ClientError as exc:
            code = exc.response["Error"].get("Code", "")
            if code == "ResourceNotFoundException":
                return False
            logger.error("DynamoDB delete_chat_session failed for %s: %s", chat_id, exc)
            raise
    
    # ========== Message Operations ==========
    
    async def add_message(
        self,
        chat_id: str,
        sender: str,
        content: str,
        message_index: int,
        sources: list[dict[str, Any]] | None = None,
        token_count: int | None = None,
    ) -> dict[str, Any]:
        """Add a message to a chat.
        
        Args:
            chat_id: Parent chat session ID
            sender: "user" or "assistant"
            content: Message content
            message_index: Sequential index within chat (0, 1, 2, ...)
            sources: Source references (for assistant messages)
            token_count: Token count (for assistant messages)
            
        Returns:
            Created message data
        """
        now = datetime.now(timezone.utc)
        # Timestamp-prefixed ID ensures DynamoDB sort-key ordering is chronological
        message_id = f"{now.strftime('%Y%m%dT%H%M%S%f')}#{uuid.uuid4()}"
        
        item = {
            'chat_id': chat_id,
            'message_id': message_id,
            'sender': sender,
            'content': content,
            'message_index': message_index,
            'timestamp': _to_iso_string(now),
        }
        
        if sources:
            item['sources'] = sources
        
        if token_count is not None:
            item['token_count'] = token_count
        
        # Serialize for DynamoDB
        item = _serialize_for_dynamodb(item)
        
        self.dynamodb.chat_messages.put_item(Item=item)
        return _deserialize_from_dynamodb(item)
    
    async def get_messages(
        self,
        chat_id: str,
        limit: int = 100,
        last_message_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get messages for a chat, sorted chronologically.
        
        Args:
            chat_id: Chat session ID
            limit: Maximum number of messages to return
            last_message_id: For pagination - message_id of last item from previous page
            
        Returns:
            List of message data (oldest first)
        """
        query_kwargs = {
            'KeyConditionExpression': Key('chat_id').eq(chat_id),
            'ScanIndexForward': True,  # Ascending order (oldest first)
            'Limit': limit,
        }
        
        if last_message_id:
            query_kwargs['ExclusiveStartKey'] = {
                'chat_id': chat_id,
                'message_id': last_message_id,
            }
        
        response = self.dynamodb.chat_messages.query(**query_kwargs)
        items = response.get('Items', [])
        return [_deserialize_from_dynamodb(item) for item in items]
    
    async def get_recent_messages(
        self,
        chat_id: str,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """Get the N most recent messages from a chat.
        
        Args:
            chat_id: Chat session ID
            count: Number of recent messages to retrieve
            
        Returns:
            List of message data (newest first)
        """
        # Query in descending order to get most recent
        response = self.dynamodb.chat_messages.query(
            KeyConditionExpression=Key('chat_id').eq(chat_id),
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=count,
        )
        
        items = response.get('Items', [])
        return [_deserialize_from_dynamodb(item) for item in items]
    
    async def delete_chat_messages(self, chat_id: str) -> int:
        """Delete all messages for a chat.
        
        Args:
            chat_id: Chat session ID
            
        Returns:
            Number of messages deleted
        """
        # Query all messages
        response = self.dynamodb.chat_messages.query(
            KeyConditionExpression=Key('chat_id').eq(chat_id),
            ProjectionExpression='chat_id, message_id',
        )
        
        items = response.get('Items', [])
        deleted_count = 0
        
        # Delete each message
        for item in items:
            try:
                self.dynamodb.chat_messages.delete_item(
                    Key={
                        'chat_id': item['chat_id'],
                        'message_id': item['message_id'],
                    }
                )
                deleted_count += 1
            except ClientError as exc:
                logger.warning(
                    "Failed to delete message %s in chat %s: %s",
                    item.get("message_id"), chat_id, exc,
                )
                # Continue deleting remaining messages
        
        return deleted_count
    
    async def get_message_count(self, chat_id: str) -> int:
        """Get total message count for a chat.
        
        Args:
            chat_id: Chat session ID
            
        Returns:
            Number of messages in the chat
        """
        response = self.dynamodb.chat_messages.query(
            KeyConditionExpression=Key('chat_id').eq(chat_id),
            Select='COUNT',
        )
        return response.get('Count', 0)
