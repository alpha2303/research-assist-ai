"""
Tests for ConversationMemory - sliding window with batch summarization.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from app.services.conversation_memory import SlidingWindowMemory
from app.core.interfaces.conversation_memory import ConversationContext, Message, MessageRole


@pytest.fixture
def mock_chat_repo():
    """Mock ChatRepository."""
    repo = AsyncMock()
    # Default: no existing session
    repo.get_chat_session = AsyncMock(return_value={
        "chat_id": "test",
        "message_count": 0,
        "running_summary": "",
        "summary_through_index": -1,
    })
    repo.update_chat_session = AsyncMock(return_value={})
    repo.get_message_count = AsyncMock(return_value=0)
    repo.delete_chat_messages = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_llm_provider():
    """Mock LLMProvider for summarization."""
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value="Summary of conversation")
    return provider


@pytest.fixture
def memory_service(mock_chat_repo, mock_llm_provider):
    """Create SlidingWindowMemory with mocked dependencies."""
    return SlidingWindowMemory(
        chat_repo=mock_chat_repo,
        llm_provider=mock_llm_provider,
        window_size=10,
        batch_size=20
    )


def create_messages(count: int) -> list[dict]:
    """Helper to create mock messages."""
    return [
        {
            "sender": "user" if i % 2 == 0 else "assistant",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i}",
            "message_id": str(uuid4()),
            "timestamp": f"2026-02-28T10:{i:02d}:00+00:00",
        }
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_get_context_within_window(memory_service, mock_chat_repo):
    """Test conversation context when messages fit within window."""
    chat_id = str(uuid4())
    messages = create_messages(5)  # Less than window_size (10)

    mock_chat_repo.get_recent_messages = AsyncMock(return_value=messages)
    mock_chat_repo.get_chat_session = AsyncMock(return_value={
        "chat_id": chat_id,
        "message_count": 5,
        "running_summary": "",
        "summary_through_index": -1,
    })

    context = await memory_service.get_conversation_context(chat_id)

    # Should return all messages without summary
    assert context.summary is None
    assert len(context.recent_messages) == 5
    assert isinstance(context, ConversationContext)
    # recent_messages are now Message objects
    assert all(isinstance(m, Message) for m in context.recent_messages)


@pytest.mark.asyncio
async def test_get_context_with_summary(memory_service, mock_chat_repo, mock_llm_provider):
    """Test conversation context when a running summary exists."""
    chat_id = str(uuid4())
    messages = create_messages(10)

    mock_chat_repo.get_recent_messages = AsyncMock(return_value=messages)
    mock_chat_repo.get_chat_session = AsyncMock(return_value={
        "chat_id": chat_id,
        "message_count": 25,
        "running_summary": "Previously summarised context...",
        "summary_through_index": 14,
    })

    context = await memory_service.get_conversation_context(chat_id)

    # Should have the persisted summary
    assert context.summary == "Previously summarised context..."
    # Should have recent messages as Message objects
    assert len(context.recent_messages) == 10
    assert context.summary_through_index == 14

    # No LLM call should be made — get_context reads persisted state
    mock_llm_provider.generate.assert_not_called()


@pytest.mark.asyncio
async def test_get_context_no_summary_no_cache(memory_service, mock_chat_repo, mock_llm_provider):
    """Test that get_context does NOT invoke the LLM (it only reads state)."""
    chat_id = str(uuid4())
    messages = create_messages(10)

    mock_chat_repo.get_recent_messages = AsyncMock(return_value=messages)
    mock_chat_repo.get_chat_session = AsyncMock(return_value={
        "chat_id": chat_id,
        "message_count": 20,
        "running_summary": "",
        "summary_through_index": -1,
    })

    context = await memory_service.get_conversation_context(chat_id)

    assert context.summary is None  # empty string → None
    assert len(context.recent_messages) == 10
    # The new implementation never calls LLM from get_context
    mock_llm_provider.generate.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_summarization_incremental(memory_service, mock_chat_repo, mock_llm_provider):
    """Test that trigger_summarization folds only the new batch."""
    chat_id = str(uuid4())
    all_messages = create_messages(30)

    mock_chat_repo.get_chat_session = AsyncMock(return_value={
        "chat_id": chat_id,
        "message_count": 30,
        "running_summary": "Old summary.",
        "summary_through_index": 9,
    })
    mock_chat_repo.get_messages = AsyncMock(return_value=all_messages)

    result = await memory_service.trigger_summarization(chat_id, batch_size=5)

    assert result == "Summary of conversation"

    # Check that LLM was called with the EXISTING summary + only the batch
    call_args = mock_llm_provider.generate.call_args
    prompt = call_args.kwargs["prompt"]
    assert "Old summary." in prompt  # Existing summary included
    assert "Message 10" in prompt    # First message in batch (index 10)
    assert "Message 14" in prompt    # Last message in batch (index 14)
    assert "Message 15" not in prompt  # NOT in this batch
    assert "Message 9" not in prompt   # Already summarised

    # Verify DynamoDB was updated
    mock_chat_repo.update_chat_session.assert_called_with(
        chat_id,
        running_summary="Summary of conversation",
        summary_through_index=14,  # 9 + 5
    )


@pytest.mark.asyncio
async def test_trigger_summarization_first_batch(memory_service, mock_chat_repo, mock_llm_provider):
    """Test first summarization with no existing summary."""
    chat_id = str(uuid4())
    all_messages = create_messages(20)

    mock_chat_repo.get_chat_session = AsyncMock(return_value={
        "chat_id": chat_id,
        "message_count": 20,
        "running_summary": "",
        "summary_through_index": -1,
    })
    mock_chat_repo.get_messages = AsyncMock(return_value=all_messages)

    result = await memory_service.trigger_summarization(chat_id, batch_size=5)

    assert result == "Summary of conversation"

    # Prompt should NOT contain "Existing summary" section
    call_args = mock_llm_provider.generate.call_args
    prompt = call_args.kwargs["prompt"]
    assert "Existing summary" not in prompt
    assert "Message 0" in prompt   # First unsummarised message
    assert "Message 4" in prompt   # Last in batch (5 messages)
    assert "Message 5" not in prompt

    mock_chat_repo.update_chat_session.assert_called_with(
        chat_id,
        running_summary="Summary of conversation",
        summary_through_index=4,  # -1 + 5
    )


@pytest.mark.asyncio
async def test_summarize_messages_format(memory_service, mock_llm_provider):
    """Test that messages are formatted correctly for summarization."""
    messages = [
        {"sender": "user", "content": "Hello"},
        {"sender": "assistant", "content": "Hi there"},
        {"sender": "user", "content": "How are you?"}
    ]

    summary = await memory_service._summarize_messages(messages)

    # Check LLM was called with formatted conversation
    call_args = mock_llm_provider.generate.call_args
    assert call_args is not None
    prompt = call_args.kwargs["prompt"]

    # Should contain formatted messages
    assert "USER: Hello" in prompt
    assert "ASSISTANT: Hi there" in prompt
    assert "USER: How are you?" in prompt

    # Should have summary instruction
    assert "Summary:" in prompt or "summarize" in prompt.lower()

    # Should use constrained generation params
    assert call_args.kwargs.get("max_tokens") == 500
    assert call_args.kwargs.get("temperature") == 0.3


@pytest.mark.asyncio
async def test_summarize_empty_messages(memory_service):
    """Test summarizing empty message list."""
    summary = await memory_service._summarize_messages([])
    assert summary == ""


@pytest.mark.asyncio
async def test_clear_cache_is_noop(memory_service):
    """Test that clear_cache is a no-op (summaries persisted in DynamoDB)."""
    # Should not raise
    memory_service.clear_cache("some_id")
    memory_service.clear_cache()


@pytest.mark.asyncio
async def test_update_window_size(memory_service):
    """Test updating window size."""
    assert memory_service.window_size == 10
    memory_service.update_window_size(15)
    assert memory_service.window_size == 15


@pytest.mark.asyncio
async def test_get_message_count(memory_service, mock_chat_repo):
    """Test get_message_count delegates to repo."""
    mock_chat_repo.get_message_count = AsyncMock(return_value=42)
    count = await memory_service.get_message_count("chat123")
    assert count == 42
    mock_chat_repo.get_message_count.assert_called_once_with("chat123")


@pytest.mark.asyncio
async def test_clear_conversation(memory_service, mock_chat_repo):
    """Test clear_conversation wipes messages and resets summary."""
    chat_id = str(uuid4())
    await memory_service.clear_conversation(chat_id)

    mock_chat_repo.delete_chat_messages.assert_called_once_with(chat_id)
    mock_chat_repo.update_chat_session.assert_called_once_with(
        chat_id,
        message_count=0,
        running_summary="",
        summary_through_index=-1,
    )


@pytest.mark.asyncio
async def test_context_with_exactly_window_size(memory_service, mock_chat_repo):
    """Test edge case where message count equals window size."""
    chat_id = str(uuid4())
    messages = create_messages(10)  # Exactly window_size

    mock_chat_repo.get_recent_messages = AsyncMock(return_value=messages)
    mock_chat_repo.get_chat_session = AsyncMock(return_value={
        "chat_id": chat_id,
        "message_count": 10,
        "running_summary": "",
        "summary_through_index": -1,
    })

    context = await memory_service.get_conversation_context(chat_id)

    # Should not have summary when no prior summary exists
    assert context.summary is None
    assert len(context.recent_messages) == 10
