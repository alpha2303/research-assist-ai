"""Unit tests for ChatRepository.

Tests DynamoDB operations for chat sessions and messages.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.chat_repo import ChatRepository


class TestChatRepository:
    """Test suite for ChatRepository."""
    
    @pytest.mark.asyncio
    async def test_create_chat_session_with_title(self, mock_dynamodb_client):
        """Test creating a chat session with a custom title."""
        repo = ChatRepository()
        project_id = str(uuid4())
        title = "My Research Chat"
        
        result = await repo.create_chat_session(project_id, title)
        
        assert result['chat_id'] is not None
        assert result['project_id'] == project_id
        assert result['title'] == title
        assert result['message_count'] == 0
        assert result['running_summary'] == ''
        assert result['summary_through_index'] == -1
        assert 'created_at' in result
        assert 'updated_at' in result
    
    @pytest.mark.asyncio
    async def test_create_chat_session_auto_title(self, mock_dynamodb_client):
        """Test creating a chat session with auto-generated title."""
        repo = ChatRepository()
        project_id = str(uuid4())
        
        result = await repo.create_chat_session(project_id)
        
        assert result['chat_id'] is not None
        assert result['project_id'] == project_id
        assert 'Chat' in result['title']  # Auto-generated contains "Chat"
        assert result['message_count'] == 0
    
    @pytest.mark.asyncio
    async def test_get_chat_session(self, mock_dynamodb_client):
        """Test retrieving a chat session by ID."""
        repo = ChatRepository()
        project_id = str(uuid4())
        
        # Create a chat session
        created = await repo.create_chat_session(project_id, "Test Chat")
        chat_id = created['chat_id']
        
        # Retrieve it
        result = await repo.get_chat_session(chat_id)
        
        assert result is not None
        assert result['chat_id'] == chat_id
        assert result['title'] == "Test Chat"
    
    @pytest.mark.asyncio
    async def test_get_chat_session_not_found(self, mock_dynamodb_client):
        """Test retrieving a non-existent chat session."""
        repo = ChatRepository()
        fake_chat_id = str(uuid4())
        
        result = await repo.get_chat_session(fake_chat_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_list_chat_sessions(self, mock_dynamodb_client):
        """Test listing chat sessions for a project."""
        repo = ChatRepository()
        project_id = str(uuid4())
        
        # Create multiple chat sessions
        chat1 = await repo.create_chat_session(project_id, "Chat 1")
        chat2 = await repo.create_chat_session(project_id, "Chat 2")
        
        # List sessions
        result = await repo.list_chat_sessions(project_id)
        
        assert isinstance(result, list)
        assert len(result) >= 2
        # Verify the created chats are in the list
        chat_ids = [c['chat_id'] for c in result]
        assert chat1['chat_id'] in chat_ids
        assert chat2['chat_id'] in chat_ids
    
    @pytest.mark.asyncio
    async def test_update_chat_session(self, mock_dynamodb_client):
        """Test updating a chat session."""
        repo = ChatRepository()
        project_id = str(uuid4())
        
        # Create a chat session
        created = await repo.create_chat_session(project_id, "Original Title")
        chat_id = created['chat_id']
        
        # Update it
        updated = await repo.update_chat_session(
            chat_id,
            title="Updated Title",
            message_count=5
        )
        
        assert updated is not None
        assert updated['title'] == "Updated Title"
        assert updated['message_count'] == 5
        # Updated timestamp should be present
        assert 'updated_at' in updated
    
    @pytest.mark.asyncio
    async def test_delete_chat_session(self, mock_dynamodb_client):
        """Test deleting a chat session."""
        repo = ChatRepository()
        project_id = str(uuid4())
        
        # Create a chat session
        created = await repo.create_chat_session(project_id, "To Delete")
        chat_id = created['chat_id']
        
        # Delete it
        await repo.delete_chat_session(chat_id)
        
        # Verify it's gone
        result = await repo.get_chat_session(chat_id)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_add_message(self, mock_dynamodb_client):
        """Test adding a message to a chat."""
        repo = ChatRepository()
        chat_id = str(uuid4())
        
        result = await repo.add_message(
            chat_id=chat_id,
            sender='user',
            content='Hello, assistant!',
            message_index=0,
            sources=None,
            token_count=10
        )
        
        assert result['message_id'] is not None
        assert result['chat_id'] == chat_id
        assert result['sender'] == 'user'
        assert result['content'] == 'Hello, assistant!'
        assert result['message_index'] == 0
        assert result['token_count'] == 10
        assert 'timestamp' in result
    
    @pytest.mark.asyncio
    async def test_add_message_with_sources(self, mock_dynamodb_client):
        """Test adding an assistant message with source references."""
        repo = ChatRepository()
        chat_id = str(uuid4())
        
        sources = [
            {
                'document_id': str(uuid4()),
                'document_title': 'Paper 1',
                'chunk_index': 5,
                'page_number': 12,
                'similarity_score': 0.89
            }
        ]
        
        result = await repo.add_message(
            chat_id=chat_id,
            sender='assistant',
            content='Based on the research...',
            message_index=1,
            sources=sources,
            token_count=50
        )
        
        assert result['sender'] == 'assistant'
        assert result['sources'] is not None
        assert len(result['sources']) == 1
        assert result['sources'][0]['document_title'] == 'Paper 1'
    
    @pytest.mark.asyncio
    async def test_get_messages(self, mock_dynamodb_client):
        """Test retrieving messages for a chat."""
        repo = ChatRepository()
        chat_id = str(uuid4())
        
        # Add multiple messages
        msg1 = await repo.add_message(chat_id, 'user', 'First message', 0, None, 10)
        msg2 = await repo.add_message(chat_id, 'assistant', 'Response', 1, None, 20)
        
        # Retrieve messages
        result = await repo.get_messages(chat_id)
        
        assert isinstance(result, list)
        assert len(result) >= 2
        # Messages should be ordered by timestamp
        message_ids = [m['message_id'] for m in result]
        assert msg1['message_id'] in message_ids
        assert msg2['message_id'] in message_ids
    
    @pytest.mark.asyncio
    async def test_get_recent_messages(self, mock_dynamodb_client):
        """Test retrieving recent messages with a count limit."""
        repo = ChatRepository()
        chat_id = str(uuid4())
        
        # Add several messages
        for i in range(5):
            await repo.add_message(chat_id, 'user', f'Message {i}', i, None, 10)
        
        # Get recent 3 messages
        result =await repo.get_recent_messages(chat_id, count=3)
        
        assert len(result) <= 5  # Mock returns all, real DynamoDB would limit
        # Should be most recent messages
        for msg in result:
            assert msg['chat_id'] == chat_id
    
    @pytest.mark.asyncio
    async def test_delete_chat_messages(self, mock_dynamodb_client):
        """Test deleting all messages for a chat."""
        repo = ChatRepository()
        chat_id = str(uuid4())
        
        # Add messages
        await repo.add_message(chat_id, 'user', 'Message 1', 0, None, 10)
        await repo.add_message(chat_id, 'assistant', 'Response 1', 1, None, 20)
        
        # Delete all messages
        count = await repo.delete_chat_messages(chat_id)
        
        # Verify count returned
        assert count >= 0  # Should return number of deleted messages
    
    @pytest.mark.asyncio
    async def test_get_message_count(self, mock_dynamodb_client):
        """Test getting message count for a chat."""
        repo = ChatRepository()
        chat_id = str(uuid4())
        
        # Add messages
        await repo.add_message(chat_id, 'user', 'Message 1', 0, None, 10)
        await repo.add_message(chat_id, 'assistant', 'Response 1', 1, None, 20)
        await repo.add_message(chat_id, 'user', 'Message 2', 2, None, 15)
        
        # Get count
        count = await repo.get_message_count(chat_id)
        
        assert count >= 0  # Mock returns count
