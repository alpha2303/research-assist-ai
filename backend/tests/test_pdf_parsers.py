"""Unit tests for PDF parsers."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.interfaces.document_parser import ParseResult
from app.implementations.pdf_parsers import PdfPlumberParser, PyMuPDF4LLMParser


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create sample PDF file path."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\nTest content")
    return pdf_file


class TestPyMuPDF4LLMParser:
    """Test cases for PyMuPDF4LLMParser."""

    def _mock_pymupdf_doc(self, page_count=1, metadata=None):
        """Create a mock pymupdf document with configurable page_count."""
        doc = MagicMock()
        doc.page_count = page_count
        doc.metadata = metadata or {}
        doc.close = MagicMock()
        return doc

    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = PyMuPDF4LLMParser()
        assert parser is not None

    @patch('app.implementations.pdf_parsers.pymupdf4llm')
    @pytest.mark.asyncio
    async def test_parse_simple_pdf_list_return(self, mock_pymupdf4llm, sample_pdf_path):
        """Test parsing PDF when page_chunks=True returns list."""
        mock_pymupdf4llm.to_markdown.return_value = [
            {"metadata": {"page": 0}, "text": "# Document Title\n\nThis is content."}
        ]

        with patch('app.implementations.pdf_parsers.pymupdf') as mock_pymupdf:
            mock_pymupdf.open.return_value = self._mock_pymupdf_doc(page_count=1)
            parser = PyMuPDF4LLMParser()
            result = await parser.parse(sample_pdf_path)

        assert isinstance(result, ParseResult)
        assert len(result.pages) == 1
        assert result.pages[0].text == "# Document Title\n\nThis is content."
        assert result.pages[0].page_number == 1
        assert result.total_pages == 1

    @patch('app.implementations.pdf_parsers.pymupdf4llm')
    @pytest.mark.asyncio
    async def test_parse_multipage_pdf(self, mock_pymupdf4llm, sample_pdf_path):
        """Test parsing multi-page PDF with per-page chunks."""
        mock_pymupdf4llm.to_markdown.return_value = [
            {"metadata": {"page": 0}, "text": "Page 1 content"},
            {"metadata": {"page": 1}, "text": "Page 2 content"},
            {"metadata": {"page": 2}, "text": "Page 3 content"},
        ]

        with patch('app.implementations.pdf_parsers.pymupdf') as mock_pymupdf:
            mock_pymupdf.open.return_value = self._mock_pymupdf_doc(page_count=3)
            parser = PyMuPDF4LLMParser()
            result = await parser.parse(sample_pdf_path)

        assert isinstance(result, ParseResult)
        assert result.total_pages == 3
        assert len(result.pages) == 3
        for i, page in enumerate(result.pages):
            assert page.page_number == i + 1
            assert f"Page {i+1} content" in page.text

    @patch('app.implementations.pdf_parsers.pymupdf4llm')
    @pytest.mark.asyncio
    async def test_parse_with_metadata(self, mock_pymupdf4llm, sample_pdf_path):
        """Test parsing preserves document metadata."""
        mock_pymupdf4llm.to_markdown.return_value = [
            {"metadata": {"page": 0}, "text": "Content"}
        ]

        doc_meta = {"title": "Test Document", "author": "Test Author"}
        with patch('app.implementations.pdf_parsers.pymupdf') as mock_pymupdf:
            mock_pymupdf.open.return_value = self._mock_pymupdf_doc(page_count=10, metadata=doc_meta)
            parser = PyMuPDF4LLMParser()
            result = await parser.parse(sample_pdf_path)

        assert result.title == "Test Document"
        assert result.author == "Test Author"
        assert result.total_pages == 10
        assert result.pages[0].metadata is not None
        assert "format" in result.pages[0].metadata

    @patch('app.implementations.pdf_parsers.pymupdf4llm')
    @pytest.mark.asyncio
    async def test_parse_error_handling(self, mock_pymupdf4llm, sample_pdf_path):
        """Test error handling during parsing."""
        mock_pymupdf4llm.to_markdown.side_effect = Exception("PDF parsing error")

        parser = PyMuPDF4LLMParser()

        with pytest.raises(RuntimeError):
            await parser.parse(sample_pdf_path)

    @patch('app.implementations.pdf_parsers.pymupdf4llm')
    @pytest.mark.asyncio
    async def test_parse_empty_pdf(self, mock_pymupdf4llm, sample_pdf_path):
        """Test parsing empty PDF (no text in chunks)."""
        mock_pymupdf4llm.to_markdown.return_value = [
            {"metadata": {"page": 0}, "text": ""}
        ]

        with patch('app.implementations.pdf_parsers.pymupdf') as mock_pymupdf:
            mock_pymupdf.open.return_value = self._mock_pymupdf_doc(page_count=1)
            parser = PyMuPDF4LLMParser()
            result = await parser.parse(sample_pdf_path)

        assert isinstance(result, ParseResult)

    @patch('app.implementations.pdf_parsers.pymupdf4llm')
    @pytest.mark.asyncio
    async def test_parse_fallback_string_return(self, mock_pymupdf4llm, sample_pdf_path):
        """Test fallback when to_markdown returns a plain string instead of list."""
        mock_pymupdf4llm.to_markdown.return_value = "Fallback content"

        with patch('app.implementations.pdf_parsers.pymupdf') as mock_pymupdf:
            mock_pymupdf.open.return_value = self._mock_pymupdf_doc(page_count=2)
            parser = PyMuPDF4LLMParser()
            result = await parser.parse(sample_pdf_path)

        assert isinstance(result, ParseResult)
        assert len(result.pages) == 1
        assert result.pages[0].text == "Fallback content"
        assert result.total_pages == 2

    @patch('app.implementations.pdf_parsers.pymupdf4llm')
    @pytest.mark.asyncio
    async def test_parse_skips_blank_pages(self, mock_pymupdf4llm, sample_pdf_path):
        """Test that blank pages are skipped."""
        mock_pymupdf4llm.to_markdown.return_value = [
            {"metadata": {"page": 0}, "text": "Real content"},
            {"metadata": {"page": 1}, "text": "   "},
            {"metadata": {"page": 2}, "text": "More content"},
        ]

        with patch('app.implementations.pdf_parsers.pymupdf') as mock_pymupdf:
            mock_pymupdf.open.return_value = self._mock_pymupdf_doc(page_count=3)
            parser = PyMuPDF4LLMParser()
            result = await parser.parse(sample_pdf_path)

        assert result.total_pages == 3
        assert len(result.pages) == 2  # blank page skipped


class TestPdfPlumberParser:
    """Test cases for PdfPlumberParser."""

    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = PdfPlumberParser()
        assert parser is not None

    @patch('app.implementations.pdf_parsers.pdfplumber')
    @pytest.mark.asyncio
    async def test_parse_simple_pdf(self, mock_pdfplumber, sample_pdf_path):
        """Test parsing simple PDF."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_page.extract_tables.return_value = []
        mock_page.width = 612
        mock_page.height = 792
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        parser = PdfPlumberParser()
        result = await parser.parse(sample_pdf_path)

        assert isinstance(result, ParseResult)
        assert len(result.pages) == 1
        assert result.pages[0].text == "Page 1 content"
        assert result.pages[0].page_number == 1
        assert result.total_pages == 1

    @patch('app.implementations.pdf_parsers.pdfplumber')
    @pytest.mark.asyncio
    async def test_parse_multipage_pdf(self, mock_pdfplumber, sample_pdf_path):
        """Test parsing multi-page PDF."""
        mock_pdf = MagicMock()
        mock_pages = []
        for i in range(3):
            mock_page = MagicMock()
            mock_page.extract_text.return_value = f"Page {i+1} content"
            mock_page.extract_tables.return_value = []
            mock_page.width = 612
            mock_page.height = 792
            mock_pages.append(mock_page)
        mock_pdf.pages = mock_pages
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        parser = PdfPlumberParser()
        result = await parser.parse(sample_pdf_path)

        assert len(result.pages) == 3
        assert result.total_pages == 3
        for i, page in enumerate(result.pages):
            assert page.page_number == i + 1

    @patch('app.implementations.pdf_parsers.pdfplumber')
    @pytest.mark.asyncio
    async def test_parse_pdf_with_tables(self, mock_pdfplumber, sample_pdf_path):
        """Test parsing PDF with tables."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Text content"
        mock_page.extract_tables.return_value = [
            [["Header1", "Header2"], ["Row1Col1", "Row1Col2"]]
        ]
        mock_page.width = 612
        mock_page.height = 792
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        parser = PdfPlumberParser()
        result = await parser.parse(sample_pdf_path)

        assert "Header1" in result.pages[0].text or "Header2" in result.pages[0].text

    @patch('app.implementations.pdf_parsers.pdfplumber')
    @pytest.mark.asyncio
    async def test_parse_empty_page(self, mock_pdfplumber, sample_pdf_path):
        """Test parsing page with no extractable text."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_page.extract_tables.return_value = []
        mock_page.width = 612
        mock_page.height = 792
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        parser = PdfPlumberParser()
        result = await parser.parse(sample_pdf_path)

        assert len(result.pages) == 1

    @patch('app.implementations.pdf_parsers.pdfplumber')
    @pytest.mark.asyncio
    async def test_parse_with_metadata(self, mock_pdfplumber, sample_pdf_path):
        """Test parsing includes page metadata."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Content"
        mock_page.extract_tables.return_value = []
        mock_page.width = 612.0
        mock_page.height = 792.0
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        parser = PdfPlumberParser()
        result = await parser.parse(sample_pdf_path)

        page = result.pages[0]
        assert page.metadata is not None
        assert "width" in page.metadata
        assert "height" in page.metadata
        assert page.metadata["width"] == 612.0
        assert page.metadata["height"] == 792.0

    @patch('app.implementations.pdf_parsers.pdfplumber')
    @pytest.mark.asyncio
    async def test_parse_error_handling(self, mock_pdfplumber, sample_pdf_path):
        """Test error handling during parsing."""
        mock_pdfplumber.open.side_effect = Exception("Cannot open PDF")

        parser = PdfPlumberParser()

        with pytest.raises(RuntimeError):
            await parser.parse(sample_pdf_path)

    @patch('app.implementations.pdf_parsers.pdfplumber')
    @pytest.mark.asyncio
    async def test_tables_to_markdown_conversion(self, mock_pdfplumber, sample_pdf_path):
        """Test table to markdown conversion."""
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_page.extract_tables.return_value = [
            [["Name", "Age"], ["Alice", "25"], ["Bob", "30"]]
        ]
        mock_page.width = 612
        mock_page.height = 792
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        parser = PdfPlumberParser()
        result = await parser.parse(sample_pdf_path)

        text = result.pages[0].text
        assert "Name" in text
        assert "Age" in text
        assert "|" in text

    def test_compare_parsers_interface(self):
        """Test that both parsers implement the same interface."""
        parser1 = PyMuPDF4LLMParser()
        parser2 = PdfPlumberParser()

        assert hasattr(parser1, 'parse')
        assert hasattr(parser2, 'parse')
        assert callable(parser1.parse)
        assert callable(parser2.parse)
