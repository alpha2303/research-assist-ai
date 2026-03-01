"""
SQLAlchemy database models for Research Assist AI.

Models:
- Project: Top-level container for related documents
- Document: Research papers with processing status
- ProjectDocument: Many-to-many linking table
- DocumentChunk: Text chunks with embeddings and BM25 search vectors
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class DocumentStatus(PyEnum):
    """Processing status of a document"""
    QUEUED = "queued"          # Uploaded, waiting for processing
    PROCESSING = "processing"  # Currently being processed
    COMPLETED = "completed"    # Successfully processed
    FAILED = "failed"          # Processing failed


class Project(Base):
    """
    Project model - logical grouping of related documents.
    
    A project can have multiple chat sessions, all sharing
    access to the same document corpus.
    """
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    project_documents = relationship("ProjectDocument", back_populates="project", cascade="all, delete-orphan")
    # Direct access to documents via the linking table
    documents = relationship("Document", secondary="project_documents", viewonly=True)
    
    def __repr__(self) -> str:
        return f"<Project(id={self.id}, title='{self.title}')>"


class Document(Base):
    """
    Document model - globally stored research papers.
    
    Documents are stored globally and linked to projects via
    ProjectDocument. This avoids duplicate processing when
    the same paper is used in multiple projects.
    
    Deduplication: SHA-256 file hash on upload
    """
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    s3_key = Column(String(500), nullable=False, unique=True)
    file_hash = Column(String(64), nullable=False, unique=True)  # SHA-256
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.QUEUED, nullable=False)
    page_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)  # Populated if status=FAILED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    project_documents = relationship("ProjectDocument", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    # Direct access to projects via the linking table
    projects = relationship("Project", secondary="project_documents", viewonly=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_document_file_hash", "file_hash"),
        Index("idx_document_status", "status"),
    )
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}', status={self.status})>"


class ProjectDocument(Base):
    """
    Many-to-many linking table between projects and documents.
    
    Allows the same document to be used in multiple projects
    without duplicate storage or processing.
    """
    __tablename__ = "project_documents"
    
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    linked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("Project", back_populates="project_documents")
    document = relationship("Document", back_populates="project_documents")
    
    def __repr__(self) -> str:
        return f"<ProjectDocument(project_id={self.project_id}, document_id={self.document_id})>"


class DocumentChunk(Base):
    """
    Document chunk model - text chunks with embeddings and BM25 search vectors.
    
    Each chunk stores:
    - Text content (for retrieval)
    - Vector embedding (for similarity search)
    - TSVector (for BM25 keyword search)
    - Metadata (page number, section heading, etc.)
    - Embedding model ID (for re-embedding support)
    """
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Order within document
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_heading = Column(String(500), nullable=True)
    token_count = Column(Integer, nullable=False)
    embedding_model_id = Column(String(100), nullable=False)
    
    # Vector embedding for similarity search
    embedding = Column(Vector(1024), nullable=False)  # Titan V2 uses 1024 dimensions
    
    # TSVector for BM25 full-text search
    search_vector = Column(TSVECTOR, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    # Indexes
    __table_args__ = (
        Index("idx_chunk_document_id", "document_id"),
        Index("idx_chunk_document_chunk", "document_id", "chunk_index"),
        Index(
            "idx_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),  # Vector similarity index with cosine distance
        Index("idx_chunk_search_vector_gin", "search_vector", postgresql_using="gin"),  # Full-text search index
    )
    
    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"
