"""PDF parser implementations using PyMuPDF4LLM and PdfPlumber."""

from pathlib import Path
from typing import Any

import pdfplumber
import pymupdf
import pymupdf4llm

from app.core.interfaces.document_parser import (
    DocumentParser,
    PageContent,
    ParseResult,
)


class PyMuPDF4LLMParser(DocumentParser):
    """
    Primary PDF parser using PyMuPDF4LLM.
    
    Converts PDF to Markdown format with excellent table handling.
    Optimized for LLM consumption with clean formatting.
    """

    async def parse(self, file_path: Path) -> ParseResult:
        """
        Parse PDF using PyMuPDF4LLM to extract Markdown content.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            ParseResult with Markdown-formatted content per page
            
        Raises:
            ValueError: If file is not a PDF
            RuntimeError: If parsing fails
        """
        if not file_path.suffix.lower() == ".pdf":
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        try:
            # Use page_chunks=True to get per-page markdown output.
            # Returns a list of dicts: [{"metadata": {…, "page": 0}, "text": "…"}, …]
            chunks = pymupdf4llm.to_markdown(str(file_path), page_chunks=True)

            # Also open with pymupdf directly to get reliable page count & doc metadata
            doc = pymupdf.open(str(file_path))
            total_pages = doc.page_count
            doc_metadata: dict[str, Any] = dict(doc.metadata) if doc.metadata else {}
            doc.close()

            pages: list[PageContent] = []

            if isinstance(chunks, list) and chunks:
                for chunk in chunks:
                    page_num = chunk.get("metadata", {}).get("page", 0) + 1  # 0-indexed → 1-indexed
                    text = chunk.get("text", "")
                    if text.strip():
                        pages.append(
                            PageContent(
                                page_number=page_num,
                                text=text,
                                metadata={"format": "markdown"},
                            )
                        )
            else:
                # Fallback: treat the entire output as one page
                markdown_text = chunks if isinstance(chunks, str) else str(chunks)
                pages.append(
                    PageContent(
                        page_number=1,
                        text=markdown_text,
                        metadata={"format": "markdown"},
                    )
                )

            return ParseResult(
                pages=pages,
                total_pages=total_pages,
                title=doc_metadata.get("title"),
                author=doc_metadata.get("author"),
                metadata=doc_metadata,
            )
            
        except Exception as e:
            raise RuntimeError(f"PyMuPDF4LLM parsing failed: {str(e)}") from e

    def get_supported_formats(self) -> list[str]:
        """Return list of supported MIME types."""
        return ["application/pdf"]

    def get_parser_name(self) -> str:
        """Return parser identifier."""
        return "pymupdf4llm"


class PdfPlumberParser(DocumentParser):
    """
    Fallback PDF parser using PdfPlumber.
    
    More robust but less optimized for LLM consumption.
    Good table extraction capabilities.
    """

    async def parse(self, file_path: Path) -> ParseResult:
        """
        Parse PDF using PdfPlumber to extract text.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            ParseResult with plain text content
            
        Raises:
            ValueError: If file is not a PDF
            RuntimeError: If parsing fails
        """
        if not file_path.suffix.lower() == ".pdf":
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        try:
            pages = []
            
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract text
                    text = page.extract_text() or ""
                    
                    # Extract tables and convert to markdown
                    tables = page.extract_tables()
                    if tables:
                        table_text = self._tables_to_markdown(tables)
                        if text:
                            text += "\n\n" + table_text
                        else:
                            text = table_text
                    
                    # Get page metadata with proper type conversion
                    page_metadata: dict[str, str | int | float] = {
                        "width": float(page.width),
                        "height": float(page.height),
                    }
                    
                    pages.append(
                        PageContent(
                            page_number=page_num,
                            text=text,
                            metadata=page_metadata
                        )
                    )
                
                # Get document metadata
                doc_metadata = pdf.metadata or {}
                
                return ParseResult(
                    pages=pages,
                    total_pages=total_pages,
                    title=doc_metadata.get("Title"),
                    author=doc_metadata.get("Author"),
                    metadata=doc_metadata
                )
                
        except Exception as e:
            raise RuntimeError(f"PdfPlumber parsing failed: {str(e)}") from e

    def _tables_to_markdown(self, tables: list[list[list[str | None]]]) -> str:
        """
        Convert extracted tables to Markdown format.
        
        Args:
            tables: List of tables, where each table is a list of rows
            
        Returns:
            Markdown-formatted table string
        """
        markdown_tables = []
        
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            # First row is header
            header = table[0]
            if not header:
                continue
            
            # Filter out None values and convert to strings
            header = [str(cell) if cell is not None else "" for cell in header]
            
            # Create markdown table
            md_lines = []
            md_lines.append("| " + " | ".join(header) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
            
            # Add data rows
            for row in table[1:]:
                if not row:
                    continue
                row_cells = [str(cell) if cell is not None else "" for cell in row]
                # Pad row if it's shorter than header
                while len(row_cells) < len(header):
                    row_cells.append("")
                md_lines.append("| " + " | ".join(row_cells) + " |")
            
            markdown_tables.append("\n".join(md_lines))
        
        return "\n\n".join(markdown_tables)

    def get_supported_formats(self) -> list[str]:
        """Return list of supported MIME types."""
        return ["application/pdf"]

    def get_parser_name(self) -> str:
        """Return parser identifier."""
        return "pdfplumber"
