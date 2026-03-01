"""
Application configuration management using Pydantic Settings.

This module provides a tiered configuration system:
1. Environment variables (.env files)
2. YAML configuration file (config.yaml)
3. Environment variable overrides (e.g., CHUNKING__CHUNK_SIZE_TOKENS)
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChunkingConfig(BaseSettings):
    """Configuration for document chunking."""

    strategy: str = "recursive"
    chunk_size_tokens: int = 800
    overlap_tokens: int = 150
    split_separators: list[str] = Field(
        default_factory=lambda: ["\n## ", "\n### ", "\n\n", "\n", ". "]
    )

    model_config = SettingsConfigDict(env_prefix="CHUNKING__")


class RetrievalConfig(BaseSettings):
    """Configuration for RAG retrieval."""

    top_k: int = 5
    similarity_threshold: float = 0.7
    use_hybrid_search: bool = True
    bm25_weight: float = 0.3
    vector_weight: float = 0.7

    model_config = SettingsConfigDict(env_prefix="RETRIEVAL__")


class MemoryConfig(BaseSettings):
    """Configuration for conversation memory."""

    recent_message_count: int = 10
    batch_fold_size: int = 5
    summarization_model: str = "amazon.nova-micro-v1:0"
    max_summary_tokens: int = 500

    model_config = SettingsConfigDict(env_prefix="MEMORY__")


class EmbeddingConfig(BaseSettings):
    """Configuration for embedding generation."""

    model_id: str = "amazon.titan-embed-text-v2:0"
    dimensions: int = 1024

    model_config = SettingsConfigDict(env_prefix="EMBEDDING__")


class LLMConfig(BaseSettings):
    """Configuration for LLM (Q&A)."""

    model_id: str = "amazon.nova-micro-v1:0"
    max_output_tokens: int = 2048
    temperature: float = 0.3
    context_window: int = 128000  # Nova Micro supports ~128k tokens

    model_config = SettingsConfigDict(env_prefix="LLM__")


class DocumentProcessingConfig(BaseSettings):
    """Configuration for document processing."""

    supported_formats: list[str] = Field(default_factory=lambda: ["application/pdf"])
    max_file_size_mb: int = 50
    primary_parser: str = "pymupdf4llm"
    fallback_parser: str = "pdfplumber"

    model_config = SettingsConfigDict(env_prefix="DOCUMENT_PROCESSING__")


class Settings(BaseSettings):
    """
    Main application settings.

    Loads configuration from:
    1. .env file (environment variables)
    2. config.yaml file (application configuration)
    3. Environment variable overrides (e.g., CHUNKING__CHUNK_SIZE_TOKENS)
    """

    # Environment variables
    database_url: str = Field(
        ...,  # Required - must be set via environment variable
        description="PostgreSQL connection URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    aws_profile: str = Field(default="default")
    aws_region: str = Field(default="us-east-1")
    bedrock_llm_model_id: str = Field(default="amazon.nova-micro-v1:0")
    bedrock_embedding_model_id: str = Field(default="amazon.titan-embed-text-v2:0")
    s3_bucket_name: str = Field(default="research-assist-documents-dev")
    s3_endpoint_url: str | None = Field(
        default=None,
        description="S3 endpoint URL (set for LocalStack, omit for AWS)"
    )
    dynamodb_chat_sessions_table: str = Field(
        default="research-assist-chat-sessions-dev"
    )
    dynamodb_chat_messages_table: str = Field(
        default="research-assist-chat-messages-dev"
    )
    dynamodb_endpoint_url: str | None = Field(
        default=None,
        description="DynamoDB endpoint URL (set for LocalStack, omit for AWS)"
    )
    config_file: str = Field(default="config.yaml")
    environment: str = Field(default="local")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins. Set via CORS_ORIGINS env var (comma-separated).",
    )

    # Application configuration sections (loaded from YAML)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    document_processing: DocumentProcessingConfig = Field(
        default_factory=DocumentProcessingConfig
    )

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs: Any):
        """
        Initialize settings by loading from .env and config.yaml.

        Environment variables take precedence over config.yaml values.
        """
        super().__init__(**kwargs)
        self._load_yaml_config()

    def _load_yaml_config(self) -> None:
        """Load configuration from YAML file and merge with existing settings."""
        config_path = Path(self.config_file)

        if not config_path.exists():
            # Config file is optional - use defaults if not found
            return

        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        if not yaml_config:
            return

        # Update configuration sections with YAML values
        # Environment variables take precedence, so we only update if not already set
        if "chunking" in yaml_config:
            self.chunking = ChunkingConfig(**yaml_config["chunking"])

        if "retrieval" in yaml_config:
            self.retrieval = RetrievalConfig(**yaml_config["retrieval"])

        if "memory" in yaml_config:
            self.memory = MemoryConfig(**yaml_config["memory"])

        if "embedding" in yaml_config:
            self.embedding = EmbeddingConfig(**yaml_config["embedding"])

        if "llm" in yaml_config:
            self.llm = LLMConfig(**yaml_config["llm"])

        if "document_processing" in yaml_config:
            self.document_processing = DocumentProcessingConfig(
                **yaml_config["document_processing"]
            )


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get the application settings singleton.

    This function should be used as a FastAPI dependency.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the settings singleton (useful for testing)."""
    global _settings
    _settings = None
