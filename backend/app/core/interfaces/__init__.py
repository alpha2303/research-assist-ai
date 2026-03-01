"""
Core interfaces for Research Assist AI.

These interfaces define the contracts for all major system components,
enabling implementation swapping without changing business logic.

Design Pattern: Dependency Inversion Principle (SOLID)
- High-level modules depend on abstractions, not concrete implementations
- Enables testing with mocks and production with real implementations
- Supports gradual migration (e.g., PGVector → Pinecone)
"""

from app.core.interfaces.conversation_memory import (
    ConversationContext,
    ConversationMemory,
    Message,
    MessageRole,
)
from app.core.interfaces.document_parser import (
    DocumentParser,
    PageContent,
    ParseResult,
)
from app.core.interfaces.embedding_provider import EmbeddingProvider
from app.core.interfaces.llm_provider import LLMProvider
from app.core.interfaces.task_queue import (
    TaskQueue,
    TaskResult,
    TaskStatus,
)
from app.core.interfaces.vector_store import SearchResult, VectorStore

__all__ = [
    # Vector Store
    "VectorStore",
    "SearchResult",
    # Embedding Provider
    "EmbeddingProvider",
    # LLM Provider
    "LLMProvider",
    # Document Parser
    "DocumentParser",
    "ParseResult",
    "PageContent",
    # Task Queue
    "TaskQueue",
    "TaskResult",
    "TaskStatus",
    # Conversation Memory
    "ConversationMemory",
    "ConversationContext",
    "Message",
    "MessageRole",
]
