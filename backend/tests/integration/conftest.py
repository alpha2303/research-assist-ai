"""Integration test fixtures.

These fixtures require a running PostgreSQL database at:
    postgresql+asyncpg://postgres:postgres@localhost:5432/research_assist_test

To run integration tests:
    pytest tests/integration/ -v
"""

import asyncio
from typing import Any, AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base, get_db
from app.main import app

# Test database URL — requires a running PostgreSQL instance
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/research_assist_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def async_client(async_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API testing against a real database."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table for integration tests."""
    storage: dict[str, dict[str, Any]] = {}
    table = MagicMock()

    def put_item(Item: dict[str, Any]) -> dict[str, Any]:
        if "message_id" in Item:
            key = f"{Item['chat_id']}:{Item['message_id']}"
        else:
            key = Item.get("chat_id")
        if key:
            storage[key] = Item.copy()
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_item(Key: dict[str, str]) -> dict[str, Any]:
        key_value = Key.get("chat_id")
        if key_value and key_value in storage:
            return {"Item": storage[key_value].copy()}
        return {}

    def query(KeyConditionExpression: Any = None, **kwargs) -> dict[str, Any]:
        index_name = kwargs.get("IndexName")
        items = []
        if index_name == "project_id-updated_at-index":
            for key, value in storage.items():
                if ":" not in key:
                    items.append(value.copy())
        else:
            for key, value in storage.items():
                if ":" in key:
                    items.append(value.copy())
        scan_forward = kwargs.get("ScanIndexForward", True)
        if not scan_forward:
            items.reverse()
        limit = kwargs.get("Limit", len(items))
        items = items[:limit]
        return {"Items": items, "Count": len(items)}

    def delete_item(Key: dict[str, str]) -> dict[str, Any]:
        key_value = Key.get("chat_id")
        if key_value and key_value in storage:
            del storage[key_value]
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def update_item(Key: dict[str, str], **kwargs) -> dict[str, Any]:
        key_value = Key.get("chat_id")
        if key_value and key_value in storage:
            values = kwargs.get("ExpressionAttributeValues", {})
            for attr_key, attr_value in values.items():
                clean_key = attr_key.lstrip(":")
                storage[key_value][clean_key] = attr_value
            return {"Attributes": storage[key_value].copy()}
        return {"Attributes": {}}

    table.put_item.side_effect = put_item
    table.get_item.side_effect = get_item
    table.query.side_effect = query
    table.delete_item.side_effect = delete_item
    table.update_item.side_effect = update_item
    yield table


@pytest.fixture
def mock_dynamodb_client(mock_dynamodb_table):
    """Create mock DynamoDB client for integration tests that need both DB and DynamoDB."""
    client = MagicMock()
    client.chat_sessions = mock_dynamodb_table
    client.chat_messages = mock_dynamodb_table
    with patch("app.repositories.chat_repo.get_dynamodb_client", return_value=client):
        yield client
