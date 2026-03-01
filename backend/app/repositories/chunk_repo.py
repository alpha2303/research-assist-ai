"""Repository for document chunk database operations."""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import DocumentChunk


class ChunkRepository:
    """Repository for document chunk database operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: Async database session
        """
        self.session = session

    async def create_chunks(self, chunks_data: list[dict[str, Any]]) -> list[DocumentChunk]:
        """
        Create multiple document chunks in a single transaction.
        
        Args:
            chunks_data: List of chunk dictionaries with all required fields
            
        Returns:
            List of created chunk models
        """
        chunks = [DocumentChunk(**chunk_data) for chunk_data in chunks_data]
        self.session.add_all(chunks)
        await self.session.commit()
        
        # Refresh all chunks to get generated IDs
        for chunk in chunks:
            await self.session.refresh(chunk)
        
        return chunks

    async def get_by_document_id(
        self,
        document_id: UUID,
        limit: int | None = None
    ) -> list[DocumentChunk]:
        """
        Get all chunks for a document.
        
        Args:
            document_id: Document UUID
            limit: Optional limit on number of chunks
            
        Returns:
            List of chunk models
        """
        query = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id
        ).order_by(DocumentChunk.chunk_index)
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_document_id(self, document_id: UUID) -> int:
        """
        Count chunks for a document.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Number of chunks
        """
        result = await self.session.execute(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_id == document_id
            )
        )
        return result.scalar_one()

    async def delete_by_document_id(self, document_id: UUID) -> int:
        """
        Delete all chunks for a document.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Number of chunks deleted
        """
        result = await self.session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id
            )
        )
        await self.session.commit()
        # rowcount is available on delete result
        return result.rowcount if result.rowcount is not None else 0  # type: ignore[attr-defined]

    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk | None:
        """
        Get a chunk by its ID.
        
        Args:
            chunk_id: Chunk UUID
            
        Returns:
            Chunk model or None if not found
        """
        result = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        )
        return result.scalar_one_or_none()

    # ── Re-embedding helpers ─────────────────────────────────────────────────

    async def count_stale_chunks(self, current_model_id: str) -> int:
        """
        Count chunks whose embedding_model_id differs from *current_model_id*.

        Args:
            current_model_id: The current embedding model identifier.

        Returns:
            Number of stale chunks.
        """
        result = await self.session.execute(
            select(func.count(DocumentChunk.id)).where(
                DocumentChunk.embedding_model_id != current_model_id
            )
        )
        return result.scalar_one()

    async def get_stale_chunk_ids(
        self,
        current_model_id: str,
        batch_size: int = 100,
        offset: int = 0,
    ) -> list[UUID]:
        """
        Get a batch of chunk IDs that need re-embedding.

        Args:
            current_model_id: The current embedding model identifier.
            batch_size: Number of IDs to return.
            offset: Pagination offset.

        Returns:
            List of chunk UUIDs.
        """
        result = await self.session.execute(
            select(DocumentChunk.id)
            .where(DocumentChunk.embedding_model_id != current_model_id)
            .order_by(DocumentChunk.id)
            .limit(batch_size)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_chunks_by_ids(self, chunk_ids: list[UUID]) -> list[DocumentChunk]:
        """
        Fetch full chunk rows by their IDs.

        Args:
            chunk_ids: Chunk UUIDs.

        Returns:
            List of chunk models.
        """
        if not chunk_ids:
            return []
        result = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
        )
        return list(result.scalars().all())

    async def bulk_update_embeddings(
        self,
        updates: list[dict[str, Any]],
    ) -> int:
        """
        Bulk-update embeddings and model IDs for a list of chunks.

        Each dict in *updates* must contain keys:
        ``id``, ``embedding``, ``embedding_model_id``.

        Args:
            updates: List of update dicts.

        Returns:
            Number of rows updated.
        """
        if not updates:
            return 0

        # Use per-row UPDATE (safe across all PG versions)
        count = 0
        for u in updates:
            await self.session.execute(
                update(DocumentChunk)
                .where(DocumentChunk.id == u["id"])
                .values(
                    embedding=u["embedding"],
                    embedding_model_id=u["embedding_model_id"],
                )
            )
            count += 1

        await self.session.commit()
        return count
