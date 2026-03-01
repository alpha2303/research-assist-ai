"""
FastAPI dependency injection providers.

This module wires together all application services into a composable
dependency chain that FastAPI resolves per-request.

Lifecycle:
  - Singleton (process-scoped): AWS clients (LLM, embedding) and stateless
    helpers (PromptBuilder) are created once and reused.  Using module-level
    lazy init avoids the hashability requirement of functools.lru_cache when
    the Settings object is the cache key.

  - Per-request: Services that hold a DB session (DocumentRepository,
    PGVectorStore, RetrievalService) are created fresh each request so they
    stay scoped to the same AsyncSession that FastAPI manages.

  - Per-request (stateless): ChatRepository, SlidingWindowMemory, ChatService
    are lightweight and created fresh each request; FastAPI deduplicates
    repeated Depends() calls within the same request automatically.

Dependency graph (bottom → top):
  get_settings()
      ↓
  get_llm_provider()          get_embedding_provider()    get_prompt_builder()
      ↓                               ↓
  get_chat_repo()   get_document_repo(session)   get_vector_store(session)
      ↓                               ↓
  get_conversation_memory()   get_retrieval_service()
              ↓                       ↓
                      get_chat_service()
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.implementations.bedrock_nova import BedrockNovaProvider
from app.implementations.pgvector_store import PGVectorStore
from app.implementations.titan_embedding import TitanEmbeddingProvider
from app.core.interfaces.conversation_memory import ConversationMemory
from app.repositories.chat_repo import ChatRepository
from app.repositories.document_repo import DocumentRepository
from app.services.chat_service import ChatService
from app.services.conversation_memory import SlidingWindowMemory
from app.services.prompt_builder import PromptBuilder
from app.services.retrieval_service import RetrievalService

# ---------------------------------------------------------------------------
# Process-scoped singletons — expensive AWS clients, created once per process
# ---------------------------------------------------------------------------

_llm_provider: BedrockNovaProvider | None = None
_embedding_provider: TitanEmbeddingProvider | None = None
_prompt_builder: PromptBuilder | None = None


def get_llm_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BedrockNovaProvider:
    """Return (or lazily create) the LLM provider singleton."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = BedrockNovaProvider(
            config=settings.llm,
            aws_profile=settings.aws_profile,
            aws_region=settings.aws_region,
        )
    return _llm_provider


def get_embedding_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TitanEmbeddingProvider:
    """Return (or lazily create) the embedding provider singleton."""
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = TitanEmbeddingProvider(
            config=settings.embedding,
            aws_profile=settings.aws_profile,
            aws_region=settings.aws_region,
        )
    return _embedding_provider


def get_prompt_builder(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PromptBuilder:
    """Return (or lazily create) the prompt builder singleton.

    PromptBuilder loads tiktoken encodings on first instantiation — caching
    avoids repeated disk I/O.
    """
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder(settings=settings)
    return _prompt_builder


# ---------------------------------------------------------------------------
# Request-scoped — tied to the AsyncSession lifetime
# ---------------------------------------------------------------------------


def get_document_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRepository:
    """Create a DocumentRepository for the current request session."""
    return DocumentRepository(session)


def get_vector_store(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PGVectorStore:
    """Create a PGVectorStore for the current request session."""
    return PGVectorStore(session)


def get_retrieval_service(
    document_repo: Annotated[DocumentRepository, Depends(get_document_repo)],
    vector_store: Annotated[PGVectorStore, Depends(get_vector_store)],
    embedding_provider: Annotated[TitanEmbeddingProvider, Depends(get_embedding_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RetrievalService:
    """Assemble the RetrievalService from its dependencies."""
    return RetrievalService(
        document_repo=document_repo,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Request-scoped — stateless wrappers, cheap to create per request
# ---------------------------------------------------------------------------


def get_chat_repo() -> ChatRepository:
    """Create a ChatRepository (DynamoDB-backed, no DB session needed)."""
    return ChatRepository()


def get_conversation_memory(
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    llm_provider: Annotated[BedrockNovaProvider, Depends(get_llm_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationMemory:
    """Assemble the SlidingWindowMemory for the current request."""
    return SlidingWindowMemory(
        chat_repo=chat_repo,
        llm_provider=llm_provider,
        window_size=settings.memory.recent_message_count,
        batch_size=settings.memory.batch_fold_size,
    )


def get_chat_service(
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repo)],
    retrieval_service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    prompt_builder: Annotated[PromptBuilder, Depends(get_prompt_builder)],
    llm_provider: Annotated[BedrockNovaProvider, Depends(get_llm_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
    conversation_memory: Annotated[ConversationMemory, Depends(get_conversation_memory)],
) -> ChatService:
    """Assemble the fully wired ChatService for the current request."""
    return ChatService(
        chat_repo=chat_repo,
        retrieval_service=retrieval_service,
        prompt_builder=prompt_builder,
        llm_provider=llm_provider,
        settings=settings,
        conversation_memory=conversation_memory,
    )


# ---------------------------------------------------------------------------
# Testing helpers
# ---------------------------------------------------------------------------


def reset_singletons() -> None:
    """Clear all cached singletons.

    Call this in test teardown whenever you need a clean DI state, e.g. when
    swapping mocked providers between test cases.
    """
    global _llm_provider, _embedding_provider, _prompt_builder
    _llm_provider = None
    _embedding_provider = None
    _prompt_builder = None
