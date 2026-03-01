"""Unit tests for text chunking service."""

import pytest

from app.core.config import ChunkingConfig
from app.services.chunking_service import TextChunker


@pytest.fixture
def chunking_config():
    """Create test chunking configuration."""
    return ChunkingConfig(
        chunk_size_tokens=800,
        overlap_tokens=150,
        split_separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "]
    )


@pytest.fixture
def text_chunker(chunking_config):
    """Create text chunker with test config."""
    return TextChunker(config=chunking_config)


class TestTextChunker:
    """Test cases for TextChunker."""

    def test_chunk_simple_text(self, text_chunker):
        """Test chunking simple text."""
        text = "This is a test. " * 100  # Repeating text
        
        chunks = text_chunker.chunk_text(text)
        
        assert len(chunks) > 0
        # Each chunk should have content
        assert all(chunk.content for chunk in chunks)
        # Chunks should have sequential indices
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_chunk_with_sections(self, text_chunker):
        """Test chunking text with section headers."""
        text = """# Introduction

This is the introduction section with some content. """ + "More content. " * 200 + """

## Background

This provides background information about the topic. """ + "Additional info. " * 200 + """

## Methods

This section describes the methods used.

### Data Collection

Details about data collection process.

### Data Analysis

Details about analysis methods.

## Results

This section presents the results.

## Conclusion

Final conclusions from the study.
"""
        
        chunks = text_chunker.chunk_text(text)
        
        assert len(chunks) > 0
        # Check that some chunks have section headings extracted
        chunks_with_sections = [c for c in chunks if c.section_heading]
        assert len(chunks_with_sections) > 0

    def test_chunk_short_text(self, text_chunker):
        """Test chunking text shorter than chunk size."""
        text = "This is a short text that fits in one chunk."
        
        chunks = text_chunker.chunk_text(text)
        
        # Should create at least one chunk
        assert len(chunks) >= 1
        assert chunks[0].content == text.strip()

    def test_chunk_empty_text(self, text_chunker):
        """Test chunking empty text."""
        text = ""
        
        chunks = text_chunker.chunk_text(text)
        
        # Should return empty list
        assert len(chunks) == 0

    def test_chunk_token_count(self, text_chunker):
        """Test that token counts are computed."""
        text = "This is a test sentence. " * 50
        
        chunks = text_chunker.chunk_text(text)
        
        # All chunks should have token counts
        assert all(chunk.token_count > 0 for chunk in chunks)
        # Token counts should be reasonable (less than chunk size)
        assert all(chunk.token_count <= 1000 for chunk in chunks)

    def test_chunk_overlap(self, text_chunker):
        """Test that chunks have overlap."""
        # Create text that will definitely span multiple chunks
        text = "Sentence number {}. " * 200
        text = text.format(*range(200))
        
        chunks = text_chunker.chunk_text(text)
        
        if len(chunks) > 1:
            # Check for overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                chunk1_end = chunks[i].content[-50:]  # Last 50 chars
                chunk2_start = chunks[i + 1].content[:50]  # First 50 chars
                # There should be some common content
                # (not perfect test, but indicative)
                assert any(word in chunk2_start for word in chunk1_end.split())

    def test_chunk_pages(self, text_chunker):
        """Test chunking multiple pages."""
        pages = [
            (1, "This is page 1 content. " * 50),
            (2, "This is page 2 content. " * 50),
        ]
        
        chunks = text_chunker.chunk_document_pages(pages)
        
        assert len(chunks) > 0
        # Chunks should have page numbers
        assert all(chunk.page_number in [1, 2] for chunk in chunks)

    def test_chunk_markdown_text(self, text_chunker):
        """Test chunking markdown formatted text."""
        markdown = """
# Main Title

## Section 1

This is the first section with some **bold** and *italic* text.

### Subsection 1.1

More detailed content here.

## Section 2

Another section with:
- Bullet point 1
- Bullet point 2
- Bullet point 3

### Subsection 2.1

Final content.
"""
        
        chunks = text_chunker.chunk_text(markdown)
        
        assert len(chunks) > 0
        # Should preserve markdown formatting
        assert any("**" in chunk.content or "*" in chunk.content for chunk in chunks if "bold" in chunk.content or "italic" in chunk.content)

    def test_chunk_very_long_text(self, text_chunker):
        """Test chunking very long text that requires multiple chunks."""
        # Create text longer than chunk size
        text = "This is a sentence. " * 500
        
        chunks = text_chunker.chunk_text(text)
        
        # Should split into multiple chunks
        assert len(chunks) > 1
        # All chunks should have content
        assert all(chunk.content for chunk in chunks)

    def test_extract_section_heading(self, text_chunker):
        """Test section heading extraction."""
        text_with_header = "## My Section\n\nSome content here."
        
        # Test internal method
        section = text_chunker._extract_section_heading(text_with_header)
        
        assert section == "My Section"

    def test_count_tokens_method(self, text_chunker):
        """Test token counting."""
        text = "This is a test sentence."
        
        token_count = text_chunker.count_tokens(text)
        
        # Should return reasonable count
        assert token_count > 0
        assert token_count < 20  # This short sentence should be < 20 tokens

    def test_handle_special_characters(self, text_chunker):
        """Test handling of special characters."""
        text = "Text with special chars: @#$%^&*() and émojis 🎉 and unicode ü."
        
        chunks = text_chunker.chunk_text(text)
        
        # Should handle without errors
        assert len(chunks) > 0
        assert chunks[0].content  # Should contain content

    def test_empty_text_handling(self, text_chunker):
        """Test handling of empty text."""
        text = ""
        
        chunks = text_chunker.chunk_text(text)
        
        # Should return empty list
        assert chunks == []

    def test_whitespace_only_text(self, text_chunker):
        """Test handling of whitespace-only text."""
        text = "   \n\n\t\t   "
        
        chunks = text_chunker.chunk_text(text)
        
        # Should return empty list for whitespace-only
        assert chunks == []

    def test_chunk_with_page_number(self, text_chunker):
        """Test chunking with page number metadata."""
        text = "This is page content. " * 10
        page_num = 5
        
        chunks = text_chunker.chunk_text(text, page_number=page_num)
        
        assert len(chunks) > 0
        # All chunks should have the page number
        assert all(chunk.page_number == page_num for chunk in chunks)

    def test_chunk_with_document_metadata(self, text_chunker):
        """Test chunking with additional metadata."""
        text = "This is content. " * 10
        metadata = {"source": "test.pdf", "author": "Test Author"}
        
        chunks = text_chunker.chunk_text(text, document_metadata=metadata)
        
        assert len(chunks) > 0
        # Metadata should be included
        assert all(chunk.metadata.get("source") == "test.pdf" for chunk in chunks)
