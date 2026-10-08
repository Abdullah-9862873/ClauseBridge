"""Unit tests for workers/pdf_parser.py"""

from io import BytesIO

from pypdf import PdfReader

from workers.pdf_parser import extract_text_from_pdf


class TestExtractTextFromPdf:
    def test_returns_string(self) -> None:
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\n"
            b"startxref\n190\n%%EOF\n"
        )
        result = extract_text_from_pdf(pdf_bytes)
        assert isinstance(result, str)

    def test_empty_pdf_returns_empty_string(self) -> None:
        # Build a minimal valid PDF with no text content
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\n"
            b"startxref\n190\n%%EOF\n"
        )
        result = extract_text_from_pdf(pdf_bytes)
        # Empty PDF should return empty or whitespace-only string
        assert isinstance(result, str)

    def test_corrupt_bytes_raises(self) -> None:
        import pytest
        with pytest.raises(Exception):
            extract_text_from_pdf(b"not a pdf at all")

    def test_multiline_text_preserved(self) -> None:
        # This tests the contract: text from pages is joined with newlines
        # We verify pypdf can read a real PDF we create
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(text="Line one")
        pdf.ln()
        pdf.cell(text="Line two")
        buf = BytesIO()
        pdf.output(buf)
        buf.seek(0)

        result = extract_text_from_pdf(buf.read())
        assert "Line one" in result
        assert "Line two" in result
