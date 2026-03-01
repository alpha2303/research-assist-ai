"""Unit tests for chunk repository."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import DocumentChunk
from app.repositories.chunk_repo import ChunkRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def chunk_repo(mock_session):
    """Create chunk repository with mock session."""
    return ChunkRepository(mock_session)


@pytest.fixture
def sample_chunk_dicts():
    """Create sample chunk dictionaries (what create_chunks expects)."""
    doc_id = uuid4()
    return [
        {
            "document_id": doc_id,
            "chunk_index": i,
            "content": f"Chunk {i} text content",
            "embedding": [0.1] * 1024,
            "token_count": 100,
            "embedding_model_id": "amazon.titan-embed-text-v2:0",
        }
        for i in range(3)
    ]


@pytest.fixture
def sample_chunks(sample_chunk_dicts):
    """Create sample chunk model instances for query results."""
    chunks = []
    for d in sample_chunk_dicts:
        chunk = MagicMock(spec=DocumentChunk)
        chunk.id = uuid4()
        chunk.document_id = d["document_id"]
        chunk.chunk_index = d["chunk_index"]
        chunk.content = d["content"]
        chunk.embedding = d["embedding"]
        chunk.token_count = d["token_count"]
        chunk.embedding_model_id = d["embedding_model_id"]
        chunks.append(chunk)
    return chunks


class TestChunkRepository:
    """Test cases for ChunkRepository."""

    @pytest.mark.asyncio
    async def test_create_chunks(self, chunk_repo, mock_session, sample_chunk_dicts):
        """Test creating chunks from dictionaries."""
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await chunk_repo.create_chunks(sample_chunk_dicts)

        assert len(result) == 3
        mock_session.add_all.assert_called_once()
        mock_session.commit.assert_called_once()
        # refresh called for each chunk
        assert mock_session.refresh.call_count == 3

    @pytest.mark.asyncio
    async def test_create_chunks_empty_list(self, chunk_repo, mock_session):
        """Test create_chunks with empty list still commits."""
        mock_session.commit = AsyncMock()

        result = await chunk_repo.create_chunks([])

        assert result == []
        mock_session.add_all.assert_called_once_with([])
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_document_id(self, chunk_repo, mock_session, sample_chunks):
        """Test getting all chunks for a document."""
        doc_id = sample_chunks[0].document_id

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_chunks
        mock_session.execute.return_value = mock_result

        chunks = await chunk_repo.get_by_document_id(doc_id)

        assert len(chunks) == 3
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_document_id_empty(self, chunk_repo, mock_session):
        """Test getting chunks when document has none."""
        doc_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        chunks = await chunk_repo.get_by_document_id(doc_id)

        assert chunks == []

    @pytest.mark.asyncio
    async def test_get_by_document_id_with_limit(self, chunk_repo, mock_session, sample_chunks):
        """Test getting chunks with a limit."""
        doc_id = sample_chunks[0].document_id

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_chunks[:2]
        mock_session.execute.return_value = mock_result

        chunks = await chunk_repo.get_by_document_id(doc_id, limit=2)

        assert len(chunks) == 2

    @pytest.mark.asyncio
    async def test_count_by_document_id(self, chunk_repo, mock_session):
        """Test counting chunks for a document."""
        doc_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 45
        mock_session.execute.return_value = mock_result

        count = await chunk_repo.count_by_document_id(doc_id)

        assert count == 45

    @pytest.mark.asyncio
    async def test_count_by_document_id_zero(self, chunk_repo, mock_session):
        """Test counting when document has no chunks."""
        doc_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        count = await chunk_repo.count_by_document_id(doc_id)

        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_by_document_id(self, chunk_repo, mock_session):
        """Test deleting all chunks for a document."""
        doc_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 45
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        deleted_count = await chunk_repo.delete_by_document_id(doc_id)

        assert deleted_count == 45
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_document_id_none_found(self, chunk_repo, mock_session):
        """Test deleting when no chunks exist."""
        doc_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        deleted_count = await chunk_repo.delete_by_document_id(doc_id)

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, chunk_repo, mock_session, sample_chunks):
        """Test getting chunk by ID when it exists."""
        chunk = sample_chunks[0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chunk
        mock_session.execute.return_value = mock_result

        result = await chunk_repo.get_by_id(chunk.id)

        assert result == chunk

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, chunk_repo, mock_session):
        """Test getting chunk by ID when it doesn't exist."""
        chunk_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await chunk_repo.get_by_id(chunk_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_count_stale_chunks(self, chunk_repo, mock_session):
        """Test counting chunks with outdated embedding model."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 10
        mock_session.execute.return_value = mock_result

        count = await chunk_repo.count_stale_chunks("amazon.titan-embed-v2:0")

        assert count == 10

    @pytest.mark.asyncio
    async def test_get_stale_chunk_ids(self, chunk_repo, mock_session):
        """Test getting batch of stale chunk IDs."""
        ids = [uuid4() for _ in range(5)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ids
        mock_session.execute.return_value = mock_result

        result = await chunk_repo.get_stale_chunk_ids(
            "amazon.titan-embed-v2:0", batch_size=50, offset=0
        )

        assert result == ids

    @pytest.mark.asyncio
    async def test_get_chunks_by_ids(self, chunk_repo, mock_session, sample_chunks):
        """Test fetching chunks by list of IDs."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sample_chunks
        mock_session.execute.return_value = mock_result

        result = await chunk_repo.get_chunks_by_ids([c.id for c in sample_chunks])

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_chunks_by_ids_empty(self, chunk_repo, mock_session):
        """Test fetching chunks with empty ID list returns empty."""
        result = await chunk_repo.get_chunks_by_ids([])

        assert result == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_update_embeddings(self, chunk_repo, mock_session):
        """Test bulk updating embeddings and model IDs."""
        updates = [
            {
                "id": uuid4(),
                "embedding": [0.5] * 1024,
                "embedding_model_id": "amazon.titan-embed-v2:0",
            }
            for _ in range(3)
        ]
        mock_session.commit = AsyncMock()

        count = await chunk_repo.bulk_update_embeddings(updates)

        assert count == 3
        assert mock_session.execute.call_count == 3
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_bulk_update_embeddings_empty(self, chunk_repo, mock_session):
        """Test bulk update with empty list does nothing."""
        count = await chunk_repo.bulk_update_embeddings([])

        assert count == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_operations_sequence(self, chunk_repo, mock_session, sample_chunk_dicts):
        """Test sequence of bulk operations."""
        doc_id = sample_chunk_dicts[0]["document_id"]
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Create chunks
        await chunk_repo.create_chunks(sample_chunk_dicts)

        # Count chunks
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 3
        mock_session.execute.return_value = mock_result
        count = await chunk_repo.count_by_document_id(doc_id)
        assert count == 3

        # Delete all
        mock_result_del = MagicMock()
        mock_result_del.rowcount = 3
        mock_session.execute.return_value = mock_result_del
        deleted = await chunk_repo.delete_by_document_id(doc_id)
        assert deleted == 3

    @pytest.mark.asyncio
    async def test_large_batch_creation(self, chunk_repo, mock_session):
        """Test creating large batch of chunks."""
        doc_id = uuid4()
        large_batch = [
            {
                "document_id": doc_id,
                "chunk_index": i,
                "content": f"Chunk {i}",
                "embedding": [0.1] * 1024,
                "token_count": 200,
                "embedding_model_id": "amazon.titan-embed-text-v2:0",
            }
            for i in range(100)
        ]
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await chunk_repo.create_chunks(large_batch)

        assert len(result) == 100
        mock_session.add_all.assert_called_once()
