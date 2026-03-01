"""Pydantic schemas for project management endpoints."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import ListResponse


class ProjectCreate(BaseModel):
    """Request schema for creating a new project."""
    
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Project title"
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Project description (optional)"
    )


class ProjectUpdate(BaseModel):
    """Request schema for updating an existing project."""
    
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Updated project title"
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Updated project description"
    )


class ProjectResponse(BaseModel):
    """Response schema for a single project."""
    
    id: UUID = Field(description="Project unique identifier")
    title: str = Field(description="Project title")
    description: str | None = Field(description="Project description")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    document_count: int = Field(
        default=0,
        description="Number of documents linked to this project"
    )
    
    model_config = {"from_attributes": True}


class ProjectListResponse(ListResponse[ProjectResponse]):
    """Response schema for paginated project list."""
    pass
