"""Router for project management endpoints.

This module defines all REST API endpoints for project CRUD operations.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas.common import ErrorResponse, PaginationParams
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Project created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request data"},
    }
)
async def create_project(
    data: ProjectCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectResponse:
    """Create a new project.
    
    Args:
        data: Project creation data (title, description)
        db: Database session dependency
        
    Returns:
        Created project with ID and timestamps
    """
    service = ProjectService(db)
    return await service.create_project(data)


@router.get(
    "",
    response_model=ProjectListResponse,
    responses={
        200: {"description": "List of projects retrieved successfully"},
    }
)
async def list_projects(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db)
) -> ProjectListResponse:
    """List all projects with pagination.
    
    Projects are sorted by updated_at descending (most recent first).
    
    Args:
        limit: Maximum number of projects to return (1-100)
        offset: Number of projects to skip
        db: Database session dependency
        
    Returns:
        Paginated list of projects with total count
    """
    pagination = PaginationParams(limit=limit, offset=offset)
    service = ProjectService(db)
    
    projects, total = await service.list_projects(pagination)
    
    return ProjectListResponse(
        items=projects,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        200: {"description": "Project retrieved successfully"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    }
)
async def get_project(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectResponse:
    """Get a project by ID.
    
    Args:
        project_id: UUID of the project to retrieve
        db: Database session dependency
        
    Returns:
        Project details
        
    Raises:
        HTTPException: 404 if project not found
    """
    service = ProjectService(db)
    project = await service.get_project(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    
    return project


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        200: {"description": "Project updated successfully"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    }
)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> ProjectResponse:
    """Update a project.
    
    Only fields provided in the request body are updated.
    
    Args:
        project_id: UUID of the project to update
        data: Update data (title, description)
        db: Database session dependency
        
    Returns:
        Updated project details
        
    Raises:
        HTTPException: 404 if project not found
    """
    service = ProjectService(db)
    project = await service.update_project(project_id, data)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Project deleted successfully"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    }
)
async def delete_project(
    project_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    """Delete a project.
    
    Cascade deletes all associated project-document links.
    Note: Chat sessions in DynamoDB must be deleted separately.
    
    Args:
        project_id: UUID of the project to delete
        db: Database session dependency
        
    Raises:
        HTTPException: 404 if project not found
    """
    service = ProjectService(db)
    deleted = await service.delete_project(project_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
