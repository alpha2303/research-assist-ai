"""Pydantic schemas for chat/conversation endpoints."""

from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import ListResponse


class ChatCreate(BaseModel):
    """Request schema for creating a new chat session."""
    
    title: str | None = Field(
        default=None,
        max_length=200,
        description="Chat title (auto-generated from first message if omitted)"
    )


class ChatResponse(BaseModel):
    """Response schema for a single chat session."""
    
    chat_id: str = Field(description="Chat session unique identifier (UUID)")
    project_id: str = Field(description="Associated project ID")
    title: str = Field(description="Chat session title")
    created_at: str = Field(description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(description="Last update timestamp (ISO 8601)")
    message_count: int = Field(
        default=0,
        description="Number of messages in this chat"
    )


class ChatListResponse(ListResponse[ChatResponse]):
    """Response schema for paginated chat list."""
    pass


class SourceReference(BaseModel):
    """Reference to a document chunk used in RAG response."""
    
    document_id: UUID = Field(description="Source document ID")
    document_title: str = Field(description="Source document title")
    chunk_id: str | None = Field(
        default=None,
        description="Chunk ID for precise tracking"
    )
    chunk_index: int | None = Field(
        default=None,
        description="Chunk index within document"
    )
    page_number: int | None = Field(
        default=None,
        description="Page number (if available)"
    )
    section_heading: str | None = Field(
        default=None,
        description="Section heading (if available)"
    )
    similarity_score: float | None = Field(
        default=None,
        description="Relevance score (0-1)"
    )
    content_preview: str | None = Field(
        default=None,
        max_length=200,
        description="Preview of chunk content (first 200 chars)"
    )


class MessageCreate(BaseModel):
    """Request schema for sending a user message."""
    
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="User message content"
    )


class MessageResponse(BaseModel):
    """Response schema for a single message."""
    
    message_id: str = Field(description="Message unique identifier")
    chat_id: str = Field(description="Parent chat session ID")
    sender: str = Field(description="Message sender: 'user' or 'assistant'")
    content: str = Field(description="Message content")
    sources: list[SourceReference] | None = Field(
        default=None,
        description="Source references (for assistant messages only)"
    )
    token_count: int | None = Field(
        default=None,
        description="Token count (for assistant messages)"
    )
    timestamp: str = Field(description="Message timestamp (ISO 8601)")


class MessageListResponse(ListResponse[MessageResponse]):
    """Response schema for paginated message list."""
    pass
