"""API router for document management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.implementations.celery_task_queue import CeleryTaskQueue
from app.repositories.document_repo import DocumentRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.document import (
    DocumentLinkRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService
from app.services.storage_service import StorageService
from app.worker.celery_app import celery_app

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Process-scoped task queue singleton
_task_queue = CeleryTaskQueue(celery_app)


def get_document_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)]
) -> DocumentService:
    """Dependency to create document service."""
    document_repo = DocumentRepository(session)
    project_repo = ProjectRepository(session)
    storage_service = StorageService(settings)
    return DocumentService(
        document_repo, project_repo, storage_service, settings,
        task_queue=_task_queue,
    )


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentUploadResponse
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload"),
    service: DocumentService = Depends(get_document_service)
) -> DocumentUploadResponse:
    """
    Upload a new document.
    
    The file is uploaded to S3 and a database record is created.
    If a file with the same hash already exists, the existing document is returned.
    
    Args:
        file: Uploaded PDF file
        service: Document service dependency
        
    Returns:
        Document upload response with document details
        
    Raises:
        400: If file validation fails
        500: If upload or database operation fails
    """
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        ) from e
    
    # Upload document
    try:
        response, is_duplicate = await service.upload_document(
            file_content=content,
            filename=file.filename or "untitled.pdf",
            content_type=file.content_type or "application/pdf"
        )
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        ) from e


@router.get(
    "/{document_id}",
    response_model=DocumentResponse
)
async def get_document(
    document_id: Annotated[UUID, Path(description="Document ID")],
    service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    Get document details by ID.
    
    Args:
        document_id: Document UUID
        service: Document service dependency
        
    Returns:
        Document details
        
    Raises:
        404: If document not found
    """
    document = await service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    return document


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse
)
async def get_document_status(
    document_id: Annotated[UUID, Path(description="Document ID")],
    service: DocumentService = Depends(get_document_service)
) -> DocumentStatusResponse:
    """
    Get document processing status.
    
    Used by frontend to poll for processing completion.
    
    Args:
        document_id: Document UUID
        service: Document service dependency
        
    Returns:
        Document status details
        
    Raises:
        404: If document not found
    """
    status_response = await service.get_document_status(document_id)
    if status_response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    return status_response


# Project-scoped document endpoints
projects_router = APIRouter(
    prefix="/api/projects/{project_id}/documents",
    tags=["documents"]
)


@projects_router.get(
    "",
    response_model=DocumentListResponse
)
async def list_project_documents(
    project_id: Annotated[UUID, Path(description="Project ID")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    service: DocumentService = Depends(get_document_service)
) -> DocumentListResponse:
    """
    List all documents linked to a project.
    
    Args:
        project_id: Project UUID
        limit: Maximum number of documents to return
        offset: Number of documents to skip
        service: Document service dependency
        
    Returns:
        Paginated list of documents
    """
    return await service.list_project_documents(project_id, limit, offset)


@projects_router.post(
    "",
    status_code=status.HTTP_201_CREATED
)
async def link_document_to_project(
    project_id: Annotated[UUID, Path(description="Project ID")],
    request: DocumentLinkRequest,
    service: DocumentService = Depends(get_document_service)
) -> dict[str, str]:
    """
    Link an existing document to a project.
    
    Used after uploading a document to associate it with a project.
    
    Args:
        project_id: Project UUID
        request: Link request with document ID
        service: Document service dependency
        
    Returns:
        Success message
        
    Raises:
        400: If project or document not found
        500: If linking fails
    """
    try:
        await service.link_document_to_project(project_id, request.document_id)
        return {"message": "Document linked to project successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link document: {str(e)}"
        ) from e


@projects_router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def unlink_document_from_project(
    project_id: Annotated[UUID, Path(description="Project ID")],
    document_id: Annotated[UUID, Path(description="Document ID")],
    service: DocumentService = Depends(get_document_service)
) -> None:
    """
    Unlink a document from a project.
    
    The document is not deleted, only the link is removed.
    
    Args:
        project_id: Project UUID
        document_id: Document UUID
        service: Document service dependency
        
    Returns:
        No content (204)
        
    Raises:
        404: If link doesn't exist
    """
    success = await service.unlink_document_from_project(project_id, document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not linked to this project"
        )
