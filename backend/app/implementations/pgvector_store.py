"""Vector store implementation using PostgreSQL with pgvector extension."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.interfaces.vector_store import SearchResult, VectorStore
from app.models.database import DocumentChunk
from app.repositories.chunk_repo import ChunkRepository


class PGVectorStore(VectorStore):
    """
    Vector store implementation using PostgreSQL with pgvector.
    
    Features:
    - HNSW index for fast similarity search
    - BM25 keyword search using PostgreSQL full-text search
    - Hybrid search with Reciprocal Rank Fusion
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize PGVector store.
        
        Args:
            session: Async database session
        """
        self.session = session
        self.chunk_repo = ChunkRepository(session)

    async def store_embeddings(
        self,
        document_id: UUID,
        chunks: list[dict[str, Any]],
    ) -> None:
        """
        Store document chunks with embeddings in PostgreSQL.
        
        Args:
            document_id: Document ID
            chunks: List of chunk dictionaries with embeddings
        """
        # Ensure document_id is set for all chunks
        for chunk_data in chunks:
            chunk_data["document_id"] = document_id
        
        # Use chunk repository to create chunks
        await self.chunk_repo.create_chunks(chunks)

    async def similarity_search(
        self,
        query_embedding: list[float],
        document_ids: list[UUID],
        top_k: int = 5,
        similarity_threshold: float | None = None,
        embedding_model_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Perform vector similarity search using cosine distance.
        
        Args:
            query_embedding: Query vector
            document_ids: Limit search to these documents
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1). Pass None to
                disable threshold filtering and return top-K by distance only.
            embedding_model_id: If set, only search chunks with this model ID
            
        Returns:
            List of search results sorted by similarity
        """
        # Build query using pgvector's cosine distance operator
        query = select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.page_number,
            DocumentChunk.section_heading,
            (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label("score")
        ).where(
            DocumentChunk.document_id.in_(document_ids),
        )

        # Apply distance threshold only when explicitly requested
        if similarity_threshold is not None:
            distance_threshold = 1.0 - similarity_threshold
            query = query.where(
                DocumentChunk.embedding.cosine_distance(query_embedding) <= distance_threshold
            )

        # Mixed-model filter: only match chunks with the same embedding model
        if embedding_model_id is not None:
            query = query.where(DocumentChunk.embedding_model_id == embedding_model_id)

        query = query.order_by(
            DocumentChunk.embedding.cosine_distance(query_embedding)
        ).limit(top_k)
        
        result = await self.session.execute(query)
        rows = result.all()
        
        # Convert to SearchResult objects
        search_results = []
        for row in rows:
            search_results.append(
                SearchResult(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    content=row.content,
                    score=float(row.score),
                    page_number=row.page_number,
                    section_heading=row.section_heading,
                    chunk_index=row.chunk_index,
                )
            )
        
        return search_results

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
        Perform hybrid search combining vector similarity and BM25.
        
        Uses Reciprocal Rank Fusion (RRF) to combine rankings.
        
        Args:
            query_embedding: Query vector for similarity search
            query_text: Query text for BM25 search
            document_ids: Limit search to these documents
            top_k: Number of results to return
            vector_weight: Weight for vector similarity scores
            bm25_weight: Weight for BM25 scores
            embedding_model_id: If set, only search chunks with this model ID
            
        Returns:
            List of search results with fused ranking
        """
        # Fetch more results from each method for better fusion
        # A 3x multiplier gives RRF enough candidates from both vector and BM25
        # rankings to improve recall and hybrid ranking quality, without the
        # higher query cost of much larger multipliers (e.g., 5x or 10x).
        fetch_k = top_k * 3
        
        # Perform vector similarity search with no threshold — let RRF rank quality.
        # Instructional queries ("give me a summary...") have low cosine similarity
        # to document content, so a fixed threshold would filter out all results.
        vector_results = await self.similarity_search(
            query_embedding=query_embedding,
            document_ids=document_ids,
            top_k=fetch_k,
            similarity_threshold=None,  # No threshold in hybrid mode — RRF handles ranking
            embedding_model_id=embedding_model_id,
        )
        
        # Perform BM25 search
        bm25_results = await self._bm25_search(
            query_text=query_text,
            document_ids=document_ids,
            top_k=fetch_k
        )
        
        # Apply Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight
        )
        
        # Return top-k results
        return fused_results[:top_k]

    async def _bm25_search(
        self,
        query_text: str,
        document_ids: list[UUID],
        top_k: int = 10
    ) -> list[SearchResult]:
        """
        Perform BM25 keyword search using PostgreSQL full-text search.
        
        Args:
            query_text: Query string
            document_ids: Limit search to these documents
            top_k: Number of results to return
            
        Returns:
            List of search results sorted by BM25 score
        """
        # Convert query to tsquery format.
        # websearch_to_tsquery uses OR between terms (like a web search), so it
        # matches chunks containing ANY of the query words rather than ALL of them.
        # This is much better for instructional queries like "give me a summary of..."
        query = select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.page_number,
            DocumentChunk.section_heading,
            # Use ts_rank for BM25-like scoring
            func.ts_rank(
                DocumentChunk.search_vector,
                func.websearch_to_tsquery('english', query_text)
            ).label("score")
        ).where(
            DocumentChunk.document_id.in_(document_ids),
            # Match query against search_vector (OR semantics via websearch_to_tsquery)
            DocumentChunk.search_vector.op("@@")(
                func.websearch_to_tsquery('english', query_text)
            )
        ).order_by(
            text("score DESC")
        ).limit(top_k)
        
        result = await self.session.execute(query)
        rows = result.all()
        
        # Convert to SearchResult objects
        search_results = []
        for row in rows:
            search_results.append(
                SearchResult(
                    chunk_id=row.id,
                    document_id=row.document_id,
                    content=row.content,
                    score=float(row.score),
                    page_number=row.page_number,
                    section_heading=row.section_heading,
                    chunk_index=row.chunk_index,
                )
            )
        
        return search_results

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[SearchResult],
        bm25_results: list[SearchResult],
        vector_weight: float,
        bm25_weight: float,
        k: int = 60
    ) -> list[SearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF formula: score = sum(weight / (k + rank))
        
        Args:
            vector_results: Results from vector similarity search
            bm25_results: Results from BM25 search
            vector_weight: Weight for vector results
            bm25_weight: Weight for BM25 results
            k: Constant for RRF (default: 60)
            
        Returns:
            Fused results sorted by combined score
        """
        # Build maps of chunk_id to rank for each result set
        vector_ranks = {
            result.chunk_id: idx + 1
            for idx, result in enumerate(vector_results)
        }
        
        bm25_ranks = {
            result.chunk_id: idx + 1
            for idx, result in enumerate(bm25_results)
        }
        
        # Collect all unique chunk IDs
        all_chunk_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())
        
        # Create map of chunk_id to SearchResult (prefer vector results for metadata)
        chunk_map = {result.chunk_id: result for result in vector_results}
        chunk_map.update({result.chunk_id: result for result in bm25_results})
        
        # Calculate RRF scores
        rrf_scores: dict[UUID, float] = {}
        for chunk_id in all_chunk_ids:
            score = 0.0
            
            # Add vector score if present
            if chunk_id in vector_ranks:
                score += vector_weight / (k + vector_ranks[chunk_id])
            
            # Add BM25 score if present
            if chunk_id in bm25_ranks:
                score += bm25_weight / (k + bm25_ranks[chunk_id])
            
            rrf_scores[chunk_id] = score
        
        # Sort by RRF score
        sorted_chunk_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True
        )
        
        # Build final results list
        fused_results = []
        for chunk_id in sorted_chunk_ids:
            result = chunk_map[chunk_id]
            # Update score to RRF score
            result.score = rrf_scores[chunk_id]
            fused_results.append(result)
        
        return fused_results

    async def delete_by_document_id(self, document_id: UUID) -> int:
        """
        Delete all chunks for a document.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Number of chunks deleted
        """
        return await self.chunk_repo.delete_by_document_id(document_id)

    async def get_chunk_count(self, document_id: UUID) -> int:
        """
        Get number of chunks for a document.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Chunk count
        """
        return await self.chunk_repo.count_by_document_id(document_id)

    async def close(self) -> None:
        """Close database session."""
        await self.session.close()
