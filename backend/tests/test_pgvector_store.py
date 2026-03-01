"""Unit tests for PGVector store."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.interfaces.vector_store import SearchResult
from app.implementations.pgvector_store import PGVectorStore


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_chunk_repo():
    """Create mock chunk repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def vector_store(mock_session, mock_chunk_repo):
    """Create vector store with mocked session and chunk repo."""
    with patch(
        "app.implementations.pgvector_store.ChunkRepository",
        return_value=mock_chunk_repo,
    ):
        store = PGVectorStore(mock_session)
    # Ensure the internal chunk_repo is our mock
    store.chunk_repo = mock_chunk_repo
    return store


@pytest.fixture
def sample_search_results():
    """Create sample SearchResult objects for query results."""
    return [
        SearchResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            content=f"Chunk {i} text content",
            score=1.0 - i * 0.1,
            page_number=i + 1,
            section_heading=f"Section {i}",
        )
        for i in range(5)
    ]


class TestPGVectorStore:
    """Test cases for PGVectorStore."""

    @pytest.mark.asyncio
    async def test_store_embeddings(self, vector_store, mock_chunk_repo):
        """Test storing chunk embeddings."""
        doc_id = uuid4()
        chunks = [
            {
                "chunk_index": 0,
                "content": "Chunk 0",
                "embedding": [0.1] * 1024,
                "token_count": 100,
                "embedding_model_id": "amazon.titan-embed-text-v2:0",
            },
            {
                "chunk_index": 1,
                "content": "Chunk 1",
                "embedding": [0.2] * 1024,
                "token_count": 100,
                "embedding_model_id": "amazon.titan-embed-text-v2:0",
            },
        ]

        await vector_store.store_embeddings(doc_id, chunks)

        mock_chunk_repo.create_chunks.assert_called_once()
        # Verify document_id was set on each chunk
        call_arg = mock_chunk_repo.create_chunks.call_args[0][0]
        assert all(c["document_id"] == doc_id for c in call_arg)

    @pytest.mark.asyncio
    async def test_store_empty_embeddings(self, vector_store, mock_chunk_repo):
        """Test storing empty list of embeddings."""
        await vector_store.store_embeddings(uuid4(), [])

        mock_chunk_repo.create_chunks.assert_called_once_with([])

    @pytest.mark.asyncio
    async def test_similarity_search(self, vector_store, mock_session):
        """Test similarity search returns SearchResult list."""
        query_embedding = [0.5] * 1024
        doc_ids = [uuid4()]

        # Mock the raw row results from session.execute
        mock_row = MagicMock()
        mock_row.id = uuid4()
        mock_row.document_id = doc_ids[0]
        mock_row.content = "chunk text"
        mock_row.score = 0.92
        mock_row.page_number = 1
        mock_row.section_heading = "Intro"

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await vector_store.similarity_search(
            query_embedding,
            document_ids=doc_ids,
            top_k=3,
        )

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].content == "chunk text"

    @pytest.mark.asyncio
    async def test_similarity_search_no_results(self, vector_store, mock_session):
        """Test similarity search when no results found."""
        query_embedding = [0.5] * 1024

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        results = await vector_store.similarity_search(
            query_embedding, document_ids=[uuid4()], top_k=5
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_similarity_search_with_model_filter(self, vector_store, mock_session):
        """Test similarity search with embedding_model_id filter."""
        query_embedding = [0.5] * 1024
        doc_ids = [uuid4()]

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        results = await vector_store.similarity_search(
            query_embedding,
            document_ids=doc_ids,
            top_k=5,
            embedding_model_id="amazon.titan-embed-text-v2:0",
        )

        assert results == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search(self, vector_store, mock_session):
        """Test hybrid search combining vector and BM25."""
        query_embedding = [0.5] * 1024
        query_text = "test query"
        doc_ids = [uuid4()]

        # similarity_search and _bm25_search both call session.execute
        mock_row1 = MagicMock()
        mock_row1.id = uuid4()
        mock_row1.document_id = doc_ids[0]
        mock_row1.content = "vector result"
        mock_row1.score = 0.9
        mock_row1.page_number = 1
        mock_row1.section_heading = None

        mock_row2 = MagicMock()
        mock_row2.id = uuid4()
        mock_row2.document_id = doc_ids[0]
        mock_row2.content = "bm25 result"
        mock_row2.score = 0.8
        mock_row2.page_number = 2
        mock_row2.section_heading = None

        mock_result = MagicMock()
        # First call: similarity_search, second: _bm25_search
        mock_result.all.side_effect = [[mock_row1], [mock_row2]]
        mock_session.execute.return_value = mock_result

        results = await vector_store.hybrid_search(
            query_embedding=query_embedding,
            query_text=query_text,
            document_ids=doc_ids,
            top_k=3,
        )

        assert isinstance(results, list)
        # should call execute at least twice (vector + bm25)
        assert mock_session.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_hybrid_search_empty(self, vector_store, mock_session):
        """Test hybrid search with no results."""
        query_embedding = [0.5] * 1024

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        results = await vector_store.hybrid_search(
            query_embedding=query_embedding,
            query_text="nothing",
            document_ids=[uuid4()],
            top_k=5,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_delete_by_document_id(self, vector_store, mock_chunk_repo):
        """Test deleting all chunks for a document."""
        doc_id = uuid4()
        mock_chunk_repo.delete_by_document_id.return_value = 45

        deleted_count = await vector_store.delete_by_document_id(doc_id)

        assert deleted_count == 45
        mock_chunk_repo.delete_by_document_id.assert_called_once_with(doc_id)

    @pytest.mark.asyncio
    async def test_delete_by_document_id_none_found(self, vector_store, mock_chunk_repo):
        """Test deleting when no chunks exist."""
        doc_id = uuid4()
        mock_chunk_repo.delete_by_document_id.return_value = 0

        deleted_count = await vector_store.delete_by_document_id(doc_id)

        assert deleted_count == 0

    @pytest.mark.asyncio
    async def test_get_chunk_count(self, vector_store, mock_chunk_repo):
        """Test counting chunks for a document."""
        doc_id = uuid4()
        mock_chunk_repo.count_by_document_id.return_value = 30

        count = await vector_store.get_chunk_count(doc_id)

        assert count == 30
        mock_chunk_repo.count_by_document_id.assert_called_once_with(doc_id)

    @pytest.mark.asyncio
    async def test_rrf_score_calculation(self, vector_store):
        """Test Reciprocal Rank Fusion scoring."""
        chunk_id_1, chunk_id_2 = uuid4(), uuid4()
        doc_id = uuid4()

        vector_results = [
            SearchResult(chunk_id=chunk_id_1, document_id=doc_id, content="A", score=0.95),
            SearchResult(chunk_id=chunk_id_2, document_id=doc_id, content="B", score=0.90),
        ]
        bm25_results = [
            SearchResult(chunk_id=chunk_id_2, document_id=doc_id, content="B", score=0.85),
            SearchResult(chunk_id=chunk_id_1, document_id=doc_id, content="A", score=0.50),
        ]

        fused = vector_store._reciprocal_rank_fusion(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=0.7,
            bm25_weight=0.3,
        )

        assert len(fused) == 2
        # Both chunk IDs should appear
        ids = {r.chunk_id for r in fused}
        assert chunk_id_1 in ids
        assert chunk_id_2 in ids

    @pytest.mark.asyncio
    async def test_close(self, vector_store, mock_session):
        """Test closing the database session."""
        await vector_store.close()

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_large_batch(self, vector_store, mock_chunk_repo):
        """Test storing large batch of embeddings."""
        doc_id = uuid4()
        large_batch = [
            {
                "chunk_index": i,
                "content": f"Chunk {i}",
                "embedding": [0.1] * 1024,
                "token_count": 100,
                "embedding_model_id": "amazon.titan-embed-text-v2:0",
            }
            for i in range(100)
        ]

        await vector_store.store_embeddings(doc_id, large_batch)

        mock_chunk_repo.create_chunks.assert_called_once()
        call_args = mock_chunk_repo.create_chunks.call_args[0][0]
        assert len(call_args) == 100
