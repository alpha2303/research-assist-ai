"""
Tests for BedrockNovaProvider.

These tests verify:
1. Synchronous generation (generate method)
2. Streaming generation (generate_stream method)
3. Error handling and retry logic
4. Configuration parameter handling
5. AWS API request/response format
"""

from unittest.mock import AsyncMock, Mock, patch
from botocore.exceptions import ClientError

import pytest

from app.core.config import LLMConfig
from app.implementations.bedrock_nova import BedrockNovaProvider


@pytest.fixture
def mock_llm_config() -> LLMConfig:
    """Create mock LLM configuration."""
    return LLMConfig(
        model_id="amazon.nova-micro-v1:0",
        max_output_tokens=2048,
        temperature=0.3
    )


@pytest.fixture
def mock_bedrock_client():
    """Create mock Bedrock runtime client."""
    client = Mock()
    return client


@pytest.fixture
def bedrock_provider(mock_llm_config: LLMConfig, mock_bedrock_client: Mock) -> BedrockNovaProvider:
    """Create BedrockNovaProvider with mocked dependencies."""
    with patch('boto3.Session') as mock_session:
        mock_session.return_value.client.return_value = mock_bedrock_client
        provider = BedrockNovaProvider(
            config=mock_llm_config,
            aws_profile="default",
            aws_region="us-east-1"
        )
        provider.bedrock_runtime = mock_bedrock_client
        return provider


@pytest.mark.asyncio
async def test_generate_success(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test successful synchronous generation."""
    prompt = "What is machine learning?"
    expected_response = "Machine learning is a subset of artificial intelligence..."
    
    # Mock Bedrock response
    mock_bedrock_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"text": expected_response}
                ]
            }
        },
        "stopReason": "end_turn",
        "usage": {
            "inputTokens": 10,
            "outputTokens": 50
        }
    }
    
    # Execute
    result = await bedrock_provider.generate(prompt)
    
    # Verify
    assert result == expected_response
    
    # Verify API call
    mock_bedrock_client.converse.assert_called_once()
    call_args = mock_bedrock_client.converse.call_args[1]
    
    assert call_args["modelId"] == "amazon.nova-micro-v1:0"
    assert call_args["messages"][0]["role"] == "user"
    assert call_args["messages"][0]["content"][0]["text"] == prompt
    assert call_args["inferenceConfig"]["maxTokens"] == 2048
    assert call_args["inferenceConfig"]["temperature"] == 0.3


@pytest.mark.asyncio
async def test_generate_with_custom_parameters(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test generation with custom max_tokens and temperature."""
    prompt = "Explain transformers"
    custom_max_tokens = 1000
    custom_temperature = 0.7
    stop_sequences = ["END", "STOP"]
    
    mock_bedrock_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Transformers are neural networks..."}]
            }
        }
    }
    
    # Execute
    await bedrock_provider.generate(
        prompt,
        max_tokens=custom_max_tokens,
        temperature=custom_temperature,
        stop_sequences=stop_sequences
    )
    
    # Verify custom parameters used
    call_args = mock_bedrock_client.converse.call_args[1]
    assert call_args["inferenceConfig"]["maxTokens"] == custom_max_tokens
    assert call_args["inferenceConfig"]["temperature"] == custom_temperature
    assert call_args["inferenceConfig"]["stopSequences"] == stop_sequences


@pytest.mark.asyncio
async def test_generate_with_throttling_retry(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test generation retries on throttling error."""
    prompt = "Test prompt"
    
    # Mock first call fails with throttling, second succeeds
    throttling_error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "converse"
    )
    
    mock_bedrock_client.converse.side_effect = [
        throttling_error,
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Success after retry"}]
                }
            }
        }
    ]
    
    # Execute
    result = await bedrock_provider.generate(prompt)
    
    # Verify retry worked
    assert result == "Success after retry"
    assert mock_bedrock_client.converse.call_count == 2


@pytest.mark.asyncio
async def test_generate_max_retries_exceeded(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test generation fails after max retries."""
    prompt = "Test prompt"
    
    # Mock all calls fail with throttling
    throttling_error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "converse"
    )
    mock_bedrock_client.converse.side_effect = throttling_error
    
    # Execute and expect failure
    with pytest.raises(RuntimeError, match="Max retries exceeded"):
        await bedrock_provider.generate(prompt)
    
    # Verify all retries attempted
    assert mock_bedrock_client.converse.call_count == 3


@pytest.mark.asyncio
async def test_generate_non_retryable_error(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test generation fails immediately on non-retryable errors."""
    prompt = "Test prompt"
    
    # Mock validation error (non-retryable)
    validation_error = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "Invalid input"}},
        "converse"
    )
    mock_bedrock_client.converse.side_effect = validation_error
    
    # Execute and expect immediate failure
    with pytest.raises(RuntimeError, match="Bedrock generation failed"):
        await bedrock_provider.generate(prompt)
    
    # Verify only one attempt
    assert mock_bedrock_client.converse.call_count == 1


@pytest.mark.asyncio
async def test_generate_stream_success(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test successful streaming generation."""
    prompt = "Tell me about AI"
    
    # Mock streaming response
    # Simulate multiple chunks being streamed
    mock_stream = [
        {"contentBlockDelta": {"delta": {"text": "AI "}}},
        {"contentBlockDelta": {"delta": {"text": "stands "}}},
        {"contentBlockDelta": {"delta": {"text": "for "}}},
        {"contentBlockDelta": {"delta": {"text": "artificial "}}},
        {"contentBlockDelta": {"delta": {"text": "intelligence."}}},
        {"messageStop": {"stopReason": "end_turn"}}
    ]
    
    mock_bedrock_client.converse_stream.return_value = {
        "stream": iter(mock_stream)
    }
    
    # Execute
    tokens = []
    async for token in bedrock_provider.generate_stream(prompt):
        tokens.append(token)
    
    # Verify
    assert tokens == ["AI ", "stands ", "for ", "artificial ", "intelligence."]
    
    # Verify API call
    mock_bedrock_client.converse_stream.assert_called_once()
    call_args = mock_bedrock_client.converse_stream.call_args[1]
    assert call_args["modelId"] == "amazon.nova-micro-v1:0"
    assert call_args["messages"][0]["content"][0]["text"] == prompt


@pytest.mark.asyncio
async def test_generate_stream_with_custom_parameters(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test streaming with custom parameters."""
    prompt = "Explain quantum computing"
    custom_max_tokens = 500
    custom_temperature = 0.5
    
    mock_stream = [
        {"contentBlockDelta": {"delta": {"text": "Quantum computing"}}}
    ]
    
    mock_bedrock_client.converse_stream.return_value = {
        "stream": iter(mock_stream)
    }
    
    # Execute
    tokens = []
    async for token in bedrock_provider.generate_stream(
        prompt,
        max_tokens=custom_max_tokens,
        temperature=custom_temperature
    ):
        tokens.append(token)
    
    # Verify custom parameters
    call_args = mock_bedrock_client.converse_stream.call_args[1]
    assert call_args["inferenceConfig"]["maxTokens"] == custom_max_tokens
    assert call_args["inferenceConfig"]["temperature"] == custom_temperature


@pytest.mark.asyncio
async def test_generate_stream_internal_error(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test streaming handles internal server errors."""
    prompt = "Test prompt"
    
    # Mock stream with internal error
    mock_stream = [
        {"contentBlockDelta": {"delta": {"text": "Some text"}}},
        {"internalServerException": {"message": "Internal error"}}
    ]
    
    mock_bedrock_client.converse_stream.return_value = {
        "stream": iter(mock_stream)
    }
    
    # Execute and expect error
    with pytest.raises(RuntimeError, match="Internal server error"):
        tokens = []
        async for token in bedrock_provider.generate_stream(prompt):
            tokens.append(token)


@pytest.mark.asyncio
async def test_generate_stream_model_error(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test streaming handles model stream errors."""
    prompt = "Test prompt"
    
    # Mock stream with model error
    mock_stream = [
        {"contentBlockDelta": {"delta": {"text": "Some text"}}},
        {"modelStreamErrorException": {"message": "Model error occurred"}}
    ]
    
    mock_bedrock_client.converse_stream.return_value = {
        "stream": iter(mock_stream)
    }
    
    # Execute and expect error
    with pytest.raises(RuntimeError, match="Model stream error"):
        tokens = []
        async for token in bedrock_provider.generate_stream(prompt):
            tokens.append(token)


@pytest.mark.asyncio
async def test_generate_stream_throttling_error(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test streaming handles throttling errors."""
    prompt = "Test prompt"
    
    # Mock stream with throttling error
    mock_stream = [
        {"throttlingException": {"message": "Rate limit exceeded"}}
    ]
    
    mock_bedrock_client.converse_stream.return_value = {
        "stream": iter(mock_stream)
    }
    
    # Execute and expect error
    with pytest.raises(RuntimeError, match="Rate limit exceeded"):
        tokens = []
        async for token in bedrock_provider.generate_stream(prompt):
            tokens.append(token)


@pytest.mark.asyncio
async def test_generate_stream_client_error(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test streaming handles ClientError exceptions."""
    prompt = "Test prompt"
    
    # Mock client error
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
        "converse_stream"
    )
    mock_bedrock_client.converse_stream.side_effect = error
    
    # Execute and expect error
    with pytest.raises(RuntimeError, match="Bedrock streaming failed"):
        tokens = []
        async for token in bedrock_provider.generate_stream(prompt):
            tokens.append(token)


@pytest.mark.asyncio
async def test_get_model_id(bedrock_provider: BedrockNovaProvider):
    """Test getting model ID."""
    model_id = bedrock_provider.get_model_id()
    assert model_id == "amazon.nova-micro-v1:0"


@pytest.mark.asyncio
async def test_close(bedrock_provider: BedrockNovaProvider):
    """Test closing provider (should not raise errors)."""
    await bedrock_provider.close()
    # No assertion needed - just verify it doesn't raise


@pytest.mark.asyncio
async def test_generate_empty_prompt(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test generation with empty prompt."""
    prompt = ""
    
    mock_bedrock_client.converse.return_value = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "I need a question to answer."}]
            }
        }
    }
    
    # Execute
    result = await bedrock_provider.generate(prompt)
    
    # Verify it still works (model handles empty input)
    assert result == "I need a question to answer."


@pytest.mark.asyncio
async def test_generate_stream_empty_response(bedrock_provider: BedrockNovaProvider, mock_bedrock_client: Mock):
    """Test streaming with no content returned."""
    prompt = "Test prompt"
    
    # Mock empty stream
    mock_stream = [
        {"messageStop": {"stopReason": "end_turn"}}
    ]
    
    mock_bedrock_client.converse_stream.return_value = {
        "stream": iter(mock_stream)
    }
    
    # Execute
    tokens = []
    async for token in bedrock_provider.generate_stream(prompt):
        tokens.append(token)
    
    # Verify no tokens received
    assert tokens == []
