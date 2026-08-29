"""
document_intake.py
--------------------
Extracts plain text from an optionally-uploaded product overview so the
Account Intake Agent can summarize a rep's own document instead of relying
solely on manually-typed fields — the CAP 931 brief's optional "upload a
proprietary internal sheet" input.

Dispatches on file extension to a small per-format helper. Each helper
takes raw bytes (not a file path), so callers can pass a Streamlit
UploadedFile's .getvalue() directly, and tests can build fixtures purely
in memory with no binary files committed to the repo.
"""

from __future__ import annotations

import io

from docx import Document
from pypdf import PdfReader

_MAX_TEXT_CHARS = 8000


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_text(filename: str, data: bytes) -> str:
    """
    Extracts and caps text from an uploaded product-overview file. filename
    is used only to pick the right extractor by extension; unrecognized
    extensions return "" rather than raising, so an unsupported upload
    degrades to "no document context" instead of crashing the research run.
    """
    name = filename.lower()
    if name.endswith(".pdf"):
        text = _extract_pdf_text(data)
    elif name.endswith(".docx"):
        text = _extract_docx_text(data)
    elif name.endswith(".txt"):
        text = data.decode("utf-8", errors="replace")
    else:
        text = ""
    return " ".join(text.split())[:_MAX_TEXT_CHARS]
