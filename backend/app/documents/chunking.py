"""Text chunking with overlap and section metadata.

Chosen values (documented and measured in RAG_DOCUMENTATION.md /
RAG_EVALUATION.md):

- CHUNK_SIZE    = 1200 characters (~250-300 tokens) target size
- CHUNK_OVERLAP = 200 characters so sentences straddling a boundary stay
                  retrievable from at least one chunk
- MIN_CHUNK     = 120 characters; smaller trailing fragments are merged into
                  the previous chunk

Chunks split on sentence boundaries where possible (never mid-word), and each
chunk carries: document name, page number (when known), section heading, and a
deterministic chunk ID "{doc}-c{index}".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
MIN_CHUNK = 120

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    chunk_id: str
    text: str
    document_name: str
    page: int | None
    section: str | None
    index: int
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "document_name": self.document_name,
            "page": self.page,
            "section": self.section,
            "index": self.index,
            "char_count": self.char_count,
        }


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_END.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _emit_chunk(buffer: str, doc: str, page: int | None, section: str | None, index: int) -> Chunk:
    return Chunk(
        chunk_id=f"{doc}-c{index}",
        text=buffer.strip(),
        document_name=doc,
        page=page,
        section=section,
        index=index,
    )


def chunk_text(
    text: str,
    document_name: str,
    pages: list[int] | None = None,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """Chunk cleaned text into overlapping pieces with sentence-boundary splits.

    `pages` optionally supplies a page number per input line (used by the PDF
    extractor). Chunks inherit the page of their first sentence.
    """
    if not text or not text.strip():
        return []

    if pages is None:
        pages = [None] * len(text.splitlines())

    # Walk paragraphs, tracking the page each paragraph starts on.
    # The joined text has ONE blank line between paragraphs (split on \n\n),
    # so advancing the offset needs para lines + 1 for that separator.
    paragraphs: list[tuple[str, int | None]] = []
    offset = 0
    for para in text.split("\n\n"):
        para_pages = pages[offset : offset + para.count("\n") + 1]
        page = next((p for p in para_pages if p is not None), None)
        paragraphs.append((para.strip(), page))
        offset += para.count("\n") + 2  # +1 line for the blank separator

    chunks: list[Chunk] = []
    buffer = ""
    buffer_page: int | None = None
    section: str | None = None
    index = 0

    def flush() -> None:
        nonlocal buffer, index
        if not buffer.strip():
            return
        min_chunk = min(MIN_CHUNK, max(chunk_size // 4, 1))
        if len(buffer.strip()) < min_chunk and chunks:
            # Merge tiny trailing fragment into the previous chunk.
            prev = chunks[-1]
            merged = (prev.text + "\n\n" + buffer.strip()).strip()
            if len(merged) <= chunk_size + MIN_CHUNK:
                chunks[-1] = Chunk(
                    chunk_id=prev.chunk_id,
                    text=merged,
                    document_name=prev.document_name,
                    page=prev.page,
                    section=prev.section,
                    index=prev.index,
                )
                buffer = ""
                return
        chunks.append(_emit_chunk(buffer, document_name, buffer_page, section, index))
        index += 1
        buffer = ""

    for para, page in paragraphs:
        for line in (ln.strip() for ln in para.split("\n")):
            if not line:
                continue
            if line.startswith("## "):
                section = line[3:].strip()
                continue
            for sentence in _split_sentences(line) or [line]:
                candidate = f"{buffer} {sentence}".strip() if buffer else sentence
                if len(candidate) <= chunk_size:
                    buffer = candidate
                    if buffer_page is None:
                        buffer_page = page
                    continue
                # Sentence does not fit: flush current buffer, carry an overlap
                # tail of the previous chunk into the new one.
                prev_tail = buffer[-chunk_overlap:] if buffer and chunk_overlap else ""
                flush()
                buffer = f"{prev_tail} {sentence}".strip() if prev_tail else sentence
                buffer_page = page
                # Very long single sentence: hard-split it.
                while len(buffer) > chunk_size:
                    chunks.append(_emit_chunk(buffer[:chunk_size], document_name, page, section, index))
                    index += 1
                    buffer = buffer[chunk_size - chunk_overlap :] if chunk_overlap else buffer[chunk_size:]
    flush()

    return chunks
