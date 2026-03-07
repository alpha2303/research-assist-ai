"""Pytest fixtures for unit testing.

This module provides reusable fixtures for unit tests, including:
- DynamoDB mock for chat testing
- tiktoken mock to avoid network access during tests

Integration test fixtures (async_engine, async_session, async_client) are in
tests/integration/conftest.py.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# tiktoken mock — prevents tests from making network calls to download the
# cl100k_base encoding file.  The mock approximates token count as
# len(text) // 4, which is close to reality for English text and passes all
# existing token-count assertions.  decode() returns an empty string because
# truncation tests only check for the presence of the truncation marker, not
# the reconstructed text.
# ---------------------------------------------------------------------------

class _MockEncoding:
    """Lightweight tiktoken encoding mock that requires no network access."""

    _CHARS_PER_TOKEN = 4

    def encode(self, text: str) -> list[int]:
        """Return a token list whose length approximates real token count."""
        n_tokens = max(0, len(text) // self._CHARS_PER_TOKEN)
        return list(range(n_tokens))

    def decode(self, tokens: list[int]) -> str:
        """Return empty string (token ids are opaque ints in the mock)."""
        return ""


@pytest.fixture(autouse=True, scope="session")
def mock_tiktoken_encoding():
    """Patch tiktoken.get_encoding for the entire test session.

    This avoids network calls to download the cl100k_base BPE file which
    would fail in environments without internet access (CI sandboxes, offline
    dev machines).
    """
    mock_enc = _MockEncoding()
    with patch("tiktoken.get_encoding", return_value=mock_enc):
        yield mock_enc


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table for testing.
    
    Yields:
        Mock DynamoDB table with common operations
    """
    # In-memory storage for test data
    storage: dict[str, dict[str, Any]] = {}
    
    table = MagicMock()
    
    def put_item(Item: dict[str, Any]) -> dict[str, Any]:
        """Mock put_item operation."""
        # Use chat_id or combination of chat_id+message_id as key
        if 'message_id' in Item:
            key = f"{Item['chat_id']}:{Item['message_id']}"
        else:
            key = Item.get('chat_id')
        if key:
            storage[key] = Item.copy()
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}
    
    def get_item(Key: dict[str, str]) -> dict[str, Any]:
        """Mock get_item operation."""
        key_value = Key.get('chat_id')
        if key_value and key_value in storage:
            return {'Item': storage[key_value].copy()}
        return {}
    
    def query(KeyConditionExpression: Any = None, **kwargs) -> dict[str, Any]:
        """Mock query operation."""
        # Check if this is a GSI query (for chat_sessions by project_id)
        index_name = kwargs.get('IndexName')
        
        items = []
        if index_name == 'project_id-updated_at-index':
            # Return chat session items (those without ':' in key)
            for key, value in storage.items():
                if ':' not in key:  # Chat session item
                    items.append(value.copy())
        else:
            # Return message items (for chat_messages query)
            for key, value in storage.items():
                if ':' in key:  # Message item
                    items.append(value.copy())
        
        # Handle ordering
        scan_forward = kwargs.get('ScanIndexForward', True)
        if not scan_forward:
            items.reverse()
        
        # Handle limit
        limit = kwargs.get('Limit', len(items))
        items = items[:limit]
        
        return {'Items': items, 'Count': len(items)}
    
    def delete_item(Key: dict[str, str]) -> dict[str, Any]:
        """Mock delete_item operation."""
        key_value = Key.get('chat_id')
        if key_value and key_value in storage:
            del storage[key_value]
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}
    
    def update_item(Key: dict[str, str], **kwargs) -> dict[str, Any]:
        """Mock update_item operation."""
        key_value = Key.get('chat_id')
        if key_value and key_value in storage:
            # Apply updates from ExpressionAttributeValues
            values = kwargs.get('ExpressionAttributeValues', {})
            for attr_key, attr_value in values.items():
                # Strip the : prefix from attribute values
                clean_key = attr_key.lstrip(':')
                storage[key_value][clean_key] = attr_value
            return {'Attributes': storage[key_value].copy()}
        return {'Attributes': {}}
    
    table.put_item.side_effect = put_item
    table.get_item.side_effect = get_item
    table.query.side_effect = query
    table.delete_item.side_effect = delete_item
    table.update_item.side_effect = update_item
    
    yield table


@pytest.fixture
def mock_dynamodb_client(mock_dynamodb_table):
    """Create a mock DynamoDB client for testing.
    
    Args:
        mock_dynamodb_table: Mock table fixture
        
    Yields:
        Mock DynamoDB client with chat_sessions and chat_messages tables
    """
    client =MagicMock()
    client.chat_sessions = mock_dynamodb_table
    client.chat_messages = mock_dynamodb_table
    
    with patch('app.repositories.chat_repo.get_dynamodb_client', return_value=client):
        yield client
