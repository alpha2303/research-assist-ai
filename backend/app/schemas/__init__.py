"""Pydantic schemas for API requests and responses."""

# Common schemas
from app.schemas.common import (
    PaginationParams,
    ErrorResponse,
    ListResponse,
)

# Project schemas
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
)

# Document schemas
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentStatusResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentLinkRequest,
)

# Chat schemas
from app.schemas.chat import (
    ChatCreate,
    ChatResponse,
    ChatListResponse,
    SourceReference,
    MessageCreate,
    MessageResponse,
    MessageListResponse,
)

# SSE event schemas
from app.schemas.sse import (
    TokenEvent,
    SourcesEvent,
    DoneEvent,
    ErrorEvent,
)

__all__ = [
    # Common
    "PaginationParams",
    "ErrorResponse",
    "ListResponse",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectListResponse",
    # Document
    "DocumentUploadResponse",
    "DocumentStatusResponse",
    "DocumentListItem",
    "DocumentListResponse",
    "DocumentLinkRequest",
    # Chat
    "ChatCreate",
    "ChatResponse",
    "ChatListResponse",
    "SourceReference",
    "MessageCreate",
    "MessageResponse",
    "MessageListResponse",
    # SSE
    "TokenEvent",
    "SourcesEvent",
    "DoneEvent",
    "ErrorEvent",
]
