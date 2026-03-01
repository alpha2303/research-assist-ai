"""
EmbeddingProvider interface for text embedding generation.

This interface abstracts embedding model operations to allow swapping
providers (e.g., Titan → OpenAI → Cohere) without changing business logic.
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """
    Abstract interface for generating text embeddings.
    
    Implementations:
    - TitanEmbeddingProvider: Amazon Titan Embeddings V2 via Bedrock
    - OpenAIEmbeddingProvider: OpenAI text-embedding-3 (future)
    - CohereEmbeddingProvider: Cohere Embed v3 (future)
    """
    
    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        May be more efficient than calling embed_text repeatedly
        depending on the provider's API.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        pass
    
    @abstractmethod
    def get_model_id(self) -> str:
        """
        Get the identifier of the embedding model being used.
        
        This is stored with each vector to support re-embedding
        when models are changed.
        
        Returns:
            Model identifier (e.g., "amazon.titan-embed-text-v2:0")
        """
        pass
    
    @abstractmethod
    def get_dimensions(self) -> int:
        """
        Get the dimensionality of the embedding vectors.
        
        Returns:
            Number of dimensions (e.g., 1024 for Titan V2)
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close any open connections and cleanup resources"""
        pass
