"""Unit tests for chat API endpoints.

Tests REST API operations for chat sessions and messages.
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient


class TestChatsRouter:
    """Test suite for chat API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_chat_session_success(
        self,
        async_client: AsyncClient,
        async_session,
        mock_dynamodb_client,
    ):
        """Test creating a chat session successfully."""
        # Create a test project first
        project_data = {
            "title": "Test Project",
            "description": "Test description"
        }
        project_response = await async_client.post("/api/projects", json=project_data)
        assert project_response.status_code == 201
        project = project_response.json()
        project_id = project['id']
        
        # Create a chat session
        chat_data = {"title": "My Research Chat"}
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.create_chat_session = AsyncMock(return_value={
                'chat_id': str(uuid4()),
                'project_id': project_id,
                'title': 'My Research Chat',
                'created_at': '2026-02-21T10:00:00Z',
                'updated_at': '2026-02-21T10:00:00Z',
                'message_count': 0,
            })
            
            response = await async_client.post(
                f"/api/projects/{project_id}/chats",
                json=chat_data
            )
        
        assert response.status_code == 201
        chat = response.json()
        assert chat['title'] == "My Research Chat"
        assert chat['project_id'] == project_id
        assert chat['message_count'] == 0
    
    @pytest.mark.asyncio
    async def test_create_chat_session_auto_title(
        self,
        async_client: AsyncClient,
        async_session,
        mock_dynamodb_client,
    ):
        """Test creating a chat session with auto-generated title."""
        # Create a test project
        project_data = {"title": "Test Project"}
        project_response = await async_client.post("/api/projects", json=project_data)
        project_id = project_response.json()['id']
        
        # Create chat without title
        chat_data = {}
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.create_chat_session = AsyncMock(return_value={
                'chat_id': str(uuid4()),
                'project_id': project_id,
                'title': 'Chat 2026-02-21 10:00',
                'created_at': '2026-02-21T10:00:00Z',
                'updated_at': '2026-02-21T10:00:00Z',
                'message_count': 0,
            })
            
            response = await async_client.post(
                f"/api/projects/{project_id}/chats",
                json=chat_data
            )
        
        assert response.status_code == 201
        chat = response.json()
        assert 'Chat' in chat['title']
    
    @pytest.mark.asyncio
    async def test_create_chat_session_project_not_found(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test creating a chat for a non-existent project returns 404."""
        fake_project_id = str(uuid4())
        chat_data = {"title": "Test Chat"}
        
        response = await async_client.post(
            f"/api/projects/{fake_project_id}/chats",
            json=chat_data
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()['detail'].lower()
    
    @pytest.mark.asyncio
    async def test_list_chat_sessions(
        self,
        async_client: AsyncClient,
        async_session,
        mock_dynamodb_client,
    ):
        """Test listing chat sessions for a project."""
        # Create a test project
        project_data = {"title": "Test Project"}
        project_response = await async_client.post("/api/projects", json=project_data)
        project_id = project_response.json()['id']
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_chat_sessions = AsyncMock(return_value=[
                {
                    'chat_id': str(uuid4()),
                    'project_id': project_id,
                    'title': 'Chat 1',
                    'created_at': '2026-02-21T10:00:00Z',
                    'updated_at': '2026-02-21T10:00:00Z',
                    'message_count': 5,
                },
                {
                    'chat_id': str(uuid4()),
                    'project_id': project_id,
                    'title': 'Chat 2',
                    'created_at': '2026-02-21T11:00:00Z',
                    'updated_at': '2026-02-21T11:00:00Z',
                    'message_count': 3,
                },
            ])
            
            response = await async_client.get(f"/api/projects/{project_id}/chats")
        
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert len(data['items']) == 2
        assert data['items'][0]['title'] == 'Chat 1'
    
    @pytest.mark.asyncio
    async def test_list_chat_sessions_with_pagination(
        self,
        async_client: AsyncClient,
        async_session,
        mock_dynamodb_client,
    ):
        """Test listing chat sessions with pagination."""
        # Create a test project
        project_data = {"title": "Test Project"}
        project_response = await async_client.post("/api/projects", json=project_data)
        project_id = project_response.json()['id']
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.list_chat_sessions = AsyncMock(return_value=[
                {'chat_id': str(uuid4()), 'project_id': project_id, 'title': f'Chat {i}',
                 'created_at': '2026-02-21T10:00:00Z', 'updated_at': '2026-02-21T10:00:00Z',
                 'message_count': 0} for i in range(10)
            ])
            
            response = await async_client.get(
                f"/api/projects/{project_id}/chats",
                params={"limit": 10}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data['items']) == 10
        assert 'total' in data
    
    @pytest.mark.asyncio
    async def test_get_chat_session(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test retrieving a specific chat session."""
        chat_id = str(uuid4())
        project_id = str(uuid4())
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_chat_session = AsyncMock(return_value={
                'chat_id': chat_id,
                'project_id': project_id,
                'title': 'Test Chat',
                'created_at': '2026-02-21T10:00:00Z',
                'updated_at': '2026-02-21T10:00:00Z',
                'message_count': 7,
            })
            
            response = await async_client.get(f"/api/chats/{chat_id}")
        
        assert response.status_code == 200
        chat = response.json()
        assert chat['chat_id'] == chat_id
        assert chat['title'] == 'Test Chat'
        assert chat['message_count'] == 7
    
    @pytest.mark.asyncio
    async def test_get_chat_session_not_found(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test retrieving a non-existent chat returns 404."""
        fake_chat_id = str(uuid4())
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_chat_session = AsyncMock(return_value=None)
            
            response = await async_client.get(f"/api/chats/{fake_chat_id}")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_chat_session(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test deleting a chat session."""
        chat_id = str(uuid4())
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_chat_session = AsyncMock(return_value={
                'chat_id': chat_id,
                'project_id': str(uuid4()),
                'title': 'To Delete',
                'created_at': '2026-02-21T10:00:00Z',
                'updated_at': '2026-02-21T10:00:00Z',
                'message_count': 0,
            })
            mock_repo.delete_chat_session = AsyncMock()
            mock_repo.delete_chat_messages = AsyncMock()
            
            response = await async_client.delete(f"/api/chats/{chat_id}")
        
        assert response.status_code == 204
    
    @pytest.mark.asyncio
    async def test_delete_chat_session_not_found(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test deleting a non-existent chat returns 404."""
        fake_chat_id = str(uuid4())
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_chat_session = AsyncMock(return_value=None)
            
            response = await async_client.delete(f"/api/chats/{fake_chat_id}")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_chat_messages(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test retrieving messages for a chat."""
        chat_id = str(uuid4())
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_chat_session = AsyncMock(return_value={
                'chat_id': chat_id,
                'project_id': str(uuid4()),
                'title': 'Test Chat',
                'created_at': '2026-02-21T10:00:00Z',
                'updated_at': '2026-02-21T10:00:00Z',
                'message_count': 2,
            })
            mock_repo.get_messages = AsyncMock(return_value=[
                {
                    'message_id': str(uuid4()),
                    'chat_id': chat_id,
                    'sender': 'user',
                    'content': 'Hello',
                    'sources': None,
                    'token_count': 5,
                    'timestamp': '2026-02-21T10:00:00Z',
                },
                {
                    'message_id': str(uuid4()),
                    'chat_id': chat_id,
                    'sender': 'assistant',
                    'content': 'Hi there!',
                    'sources': None,
                    'token_count': 10,
                    'timestamp': '2026-02-21T10:01:00Z',
                },
            ])
            
            response = await async_client.get(f"/api/chats/{chat_id}/messages")
        
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert len(data['items']) == 2
        assert data['items'][0]['sender'] == 'user'
        assert data['items'][1]['sender'] == 'assistant'
    
    @pytest.mark.asyncio
    async def test_get_chat_messages_not_found(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test retrieving messages for a non-existent chat returns 404."""
        fake_chat_id = str(uuid4())
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_chat_session = AsyncMock(return_value=None)
            
            response = await async_client.get(f"/api/chats/{fake_chat_id}/messages")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_chat_messages_with_pagination(
        self,
        async_client: AsyncClient,
        mock_dynamodb_client,
    ):
        """Test retrieving messages with pagination."""
        chat_id = str(uuid4())
        
        with patch('app.dependencies.ChatRepository') as MockRepo:
            mock_repo = MockRepo.return_value
            mock_repo.get_chat_session = AsyncMock(return_value={
                'chat_id': chat_id,
                'project_id': str(uuid4()),
                'title': 'Test Chat',
                'created_at': '2026-02-21T10:00:00Z',
                'updated_at': '2026-02-21T10:00:00Z',
                'message_count': 50,
            })
            mock_repo.get_messages = AsyncMock(return_value=[
                {
                    'message_id': str(uuid4()),
                    'chat_id': chat_id,
                    'sender': 'user',
                    'content': f'Message {i}',
                    'sources': None,
                    'token_count': 10,
                    'timestamp': '2026-02-21T10:00:00Z',
                } for i in range(20)
            ])
            
            response = await async_client.get(
                f"/api/chats/{chat_id}/messages",
                params={"limit": 20}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data['items']) == 20
        assert 'total' in data
