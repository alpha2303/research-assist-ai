"""Repository layer for project CRUD operations.

This module provides database access methods for the Project model using
async SQLAlchemy operations. All database queries are encapsulated here.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Project
from app.schemas.common import PaginationParams


class ProjectRepository:
    """Repository for project database operations.
    
    Handles all SQLAlchemy queries for the Project model, including
    CRUD operations and pagination.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.
        
        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session
    
    async def create(self, title: str, description: Optional[str] = None) -> Project:
        """Create a new project.
        
        Args:
            title: Project title (required)
            description: Project description (optional)
            
        Returns:
            Created Project instance with generated ID and timestamps
        """
        project = Project(title=title, description=description)
        self.session.add(project)
        await self.session.flush()  # Generate ID before commit
        await self.session.refresh(project)  # Load all attributes
        return project
    
    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """Get a project by ID.
        
        Args:
            project_id: UUID of the project to retrieve
            
        Returns:
            Project instance if found, None otherwise
        """
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> tuple[list[Project], int]:
        """Get all projects with pagination.
        
        Projects are sorted by updated_at descending (most recent first).
        
        Args:
            pagination: Optional pagination parameters (limit/offset)
            
        Returns:
            Tuple of (list of projects, total count)
        """
        # Count query
        count_stmt = select(func.count()).select_from(Project)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()
        
        # Data query with pagination
        stmt = select(Project).order_by(Project.updated_at.desc())
        
        if pagination:
            stmt = stmt.limit(pagination.limit).offset(pagination.offset)
        
        result = await self.session.execute(stmt)
        projects = list(result.scalars().all())
        
        return projects, total
    
    async def update(
        self,
        project_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Project]:
        """Update a project's attributes.
        
        Only provided fields are updated. None values are ignored.
        The updated_at timestamp is automatically updated by the model.
        
        Args:
            project_id: UUID of the project to update
            title: New title (optional)
            description: New description (optional)
            
        Returns:
            Updated Project instance if found, None otherwise
        """
        # Build update dict with only provided values
        update_data = {}
        if title is not None:
            update_data['title'] = title
        if description is not None:
            update_data['description'] = description
        
        if not update_data:
            # No fields to update, just fetch and return
            return await self.get_by_id(project_id)
        
        stmt = (
            update(Project)
            .where(Project.id == project_id)
            .values(**update_data)
            .returning(Project)
        )
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def delete(self, project_id: UUID) -> bool:
        """Delete a project by ID.
        
        Cascade deletes related records (project_documents associations).
        Chat sessions should be deleted separately via DynamoDB.
        
        Args:
            project_id: UUID of the project to delete
            
        Returns:
            True if project was deleted, False if not found
        """
        stmt = delete(Project).where(Project.id == project_id)
        result: CursorResult = await self.session.execute(stmt)  # type: ignore[assignment]
        return result.rowcount > 0
    
    async def get_document_count(self, project_id: UUID) -> int:
        """Get the number of documents linked to a project.
        
        Args:
            project_id: UUID of the project
            
        Returns:
            Count of linked documents
        """
        from app.models.database import ProjectDocument
        
        stmt = (
            select(func.count())
            .select_from(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
