"""
Service layer for document retrieval operations.

This service orchestrates the retrieval pipeline for RAG:
1. Get documents linked to a project
2. Generate query embedding
3. Perform hybrid search (vector + BM25)
4. Format results for LLM context
5. Extract source metadata for attribution

Errors from downstream services (DocumentRepository, EmbeddingProvider,
VectorStore) propagate to the caller so the ChatService can degrade
gracefully.  All failures are logged here for observability.
"""

import logging
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from app.core.config import Settings
from app.core.interfaces import EmbeddingProvider, SearchResult, VectorStore
from app.repositories.document_repo import DocumentRepository

logger = logging.getLogger(__name__)


@dataclass
class SourceReference:
    """
    Source reference for citation in AI responses.
    
    Attributes:
        document_id: Document UUID
        document_title: Title of the source document
        page_number: Page number where content was found (if available)
        chunk_id: ID of the chunk for precise tracking
        chunk_index: Index of the chunk within the document
        similarity_score: Relevance score (0-1)
        content_preview: Preview of the chunk content (first 200 chars)
    """
    document_id: UUID
    document_title: str
    page_number: int | None
    chunk_id: UUID
    chunk_index: int | None = None
    similarity_score: float | None = None
    content_preview: str | None = None


@dataclass
class RetrievalResult:
    """
    Result of a retrieval operation.
    
    Attributes:
        context: Formatted context string ready for LLM prompt
        sources: List of source references for attribution
        chunk_count: Number of chunks retrieved
    """
    context: str
    sources: list[SourceReference]
    chunk_count: int


class RetrievalService:
    """Service for document retrieval and context assembly."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        settings: Settings
    ):
        """
        Initialize retrieval service.
        
        Args:
            document_repo: Document repository for fetching project documents
            vector_store: Vector store for hybrid search
            embedding_provider: Provider for generating query embeddings
            settings: Application settings (retrieval config)
        """
        self.document_repo = document_repo
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.settings = settings

    async def retrieve_for_query(
        self,
        project_id: UUID,
        query: str,
        top_k: int | None = None,
    ) -> RetrievalResult:
        """
        Retrieve relevant document chunks for a query within a project scope.
        
        This is the main retrieval method used by the chat service.
        
        Process:
        1. Get all document IDs linked to the project
        2. Generate query embedding
        3. Perform hybrid search (vector + BM25) filtered by document IDs
        4. Format chunks as labeled context blocks
        5. Extract source metadata for attribution
        
        Args:
            project_id: Project UUID to scope the search
            query: User's query text
            top_k: Number of chunks to retrieve (defaults to config.retrieval.top_k)
            
        Returns:
            RetrievalResult with formatted context and source references
            
        Raises:
            ValueError: If project has no documents
        """
        # Use config default if not specified
        if top_k is None:
            top_k = self.settings.retrieval.top_k

        # Step 1: Get document IDs linked to this project
        documents = await self.document_repo.get_documents_by_project(
            project_id=project_id,
            limit=1000  # High limit to get all documents
        )
        
        if not documents:
            raise ValueError(f"Project {project_id} has no linked documents")
        
        document_ids: list[UUID] = [cast(UUID, doc.id) for doc in documents]
        
        # Create document ID -> title mapping for source references
        doc_title_map: dict[UUID, str] = {
            cast(UUID, doc.id): cast(str, doc.title) for doc in documents
        }
        
        # Step 2: Generate query embedding
        try:
            query_embedding = await self.embedding_provider.embed_text(query)
        except Exception as exc:
            logger.error(
                "Embedding generation failed for project %s: %s",
                project_id, exc,
            )
            raise
        
        # Step 3: Perform hybrid search
        try:
            search_results = await self._perform_search(
                query_embedding=query_embedding,
                query_text=query,
                document_ids=document_ids,
                top_k=top_k
            )
        except Exception as exc:
            logger.error(
                "Vector search failed for project %s: %s",
                project_id, exc,
            )
            raise
        
        if not search_results:
            # No results found - return empty result
            return RetrievalResult(
                context="",
                sources=[],
                chunk_count=0
            )
        
        # Step 4: Format chunks for LLM context
        context = self._format_context(search_results, doc_title_map)
        
        # Step 5: Extract source metadata
        sources = self._extract_sources(search_results, doc_title_map)
        
        return RetrievalResult(
            context=context,
            sources=sources,
            chunk_count=len(search_results)
        )

    async def _perform_search(
        self,
        query_embedding: list[float],
        query_text: str,
        document_ids: list[UUID],
        top_k: int
    ) -> list[SearchResult]:
        """
        Perform vector or hybrid search based on configuration.

        When a re-embedding migration is in progress some chunks may be encoded
        with a different model.  We pass the *current* model ID so the vector
        store only compares embeddings generated by the same model.
        
        Args:
            query_embedding: Query vector
            query_text: Query text for BM25
            document_ids: Document IDs to filter by
            top_k: Number of results
            
        Returns:
            List of search results
        """
        current_model_id = self.settings.embedding.model_id

        if self.settings.retrieval.use_hybrid_search:
            # Hybrid search (vector + BM25)
            return await self.vector_store.hybrid_search(
                query_embedding=query_embedding,
                query_text=query_text,
                document_ids=document_ids,
                top_k=top_k,
                vector_weight=self.settings.retrieval.vector_weight,
                bm25_weight=self.settings.retrieval.bm25_weight,
                embedding_model_id=current_model_id,
            )
        else:
            # Vector-only search
            return await self.vector_store.similarity_search(
                query_embedding=query_embedding,
                document_ids=document_ids,
                top_k=top_k,
                similarity_threshold=self.settings.retrieval.similarity_threshold,
                embedding_model_id=current_model_id,
            )

    def _format_context(
        self,
        search_results: list[SearchResult],
        doc_title_map: dict[UUID, str]
    ) -> str:
        """
        Format retrieved chunks as labeled context blocks for the LLM.
        
        Format:
        ```
        [Source 1: Document Title, Page 5]
        Content of the first chunk...
        
        [Source 2: Another Document, Page 12]
        Content of the second chunk...
        ```
        
        Args:
            search_results: Search results from vector store
            doc_title_map: Mapping of document_id to document title
            
        Returns:
            Formatted context string
        """
        if not search_results:
            return ""
        
        context_blocks = []
        
        for idx, result in enumerate(search_results, start=1):
            # Get document title
            doc_title = doc_title_map.get(result.document_id, "Unknown Document")
            
            # Build source label
            source_label = f"[Source {idx}: {doc_title}"
            if result.page_number is not None:
                source_label += f", Page {result.page_number}"
            source_label += "]"
            
            # Add section heading if available
            if result.section_heading:
                source_label += f"\nSection: {result.section_heading}"
            
            # Combine label and content
            context_block = f"{source_label}\n{result.content}"
            context_blocks.append(context_block)
        
        # Join all blocks with double newline separation
        return "\n\n".join(context_blocks)

    def _extract_sources(
        self,
        search_results: list[SearchResult],
        doc_title_map: dict[UUID, str]
    ) -> list[SourceReference]:
        """
        Extract source references from search results for attribution.
        
        These source references will be:
        - Stored with the assistant message in DynamoDB
        - Sent to the frontend via SSE for display
        - Used for citation links in the UI
        
        Args:
            search_results: Search results from vector store
            doc_title_map: Mapping of document_id to document title
            
        Returns:
            List of source references with deduplication
        """
        sources = []
        seen = set()  # For deduplication: (document_id, page_number)
        
        for result in search_results:
            doc_title = doc_title_map.get(result.document_id, "Unknown Document")
            
            # Create unique key for deduplication
            key = (result.document_id, result.page_number)
            
            if key not in seen:
                sources.append(SourceReference(
                    document_id=result.document_id,
                    document_title=doc_title,
                    page_number=result.page_number,
                    chunk_id=result.chunk_id,
                    chunk_index=result.chunk_index,
                    similarity_score=result.score,
                    content_preview=result.content[:200] if result.content else None,
                ))
                seen.add(key)
        
        return sources
