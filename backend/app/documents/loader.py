"""Document loading and text extraction for PDF, TXT, and Markdown.

- TXT/MD: decoded as UTF-8 (with a latin-1 fallback), normalized CRLF.
- PDF: page-wise extraction with pypdf; page numbers become chunk metadata.
"""

from __future__ import annotations

import io
import re

from pypdf import PdfReader

from app.documents.cleaning import clean_text

SUPPORTED_EXTENSIONS = {".pdf": "pdf", ".txt": "txt", ".md": "markdown"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB hard ceiling (config also enforces this)


class DocumentError(ValueError):
    """Raised for invalid documents (wrong type, empty, unreadable, too large)."""


def sniff_filetype(filename: str, data: bytes) -> str:
    """Validate extension, magic bytes, and size. Raises DocumentError."""
    lower = (filename or "").lower()
    ext = next((e for e in SUPPORTED_EXTENSIONS if lower.endswith(e)), None)
    if ext is None:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise DocumentError(f"Unsupported file type. Allowed: {allowed}")
    if len(data) == 0:
        raise DocumentError("File is empty (0 bytes).")
    if len(data) > MAX_BYTES:
        raise DocumentError("File exceeds the 10 MB size limit.")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise DocumentError("File has a .pdf extension but is not a valid PDF.")
    return SUPPORTED_EXTENSIONS[ext]


def extract_document(filename: str, data: bytes) -> tuple[str, str, list[int | None]]:
    """Extract cleaned text from raw bytes.

    Returns (clean_text, filetype, per_line_pages) where per_line_pages maps
    each line of the returned text to its page number (PDF) or None.
    """
    filetype = sniff_filetype(filename, data)

    if filetype == "pdf":
        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception as exc:  # corrupt / encrypted PDFs
            raise DocumentError(f"Could not read PDF: {exc}") from exc
        if reader.is_encrypted:
            raise DocumentError("Encrypted PDFs are not supported.")
        pages_out: list[str] = []
        line_pages: list[int | None] = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                raw = page.extract_text() or ""
            except Exception:
                raw = ""
            cleaned = clean_text(raw)
            pages_out.append(cleaned)
            for line in cleaned.splitlines():
                line_pages.append(i)
        text = "\n\n".join(p for p in pages_out if p.strip())
        if not text.strip():
            raise DocumentError(
                "No extractable text found in the PDF (it may be a scanned image). "
                "MedRAG-X does not run OCR."
            )
        return text, filetype, line_pages

    # TXT / Markdown
    try:
        raw = data.decode("utf-8")
    except UnicodeDecodeError:
        raw = data.decode("latin-1", errors="replace")
    text = clean_text(raw)
    if not text.strip():
        raise DocumentError("Document contains no usable text.")
    return text, filetype, None
