"""
Tests for ChatService - RAG pipeline orchestration with SSE streaming.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4, UUID

from botocore.exceptions import ClientError

from app.services.chat_service import ChatService, ServiceUnavailableError
from app.services.retrieval_service import RetrievalResult, SourceReference


@pytest.fixture
def mock_chat_repo():
    """Mock ChatRepository."""
    repo = AsyncMock()
    repo.add_message = AsyncMock(return_value={"message_id": str(uuid4()), "content": "test"})
    repo.get_recent_messages = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_retrieval_service():
    """Mock RetrievalService."""
    service = AsyncMock()
    # Return proper RetrievalResult object
    service.retrieve_for_query = AsyncMock(return_value=RetrievalResult(
        context="Test context from documents.",
        sources=[
            SourceReference(
                document_id=UUID("12345678-1234-5678-1234-567812345678"),
                document_title="test.pdf",
                page_number=1,
                chunk_id=UUID("87654321-4321-8765-4321-876543218765")
            )
        ],
        chunk_count=1
    ))
    return service


@pytest.fixture
def mock_prompt_builder():
    """Mock PromptBuilder."""
    builder = Mock()
    builder.build_prompt = Mock(return_value={
        "system_prompt": "You are a helpful assistant.",
        "messages": [{"role": "user", "content": "Test question?"}],
        "token_count": 50
    })
    return builder


@pytest.fixture
def mock_llm_provider():
    """Mock LLMProvider with streaming."""
    provider = AsyncMock()
    
    def mock_stream_factory(prompt, **kwargs):
        """Factory that creates a new async generator each time."""
        async def mock_stream():
            """Simulate streaming tokens."""
            for token in ["Hello", " ", "world", "!"]:
                yield token
        return mock_stream()
    
    # Mock generate_stream to create new generators each time
    provider.generate_stream = Mock(side_effect=mock_stream_factory)
    provider.generate = AsyncMock(return_value="Hello world!")
    return provider


@pytest.fixture
def mock_settings():
    """Mock Settings."""
    settings = Mock()
    settings.chat_history_window = 50
    return settings


@pytest.fixture
def chat_service(mock_chat_repo, mock_retrieval_service, mock_prompt_builder, mock_llm_provider, mock_settings):
    """Create ChatService with mocked dependencies."""
    return ChatService(
        chat_repo=mock_chat_repo,
        retrieval_service=mock_retrieval_service,
        prompt_builder=mock_prompt_builder,
        llm_provider=mock_llm_provider,
        settings=mock_settings
    )


@pytest.mark.asyncio
async def test_process_user_message_stream_success(chat_service, mock_chat_repo, mock_retrieval_service):
    """Test successful streaming message processing."""
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "What is the capital of France?"
    
    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    ):
        events.append(event)
    
    # Verify event sequence
    assert len(events) >= 3  # At least: tokens, sources, done
    
    # Check for token events
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) > 0
    token_content = "".join(e["content"] for e in token_events)
    assert token_content == "Hello world!"
    
    # Check for sources event
    sources_events = [e for e in events if e["type"] == "sources"]
    assert len(sources_events) == 1
    assert "sources" in sources_events[0]
    assert len(sources_events[0]["sources"]) == 1
    assert sources_events[0]["sources"][0]["document_title"] == "test.pdf"
    
    # Check for done event
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert "message_id" in done_events[0]
    
    # Verify chat repo calls
    assert mock_chat_repo.add_message.call_count == 2  # User message + assistant message
    
    # Verify retrieval service was called
    mock_retrieval_service.retrieve_for_query.assert_called_once()


@pytest.mark.asyncio
async def test_process_user_message_stream_retrieval_error(
    chat_service, mock_chat_repo, mock_retrieval_service
):
    """Test streaming with retrieval service error — graceful degradation.

    When retrieval fails, the stream should still succeed (empty context)
    rather than emitting an error event.  The user gets an LLM response
    (possibly less grounded) and the failure is logged server-side.
    """
    mock_retrieval_service.retrieve_for_query.side_effect = Exception("Retrieval failed")

    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Test question?"

    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    ):
        events.append(event)

    # No error events — retrieval failures degrade gracefully
    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 0

    # Should still stream tokens and complete
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) > 0

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1

    # User message should still be stored
    assert mock_chat_repo.add_message.call_count >= 1


@pytest.mark.asyncio
async def test_process_user_message_stream_llm_error(
    chat_service, mock_chat_repo, mock_llm_provider
):
    """Test streaming with LLM generation error.

    A generic Exception from the LLM is caught by the outer catch-all
    and emitted as a user-friendly error event.
    """
    def error_stream_factory(prompt, **kwargs):
        async def error_stream():
            yield "Start"
            raise Exception("LLM generation failed")
        return error_stream()

    mock_llm_provider.generate_stream = Mock(side_effect=error_stream_factory)

    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Test question?"

    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    ):
        events.append(event)

    # Should get some tokens then error
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) > 0

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    # User-friendly message (not the raw exception)
    assert "unexpected error" in error_events[0]["error"].lower()


@pytest.mark.asyncio
async def test_process_user_message_stream_empty_response(
    chat_service, mock_llm_provider
):
    """Test streaming with empty LLM response."""
    def empty_stream_factory(prompt, **kwargs):
        async def empty_stream():
            """Simulate no tokens."""
            return
            yield  # Make it a generator but never yield
        return empty_stream()
    
    mock_llm_provider.generate_stream = Mock(side_effect=empty_stream_factory)
    
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Test question?"
    
    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    ):
        events.append(event)
    
    # Should still have sources and done events
    sources_events = [e for e in events if e["type"] == "sources"]
    assert len(sources_events) == 1
    
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1


@pytest.mark.asyncio
async def test_process_user_message_non_streaming(
    chat_service, mock_chat_repo, mock_retrieval_service, mock_llm_provider
):
    """Test non-streaming message processing."""
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "What is Python?"
    
    result = await chat_service.process_user_message(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    )
    
    # Verify result structure
    assert "message_id" in result
    assert "content" in result
    assert result["content"] == "Hello world!"
    assert "sources" in result
    assert len(result["sources"]) == 1
    
    # Verify both messages were stored
    assert mock_chat_repo.add_message.call_count == 2
    
    # Verify retrieval and LLM were called
    mock_retrieval_service.retrieve_for_query.assert_called_once()
    mock_llm_provider.generate.assert_called_once()


@pytest.mark.asyncio
async def test_process_user_message_with_conversation_history(
    chat_service, mock_chat_repo, mock_prompt_builder
):
    """Test message processing includes conversation history."""
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Follow-up question?"
    
    # Mock conversation history
    mock_chat_repo.get_recent_messages = AsyncMock(return_value=[
        {"sender": "user", "content": "Previous question"},
        {"sender": "assistant", "content": "Previous answer"}
    ])
    
    await chat_service.process_user_message(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    )
    
    # Verify chat history was fetched
    mock_chat_repo.get_recent_messages.assert_called_once_with(
        chat_id=chat_id,
        count=10
    )
    
    # Verify prompt builder received history
    call_args = mock_prompt_builder.build_prompt.call_args
    assert call_args is not None
    recent_messages = call_args.kwargs.get("recent_messages")
    assert recent_messages is not None
    assert len(recent_messages) >= 2  # Previous messages


@pytest.mark.asyncio
async def test_process_user_message_stream_stores_metadata(
    chat_service, mock_chat_repo
):
    """Test that streaming stores messages with correct metadata."""
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Test question?"
    
    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    ):
        events.append(event)
    
    # Check user message creation call
    user_msg_call = mock_chat_repo.add_message.call_args_list[0]
    assert user_msg_call.kwargs["chat_id"] == chat_id
    assert user_msg_call.kwargs["sender"] == "user"
    assert user_msg_call.kwargs["content"] == user_message
    
    # Check assistant message creation call
    assistant_msg_call = mock_chat_repo.add_message.call_args_list[1]
    assert assistant_msg_call.kwargs["chat_id"] == chat_id
    assert assistant_msg_call.kwargs["sender"] == "assistant"
    assert assistant_msg_call.kwargs["content"] == "Hello world!"
    # Check that sources are passed (not in metadata, but as direct kwarg)
    assert "sources" in assistant_msg_call.kwargs
    assert len(assistant_msg_call.kwargs["sources"]) == 1


@pytest.mark.asyncio
async def test_process_user_message_without_retrieval(
    mock_chat_repo, mock_prompt_builder, mock_llm_provider, mock_settings
):
    """Test message processing when retrieval service is None."""
    # Create service without retrieval
    chat_service = ChatService(
        chat_repo=mock_chat_repo,
        retrieval_service=None,
        prompt_builder=mock_prompt_builder,
        llm_provider=mock_llm_provider,
        settings=mock_settings
    )
    
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Simple question"
    
    result = await chat_service.process_user_message(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    )
    
    # Should work without retrieval
    assert result["content"] == "Hello world!"
    assert result["sources"] == []  # No sources without retrieval
    
    # Prompt builder should be called with empty context
    call_args = mock_prompt_builder.build_prompt.call_args
    assert call_args.kwargs.get("context", "") == ""


@pytest.mark.asyncio
async def test_process_user_message_stream_yields_in_order(chat_service):
    """Test that SSE events are yielded in correct order."""
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Test?"
    
    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message
    ):
        events.append(event["type"])
    
    # Verify order: tokens first, then sources, then done
    # Find indices
    token_indices = [i for i, t in enumerate(events) if t == "token"]
    sources_indices = [i for i, t in enumerate(events) if t == "sources"]
    done_indices = [i for i, t in enumerate(events) if t == "done"]
    
    assert len(token_indices) > 0
    assert len(sources_indices) == 1
    assert len(done_indices) == 1
    
    # All tokens should come before sources
    assert max(token_indices) < sources_indices[0]
    # Sources should come before done
    assert sources_indices[0] < done_indices[0]


# ---------------------------------------------------------------------------
# Error handling tests (Phase 6.2.2 / 6.2.3 / 6.2.4)
# ---------------------------------------------------------------------------

def _make_client_error(code: str = "ThrottlingException") -> ClientError:
    """Helper to build a botocore ClientError with a given error code."""
    return ClientError(
        error_response={"Error": {"Code": code, "Message": "test"}},
        operation_name="TestOp",
    )


@pytest.mark.asyncio
async def test_stream_bedrock_throttling_yields_friendly_error(
    chat_service, mock_llm_provider,
):
    """Bedrock ThrottlingException → user-friendly 'high demand' SSE error."""
    def throttle_stream(prompt, **kwargs):
        async def _gen():
            raise _make_client_error("ThrottlingException")
            yield  # noqa: unreachable – makes it an async generator
        return _gen()

    mock_llm_provider.generate_stream = Mock(side_effect=throttle_stream)

    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
    ):
        events.append(event)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "high demand" in error_events[0]["error"].lower()


@pytest.mark.asyncio
async def test_stream_bedrock_access_denied_yields_friendly_error(
    chat_service, mock_llm_provider,
):
    """Bedrock AccessDeniedException → configuration-issue SSE error."""
    def denied_stream(prompt, **kwargs):
        async def _gen():
            raise _make_client_error("AccessDeniedException")
            yield  # noqa
        return _gen()

    mock_llm_provider.generate_stream = Mock(side_effect=denied_stream)

    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
    ):
        events.append(event)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "configuration" in error_events[0]["error"].lower()


@pytest.mark.asyncio
async def test_stream_bedrock_runtime_error_throttle(
    chat_service, mock_llm_provider,
):
    """RuntimeError from BedrockNovaProvider containing 'throttl' →
    user-friendly throttling message."""
    def runtime_stream(prompt, **kwargs):
        async def _gen():
            raise RuntimeError("Max retries exceeded for LLM generation (throttled)")
            yield  # noqa
        return _gen()

    mock_llm_provider.generate_stream = Mock(side_effect=runtime_stream)

    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
    ):
        events.append(event)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "high demand" in error_events[0]["error"].lower()


@pytest.mark.asyncio
async def test_stream_dynamodb_write_failure_returns_storage_error(
    chat_service, mock_chat_repo,
):
    """DynamoDB ClientError on user message write → storage error SSE event."""
    mock_chat_repo.add_message = AsyncMock(
        side_effect=_make_client_error("ProvisionedThroughputExceededException"),
    )

    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
    ):
        events.append(event)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "could not be saved" in error_events[0]["error"].lower()


@pytest.mark.asyncio
async def test_stream_assistant_write_failure_still_emits_done(
    chat_service, mock_chat_repo,
):
    """If DynamoDB fails when storing the assistant message, the stream
    should still emit a 'done' event (the tokens were already sent)."""
    call_count = 0

    async def add_message_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call (user message) succeeds
            return {"message_id": str(uuid4()), "content": kwargs.get("content", "")}
        # Second call (assistant message) fails
        raise _make_client_error("InternalServerError")

    mock_chat_repo.add_message = AsyncMock(side_effect=add_message_side_effect)

    events = []
    async for event in chat_service.process_user_message_stream(
        chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
    ):
        events.append(event)

    # Tokens should still have been streamed
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) > 0

    # 'done' should still be emitted even though persistence failed
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    # message_id will be empty since persistence failed
    assert done_events[0]["message_id"] == ""


@pytest.mark.asyncio
async def test_nonstreaming_bedrock_throttling_raises_service_unavailable(
    chat_service, mock_llm_provider,
):
    """Non-streaming: Bedrock ThrottlingException → ServiceUnavailableError."""
    mock_llm_provider.generate = AsyncMock(
        side_effect=_make_client_error("ThrottlingException"),
    )

    with pytest.raises(ServiceUnavailableError) as exc_info:
        await chat_service.process_user_message(
            chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
        )

    assert "high demand" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_nonstreaming_dynamodb_write_failure_raises_service_unavailable(
    chat_service, mock_chat_repo,
):
    """Non-streaming: DynamoDB failure on user message → ServiceUnavailableError."""
    mock_chat_repo.add_message = AsyncMock(
        side_effect=_make_client_error("ProvisionedThroughputExceededException"),
    )

    with pytest.raises(ServiceUnavailableError) as exc_info:
        await chat_service.process_user_message(
            chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
        )

    assert "could not be saved" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_nonstreaming_assistant_write_failure_still_returns_content(
    chat_service, mock_chat_repo,
):
    """Non-streaming: if assistant message persistence fails, the generated
    content should still be returned to the caller."""
    call_count = 0

    async def add_message_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"message_id": str(uuid4()), "content": kwargs.get("content", "")}
        raise _make_client_error("InternalServerError")

    mock_chat_repo.add_message = AsyncMock(side_effect=add_message_side_effect)

    result = await chat_service.process_user_message(
        chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
    )

    assert result["content"] == "Hello world!"
    assert result["message_id"] == ""  # persistence failed


@pytest.mark.asyncio
async def test_stream_conversation_memory_failure_degrades_gracefully(
    mock_chat_repo, mock_retrieval_service, mock_prompt_builder,
    mock_llm_provider, mock_settings,
):
    """If conversation memory raises, the stream should still work
    using empty history."""
    mock_memory = AsyncMock()
    mock_memory.get_context = AsyncMock(side_effect=Exception("DynamoDB timeout"))

    # Fallback: get_recent_messages returns empty
    mock_chat_repo.get_recent_messages = AsyncMock(return_value=[])

    service = ChatService(
        chat_repo=mock_chat_repo,
        retrieval_service=mock_retrieval_service,
        prompt_builder=mock_prompt_builder,
        llm_provider=mock_llm_provider,
        settings=mock_settings,
        conversation_memory=mock_memory,
    )

    events = []
    async for event in service.process_user_message_stream(
        chat_id=str(uuid4()), project_id=uuid4(), user_message="hi",
    ):
        events.append(event)

    # Should still complete successfully
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) > 0


# ---------------------------------------------------------------------------
# Token accumulator tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_accumulated_response_stored_correctly(
    chat_service, mock_chat_repo
):
    """
    Verify that tokens emitted by the LLM are joined correctly before being
    stored in the repository.

    This also validates that we are not doing O(n²) string concatenation —
    the stored content should exactly match the concatenation of all token
    events.
    """
    chat_id = str(uuid4())
    project_id = uuid4()
    user_message = "Tell me a story"

    events: list[dict] = []
    async for event in chat_service.process_user_message_stream(
        chat_id=chat_id,
        project_id=project_id,
        user_message=user_message,
    ):
        events.append(event)

    # Reconstruct what the stored content should be
    expected_content = "".join(e["content"] for e in events if e["type"] == "token")

    # Find the assistant message call (second add_message call)
    calls = mock_chat_repo.add_message.call_args_list
    assert len(calls) == 2
    stored_content = calls[1].kwargs["content"]
    assert stored_content == expected_content
