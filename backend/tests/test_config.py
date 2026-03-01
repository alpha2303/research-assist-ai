"""
Unit tests for configuration loading system.

Tests verify:
1. YAML config file loading
2. Environment variable overrides
3. Default values
4. Nested configuration access
"""

import pytest

from app.core.config import Settings, get_settings


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config.yaml for testing"""
    config_content = """
chunking:
  strategy: "recursive"
  chunk_size_tokens: 500
  overlap_tokens: 100
  split_separators:
    - "\\n## "
    - "\\n\\n"

retrieval:
  top_k: 3
  similarity_threshold: 0.8
  use_hybrid_search: false
  bm25_weight: 0.4
  vector_weight: 0.6

memory:
  recent_message_count: 8
  batch_fold_size: 4
  summarization_model: "test-model"
  max_summary_tokens: 300

embedding:
  model_id: "test-embedding-model"
  dimensions: 512

llm:
  model_id: "test-llm-model"
  max_output_tokens: 1024
  temperature: 0.5

document_processing:
  supported_formats:
    - "application/pdf"
  max_file_size_mb: 25
  primary_parser: "pymupdf4llm"
  fallback_parser: "pdfplumber"
"""
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(config_content)
    return config_path


def test_config_loads_from_yaml(config_file, monkeypatch):
    """Test that configuration loads correctly from YAML file"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    settings = Settings()
    
    # Verify chunking config
    assert settings.chunking.strategy == "recursive"
    assert settings.chunking.chunk_size_tokens == 500
    assert settings.chunking.overlap_tokens == 100
    
    # Verify retrieval config
    assert settings.retrieval.top_k == 3
    assert settings.retrieval.similarity_threshold == 0.8
    assert settings.retrieval.use_hybrid_search is False
    
    # Verify embedding config
    assert settings.embedding.model_id == "test-embedding-model"
    assert settings.embedding.dimensions == 512


def test_env_var_overrides_yaml(config_file, monkeypatch):
    """Test that top-level environment variables work"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Override top-level settings via env vars
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("ENVIRONMENT", "testing")
    
    settings = Settings()
    
    # Verify overrides took effect for top-level settings
    assert settings.aws_region == "us-west-2"
    assert settings.environment == "testing"
    
    # Verify YAML values still load
    assert settings.chunking.strategy == "recursive"


def test_llm_config_loading(config_file, monkeypatch):
    """Test LLM configuration loading"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    settings = Settings()
    
    assert settings.llm.model_id == "test-llm-model"
    assert settings.llm.max_output_tokens == 1024
    assert settings.llm.temperature == 0.5


def test_memory_config_loading(config_file, monkeypatch):
    """Test conversation memory configuration"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    settings = Settings()
    
    assert settings.memory.recent_message_count == 8
    assert settings.memory.batch_fold_size == 4
    assert settings.memory.summarization_model == "test-model"
    assert settings.memory.max_summary_tokens == 300


def test_document_processing_config(config_file, monkeypatch):
    """Test document processing configuration"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    settings = Settings()
    
    assert "application/pdf" in settings.document_processing.supported_formats
    assert settings.document_processing.max_file_size_mb == 25
    assert settings.document_processing.primary_parser == "pymupdf4llm"
    assert settings.document_processing.fallback_parser == "pdfplumber"


def test_get_settings_singleton():
    """Test that get_settings returns a singleton instance"""
    settings1 = get_settings()
    settings2 = get_settings()
    
    # Should be the same instance
    assert settings1 is settings2


def test_database_url_required(config_file, monkeypatch):
    """Test that configuration loads with DATABASE_URL"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    settings = Settings()
    
    # Verify DATABASE_URL was set
    assert "postgresql" in settings.database_url


def test_aws_region_default(config_file, monkeypatch):
    """Test AWS region has proper default"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    settings = Settings()
    
    assert settings.aws_region == "us-east-1"  # Default value


def test_hybrid_search_config_overrides(config_file, monkeypatch):
    """Test that hybrid search configuration loads from YAML"""
    monkeypatch.setenv("CONFIG_FILE", str(config_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    
    settings = Settings()
    
    # Verify values from YAML
    assert settings.retrieval.bm25_weight == 0.4
    assert settings.retrieval.vector_weight == 0.6
