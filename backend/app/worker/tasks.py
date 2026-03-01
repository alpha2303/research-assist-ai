"""Celery tasks for document processing pipeline."""

import logging
import tempfile
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.db.base import get_session_factory, init_db, _engine
from app.implementations.pdf_parsers import PdfPlumberParser, PyMuPDF4LLMParser
from app.implementations.pgvector_store import PGVectorStore
from app.implementations.titan_embedding import TitanEmbeddingProvider
from app.models.database import DocumentStatus
from app.repositories.document_repo import DocumentRepository
from app.services.chunking_service import TextChunker
from app.services.storage_service import StorageService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _ensure_db() -> None:
    """Lazily initialise the async DB engine for the worker process."""
    if _engine is None:
        settings = get_settings()
        init_db(settings.database_url)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def process_document(self, document_id: str) -> dict[str, str | int]:
    """
    Process a document through the full ingestion pipeline.
    
    Pipeline stages:
    1. Download document from S3
    2. Parse PDF to extract text
    3. Chunk text with overlap
    4. Generate embeddings for chunks
    5. Store chunks and embeddings in database
    
    Args:
        self: Celery task instance (for retry logic)
        document_id: UUID of document to process (as string)
        
    Returns:
        Dict with status and metrics
        
    Raises:
        Exception: If processing fails after max retries
    """
    import asyncio
    
    # Convert string UUID to UUID object
    doc_uuid = UUID(document_id)
    
    # Run async processing in event loop
    try:
        result = asyncio.run(_process_document_async(doc_uuid))
        return result
    except Exception as exc:
        # Retry on failure
        if self.request.retries < self.max_retries:
            # Update document status to show retry
            asyncio.run(_update_document_status(
                doc_uuid,
                DocumentStatus.PROCESSING,
                f"Retry {self.request.retries + 1}/{self.max_retries}"
            ))
            raise self.retry(exc=exc)
        else:
            # Max retries exceeded - mark as failed
            asyncio.run(_update_document_status(
                doc_uuid,
                DocumentStatus.FAILED,
                f"Processing failed after {self.max_retries} retries: {str(exc)}"
            ))
            raise


async def _process_document_async(document_id: UUID) -> dict[str, str | int]:
    """
    Async implementation of document processing pipeline.
    
    Args:
        document_id: Document UUID
        
    Returns:
        Processing results with metrics
    """
    settings = get_settings()
    
    # Ensure DB is initialised in worker process
    _ensure_db()
    
    # Create async session factory
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        # Initialize services
        document_repo = DocumentRepository(session)
        storage_service = StorageService(settings)
        vector_store = PGVectorStore(session)
        embedding_provider = TitanEmbeddingProvider(
            settings.embedding,
            settings.aws_profile,
            settings.aws_region
        )
        chunker = TextChunker(settings.chunking)
        
        # Get document from database
        document = await document_repo.get_by_id(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Update status to processing
        await document_repo.update_status(document_id, DocumentStatus.PROCESSING)
        
        try:
            # Stage 1: Download from S3
            file_content = storage_service.download_file(document.s3_key)  # type: ignore[arg-type]
            
            # Stage 2: Parse PDF
            parse_result = await _parse_document(
                file_content,
                document.title,  # type: ignore[arg-type]
                settings
            )
            
            # Stage 3: Chunk text
            # Convert pages to list of (page_number, text) tuples
            pages_data = [
                (page.page_number, page.text)
                for page in parse_result.pages
            ]
            
            chunks = chunker.chunk_document_pages(
                pages_data,
                document_metadata={
                    "document_id": str(document_id),
                    "title": document.title  # type: ignore[dict-item]
                }
            )
            
            if not chunks:
                raise ValueError("No chunks extracted from document")
            
            # Stage 4: Generate embeddings
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await embedding_provider.embed_batch(chunk_texts)
            
            # Stage 5: Store in database
            chunks_data = []
            for chunk, embedding in zip(chunks, embeddings):
                chunks_data.append({
                    "document_id": document_id,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "embedding": embedding,
                    "page_number": chunk.page_number,
                    "section_heading": chunk.section_heading,
                    "token_count": chunk.token_count,
                    "embedding_model_id": embedding_provider.get_model_id()
                })
            
            await vector_store.store_embeddings(document_id, chunks_data)
            
            # Update document with results
            document.page_count = parse_result.total_pages  # type: ignore[assignment]
            await document_repo.update_status(document_id, DocumentStatus.COMPLETED)
            
            # Return success metrics
            return {
                "status": "success",
                "document_id": str(document_id),
                "page_count": parse_result.total_pages,
                "chunk_count": len(chunks),
                "total_tokens": sum(chunk.token_count for chunk in chunks)
            }
            
        except Exception as e:
            # Update document status to failed
            await document_repo.update_status(
                document_id,
                DocumentStatus.FAILED,
                str(e)
            )
            raise


async def _parse_document(
    file_content: bytes,
    filename: str,
    settings
):
    """
    Parse document with fallback logic.
    
    Args:
        file_content: Binary file content
        filename: Original filename
        settings: Application settings
        
    Returns:
        ParseResult from successful parser
        
    Raises:
        RuntimeError: If all parsers fail
    """
    # Save to temporary file
    with tempfile.NamedTemporaryFile(
        suffix=Path(filename).suffix,
        delete=False
    ) as tmp_file:
        tmp_file.write(file_content)
        tmp_path = Path(tmp_file.name)
    
    try:
        # Try primary parser
        if settings.document_processing.primary_parser == "pymupdf4llm":
            parser = PyMuPDF4LLMParser()
        else:
            parser = PdfPlumberParser()
        
        try:
            result = await parser.parse(tmp_path)
            return result
        except Exception as primary_error:
            # Try fallback parser
            fallback_name = settings.document_processing.fallback_parser
            
            if fallback_name == "pdfplumber":
                fallback_parser = PdfPlumberParser()
            else:
                fallback_parser = PyMuPDF4LLMParser()
            
            try:
                result = await fallback_parser.parse(tmp_path)
                return result
            except Exception as fallback_error:
                raise RuntimeError(
                    f"All parsers failed. Primary: {str(primary_error)}, "
                    f"Fallback: {str(fallback_error)}"
                )
    finally:
        # Clean up temporary file
        tmp_path.unlink(missing_ok=True)


async def _update_document_status(
    document_id: UUID,
    status: DocumentStatus,
    error_message: str | None = None
) -> None:
    """
    Update document processing status.
    
    Args:
        document_id: Document UUID
        status: DocumentStatus enum value
        error_message: Optional error message
    """
    _ensure_db()
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        document_repo = DocumentRepository(session)
        await document_repo.update_status(document_id, status, error_message)


# ═══════════════════════════════════════════════════════════════════════════════
# RE-EMBEDDING TASK
# ═══════════════════════════════════════════════════════════════════════════════

REEMBED_BATCH_SIZE = 50


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def re_embed_chunks(self, target_model_id: str) -> dict[str, str | int]:
    """
    Bulk re-embed all chunks whose ``embedding_model_id`` differs from
    *target_model_id*.

    Processing is batched to limit memory usage and allow the task to
    be effectively resumed if interrupted (already-updated chunks are
    simply skipped on the next invocation).

    Args:
        self: Celery task instance (for retry/progress).
        target_model_id: The embedding model ID to converge to.

    Returns:
        Dict with ``status``, ``updated``, and ``remaining`` keys.
    """
    import asyncio

    try:
        result = asyncio.run(_re_embed_async(target_model_id))
        return result
    except Exception as exc:
        logger.exception("Re-embedding task failed: %s", exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


async def _re_embed_async(target_model_id: str) -> dict[str, str | int]:
    """
    Async implementation of the re-embedding pipeline.

    Processes stale chunks in fixed-size batches until none remain.
    """
    settings = get_settings()
    _ensure_db()
    session_factory = get_session_factory()

    embedding_provider = TitanEmbeddingProvider(
        settings.embedding,
        settings.aws_profile,
        settings.aws_region,
    )

    total_updated = 0

    while True:
        async with session_factory() as session:
            from app.repositories.chunk_repo import ChunkRepository

            chunk_repo = ChunkRepository(session)

            # Fetch a batch of stale chunk IDs
            stale_ids = await chunk_repo.get_stale_chunk_ids(
                current_model_id=target_model_id,
                batch_size=REEMBED_BATCH_SIZE,
            )

            if not stale_ids:
                break  # All chunks are up-to-date

            # Load full chunk rows
            chunks = await chunk_repo.get_chunks_by_ids(stale_ids)

            # Generate new embeddings
            texts = [c.content for c in chunks]
            embeddings = await embedding_provider.embed_batch(texts)

            # Build update payloads
            updates = [
                {
                    "id": chunk.id,
                    "embedding": emb,
                    "embedding_model_id": target_model_id,
                }
                for chunk, emb in zip(chunks, embeddings)
            ]

            updated = await chunk_repo.bulk_update_embeddings(updates)
            total_updated += updated

            logger.info(
                "Re-embedded batch of %d chunks (total so far: %d)",
                updated,
                total_updated,
            )

    # Final count of remaining stale chunks (should be 0)
    async with session_factory() as session:
        from app.repositories.chunk_repo import ChunkRepository

        chunk_repo = ChunkRepository(session)
        remaining = await chunk_repo.count_stale_chunks(target_model_id)

    logger.info(
        "Re-embedding complete — %d updated, %d remaining",
        total_updated,
        remaining,
    )

    return {
        "status": "completed",
        "updated": total_updated,
        "remaining": remaining,
    }
