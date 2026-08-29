"""
Tests for document_intake.py's text extraction. Builds tiny PDF/DOCX
fixtures in memory at test time (via fpdf2 and python-docx, both already
project dependencies) instead of committing binary fixture files.
"""

import io

from docx import Document as DocxDocument
from fpdf import FPDF

from document_intake import extract_text


def _build_pdf_bytes(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    return bytes(pdf.output())


def _build_docx_bytes(text: str) -> bytes:
    doc = DocxDocument()
    doc.add_paragraph(text)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_extract_text_from_pdf():
    data = _build_pdf_bytes("Scoutly Curated Sourcing overview")
    assert "Scoutly Curated Sourcing overview" in extract_text("overview.pdf", data)


def test_extract_text_from_docx():
    data = _build_docx_bytes("A boutique sourcing service one-pager")
    assert "A boutique sourcing service one-pager" in extract_text("overview.docx", data)


def test_extract_text_from_txt():
    data = b"Plain text product overview"
    assert extract_text("overview.txt", data) == "Plain text product overview"


def test_extract_text_returns_empty_for_unsupported_extension():
    assert extract_text("overview.xyz", b"whatever") == ""


def test_extract_text_caps_length():
    data = ("word " * 5000).encode("utf-8")
    assert len(extract_text("overview.txt", data)) <= 8000
