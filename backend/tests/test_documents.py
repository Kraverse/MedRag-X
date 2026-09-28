"""Document processing tests: validation, extraction, cleaning."""

from __future__ import annotations

import pytest

from app.documents.cleaning import clean_text, paragraph_is_useful
from app.documents.loader import DocumentError, extract_document, sniff_filetype


def make_pdf(pages: list[str]) -> bytes:
    """Build a tiny valid multi-page PDF with correct xref offsets."""
    header = b"%PDF-1.4\n"
    parts: list[bytes] = []
    running = 0
    offsets: dict[int, int] = {}

    def add_object(obj_id: int, payload: bytes) -> None:
        nonlocal running
        offsets[obj_id] = len(header) + running
        chunk = f"{obj_id} 0 obj\n".encode() + payload + b"\nendobj\n"
        parts.append(chunk)
        running += len(chunk)

    content_ids: list[int] = []
    page_ids: list[int] = []

    # Object layout: 1=Catalog, 2=Pages, 3=Font, then alternating content/page objects.
    next_id = 4
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
        cid = next_id
        content_ids.append(cid)
        next_id += 1
        pid = next_id
        page_ids.append(pid)
        next_id += 1

    # Catalog, Pages, Font
    add_object(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    add_object(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    add_object(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # Content + page objects
    for text, cid, pid in zip(pages, content_ids, page_ids):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
        add_object(cid, f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        add_object(
            pid,
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {cid} 0 R "
                f"/Resources << /Font << /F1 3 0 R >> >> >>"
            ).encode(),
        )

    body = b"".join(parts)
    total = 3 + 2 * len(pages) + 1
    xref_start = len(header) + len(body)
    xref = f"xref\n0 {total}\n0000000000 65535 f \n".encode()
    for obj_id in range(1, total):
        xref += f"{offsets[obj_id]:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode()
    return header + body + xref + trailer


class TestValidation:
    def test_rejects_unsupported_extension(self):
        with pytest.raises(DocumentError, match="Unsupported file type"):
            sniff_filetype("report.docx", b"some data")

    def test_rejects_empty_file(self):
        with pytest.raises(DocumentError, match="empty"):
            sniff_filetype("notes.txt", b"")

    def test_rejects_oversized_file(self):
        with pytest.raises(DocumentError, match="10 MB"):
            sniff_filetype("big.pdf", b"x" * (10 * 1024 * 1024 + 1))

    def test_rejects_fake_pdf(self):
        with pytest.raises(DocumentError, match="not a valid PDF"):
            sniff_filetype("fake.pdf", b"definitely not a pdf header")


class TestExtraction:
    def test_txt_roundtrip(self):
        text, ftype, pages = extract_document("notes.txt", "Hello world".encode())
        assert text == "Hello world"
        assert ftype == "txt"
        assert pages is None

    def test_md_normalizes_headings(self):
        text, ftype, _ = extract_document("doc.md", "# Title\n\nBody text here.".encode())
        assert ftype == "markdown"
        assert "## Title" in text

    def test_pdf_multi_page(self):
        pdf = make_pdf(["Page one text about sleep.", "Page two text about memory."])
        text, ftype, pages = extract_document("paper.pdf", pdf)
        assert ftype == "pdf"
        assert "Page one text" in text
        assert "Page two text" in text
        assert pages is not None and len(pages) > 0

    def test_empty_txt_raises(self):
        with pytest.raises(DocumentError, match="no usable text"):
            extract_document("empty.txt", b"   \n\n  ")

    def test_corrupt_pdf_raises(self):
        with pytest.raises(DocumentError):
            extract_document("corrupt.pdf", b"%PDF-1.4 garbage bytes")

    def test_encrypted_pdf_rejected(self):
        # pypdf marks this trivial header-only buffer as non-readable; both
        # paths (encryption error / read error) must raise DocumentError.
        with pytest.raises(DocumentError):
            extract_document("enc.pdf", b"%PDF-1.4\n%%EOF")


class TestCleaning:
    def test_dehyphenation(self):
        assert "example" in clean_text("exam-\nple word")

    def test_whitespace_collapse(self):
        out = clean_text("Hello\n\n\nworld   spaced\t\ttext")
        assert "Hello" in out and "world spaced text" in out

    def test_control_chars_removed(self):
        out = clean_text("a\x00b\x0cc")
        assert "\x00" not in out and "\x0c" not in out

    def test_useful_filter(self):
        assert paragraph_is_useful("A real sentence about sleep science continues here.")
        assert not paragraph_is_useful("## Intro")
        assert not paragraph_is_useful("12345")
