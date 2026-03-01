"""Text chunking service for splitting documents into manageable pieces."""

import re
from dataclasses import dataclass

import tiktoken

from app.core.config import ChunkingConfig


@dataclass
class TextChunk:
    """A chunk of text with metadata."""

    content: str
    chunk_index: int
    page_number: int | None
    section_heading: str | None
    token_count: int
    char_start: int
    char_end: int
    metadata: dict[str, str | int | float]


class TextChunker:
    """
    Service for chunking text documents with overlap.
    
    Uses recursive character splitting with configurable separators
    and token-based sizing for optimal LLM processing.
    """

    def __init__(self, config: ChunkingConfig):
        """
        Initialize text chunker with configuration.
        
        Args:
            config: Chunking configuration (chunk size, overlap, separators)
        """
        self.config = config
        
        # Initialize tiktoken encoder for accurate token counting
        # Using cl100k_base encoding (GPT-4, GPT-3.5-turbo)
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.encoder.encode(text))

    def chunk_text(
        self,
        text: str,
        page_number: int | None = None,
        document_metadata: dict[str, str | int | float] | None = None
    ) -> list[TextChunk]:
        """
        Chunk text into overlapping segments.
        
        Args:
            text: Text to chunk
            page_number: Page number this text came from (if applicable)
            document_metadata: Additional metadata to include in chunks
            
        Returns:
            List of text chunks with metadata
        """
        if not text.strip():
            return []
        
        metadata = document_metadata or {}
        
        # Split text recursively using configured separators
        chunks = self._recursive_split(text)
        
        # Create TextChunk objects with metadata
        result_chunks = []
        char_position = 0
        
        for idx, chunk_text in enumerate(chunks):
            # Extract section heading if present (look for markdown headers)
            section_heading = self._extract_section_heading(chunk_text)
            
            # Count tokens
            token_count = self.count_tokens(chunk_text)
            
            # Calculate character positions
            char_start = char_position
            char_end = char_start + len(chunk_text)
            char_position = char_end
            
            result_chunks.append(
                TextChunk(
                    content=chunk_text,
                    chunk_index=idx,
                    page_number=page_number,
                    section_heading=section_heading,
                    token_count=token_count,
                    char_start=char_start,
                    char_end=char_end,
                    metadata=metadata
                )
            )
        
        return result_chunks

    def _recursive_split(
        self,
        text: str,
        separators: list[str] | None = None
    ) -> list[str]:
        """
        Recursively split text using hierarchical separators.
        
        Tries separators in order until finding one that produces
        appropriately sized chunks.
        
        Args:
            text: Text to split
            separators: List of separators to try (uses config default if None)
            
        Returns:
            List of text chunks
        """
        if separators is None:
            separators = self.config.split_separators.copy()
        
        # Base case: no more separators or text is small enough
        if not separators or self.count_tokens(text) <= self.config.chunk_size_tokens:
            return [text] if text.strip() else []
        
        # Try current separator
        separator = separators[0]
        remaining_separators = separators[1:]
        
        # Split by current separator
        splits = text.split(separator)
        
        # Merge splits into chunks with overlap
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for split in splits:
            split_tokens = self.count_tokens(split)
            
            # If adding this split would exceed chunk size
            if current_tokens + split_tokens > self.config.chunk_size_tokens and current_chunk:
                # Save current chunk
                chunk_text = separator.join(current_chunk)
                chunks.append(chunk_text)
                
                # Start new chunk with overlap
                # Keep last few splits for overlap
                overlap_parts = []
                overlap_tokens = 0
                
                for part in reversed(current_chunk):
                    part_tokens = self.count_tokens(part)
                    if overlap_tokens + part_tokens <= self.config.overlap_tokens:
                        overlap_parts.insert(0, part)
                        overlap_tokens += part_tokens
                    else:
                        break
                
                current_chunk = overlap_parts
                current_tokens = overlap_tokens
            
            # Add current split
            current_chunk.append(split)
            current_tokens += split_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = separator.join(current_chunk)
            chunks.append(chunk_text)
        
        # If any chunk is still too large, recursively split it
        result = []
        for chunk in chunks:
            if self.count_tokens(chunk) > self.config.chunk_size_tokens:
                # Try next separator
                sub_chunks = self._recursive_split(chunk, remaining_separators)
                result.extend(sub_chunks)
            else:
                result.append(chunk)
        
        return result

    def _extract_section_heading(self, text: str) -> str | None:
        """
        Extract section heading from chunk text.
        
        Looks for markdown-style headers (# Header, ## Subheader, etc.)
        at the beginning of the chunk.
        
        Args:
            text: Chunk text
            
        Returns:
            Section heading or None if not found
        """
        # Match markdown headers at start of text
        match = re.match(r'^(#{1,6})\s+(.+?)(?:\n|$)', text)
        if match:
            return match.group(2).strip()
        
        return None

    def chunk_document_pages(
        self,
        pages: list[tuple[int, str]],
        document_metadata: dict[str, str | int | float] | None = None
    ) -> list[TextChunk]:
        """
        Chunk multiple pages of a document.
        
        Args:
            pages: List of (page_number, text) tuples
            document_metadata: Additional metadata to include in chunks
            
        Returns:
            List of text chunks from all pages
        """
        all_chunks = []
        global_chunk_index = 0
        
        for page_number, page_text in pages:
            page_chunks = self.chunk_text(
                page_text,
                page_number=page_number,
                document_metadata=document_metadata
            )
            
            # Update global chunk indices
            for chunk in page_chunks:
                chunk.chunk_index = global_chunk_index
                global_chunk_index += 1
            
            all_chunks.extend(page_chunks)
        
        return all_chunks
