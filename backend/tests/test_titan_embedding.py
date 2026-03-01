"""Unit tests for Titan embedding provider."""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.core.config import EmbeddingConfig
from app.implementations.titan_embedding import TitanEmbeddingProvider


@pytest.fixture
def embedding_config():
    """Create test embedding configuration."""
    return EmbeddingConfig(
        model_id="amazon.titan-embed-text-v2:0",
        dimensions=1024
    )


@pytest.fixture
def mock_bedrock_client():
    """Create mock Bedrock runtime client."""
    client = MagicMock()
    return client


@pytest.fixture
def titan_provider(embedding_config, mock_bedrock_client):
    """Create Titan provider with mocked client."""
    with patch('app.implementations.titan_embedding.boto3.Session') as mock_session:
        mock_session.return_value.client.return_value = mock_bedrock_client
        provider = TitanEmbeddingProvider(
            config=embedding_config,
            aws_profile="default",
            aws_region="us-east-1"
        )
        return provider


class TestTitanEmbeddingProvider:
    """Test cases for TitanEmbeddingProvider."""

    def test_provider_initialization(self, embedding_config):
        """Test provider can be initialized."""
        with patch('app.implementations.titan_embedding.boto3.Session'):
            provider = TitanEmbeddingProvider(
                config=embedding_config,
                aws_profile="default",
                aws_region="us-east-1"
            )
            assert provider is not None
            assert provider.config == embedding_config

    async def test_embed_text_success(self, titan_provider, mock_bedrock_client):
        """Test successful text embedding."""
        text = "This is a test sentence."
        
        # Mock successful response
        mock_response = {
            "body": MagicMock()
        }
        embedding_vector = [0.1] * 1024
        response_body = json.dumps({"embedding": embedding_vector})
        mock_response["body"].read.return_value = response_body.encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        result = await titan_provider.embed_text(text)
        
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)
        mock_bedrock_client.invoke_model.assert_called_once()

    async def test_embed_text_with_retry_success(self, titan_provider, mock_bedrock_client):
        """Test embedding with retry after initial failure."""
        text = "Test text"
        
        # First call fails, second succeeds
        error_response = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel"
        )
        success_response = {
            "body": MagicMock()
        }
        embedding_vector = [0.2] * 1024
        success_response["body"].read.return_value = json.dumps(
            {"embedding": embedding_vector}
        ).encode()
        
        mock_bedrock_client.invoke_model.side_effect = [
            error_response,
            success_response
        ]
        
        with patch('time.sleep'):  # Speed up test
            result = await titan_provider.embed_text(text)
        
        assert len(result) == 1024
        # Should have retried
        assert mock_bedrock_client.invoke_model.call_count == 2

    async def test_embed_text_retry_exhausted(self, titan_provider, mock_bedrock_client):
        """Test embedding fails after all retries exhausted."""
        text = "Test text"
        
        # All calls fail with throttling (which triggers retries)
        error_response = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit exceeded"}},
            "InvokeModel"
        )
        mock_bedrock_client.invoke_model.side_effect = error_response
        
        with patch('asyncio.sleep'):  # Speed up test
            with pytest.raises(RuntimeError, match="Bedrock embedding failed"):
                await titan_provider.embed_text(text)
        
        # Should have tried max_retries times
        assert mock_bedrock_client.invoke_model.call_count == 3

    async def test_embed_batch_success(self, titan_provider, mock_bedrock_client):
        """Test batch embedding."""
        texts = ["Text 1", "Text 2", "Text 3"]
        
        # Mock responses for each text
        def mock_invoke(modelId, body, **kwargs):
            response = {"body": MagicMock()}
            embedding = [0.1] * 1024
            response["body"].read.return_value = json.dumps(
                {"embedding": embedding}
            ).encode()
            return response
        
        mock_bedrock_client.invoke_model.side_effect = mock_invoke
        
        results = await titan_provider.embed_batch(texts)
        
        assert len(results) == 3
        assert all(len(emb) == 1024 for emb in results)
        assert mock_bedrock_client.invoke_model.call_count == 3

    async def test_embed_empty_text(self, titan_provider, mock_bedrock_client):
        """Test embedding empty text."""
        text = ""
        
        mock_response = {
            "body": MagicMock()
        }
        embedding_vector = [0.0] * 1024
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embedding_vector}
        ).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        result = await titan_provider.embed_text(text)
        
        assert len(result) == 1024

    async def test_embed_long_text(self, titan_provider, mock_bedrock_client):
        """Test embedding very long text."""
        # Create text longer than typical token limit
        text = "This is a sentence. " * 1000
        
        mock_response = {
            "body": MagicMock()
        }
        embedding_vector = [0.1] * 1024
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embedding_vector}
        ).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        result = await titan_provider.embed_text(text)
        
        # Should handle long text (may truncate internally)
        assert len(result) == 1024

    async def test_embed_special_characters(self, titan_provider, mock_bedrock_client):
        """Test embedding text with special characters."""
        text = "Special chars: @#$%^&*() émojis 🎉 unicode ü"
        
        mock_response = {
            "body": MagicMock()
        }
        embedding_vector = [0.1] * 1024
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embedding_vector}
        ).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        result = await titan_provider.embed_text(text)
        
        assert len(result) == 1024

    async def test_embed_batch_empty_list(self, titan_provider):
        """Test batch embedding with empty list."""
        texts = []
        
        results = await titan_provider.embed_batch(texts)
        
        assert results == []

    async def test_embed_batch_partial_failure(self, titan_provider, mock_bedrock_client):
        """Test batch embedding with some failures."""
        texts = ["Text 1", "Text 2", "Text 3"]
        
        # First succeeds, second fails, third succeeds
        def mock_invoke(modelId, body, **kwargs):
            if mock_bedrock_client.invoke_model.call_count == 2:
                raise ClientError(
                    {"Error": {"Code": "ValidationException", "Message": "Invalid"}},
                    "InvokeModel"
                )
            response = {"body": MagicMock()}
            embedding = [0.1] * 1024
            response["body"].read.return_value = json.dumps(
                {"embedding": embedding}
            ).encode()
            return response
        
        mock_bedrock_client.invoke_model.side_effect = mock_invoke
        
        # Should raise on first failure (no partial results)
        with pytest.raises(RuntimeError, match="Bedrock embedding failed"):
            await titan_provider.embed_batch(texts)

    async def test_exponential_backoff(self, titan_provider, mock_bedrock_client):
        """Test exponential backoff retry delays."""
        text = "Test"
        
        error_response = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Throttled"}},
            "InvokeModel"
        )
        mock_bedrock_client.invoke_model.side_effect = error_response
        
        with patch('asyncio.sleep') as mock_sleep:
            try:
                await titan_provider.embed_text(text)
            except RuntimeError:
                pass
            
            # Check that sleep was called with increasing delays
            # First retry: 1s, second: 2s (exponential backoff)
            assert mock_sleep.call_count >= 2
            delays = [call[0][0] for call in mock_sleep.call_args_list]
            # Verify delays are increasing
            assert delays[1] > delays[0]

    async def test_invoke_model_request_format(self, titan_provider, mock_bedrock_client):
        """Test that invoke_model is called with correct request format."""
        text = "Test text"
        
        mock_response = {
            "body": MagicMock()
        }
        embedding_vector = [0.1] * 1024
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embedding_vector}
        ).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        await titan_provider.embed_text(text)
        
        # Verify request format
        call_kwargs = mock_bedrock_client.invoke_model.call_args[1]
        assert "modelId" in call_kwargs
        assert "body" in call_kwargs
        
        # Parse body
        body = json.loads(call_kwargs["body"])
        assert "inputText" in body
        assert body["inputText"] == text

    async def test_response_parsing(self, titan_provider, mock_bedrock_client):
        """Test parsing of response from Bedrock."""
        text = "Test"
        
        # Create response with specific embedding values
        test_embedding = [float(i) / 1024 for i in range(1024)]
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": test_embedding}
        ).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        result = await titan_provider.embed_text(text)
        
        # Verify embedding values match
        assert result == test_embedding

    async def test_concurrent_embeds_independence(self, titan_provider, mock_bedrock_client):
        """Test that multiple embed calls are independent."""
        mock_response = {
            "body": MagicMock()
        }
        embedding_vector = [0.1] * 1024
        mock_response["body"].read.return_value = json.dumps(
            {"embedding": embedding_vector}
        ).encode()
        mock_bedrock_client.invoke_model.return_value = mock_response
        
        result1 = await titan_provider.embed_text("Text 1")
        result2 = await titan_provider.embed_text("Text 2")
        
        # Both should succeed independently
        assert len(result1) == 1024
        assert len(result2) == 1024
        assert mock_bedrock_client.invoke_model.call_count == 2
