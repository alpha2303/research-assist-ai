"""
Tests for RetrievalService.

These tests verify:
1. Project-scoped retrieval (only searches documents linked to project)
2. Query embedding generation
3. Hybrid search execution with correct parameters
4. Context formatting for LLM prompts
5. Source metadata extraction for attribution
6. Edge cases (empty projects, no results, etc.)
"""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.config import RetrievalConfig, Settings
from app.core.interfaces import SearchResult
from app.models.database import Document
from app.repositories.document_repo import DocumentRepository
from app.services.retrieval_service import (
    RetrievalResult,
    RetrievalService
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings with retrieval config."""
    settings = Mock(spec=Settings)
    settings.retrieval = RetrievalConfig(
        top_k=15,
        similarity_threshold=0.5,
        use_hybrid_search=True,
        bm25_weight=0.3,
        vector_weight=0.7
    )
    settings.embedding = Mock()
    settings.embedding.model_id = "amazon.titan-embed-text-v2:0"
    return settings


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    """Create mock embedding provider."""
    provider = AsyncMock()
    # Return a simple vector of 3 dimensions for testing
    provider.embed_text.return_value = [0.1, 0.2, 0.3]
    return provider


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_document_repo() -> AsyncMock:
    """Create mock document repository."""
    repo = AsyncMock(spec=DocumentRepository)
    return repo


@pytest.fixture
def retrieval_service(
    mock_document_repo: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_embedding_provider: AsyncMock,
    mock_settings: Settings
) -> RetrievalService:
    """Create retrieval service with mocked dependencies."""
    return RetrievalService(
        document_repo=mock_document_repo,
        vector_store=mock_vector_store,
        embedding_provider=mock_embedding_provider,
        settings=mock_settings
    )


@pytest.mark.asyncio
async def test_retrieve_for_query_success(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock,
    mock_embedding_provider: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_settings: Settings
):
    """Test successful retrieval with hybrid search."""
    # Setup test data
    project_id = uuid4()
    query = "What is the transformer architecture?"
    
    doc1_id = uuid4()
    doc2_id = uuid4()
    
    # Mock documents
    doc1 = Mock(spec=Document)
    doc1.id = doc1_id
    doc1.title = "Attention Is All You Need"
    
    doc2 = Mock(spec=Document)
    doc2.id = doc2_id
    doc2.title = "BERT: Pre-training of Deep Bidirectional Transformers"
    
    mock_document_repo.get_documents_by_project.return_value = [doc1, doc2]
    
    # Mock search results
    chunk1_id = uuid4()
    chunk2_id = uuid4()
    
    search_results = [
        SearchResult(
            chunk_id=chunk1_id,
            document_id=doc1_id,
            content="The Transformer uses self-attention mechanisms...",
            score=0.92,
            page_number=3,
            section_heading="Model Architecture"
        ),
        SearchResult(
            chunk_id=chunk2_id,
            document_id=doc2_id,
            content="BERT is designed to pre-train deep bidirectional representations...",
            score=0.87,
            page_number=5,
            section_heading="Introduction"
        )
    ]
    
    mock_vector_store.hybrid_search.return_value = search_results
    
    # Execute
    result = await retrieval_service.retrieve_for_query(
        project_id=project_id,
        query=query
    )
    
    # Verify document repo called correctly
    mock_document_repo.get_documents_by_project.assert_called_once_with(
        project_id=project_id,
        limit=1000
    )
    
    # Verify embedding generated
    mock_embedding_provider.embed_text.assert_called_once_with(query)
    
    # Verify hybrid search called with correct parameters
    mock_vector_store.hybrid_search.assert_called_once()
    call_args = mock_vector_store.hybrid_search.call_args
    assert call_args.kwargs['query_embedding'] == [0.1, 0.2, 0.3]
    assert call_args.kwargs['query_text'] == query
    assert set(call_args.kwargs['document_ids']) == {doc1_id, doc2_id}
    assert call_args.kwargs['top_k'] == mock_settings.retrieval.top_k
    assert call_args.kwargs['vector_weight'] == 0.7
    assert call_args.kwargs['bm25_weight'] == 0.3
    
    # Verify result structure
    assert isinstance(result, RetrievalResult)
    assert result.chunk_count == 2
    assert len(result.sources) == 2
    
    # Verify context formatting
    assert "[Source 1: Attention Is All You Need, Page 3]" in result.context
    assert "Section: Model Architecture" in result.context
    assert "The Transformer uses self-attention mechanisms..." in result.context
    
    assert "[Source 2: BERT: Pre-training of Deep Bidirectional Transformers, Page 5]" in result.context
    assert "Section: Introduction" in result.context
    assert "BERT is designed to pre-train deep bidirectional representations..." in result.context
    
    # Verify sources
    assert len(result.sources) == 2
    
    source1 = result.sources[0]
    assert source1.document_id == doc1_id
    assert source1.document_title == "Attention Is All You Need"
    assert source1.page_number == 3
    assert source1.chunk_id == chunk1_id
    
    source2 = result.sources[1]
    assert source2.document_id == doc2_id
    assert source2.document_title == "BERT: Pre-training of Deep Bidirectional Transformers"
    assert source2.page_number == 5
    assert source2.chunk_id == chunk2_id


@pytest.mark.asyncio
async def test_retrieve_for_query_no_documents(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock
):
    """Test retrieval fails when project has no documents."""
    project_id = uuid4()
    query = "What is machine learning?"
    
    # Mock empty document list
    mock_document_repo.get_documents_by_project.return_value = []
    
    # Execute and expect ValueError
    with pytest.raises(ValueError, match="has no linked documents"):
        await retrieval_service.retrieve_for_query(
            project_id=project_id,
            query=query
        )


@pytest.mark.asyncio
async def test_retrieve_for_query_no_results(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock,
    mock_vector_store: AsyncMock
):
    """Test retrieval returns empty result when no chunks match."""
    project_id = uuid4()
    query = "quantum computing"
    
    # Mock documents
    doc1 = Mock(spec=Document)
    doc1.id = uuid4()
    doc1.title = "Deep Learning Basics"
    
    mock_document_repo.get_documents_by_project.return_value = [doc1]
    
    # Mock empty search results
    mock_vector_store.hybrid_search.return_value = []
    
    # Execute
    result = await retrieval_service.retrieve_for_query(
        project_id=project_id,
        query=query
    )
    
    # Verify empty result
    assert result.context == ""
    assert result.sources == []
    assert result.chunk_count == 0


@pytest.mark.asyncio
async def test_retrieve_for_query_custom_top_k(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock,
    mock_vector_store: AsyncMock
):
    """Test retrieval with custom top_k parameter."""
    project_id = uuid4()
    query = "neural networks"
    custom_top_k = 10
    
    # Mock documents
    doc1 = Mock(spec=Document)
    doc1.id = uuid4()
    doc1.title = "Neural Network Fundamentals"
    
    mock_document_repo.get_documents_by_project.return_value = [doc1]
    mock_vector_store.hybrid_search.return_value = []
    
    # Execute with custom top_k
    await retrieval_service.retrieve_for_query(
        project_id=project_id,
        query=query,
        top_k=custom_top_k
    )
    
    # Verify custom top_k used
    call_args = mock_vector_store.hybrid_search.call_args
    assert call_args.kwargs['top_k'] == custom_top_k


@pytest.mark.asyncio
async def test_retrieve_for_query_vector_only_search(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock,
    mock_vector_store: AsyncMock,
    mock_settings: Settings
):
    """Test retrieval uses vector-only search when hybrid is disabled."""
    # Disable hybrid search
    mock_settings.retrieval.use_hybrid_search = False
    
    project_id = uuid4()
    query = "machine learning"
    
    # Mock documents
    doc1 = Mock(spec=Document)
    doc1.id = uuid4()
    doc1.title = "ML Basics"
    
    mock_document_repo.get_documents_by_project.return_value = [doc1]
    mock_vector_store.similarity_search.return_value = []
    
    # Execute
    await retrieval_service.retrieve_for_query(
        project_id=project_id,
        query=query
    )
    
    # Verify similarity_search used instead of hybrid_search
    mock_vector_store.similarity_search.assert_called_once()
    mock_vector_store.hybrid_search.assert_not_called()
    
    # Verify correct parameters
    call_args = mock_vector_store.similarity_search.call_args
    assert call_args.kwargs['query_embedding'] == [0.1, 0.2, 0.3]
    assert call_args.kwargs['top_k'] == mock_settings.retrieval.top_k
    assert call_args.kwargs['similarity_threshold'] is None


@pytest.mark.asyncio
async def test_context_formatting_without_page_number(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock,
    mock_vector_store: AsyncMock
):
    """Test context formatting when chunks have no page number."""
    project_id = uuid4()
    query = "test query"
    
    doc_id = uuid4()
    doc1 = Mock(spec=Document)
    doc1.id = doc_id
    doc1.title = "Test Document"
    
    mock_document_repo.get_documents_by_project.return_value = [doc1]
    
    # Search result without page number
    search_results = [
        SearchResult(
            chunk_id=uuid4(),
            document_id=doc_id,
            content="This is a chunk without page info.",
            score=0.8,
            page_number=None,  # No page number
            section_heading=None
        )
    ]
    
    mock_vector_store.hybrid_search.return_value = search_results
    
    # Execute
    result = await retrieval_service.retrieve_for_query(
        project_id=project_id,
        query=query
    )
    
    # Verify context doesn't include page number
    assert "[Source 1: Test Document]" in result.context
    assert "Page" not in result.context
    assert "This is a chunk without page info." in result.context


@pytest.mark.asyncio
async def test_source_deduplication(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock,
    mock_vector_store: AsyncMock
):
    """Test that sources are deduplicated by document_id + page_number."""
    project_id = uuid4()
    query = "test query"
    
    doc_id = uuid4()
    doc1 = Mock(spec=Document)
    doc1.id = doc_id
    doc1.title = "Research Paper"
    
    mock_document_repo.get_documents_by_project.return_value = [doc1]
    
    # Multiple chunks from same document and page
    search_results = [
        SearchResult(
            chunk_id=uuid4(),
            document_id=doc_id,
            content="First chunk from page 5.",
            score=0.9,
            page_number=5,
            section_heading="Introduction"
        ),
        SearchResult(
            chunk_id=uuid4(),
            document_id=doc_id,
            content="Second chunk also from page 5.",
            score=0.85,
            page_number=5,
            section_heading="Introduction"
        ),
        SearchResult(
            chunk_id=uuid4(),
            document_id=doc_id,
            content="Third chunk from page 7.",
            score=0.8,
            page_number=7,
            section_heading="Methods"
        )
    ]
    
    mock_vector_store.hybrid_search.return_value = search_results
    
    # Execute
    result = await retrieval_service.retrieve_for_query(
        project_id=project_id,
        query=query
    )
    
    # Verify sources are deduplicated (only 2 sources: page 5 and page 7)
    assert len(result.sources) == 2
    assert result.sources[0].page_number == 5
    assert result.sources[1].page_number == 7
    
    # But context should include all 3 chunks
    assert result.chunk_count == 3
    assert "First chunk from page 5" in result.context
    assert "Second chunk also from page 5" in result.context
    assert "Third chunk from page 7" in result.context


@pytest.mark.asyncio
async def test_project_isolation(
    retrieval_service: RetrievalService,
    mock_document_repo: AsyncMock,
    mock_vector_store: AsyncMock
):
    """Test that retrieval only searches documents linked to the specific project."""
    project1_id = uuid4()
    project2_id = uuid4()
    query = "machine learning"
    
    # Project 1 has documents A and B
    doc_a_id = uuid4()
    doc_b_id = uuid4()
    
    doc_a = Mock(spec=Document)
    doc_a.id = doc_a_id
    doc_a.title = "Document A"
    
    doc_b = Mock(spec=Document)
    doc_b.id = doc_b_id
    doc_b.title = "Document B"
    
    # Mock repo to return only project 1's documents
    mock_document_repo.get_documents_by_project.return_value = [doc_a, doc_b]
    
    mock_vector_store.hybrid_search.return_value = []
    
    # Execute retrieval for project 1
    await retrieval_service.retrieve_for_query(
        project_id=project1_id,
        query=query
    )
    
    # Verify only project 1's document IDs were passed to vector store
    call_args = mock_vector_store.hybrid_search.call_args
    document_ids = call_args.kwargs['document_ids']
    assert set(document_ids) == {doc_a_id, doc_b_id}
    
    # Project 2 would have different documents
    doc_c_id = uuid4()
    doc_c = Mock(spec=Document)
    doc_c.id = doc_c_id
    doc_c.title = "Document C"
    
    mock_document_repo.get_documents_by_project.return_value = [doc_c]
    
    # Execute retrieval for project 2
    await retrieval_service.retrieve_for_query(
        project_id=project2_id,
        query=query
    )
    
    # Verify only project 2's document IDs were passed
    call_args = mock_vector_store.hybrid_search.call_args
    document_ids = call_args.kwargs['document_ids']
    assert document_ids == [doc_c_id]
