"""Service layer for project business logic.

This module provides business logic for project operations, orchestrating
repository calls and handling validation, error cases, and data transformation.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Project
from app.repositories.project_repo import ProjectRepository
from app.schemas.common import PaginationParams
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)


class ProjectService:
    """Service for project business logic.
    
    Orchestrates repository operations and applies business rules.
    Transforms database models to API response schemas.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.
        
        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.repo = ProjectRepository(session)
    
    async def create_project(self, data: ProjectCreate) -> ProjectResponse:
        """Create a new project.
        
        Args:
            data: Project creation data (title, description)
            
        Returns:
            Created project as response schema
        """
        project = await self.repo.create(
            title=data.title,
            description=data.description
        )
        
        return await self._to_response(project)
    
    async def get_project(self, project_id: UUID) -> Optional[ProjectResponse]:
        """Get a project by ID.
        
        Args:
            project_id: UUID of the project to retrieve
            
        Returns:
            Project response schema if found, None otherwise
        """
        project = await self.repo.get_by_id(project_id)
        if not project:
            return None
        
        return await self._to_response(project)
    
    async def list_projects(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> tuple[list[ProjectResponse], int]:
        """List all projects with pagination.
        
        Args:
            pagination: Optional pagination parameters
            
        Returns:
            Tuple of (list of project responses, total count)
        """
        projects, total = await self.repo.get_all(pagination)
        
        responses = []
        for project in projects:
            responses.append(await self._to_response(project))
        
        return responses, total
    
    async def update_project(
        self,
        project_id: UUID,
        data: ProjectUpdate
    ) -> Optional[ProjectResponse]:
        """Update a project.
        
        Only fields provided in the update data are modified.
        
        Args:
            project_id: UUID of the project to update
            data: Update data (title, description)
            
        Returns:
            Updated project response if found, None otherwise
        """
        project = await self.repo.update(
            project_id=project_id,
            title=data.title,
            description=data.description
        )
        
        if not project:
            return None
        
        return await self._to_response(project)
    
    async def delete_project(self, project_id: UUID) -> bool:
        """Delete a project.
        
        Note: Chat sessions in DynamoDB should be deleted separately
        by the caller (this only handles PostgreSQL cascade).
        
        Args:
            project_id: UUID of the project to delete
            
        Returns:
            True if project was deleted, False if not found
        """
        return await self.repo.delete(project_id)
    
    async def _to_response(self, project: Project) -> ProjectResponse:
        """Convert database model to response schema.
        
        Args:
            project: Project model instance
            
        Returns:
            ProjectResponse schema with document count
        """
        document_count = await self.repo.get_document_count(project.id)  # type: ignore[arg-type]
        
        # Use model_validate with from_attributes to convert SQLAlchemy model
        response = ProjectResponse.model_validate(project)
        response.document_count = document_count
        
        return response
