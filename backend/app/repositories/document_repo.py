"""Repository for document database operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Document, DocumentStatus, ProjectDocument


class DocumentRepository:
    """Repository for document database operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: Async database session
        """
        self.session = session

    async def create(self, document_data: dict[str, Any]) -> Document:
        """
        Create a new document in the database.
        
        Args:
            document_data: Document attributes
            
        Returns:
            Created document model
            
        Raises:
            IntegrityError: If a document with the same unique key already exists
                (e.g., duplicate file_hash).  The session is rolled back before
                re-raising so the caller can continue using it.
        """
        document = Document(**document_data)
        self.session.add(document)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(document)
        return document

    async def get_by_id(self, document_id: UUID) -> Document | None:
        """
        Get a document by its ID.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Document model or None if not found
        """
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Document | None:
        """
        Get a document by its file hash (for deduplication).
        
        Args:
            file_hash: SHA-256 hash of the file
            
        Returns:
            Document model or None if not found
        """
        result = await self.session.execute(
            select(Document).where(Document.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        error_message: str | None = None
    ) -> Document | None:
        """
        Update document processing status.
        
        Args:
            document_id: Document UUID
            status: New status (DocumentStatus enum)
            error_message: Error message if status is failed
            
        Returns:
            Updated document model or None if not found
        """
        document = await self.get_by_id(document_id)
        if document is None:
            return None
        
        # SQLAlchemy ORM updates
        document.status = status  # type: ignore[assignment]
        document.error_message = error_message  # type: ignore[assignment]
        
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def get_documents_by_project(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> list[Document]:
        """
        Get all documents linked to a project.
        
        Args:
            project_id: Project UUID
            limit: Maximum number of documents to return
            offset: Number of documents to skip
            
        Returns:
            List of document models
        """
        result = await self.session.execute(
            select(Document)
            .join(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def link_to_project(
        self,
        project_id: UUID,
        document_id: UUID
    ) -> ProjectDocument:
        """
        Link a document to a project.
        
        Args:
            project_id: Project UUID
            document_id: Document UUID
            
        Returns:
            Created ProjectDocument link
        """
        # Check if link already exists
        result = await self.session.execute(
            select(ProjectDocument).where(
                ProjectDocument.project_id == project_id,
                ProjectDocument.document_id == document_id
            )
        )
        existing_link = result.scalar_one_or_none()
        
        if existing_link:
            return existing_link
        
        # Create new link
        project_document = ProjectDocument(
            project_id=project_id,
            document_id=document_id
        )
        self.session.add(project_document)
        await self.session.commit()
        await self.session.refresh(project_document)
        return project_document

    async def unlink_from_project(
        self,
        project_id: UUID,
        document_id: UUID
    ) -> bool:
        """
        Unlink a document from a project.
        
        Args:
            project_id: Project UUID
            document_id: Document UUID
            
        Returns:
            True if link was removed, False if it didn't exist
        """
        result = await self.session.execute(
            select(ProjectDocument).where(
                ProjectDocument.project_id == project_id,
                ProjectDocument.document_id == document_id
            )
        )
        link = result.scalar_one_or_none()
        
        if link is None:
            return False
        
        await self.session.delete(link)
        await self.session.commit()
        return True

    async def delete(self, document_id: UUID) -> bool:
        """
        Delete a document (admin operation, removes all links).
        
        Args:
            document_id: Document UUID
            
        Returns:
            True if document was deleted, False if it didn't exist
        """
        document = await self.get_by_id(document_id)
        if document is None:
            return False
        
        await self.session.delete(document)
        await self.session.commit()
        return True

    async def count_by_project(self, project_id: UUID) -> int:
        """
        Count documents linked to a project.
        
        Args:
            project_id: Project UUID
            
        Returns:
            Number of documents
        """
        result = await self.session.execute(
            select(func.count(Document.id))
            .join(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
        )
        return result.scalar_one()
