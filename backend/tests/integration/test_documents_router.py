"""Unit tests for document router endpoints."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import UploadFile
from httpx import AsyncClient

from app.models.database import Document


@pytest.fixture
def mock_document_service():
    """Create mock document service."""
    service = AsyncMock()
    return service


@pytest.fixture
def sample_document():
    """Create sample document."""
    doc = Document()
    doc.id = uuid4()
    doc.title = "test.pdf"
    doc.file_hash = "abc123"
    doc.file_size = 102400
    doc.mime_type = "application/pdf"
    doc.s3_key = "documents/test.pdf"
    doc.status = "ready"
    doc.page_count = 10
    doc.chunk_count = 45
    return doc


class TestDocumentRouter:
    """Test cases for document router endpoints."""

    @pytest.mark.asyncio
    async def test_upload_document_success(self, async_client: AsyncClient, sample_document):
        """Test successful document upload."""
        project_id = str(uuid4())
        
        # Create fake PDF file
        file_content = b"%PDF-1.4\nTest content"
        files = {
            "file": ("test.pdf", file_content, "application/pdf")
        }
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.upload_document.return_value = {
                "id": str(sample_document.id),
                "title": sample_document.title,
                "file_hash": sample_document.file_hash,
                "file_size": sample_document.file_size,
                "mime_type": sample_document.mime_type,
                "status": "queued",
                "s3_key": sample_document.s3_key,
                "created_at": "2026-02-21T10:00:00",
                "is_duplicate": False,
            }
            mock_service_class.return_value = mock_service
            
            response = await async_client.post(
                "/api/documents/upload",
                files=files,
                data={"project_id": project_id}
            )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["is_duplicate"] is False

    @pytest.mark.asyncio
    async def test_upload_document_no_file(self, async_client: AsyncClient):
        """Test upload without file."""
        project_id = str(uuid4())
        
        response = await async_client.post(
            "/api/documents/upload",
            data={"project_id": project_id}
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_document_success(self, async_client: AsyncClient, sample_document):
        """Test getting document by ID."""
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_document.return_value = sample_document
            mock_service_class.return_value = mock_service
            
            response = await async_client.get(f"/api/documents/{sample_document.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_document.id)
        assert data["title"] == sample_document.title

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, async_client: AsyncClient):
        """Test getting non-existent document."""
        doc_id = uuid4()
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_document.return_value = None
            mock_service_class.return_value = mock_service
            
            response = await async_client.get(f"/api/documents/{doc_id}")
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_document_status(self, async_client: AsyncClient, sample_document):
        """Test getting document status."""
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_document_status.return_value = {
                "id": str(sample_document.id),
                "title": sample_document.title,
                "status": sample_document.status,
                "chunk_count": sample_document.chunk_count,
                "error_message": None,
                "page_count": sample_document.page_count,
                "file_size": sample_document.file_size,
                "mime_type": sample_document.mime_type,
                "created_at": "2026-02-21T10:00:00",
                "updated_at": "2026-02-21T10:05:00",
            }
            mock_service_class.return_value = mock_service
            
            response = await async_client.get(
                f"/api/documents/{sample_document.id}/status"
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["chunk_count"] == 45

    @pytest.mark.asyncio
    async def test_list_project_documents(self, async_client: AsyncClient):
        """Test listing documents for a project."""
        project_id = uuid4()
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.list_project_documents.return_value = [
                Document(id=uuid4(), title="doc1.pdf", status="ready"),
                Document(id=uuid4(), title="doc2.pdf", status="processing"),
            ]
            mock_service_class.return_value = mock_service
            
            response = await async_client.get(
                f"/api/projects/{project_id}/documents"
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_link_document_to_project(self, async_client: AsyncClient):
        """Test linking document to project."""
        project_id = uuid4()
        doc_id = uuid4()
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.link_document.return_value = None
            mock_service_class.return_value = mock_service
            
            response = await async_client.post(
                f"/api/projects/{project_id}/documents",
                json={"document_id": str(doc_id)}
            )
        
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_unlink_document_from_project(self, async_client: AsyncClient):
        """Test unlinking document from project."""
        project_id = uuid4()
        doc_id = uuid4()
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.unlink_document.return_value = None
            mock_service_class.return_value = mock_service
            
            response = await async_client.delete(
                f"/api/projects/{project_id}/documents/{doc_id}"
            )
        
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_upload_duplicate_document(self, async_client: AsyncClient, sample_document):
        """Test uploading duplicate document."""
        project_id = str(uuid4())
        
        file_content = b"%PDF-1.4\nTest content"
        files = {
            "file": ("test.pdf", file_content, "application/pdf")
        }
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.upload_document.return_value = {
                "id": str(sample_document.id),
                "title": sample_document.title,
                "file_hash": sample_document.file_hash,
                "file_size": sample_document.file_size,
                "mime_type": sample_document.mime_type,
                "status": "ready",
                "s3_key": sample_document.s3_key,
                "created_at": "2026-02-21T10:00:00",
                "is_duplicate": True,  # Duplicate flag set
            }
            mock_service_class.return_value = mock_service
            
            response = await async_client.post(
                "/api/documents/upload",
                files=files,
                data={"project_id": project_id}
            )
        
        assert response.status_code == 201
        data = response.json()
        assert data["is_duplicate"] is True

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, async_client: AsyncClient):
        """Test uploading non-PDF file."""
        project_id = str(uuid4())
        
        file_content = b"Plain text content"
        files = {
            "file": ("document.txt", file_content, "text/plain")
        }
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.upload_document.side_effect = ValueError("Only PDF files")
            mock_service_class.return_value = mock_service
            
            response = await async_client.post(
                "/api/documents/upload",
                files=files,
                data={"project_id": project_id}
            )
        
        # Should return 400 Bad Request
        assert response.status_code in [400, 422, 500]

    @pytest.mark.asyncio
    async def test_get_document_invalid_uuid(self, async_client: AsyncClient):
        """Test getting document with invalid UUID."""
        response = await async_client.get("/api/documents/invalid-uuid")
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_large_file(self, async_client: AsyncClient):
        """Test uploading file that exceeds size limit."""
        project_id = str(uuid4())
        
        # Create file larger than 50MB
        file_content = b"X" * (60 * 1024 * 1024)
        files = {
            "file": ("large.pdf", file_content, "application/pdf")
        }
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.upload_document.side_effect = ValueError("File too large")
            mock_service_class.return_value = mock_service
            
            response = await async_client.post(
                "/api/documents/upload",
                files=files,
                data={"project_id": project_id}
            )
        
        # Should handle error
        assert response.status_code in [400, 413, 422, 500]

    @pytest.mark.asyncio
    async def test_get_document_status_processing(self, async_client: AsyncClient):
        """Test getting status of document being processed."""
        doc_id = uuid4()
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_document_status.return_value = {
                "id": str(doc_id),
                "title": "processing.pdf",
                "status": "processing",
                "chunk_count": 0,
                "error_message": None,
                "page_count": None,
                "file_size": 102400,
                "mime_type": "application/pdf",
                "created_at": "2026-02-21T10:00:00",
                "updated_at": "2026-02-21T10:01:00",
            }
            mock_service_class.return_value = mock_service
            
            response = await async_client.get(f"/api/documents/{doc_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_document_status_failed(self, async_client: AsyncClient):
        """Test getting status of failed document."""
        doc_id = uuid4()
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_document_status.return_value = {
                "id": str(doc_id),
                "title": "failed.pdf",
                "status": "failed",
                "chunk_count": 0,
                "error_message": "PDF parsing failed",
                "page_count": None,
                "file_size": 102400,
                "mime_type": "application/pdf",
                "created_at": "2026-02-21T10:00:00",
                "updated_at": "2026-02-21T10:02:00",
            }
            mock_service_class.return_value = mock_service
            
            response = await async_client.get(f"/api/documents/{doc_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error_message"] is not None

    @pytest.mark.asyncio
    async def test_list_empty_project_documents(self, async_client: AsyncClient):
        """Test listing documents for project with no documents."""
        project_id = uuid4()
        
        with patch('app.routers.documents.DocumentService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.list_project_documents.return_value = []
            mock_service_class.return_value = mock_service
            
            response = await async_client.get(
                f"/api/projects/{project_id}/documents"
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data == []
