"""Pydantic schemas for document management endpoints."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import ListResponse


class DocumentUploadResponse(BaseModel):
    """Response schema after document upload."""
    
    id: UUID = Field(description="Unique document identifier")
    title: str = Field(description="Document title (filename)")
    file_hash: str = Field(description="SHA-256 hash of file for deduplication")
    file_size_bytes: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type (e.g., application/pdf)")
    status: str = Field(description="Processing status (queued/processing/ready/failed)")
    s3_key: str = Field(description="S3 object key")
    created_at: datetime = Field(description="Upload timestamp")
    is_duplicate: bool = Field(
        default=False,
        description="True if this file hash was already uploaded previously"
    )
    
    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    """Detailed document information response."""
    
    id: UUID = Field(description="Unique document identifier")
    title: str = Field(description="Document title (filename)")
    file_hash: str = Field(description="SHA-256 hash of file")
    file_size_bytes: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type")
    status: str = Field(description="Processing status")
    s3_key: str = Field(description="S3 object key")
    page_count: int | None = Field(default=None, description="Number of pages")
    error_message: str | None = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(description="Upload timestamp")
    
    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    """Response schema for document processing status."""
    
    id: UUID = Field(description="Document unique identifier")
    title: str = Field(description="Document title")
    status: str = Field(description="Processing status")
    error_message: str | None = Field(
        default=None,
        description="Error message if status=failed"
    )
    page_count: int | None = Field(
        default=None,
        description="Number of pages (available after processing)"
    )
    file_size_bytes: int = Field(description="File size in bytes")
    mime_type: str = Field(description="MIME type (e.g., application/pdf)")
    created_at: datetime = Field(description="Upload timestamp")
    
    model_config = {"from_attributes": True}


class DocumentListItem(BaseModel):
    """Schema for a document in list responses."""
    
    id: UUID = Field(description="Document unique identifier")
    title: str = Field(description="Document title")
    status: str = Field(description="Processing status")
    page_count: int | None = Field(description="Number of pages")
    file_size_bytes: int = Field(description="File size in bytes")
    created_at: datetime = Field(description="Upload timestamp")
    
    model_config = {"from_attributes": True}


class DocumentListResponse(ListResponse[DocumentListItem]):
    """Response schema for paginated document list."""
    pass


class DocumentLinkRequest(BaseModel):
    """Request schema for linking an existing document to a project."""
    
    document_id: UUID = Field(description="ID of the document to link")

