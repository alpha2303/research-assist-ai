"""Service layer for document management operations."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID

from app.core.config import Settings
from app.core.interfaces.task_queue import TaskQueue
from app.models.database import DocumentStatus
from app.repositories.document_repo import DocumentRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.document import (
    DocumentListItem,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.storage_service import StorageService


class DocumentService:
    """Service for document management business logic."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        project_repo: ProjectRepository,
        storage_service: StorageService,
        settings: Settings,
        task_queue: TaskQueue | None = None,
    ):
        """
        Initialize document service.
        
        Args:
            document_repo: Document repository
            project_repo: Project repository
            storage_service: Storage service for S3 operations
            settings: Application settings
            task_queue: Optional task queue for async processing
        """
        self.document_repo = document_repo
        self.project_repo = project_repo
        self.storage_service = storage_service
        self.settings = settings
        self._task_queue = task_queue

    async def upload_document(
        self,
        file_content: bytes,
        filename: str,
        content_type: str
    ) -> tuple[DocumentUploadResponse, bool]:
        """
        Upload a document to S3 and create database record.
        
        Handles deduplication by checking file hash.
        
        Args:
            file_content: Binary file content
            filename: Original filename
            content_type: MIME type
            
        Returns:
            Tuple of (DocumentUploadResponse, is_duplicate)
            
        Raises:
            ValueError: If file validation fails
        """
        # Validate file
        self._validate_file(file_content, content_type)
        
        # Create file-like object
        file_obj = BytesIO(file_content)
        
        # Compute hash and upload to S3
        file_hash, s3_key = self.storage_service.upload_file(
            file_obj,
            filename,
            content_type
        )
        
        # Check if document with this hash already exists
        existing_doc = await self.document_repo.get_by_hash(file_hash)
        
        if existing_doc:
            # File already exists - return existing document
            response = DocumentUploadResponse.model_validate(existing_doc)
            response.is_duplicate = True
            
            # Re-submit processing if document is stuck in QUEUED
            if existing_doc.status == DocumentStatus.QUEUED:  # type: ignore[truthy-bool]
                await self._submit_processing_task(existing_doc.id)  # type: ignore[arg-type]
            
            return response, True
        
        # Create new document record
        document = await self.document_repo.create({
            "title": filename,
            "file_hash": file_hash,
            "file_size_bytes": len(file_content),
            "mime_type": content_type,
            "s3_key": s3_key,
            "status": DocumentStatus.QUEUED,
        })
        
        response = DocumentUploadResponse.model_validate(document)
        response.is_duplicate = False
        
        # Submit async processing task (only for new documents)
        await self._submit_processing_task(document.id)  # type: ignore[arg-type]
        
        return response, False

    async def _submit_processing_task(self, document_id: UUID) -> None:
        """
        Submit document processing task via the TaskQueue interface.

        Falls back to a direct Celery import when no TaskQueue was injected
        (backwards-compatible with code that doesn't use DI yet).
        
        Args:
            document_id: Document UUID
        """
        if self._task_queue is not None:
            await self._task_queue.submit_task(
                "app.worker.tasks.process_document",
                args=[str(document_id)],
            )
        else:
            # Legacy fallback — direct Celery call
            from app.worker.tasks import process_document
            process_document.delay(str(document_id))

    async def get_document(self, document_id: UUID) -> DocumentResponse | None:
        """
        Get document details by ID.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Document response or None if not found
        """
        document = await self.document_repo.get_by_id(document_id)
        if document is None:
            return None
        
        return DocumentResponse.model_validate(document)

    async def get_document_status(
        self,
        document_id: UUID
    ) -> DocumentStatusResponse | None:
        """
        Get document processing status.
        
        Args:
            document_id: Document UUID
            
        Returns:
            Document status response or None if not found
        """
        document = await self.document_repo.get_by_id(document_id)
        if document is None:
            return None
        
        return DocumentStatusResponse.model_validate(document)

    async def list_project_documents(
        self,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> DocumentListResponse:
        """
        List all documents for a project.
        
        Args:
            project_id: Project UUID
            limit: Maximum number of documents to return
            offset: Number of documents to skip
            
        Returns:
            Document list response with pagination
        """
        documents = await self.document_repo.get_documents_by_project(
            project_id,
            limit,
            offset
        )
        total = await self.document_repo.count_by_project(project_id)
        
        items = [DocumentListItem.model_validate(doc) for doc in documents]
        
        return DocumentListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset
        )

    async def link_document_to_project(
        self,
        project_id: UUID,
        document_id: UUID
    ) -> bool:
        """
        Link a document to a project.
        
        Args:
            project_id: Project UUID
            document_id: Document UUID
            
        Returns:
            True if link was created
            
        Raises:
            ValueError: If project or document doesn't exist
        """
        # Verify project exists
        project = await self.project_repo.get_by_id(project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")
        
        # Verify document exists
        document = await self.document_repo.get_by_id(document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        
        # Create link
        await self.document_repo.link_to_project(project_id, document_id)
        return True

    async def unlink_document_from_project(
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
        return await self.document_repo.unlink_from_project(
            project_id,
            document_id
        )

    def _validate_file(self, file_content: bytes, content_type: str) -> None:
        """
        Validate file before processing.
        
        Args:
            file_content: Binary file content
            content_type: MIME type
            
        Raises:
            ValueError: If validation fails
        """
        # Check file size
        file_size_mb = len(file_content) / (1024 * 1024)
        max_size_mb = self.settings.document_processing.max_file_size_mb
        
        if file_size_mb > max_size_mb:
            raise ValueError(
                f"File size ({file_size_mb:.2f}MB) exceeds maximum "
                f"allowed size ({max_size_mb}MB)"
            )
        
        # Check content type
        supported_types = self.settings.document_processing.supported_formats
        if content_type not in supported_types:
            raise ValueError(
                f"Unsupported file type: {content_type}. "
                f"Supported types: {', '.join(supported_types)}"
            )
