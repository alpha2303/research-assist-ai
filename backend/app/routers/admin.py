"""
Admin router — operational endpoints for system management.

Routes:
    POST /api/admin/re-embed   — Trigger bulk re-embedding of stale chunks.
    GET  /api/admin/re-embed/status — Check re-embedding progress.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.dependencies import get_embedding_provider
from app.implementations.titan_embedding import TitanEmbeddingProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class ReEmbedResponse(BaseModel):
    """Response returned when a re-embedding task is submitted."""

    status: str
    task_id: str
    stale_chunk_count: int
    current_model_id: str


class ReEmbedStatusResponse(BaseModel):
    """Progress snapshot for the re-embedding pipeline."""

    stale_chunk_count: int
    current_model_id: str


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/re-embed", response_model=ReEmbedResponse)
async def trigger_re_embed(
    settings: Settings = Depends(get_settings),
    embedding_provider: TitanEmbeddingProvider = Depends(get_embedding_provider),
):
    """
    Trigger bulk re-embedding of all chunks whose ``embedding_model_id``
    differs from the currently configured model.

    Enqueues a Celery task that processes chunks in batches.
    """
    from app.worker.tasks import re_embed_chunks

    current_model_id = embedding_provider.get_model_id()

    # Quick check: count stale chunks
    from app.db.base import get_session_factory
    from app.repositories.chunk_repo import ChunkRepository

    session_factory = get_session_factory()
    async with session_factory() as session:
        chunk_repo = ChunkRepository(session)
        stale_count = await chunk_repo.count_stale_chunks(current_model_id)

    if stale_count == 0:
        raise HTTPException(
            status_code=200,
            detail="All chunks are already using the current embedding model.",
        )

    # Enqueue the Celery task
    task = re_embed_chunks.delay(current_model_id)

    logger.info(
        "Re-embedding task %s queued — %d stale chunks with target model %s",
        task.id,
        stale_count,
        current_model_id,
    )

    return ReEmbedResponse(
        status="queued",
        task_id=task.id,
        stale_chunk_count=stale_count,
        current_model_id=current_model_id,
    )


@router.get("/re-embed/status", response_model=ReEmbedStatusResponse)
async def re_embed_status(
    settings: Settings = Depends(get_settings),
    embedding_provider: TitanEmbeddingProvider = Depends(get_embedding_provider),
):
    """Return how many chunks still need re-embedding."""
    from app.db.base import get_session_factory
    from app.repositories.chunk_repo import ChunkRepository

    current_model_id = embedding_provider.get_model_id()

    session_factory = get_session_factory()
    async with session_factory() as session:
        chunk_repo = ChunkRepository(session)
        stale_count = await chunk_repo.count_stale_chunks(current_model_id)

    return ReEmbedStatusResponse(
        stale_chunk_count=stale_count,
        current_model_id=current_model_id,
    )
