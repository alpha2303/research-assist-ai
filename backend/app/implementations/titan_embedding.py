"""Embedding provider implementation using AWS Bedrock Titan Embeddings."""

import asyncio
import json

import boto3
from botocore.exceptions import ClientError

from app.core.config import EmbeddingConfig
from app.core.interfaces.embedding_provider import EmbeddingProvider


class TitanEmbeddingProvider(EmbeddingProvider):
    """
    Embedding provider using Amazon Titan Embeddings V2 via Bedrock.
    
    Features:
    - 1024-dimension embeddings
    - Optimized for semantic similarity
    - Rate limiting with exponential backoff
    - Batch processing support
    """

    def __init__(self, config: EmbeddingConfig, aws_profile: str, aws_region: str):
        """
        Initialize Titan embedding provider.
        
        Args:
            config: Embedding configuration
            aws_profile: AWS profile name
            aws_region: AWS region
        """
        self.config = config
        
        # Initialize Bedrock runtime client
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        self.bedrock_runtime = session.client("bedrock-runtime")
        
        # Rate limiting configuration
        self.max_retries = 3
        self.initial_retry_delay = 1.0  # seconds

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text using Titan Embeddings V2.
        
        Args:
            text: Text to embed
            
        Returns:
            1024-dimension embedding vector
            
        Raises:
            RuntimeError: If embedding generation fails after retries
        """
        # Truncate text if too long (Titan V2 has a token limit)
        # Approximately 8000 tokens = 32000 characters
        max_chars = 30000
        if len(text) > max_chars:
            text = text[:max_chars]
        
        # Prepare request body
        body = json.dumps({
            "inputText": text,
            "dimensions": self.config.dimensions,
            "normalize": True  # Normalize embeddings for cosine similarity
        })
        
        # Call Bedrock with retry logic
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.to_thread(
                    self.bedrock_runtime.invoke_model,
                    modelId=self.config.model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                
                # Parse response
                response_body = json.loads(response["body"].read())
                embedding = response_body["embedding"]
                
                return embedding
                
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                
                # Handle throttling with exponential backoff
                if error_code == "ThrottlingException" and attempt < self.max_retries - 1:
                    delay = self.initial_retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                
                # Re-raise other errors
                raise RuntimeError(
                    f"Bedrock embedding failed: {error_code} - {str(e)}"
                ) from e
                
            except Exception as e:
                raise RuntimeError(f"Embedding generation failed: {str(e)}") from e
        
        raise RuntimeError("Max retries exceeded for embedding generation")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Titan V2 doesn't support native batching, so we process sequentially
        with rate limiting.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for text in texts:
            embedding = await self.embed_text(text)
            embeddings.append(embedding)
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        
        return embeddings

    def get_model_id(self) -> str:
        """Get the Titan model identifier."""
        return self.config.model_id

    def get_dimensions(self) -> int:
        """Get embedding dimensionality (1024 for Titan V2)."""
        return self.config.dimensions

    async def close(self) -> None:
        """Close Bedrock client connections."""
        # Boto3 clients are thread-safe and don't need explicit closing
        # But we implement this for interface compliance
        pass
