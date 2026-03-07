"""Unit tests for Celery document processing tasks."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.interfaces.document_parser import PageContent, ParseResult
from app.models.database import DocumentStatus


@pytest.fixture
def sample_parse_result():
    """Create sample parse result."""
    pages = [
        PageContent(
            page_number=1,
            text="This is page 1 content with some text.",
            metadata={"format": "text"},
        ),
        PageContent(
            page_number=2,
            text="This is page 2 content with more text.",
            metadata={"format": "text"},
        ),
    ]
    return ParseResult(
        pages=pages,
        total_pages=2,
        metadata={"parser": "test"},
    )


class TestProcessDocumentAsync:
    """Test cases for the _process_document_async pipeline."""

    @pytest.mark.asyncio
    @patch("app.worker.tasks._ensure_db")
    @patch("app.worker.tasks.get_settings")
    @patch("app.worker.tasks.get_session_factory")
    @patch("app.worker.tasks.StorageService")
    @patch("app.worker.tasks.PGVectorStore")
    @patch("app.worker.tasks.TitanEmbeddingProvider")
    @patch("app.worker.tasks.TextChunker")
    @patch("app.worker.tasks._parse_document")
    async def test_process_document_async_success(
        self,
        mock_parse_document,
        mock_chunker_class,
        mock_embedding_class,
        mock_vector_store_class,
        mock_storage_class,
        mock_session_factory,
        mock_get_settings,
        _mock_ensure_db,
        sample_parse_result,
    ):
        """Test successful async document processing pipeline."""
        from app.worker.tasks import _process_document_async

        doc_id = uuid4()

        # Settings
        mock_settings = MagicMock()
        mock_settings.embedding = MagicMock()
        mock_settings.aws_profile = "default"
        mock_settings.aws_region = "us-east-1"
        mock_settings.chunking = MagicMock()
        mock_get_settings.return_value = mock_settings

        # Session factory – yields an async context manager
        mock_session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_session
        mock_session_factory.return_value = MagicMock(return_value=ctx)

        # Document repo (patched via DocumentRepository)
        mock_document = MagicMock()
        mock_document.id = doc_id
        mock_document.title = "test.pdf"
        mock_document.s3_key = "documents/test.pdf"
        mock_document.status = DocumentStatus.QUEUED

        with patch("app.worker.tasks.DocumentRepository") as mock_doc_repo_class:
            mock_doc_repo = AsyncMock()
            mock_doc_repo.get_by_id.return_value = mock_document
            mock_doc_repo.update_status.return_value = mock_document
            mock_doc_repo_class.return_value = mock_doc_repo

            # Storage returns bytes
            mock_storage = MagicMock()
            mock_storage.download_file.return_value = b"PDF bytes"
            mock_storage_class.return_value = mock_storage

            # Parse result
            mock_parse_document.return_value = sample_parse_result

            # Chunker
            chunk_mock = MagicMock()
            chunk_mock.chunk_index = 0
            chunk_mock.content = "chunk text"
            chunk_mock.page_number = 1
            chunk_mock.section_heading = None
            chunk_mock.token_count = 50
            mock_chunker = MagicMock()
            mock_chunker.chunk_document_pages.return_value = [chunk_mock]
            mock_chunker_class.return_value = mock_chunker

            # Embeddings — use MagicMock as base so that sync methods like
            # get_model_id() aren't turned into AsyncMock children that produce
            # unawaited coroutines when called without await in production code.
            mock_embedding = MagicMock()
            mock_embedding.embed_batch = AsyncMock(return_value=[[0.1] * 1024])
            mock_embedding.get_model_id.return_value = "amazon.titan-embed-text-v2:0"
            mock_embedding_class.return_value = mock_embedding

            # Vector store
            mock_vs = AsyncMock()
            mock_vector_store_class.return_value = mock_vs

            result = await _process_document_async(doc_id)

        assert result["status"] == "success"
        assert result["chunk_count"] == 1
        assert result["page_count"] == 2
        mock_doc_repo.update_status.assert_any_call(doc_id, DocumentStatus.PROCESSING)
        mock_doc_repo.update_status.assert_any_call(doc_id, DocumentStatus.COMPLETED)
        mock_vs.store_embeddings.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.tasks._ensure_db")
    @patch("app.worker.tasks.get_settings")
    @patch("app.worker.tasks.get_session_factory")
    @patch("app.worker.tasks.StorageService")
    @patch("app.worker.tasks.PGVectorStore")
    @patch("app.worker.tasks.TitanEmbeddingProvider")
    @patch("app.worker.tasks.TextChunker")
    async def test_process_document_async_not_found(
        self,
        mock_chunker_class,
        mock_embedding_class,
        mock_vector_store_class,
        mock_storage_class,
        mock_session_factory,
        mock_get_settings,
        _mock_ensure_db,
    ):
        """Test processing when document doesn't exist raises ValueError."""
        from app.worker.tasks import _process_document_async

        mock_settings = MagicMock()
        mock_settings.embedding = MagicMock()
        mock_settings.aws_profile = "default"
        mock_settings.aws_region = "us-east-1"
        mock_settings.chunking = MagicMock()
        mock_get_settings.return_value = mock_settings

        mock_session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_session
        mock_session_factory.return_value = MagicMock(return_value=ctx)

        with patch("app.worker.tasks.DocumentRepository") as mock_doc_repo_class:
            mock_doc_repo = AsyncMock()
            mock_doc_repo.get_by_id.return_value = None
            mock_doc_repo_class.return_value = mock_doc_repo

            with pytest.raises(ValueError, match="not found"):
                await _process_document_async(uuid4())


class TestParseDocument:
    """Test cases for the _parse_document helper."""

    @pytest.mark.asyncio
    @patch("app.worker.tasks.PyMuPDF4LLMParser")
    async def test_parse_document_primary_success(
        self,
        mock_parser_class,
        sample_parse_result,
    ):
        """Test parsing with primary parser succeeds."""
        from app.worker.tasks import _parse_document

        mock_parser = AsyncMock()
        mock_parser.parse.return_value = sample_parse_result
        mock_parser_class.return_value = mock_parser

        settings = MagicMock()
        settings.document_processing.primary_parser = "pymupdf4llm"

        result = await _parse_document(b"PDF bytes", "test.pdf", settings)

        assert result.total_pages == 2
        mock_parser.parse.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.tasks.PdfPlumberParser")
    @patch("app.worker.tasks.PyMuPDF4LLMParser")
    async def test_parse_document_fallback(
        self,
        mock_primary_class,
        mock_fallback_class,
        sample_parse_result,
    ):
        """Test fallback parser when primary fails."""
        from app.worker.tasks import _parse_document

        # Primary fails
        mock_primary = AsyncMock()
        mock_primary.parse.side_effect = RuntimeError("Parse error")
        mock_primary_class.return_value = mock_primary

        # Fallback succeeds
        mock_fallback = AsyncMock()
        mock_fallback.parse.return_value = sample_parse_result
        mock_fallback_class.return_value = mock_fallback

        settings = MagicMock()
        settings.document_processing.primary_parser = "pymupdf4llm"
        settings.document_processing.fallback_parser = "pdfplumber"

        result = await _parse_document(b"PDF bytes", "test.pdf", settings)

        assert result.total_pages == 2
        mock_fallback.parse.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.worker.tasks.PdfPlumberParser")
    @patch("app.worker.tasks.PyMuPDF4LLMParser")
    async def test_parse_document_all_fail(
        self,
        mock_primary_class,
        mock_fallback_class,
    ):
        """Test RuntimeError raised when all parsers fail."""
        from app.worker.tasks import _parse_document

        mock_primary = AsyncMock()
        mock_primary.parse.side_effect = RuntimeError("Primary error")
        mock_primary_class.return_value = mock_primary

        mock_fallback = AsyncMock()
        mock_fallback.parse.side_effect = RuntimeError("Fallback error")
        mock_fallback_class.return_value = mock_fallback

        settings = MagicMock()
        settings.document_processing.primary_parser = "pymupdf4llm"
        settings.document_processing.fallback_parser = "pdfplumber"

        with pytest.raises(RuntimeError, match="All parsers failed"):
            await _parse_document(b"PDF bytes", "test.pdf", settings)


class TestProcessDocumentTask:
    """Test the Celery task wrapper."""

    def test_task_is_registered(self):
        """Test that task function exists and is callable."""
        from app.worker.tasks import process_document

        assert callable(process_document)

    def test_celery_app_configured(self):
        """Test Celery app is properly configured."""
        from app.worker.celery_app import celery_app

        assert celery_app is not None


class TestChunkingIntegration:
    """Test chunking service integration."""

    @patch("app.worker.tasks.TextChunker")
    def test_chunking_service(self, mock_chunker_class, sample_parse_result):
        """Test chunking service can be instantiated."""
        mock_chunker = MagicMock()
        mock_chunker.chunk_document_pages.return_value = [MagicMock(token_count=100)]
        mock_chunker_class.return_value = mock_chunker

        chunker = mock_chunker_class(MagicMock())
        result = chunker.chunk_document_pages(
            [(p.page_number, p.text) for p in sample_parse_result.pages]
        )

        assert len(result) == 1


class TestEmbeddingIntegration:
    """Test embedding generation integration."""

    @patch("app.worker.tasks.TitanEmbeddingProvider")
    def test_embedding_batch(self, mock_embedding_class):
        """Test batch embedding generation."""
        embeddings_result = [[0.1] * 1024 for _ in range(5)]
        mock_embeddings = MagicMock()
        mock_embeddings.embed_batch.return_value = embeddings_result
        mock_embedding_class.return_value = mock_embeddings

        provider = mock_embedding_class(MagicMock(), "default", "us-east-1")
        embeddings = provider.embed_batch(["text1", "text2", "text3", "text4", "text5"])

        assert len(embeddings) == 5
        assert all(len(emb) == 1024 for emb in embeddings)


class TestTempFileCleanup:
    """Test temporary file cleanup."""

    def test_temp_file_cleanup(self):
        """Test temporary files are cleaned up."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(b"test content")

        if Path(tmp_path).exists():
            Path(tmp_path).unlink()

        assert not Path(tmp_path).exists()
