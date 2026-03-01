"""Common Pydantic schemas used across the API."""

from typing import Generic, TypeVar
from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip"
    )


class ErrorResponse(BaseModel):
    """Standard error response format."""
    
    error: str = Field(description="Error type or code")
    message: str = Field(description="Human-readable error message")
    details: dict | None = Field(
        default=None,
        description="Additional error details (optional)"
    )


T = TypeVar('T')


class ListResponse(BaseModel, Generic[T]):
    """Generic paginated list response envelope."""
    
    items: list[T] = Field(description="List of items")
    total: int = Field(description="Total number of items available")
    limit: int = Field(description="Maximum items per page")
    offset: int = Field(description="Number of items skipped")
