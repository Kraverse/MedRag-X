"""Text cleaning utilities applied after extraction and before chunking."""

from __future__ import annotations

import re
import unicodedata

_HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")


def _lift_headings(para: str) -> str:
    """Within one paragraph block, put short markdown headings on their own
    line and join the remaining soft-wrapped body lines into a single blob."""
    out_lines: list[str] = []
    body: list[str] = []

    def flush_body() -> None:
        if body:
            blob = " ".join(part.strip() for part in body if part.strip())
            blob = re.sub(r"[ ]{2,}", " ", blob).strip()
            if blob:
                out_lines.append(blob)
            body.clear()

    for line in para.splitlines():
        m = _HEADING_RE.match(line.strip())
        if m and len(m.group(2)) <= 80:
            flush_body()
            out_lines.append(f"## {m.group(2)}")
        else:
            body.append(line)
    flush_body()
    return "\n".join(out_lines)


def clean_text(text: str) -> str:
    """Normalize and lightly clean extracted text.

    Steps (in order):
    1. Unicode NFKC normalization (fixes ligatures, odd spaces from PDFs).
    2. Strip control characters except tab/newline.
    3. Join words broken by hyphenated line wraps: "exam-\\nple" -> "example".
    4. Split paragraphs on blank lines; within each paragraph, lift short
       markdown headings onto their own line (so chunking records them as
       section metadata) and join soft-wrapped body lines.
    5. Collapse repeated whitespace.
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    # Remove control chars except \n and \t
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or not unicodedata.category(ch).startswith("C"))

    # De-hyphenate line-wrapped words: "exam-\nple" -> "example"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    cleaned_paragraphs: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = _lift_headings(para.replace("\t", " "))
        if para.strip():
            cleaned_paragraphs.append(para.strip())

    return "\n\n".join(cleaned_paragraphs)


def paragraph_is_useful(para: str) -> bool:
    """Filter headings-only fragments and obvious boilerplate."""
    stripped = para.strip()
    if not stripped:
        return False
    # A lone heading gives retrieval nothing to match; keep it attached to body text instead.
    if stripped.startswith("## ") and len(stripped) < 80:
        return False
    alpha = sum(ch.isalpha() for ch in stripped)
    if len(stripped) < 3:
        return False
    if alpha / max(len(stripped), 1) < 0.2:  # mostly numbers/punct (page numbers, lines)
        return False
    return True
