"""
VectorStore interface for vector similarity search operations.

This interface abstracts vector database operations to allow swapping
implementations (e.g., PGVector → Pinecone → OpenSearch) without
changing business logic.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class SearchResult:
    """A single search result from vector/hybrid search"""
    
    def __init__(
        self,
        chunk_id: UUID,
        document_id: UUID,
        content: str,
        score: float,
        page_number: int | None = None,
        section_heading: str | None = None,
        chunk_index: int | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.score = score
        self.page_number = page_number
        self.section_heading = section_heading
        self.chunk_index = chunk_index
        self.metadata = metadata or {}


class VectorStore(ABC):
    """
    Abstract interface for vector storage and retrieval operations.
    
    Implementations:
    - PGVectorStore: PostgreSQL with pgvector extension
    - PineconeVectorStore: Pinecone cloud vector database (future)
    - OpenSearchVectorStore: AWS OpenSearch Service (future)
    """
    
    @abstractmethod
    async def store_embeddings(
        self,
        document_id: UUID,
        chunks: list[dict[str, Any]],
    ) -> None:
        """
        Store document chunks with their embeddings.
        
        Args:
            document_id: ID of the document these chunks belong to
            chunks: List of chunk dictionaries containing:
                - chunk_index: int
                - content: str
                - embedding: list[float]
                - page_number: int | None
                - section_heading: str | None
                - token_count: int
                - embedding_model_id: str
        """
        pass
    
    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: list[float],
        document_ids: list[UUID],
        top_k: int = 5,
        similarity_threshold: float | None = 0.7,
        embedding_model_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Perform vector similarity search.
        
        Args:
            query_embedding: Query vector
            document_ids: Limit search to these documents (project scope)
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1). Pass None to
                disable threshold filtering and return top-K by distance only.
            embedding_model_id: If set, only match chunks with this model ID
            
        Returns:
            List of SearchResult objects sorted by similarity score
        """
        pass
    
    @abstractmethod
    async def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        document_ids: list[UUID],
        top_k: int = 5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        embedding_model_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Perform hybrid search combining vector similarity and BM25 keyword search.
        
        Uses weighted Reciprocal Rank Fusion to combine results.
        
        Args:
            query_embedding: Query vector
            query_text: Query text for BM25 search
            document_ids: Limit search to these documents
            top_k: Number of results to return
            vector_weight: Weight for vector similarity scores
            bm25_weight: Weight for BM25 scores
            embedding_model_id: If set, only match chunks with this model ID
            
        Returns:
            List of SearchResult objects with fused ranking
        """
        pass
    
    @abstractmethod
    async def delete_by_document_id(self, document_id: UUID) -> int:
        """
        Delete all chunks for a given document.
        
        Used when:
        - Document is deleted
        - Document is being re-processed
        - Re-embedding with a new model
        
        Args:
            document_id: Document whose chunks should be deleted
            
        Returns:
            Number of chunks deleted
        """
        pass
    
    @abstractmethod
    async def get_chunk_count(self, document_id: UUID) -> int:
        """
        Get the number of chunks stored for a document.
        
        Args:
            document_id: Document to count chunks for
            
        Returns:
            Number of chunks
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close database connections and cleanup resources"""
        pass
