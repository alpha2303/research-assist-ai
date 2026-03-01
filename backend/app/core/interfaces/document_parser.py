"""
DocumentParser interface for extracting text from various document formats.

This interface abstracts document parsing to allow multiple parsers
and fallback strategies without changing the ingestion pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PageContent:
    """Content extracted from a single page"""
    page_number: int
    text: str
    metadata: dict[str, str | int | float] | None = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ParseResult:
    """Result of parsing a document"""
    pages: list[PageContent]
    total_pages: int
    title: str | None = None
    author: str | None = None
    metadata: dict[str, str | int | float] | None = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def get_full_text(self) -> str:
        """Get all page content as a single string"""
        return "\n\n".join(page.text for page in self.pages)


class DocumentParser(ABC):
    """
    Abstract interface for document parsing operations.
    
    Implementations:
    - PyMuPDF4LLMParser: Uses pymupdf4llm for PDF → Markdown conversion
    - PdfPlumberParser: Fallback parser using pdfplumber
    - DocxParser: Microsoft Word documents (future)
    - HTMLParser: Web pages and HTML documents (future)
    """
    
    @abstractmethod
    async def parse(self, file_path: Path) -> ParseResult:
        """
        Parse a document file and extract its content.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            ParseResult containing extracted text and metadata
            
        Raises:
            ValueError: If file format is not supported
            RuntimeError: If parsing fails
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """
        Get list of MIME types this parser supports.
        
        Returns:
            List of MIME type strings (e.g., ["application/pdf"])
        """
        pass
    
    @abstractmethod
    def get_parser_name(self) -> str:
        """
        Get the name/identifier of this parser.
        
        Used for logging and fallback selection.
        
        Returns:
            Parser name (e.g., "pymupdf4llm", "pdfplumber")
        """
        pass
