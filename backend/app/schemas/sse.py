"""Pydantic schemas for Server-Sent Events (SSE) streaming responses."""

from pydantic import BaseModel, Field
from app.schemas.chat import SourceReference


class TokenEvent(BaseModel):
    """SSE event for streaming LLM response tokens.
    
    Event type: 'token'
    """
    
    event: str = Field(default="token", description="Event type")
    data: str = Field(description="Token or text chunk from LLM")


class SourcesEvent(BaseModel):
    """SSE event for sending retrieved source documents.
    
    Sent after retrieval completes, before LLM starts generating.
    Event type: 'sources'
    """
    
    event: str = Field(default="sources", description="Event type")
    data: list[SourceReference] = Field(
        description="List of source documents used for RAG"
    )


class DoneEvent(BaseModel):
    """SSE event indicating stream completion.
    
    Sent after the LLM finishes generating the complete response.
    Event type: 'done'
    """
    
    event: str = Field(default="done", description="Event type")
    data: dict = Field(
        description="Completion metadata (e.g., message_id, token_count)"
    )


class ErrorEvent(BaseModel):
    """SSE event for error conditions during streaming.
    
    Event type: 'error'
    """
    
    event: str = Field(default="error", description="Event type")
    data: dict = Field(
        description="Error details: {error: str, message: str, details?: dict}"
    )
