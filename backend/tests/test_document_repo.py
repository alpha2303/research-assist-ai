"""Unit tests for document repository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Document, ProjectDocument
from app.repositories.document_repo import DocumentRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def document_repo(mock_session):
    """Create document repository with mock session."""
    return DocumentRepository(mock_session)


@pytest.fixture
def sample_document_data():
    """Sample document data dict for testing."""
    return {
        "title": "Test Document.pdf",
        "file_hash": "abc123hash",
        "file_size_bytes": 102400,
        "mime_type": "application/pdf",
        "s3_key": "documents/test-doc.pdf",
        "status": "queued",
    }


@pytest.fixture
def sample_document():
    """Create a mock Document instance."""
    doc = MagicMock(spec=Document)
    doc.id = uuid4()
    doc.title = "Test Document.pdf"
    doc.file_hash = "abc123hash"
    doc.file_size = 102400
    doc.mime_type = "application/pdf"
    doc.s3_key = "documents/test-doc.pdf"
    doc.status = "queued"
    doc.page_count = None
    doc.chunk_count = 0
    doc.error_message = None
    doc.created_at = datetime.now(timezone.utc)
    doc.updated_at = datetime.now(timezone.utc)
    return doc


class TestDocumentRepository:
    """Test cases for DocumentRepository."""

    @pytest.mark.asyncio
    async def test_create_document(self, document_repo, mock_session, sample_document_data):
        """Test creating a new document from a dict."""
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        await document_repo.create(sample_document_data)

        mock_session.add.assert_called_once()
        added_doc = mock_session.add.call_args[0][0]
        assert isinstance(added_doc, Document)
        assert added_doc.title == sample_document_data["title"]
        assert added_doc.file_hash == sample_document_data["file_hash"]
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(added_doc)

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, document_repo, mock_session, sample_document):
        """Test getting document by ID when it exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_document
        mock_session.execute.return_value = mock_result

        result = await document_repo.get_by_id(sample_document.id)

        assert result == sample_document

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, document_repo, mock_session):
        """Test getting document by ID when it doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await document_repo.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_hash_found(self, document_repo, mock_session, sample_document):
        """Test getting document by file hash when it exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_document
        mock_session.execute.return_value = mock_result

        result = await document_repo.get_by_hash("abc123hash")

        assert result == sample_document

    @pytest.mark.asyncio
    async def test_get_by_hash_not_found(self, document_repo, mock_session):
        """Test getting document by hash when it doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await document_repo.get_by_hash("nonexistent_hash")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_success(self, document_repo, mock_session, sample_document):
        """Test updating document status returns the updated document."""
        # get_by_id called first inside update_status
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_document
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await document_repo.update_status(sample_document.id, "processing")

        assert result is not None
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_with_error(self, document_repo, mock_session, sample_document):
        """Test updating document status to failed with error message."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_document
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await document_repo.update_status(
            sample_document.id, "failed", error_message="PDF parsing failed"
        )

        assert result is not None
        assert sample_document.error_message == "PDF parsing failed"

    @pytest.mark.asyncio
    async def test_update_status_document_not_found(self, document_repo, mock_session):
        """Test updating status when document doesn't exist returns None."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await document_repo.update_status(uuid4(), "processing")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_documents_by_project(self, document_repo, mock_session, sample_document):
        """Test getting all documents for a project."""
        doc2 = MagicMock(spec=Document)
        doc2.id = uuid4()
        doc2.title = "Document 2.pdf"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_document, doc2]
        mock_session.execute.return_value = mock_result

        documents = await document_repo.get_documents_by_project(uuid4())

        assert len(documents) == 2
        assert documents[0] == sample_document

    @pytest.mark.asyncio
    async def test_get_documents_by_project_empty(self, document_repo, mock_session):
        """Test getting documents for project with no documents."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        documents = await document_repo.get_documents_by_project(uuid4())

        assert documents == []

    @pytest.mark.asyncio
    async def test_link_to_project_new(self, document_repo, mock_session):
        """Test linking a document to a project (new link)."""
        project_id = uuid4()
        doc_id = uuid4()

        # First execute: check existing → None
        mock_result_check = MagicMock()
        mock_result_check.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result_check
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        await document_repo.link_to_project(project_id, doc_id)

        mock_session.add.assert_called_once()
        added_link = mock_session.add.call_args[0][0]
        assert isinstance(added_link, ProjectDocument)
        assert str(added_link.project_id) == str(project_id)
        assert str(added_link.document_id) == str(doc_id)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_to_project_already_exists(self, document_repo, mock_session):
        """Test linking when link already exists returns existing link."""
        existing_link = MagicMock(spec=ProjectDocument)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_link
        mock_session.execute.return_value = mock_result

        result = await document_repo.link_to_project(uuid4(), uuid4())

        assert result == existing_link
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_unlink_from_project(self, document_repo, mock_session):
        """Test unlinking a document from a project."""
        link = MagicMock(spec=ProjectDocument)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = link
        mock_session.execute.return_value = mock_result
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        success = await document_repo.unlink_from_project(uuid4(), uuid4())

        assert success is True
        mock_session.delete.assert_called_once_with(link)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_unlink_from_project_not_linked(self, document_repo, mock_session):
        """Test unlinking when no link exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        success = await document_repo.unlink_from_project(uuid4(), uuid4())

        assert success is False

    @pytest.mark.asyncio
    async def test_delete_document(self, document_repo, mock_session, sample_document):
        """Test deleting a document."""
        # get_by_id returns the document
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_document
        mock_session.execute.return_value = mock_result
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        success = await document_repo.delete(sample_document.id)

        assert success is True
        mock_session.delete.assert_called_once_with(sample_document)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, document_repo, mock_session):
        """Test deleting a document that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        success = await document_repo.delete(uuid4())

        assert success is False

    @pytest.mark.asyncio
    async def test_count_by_project(self, document_repo, mock_session):
        """Test counting documents in a project."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute.return_value = mock_result

        count = await document_repo.count_by_project(uuid4())

        assert count == 5
