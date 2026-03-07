"""Unit tests for document service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_document_repo():
    """Create mock document repository."""
    return AsyncMock()


@pytest.fixture
def mock_project_repo():
    """Create mock project repository."""
    return AsyncMock()


@pytest.fixture
def mock_storage():
    """Create mock storage service."""
    storage = MagicMock()
    storage.upload_file.return_value = ("abc123hash", "documents/abc123hash.pdf")
    storage.delete_file = MagicMock()
    return storage


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.document_processing.max_file_size_mb = 50
    settings.document_processing.supported_formats = ["application/pdf"]
    return settings


@pytest.fixture
def mock_task_queue():
    """Create mock task queue."""
    return AsyncMock()


@pytest.fixture
def document_service(
    mock_document_repo, mock_project_repo, mock_storage, mock_settings, mock_task_queue
):
    """Create document service with mocked dependencies."""
    return DocumentService(
        document_repo=mock_document_repo,
        project_repo=mock_project_repo,
        storage_service=mock_storage,
        settings=mock_settings,
        task_queue=mock_task_queue,
    )


def _make_doc_orm(**overrides):
    """Create a MagicMock that behaves like a Document ORM instance."""
    defaults = {
        "id": uuid4(),
        "title": "test.pdf",
        "file_hash": "abc123hash",
        "file_size_bytes": 12345,
        "mime_type": "application/pdf",
        "s3_key": "documents/abc123hash.pdf",
        "status": "queued",
        "page_count": None,
        "chunk_count": 0,
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    doc = MagicMock()
    for k, v in defaults.items():
        setattr(doc, k, v)
    # Support model_validate(doc) via from_attributes
    doc.__dict__.update(defaults)
    return doc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDocumentService:
    """Test cases for DocumentService."""

    # ── upload_document ───────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_upload_document_new(
        self, document_service, mock_storage, mock_document_repo, mock_task_queue
    ):
        """Test successful new document upload."""
        file_content = b"%PDF-1.4 test content"
        filename = "test.pdf"
        content_type = "application/pdf"

        created_doc = _make_doc_orm(status="queued")
        mock_document_repo.get_by_hash.return_value = None
        mock_document_repo.create.return_value = created_doc

        response, is_duplicate = await document_service.upload_document(
            file_content, filename, content_type
        )

        assert isinstance(response, DocumentUploadResponse)
        assert is_duplicate is False
        mock_storage.upload_file.assert_called_once()
        mock_document_repo.create.assert_called_once()
        mock_task_queue.submit_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_document_duplicate(
        self, document_service, mock_storage, mock_document_repo, mock_task_queue
    ):
        """Test uploading duplicate document reuses existing record."""
        file_content = b"%PDF-1.4 duplicate"
        existing_doc = _make_doc_orm(status="ready")
        mock_document_repo.get_by_hash.return_value = existing_doc

        response, is_duplicate = await document_service.upload_document(
            file_content, "test.pdf", "application/pdf"
        )

        assert is_duplicate is True
        assert response.is_duplicate is True
        # No new document should be created
        mock_document_repo.create.assert_not_called()
        # No processing task should be submitted
        mock_task_queue.submit_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_document_file_too_large(self, document_service):
        """Test upload fails when file is too large."""
        big = b"x" * (51 * 1024 * 1024)  # 51 MB

        with pytest.raises(ValueError, match="exceeds maximum"):
            await document_service.upload_document(big, "big.pdf", "application/pdf")

    @pytest.mark.asyncio
    async def test_upload_document_invalid_type(self, document_service):
        """Test upload fails for unsupported MIME type."""
        with pytest.raises(ValueError, match="Unsupported file type"):
            await document_service.upload_document(
                b"hello", "doc.txt", "text/plain"
            )

    # ── get_document ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_document_found(self, document_service, mock_document_repo):
        """Test getting document by ID when exists."""
        doc = _make_doc_orm()
        mock_document_repo.get_by_id.return_value = doc

        result = await document_service.get_document(doc.id)

        assert isinstance(result, DocumentResponse)
        assert result.id == doc.id

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, document_service, mock_document_repo):
        """Test getting document when it doesn't exist."""
        mock_document_repo.get_by_id.return_value = None

        result = await document_service.get_document(uuid4())

        assert result is None

    # ── get_document_status ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_document_status(self, document_service, mock_document_repo):
        """Test getting document processing status."""
        doc = _make_doc_orm(status="processing", page_count=5, chunk_count=30)
        mock_document_repo.get_by_id.return_value = doc

        result = await document_service.get_document_status(doc.id)

        assert isinstance(result, DocumentStatusResponse)
        assert result.status == "processing"

    @pytest.mark.asyncio
    async def test_get_document_status_not_found(
        self, document_service, mock_document_repo
    ):
        """Test status for nonexistent document returns None."""
        mock_document_repo.get_by_id.return_value = None

        result = await document_service.get_document_status(uuid4())

        assert result is None

    # ── list_project_documents ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_project_documents(
        self, document_service, mock_document_repo
    ):
        """Test listing documents for a project."""
        project_id = uuid4()
        docs = [_make_doc_orm(title="a.pdf"), _make_doc_orm(title="b.pdf")]
        mock_document_repo.get_documents_by_project.return_value = docs
        mock_document_repo.count_by_project.return_value = 2

        result = await document_service.list_project_documents(project_id)

        assert isinstance(result, DocumentListResponse)
        assert result.total == 2

    # ── link / unlink ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_link_document_to_project(
        self, document_service, mock_document_repo, mock_project_repo
    ):
        """Test linking document to project."""
        project_id = uuid4()
        doc_id = uuid4()
        mock_project_repo.get_by_id.return_value = MagicMock()
        mock_document_repo.get_by_id.return_value = MagicMock()

        result = await document_service.link_document_to_project(project_id, doc_id)

        assert result is True
        mock_document_repo.link_to_project.assert_called_once_with(project_id, doc_id)

    @pytest.mark.asyncio
    async def test_link_document_project_not_found(
        self, document_service, mock_project_repo
    ):
        """Test linking fails when project not found."""
        mock_project_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await document_service.link_document_to_project(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_link_document_doc_not_found(
        self, document_service, mock_project_repo, mock_document_repo
    ):
        """Test linking fails when document not found."""
        mock_project_repo.get_by_id.return_value = MagicMock()
        mock_document_repo.get_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await document_service.link_document_to_project(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_unlink_document_from_project(
        self, document_service, mock_document_repo
    ):
        """Test unlinking document from project."""
        mock_document_repo.unlink_from_project.return_value = True

        result = await document_service.unlink_document_from_project(uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_unlink_not_linked(self, document_service, mock_document_repo):
        """Test unlink returns False when no link existed."""
        mock_document_repo.unlink_from_project.return_value = False

        result = await document_service.unlink_document_from_project(uuid4(), uuid4())

        assert result is False

    # ── _validate_file ────────────────────────────────────────────────────

    def test_validate_file_success(self, document_service):
        """Test validation passes for valid PDF content."""
        # Should not raise
        document_service._validate_file(b"%PDF-content", "application/pdf")

    def test_validate_file_wrong_type(self, document_service):
        """Test validation fails for unsupported type."""
        with pytest.raises(ValueError, match="Unsupported file type"):
            document_service._validate_file(b"hello", "text/plain")

    def test_validate_file_too_large(self, document_service):
        """Test validation fails for oversized file."""
        big = b"x" * (51 * 1024 * 1024)
        with pytest.raises(ValueError, match="exceeds maximum"):
            document_service._validate_file(big, "application/pdf")

    def test_validate_file_bad_magic_bytes(self, document_service):
        """Test that a file claiming to be PDF but lacking %PDF magic bytes is rejected."""
        # Content-Type says PDF but content is not a PDF
        with pytest.raises(ValueError, match="does not match the declared type"):
            document_service._validate_file(b"This is not a PDF", "application/pdf")

    def test_validate_file_good_magic_bytes(self, document_service):
        """Test that a file with valid %PDF magic bytes passes validation."""
        valid_pdf_header = b"%PDF-1.4 binary content here"
        # Should not raise
        document_service._validate_file(valid_pdf_header, "application/pdf")

    # ── race condition (IntegrityError) ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_upload_document_race_condition(
        self, document_service, mock_storage, mock_document_repo, mock_task_queue
    ):
        """
        Test that a concurrent upload (IntegrityError) is handled gracefully:
        the service falls back to returning the existing document as a duplicate.
        """
        from sqlalchemy.exc import IntegrityError
        from app.models.database import DocumentStatus

        file_content = b"%PDF-1.4 race condition test"
        # Use the actual enum value so the status comparison inside the service
        # works correctly (ORM returns enum values, not plain strings).
        existing_doc = _make_doc_orm(status=DocumentStatus.QUEUED)

        # get_by_hash returns None initially (passes dedup check) but after the
        # IntegrityError we return the existing document on the second call.
        mock_document_repo.get_by_hash.side_effect = [None, existing_doc]
        mock_document_repo.create.side_effect = IntegrityError(
            "duplicate key", params={}, orig=Exception("duplicate key")
        )

        response, is_duplicate = await document_service.upload_document(
            file_content, "test.pdf", "application/pdf"
        )

        assert is_duplicate is True
        assert response.is_duplicate is True
        # Processing task submitted because status is QUEUED
        mock_task_queue.submit_task.assert_called_once()
