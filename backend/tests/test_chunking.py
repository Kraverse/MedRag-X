"""Chunking tests: creation, overlap, metadata preservation."""

from __future__ import annotations

from app.documents.chunking import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MIN_CHUNK,
    chunk_text,
)


def make_document(paragraphs: int, sentences_per_para: int = 5) -> str:
    sentence = (
        "Simulated participants completed modeled cognitive assessments while wrist sensors "
        "recorded synthetic activity counts for the demonstration dataset. "
    )
    paras = []
    for p in range(paragraphs):
        body = sentence * sentences_per_para
        paras.append(f"## Section {p + 1}\n\n{body.strip()}")
    return "\n\n".join(paras)


class TestChunkCreation:
    def test_empty_text_gives_no_chunks(self):
        assert chunk_text("", "doc.md") == []
        assert chunk_text("   \n\n  ", "doc.md") == []

    def test_short_text_single_chunk(self):
        chunks = chunk_text("A short demo paragraph about synthetic sleep data.", "doc.md")
        assert len(chunks) == 1
        assert chunks[0].text.strip() == "A short demo paragraph about synthetic sleep data."

    def test_long_text_multiple_chunks(self):
        text = make_document(paragraphs=6)
        chunks = chunk_text(text, "doc.md")
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.text) <= CHUNK_SIZE + MIN_CHUNK + CHUNK_OVERLAP + 50

    def test_no_chunk_mid_word(self):
        text = ("Supercalifragilistic word. " * 100).strip()
        chunks = chunk_text(text, "doc.md")
        for c in chunks:
            assert "Supercalifragilistic" in c.text  # never split inside the word

    def test_overlap_between_consecutive_chunks(self):
        text = make_document(paragraphs=6)
        chunks = chunk_text(text, "doc.md")
        for a, b in zip(chunks, chunks[1:]):
            tail_a = a.text[-CHUNK_OVERLAP:]
            assert any(w in b.text[: CHUNK_OVERLAP + 150] for w in tail_a.split()[:6])

    def test_deterministic_chunk_ids(self):
        text = make_document(paragraphs=3)
        c1 = chunk_text(text, "paper.md")
        c2 = chunk_text(text, "paper.md")
        assert [c.chunk_id for c in c1] == [c.chunk_id for c in c2]
        assert c1[0].chunk_id == "paper.md-c0"


class TestMetadata:
    def test_document_name_preserved(self):
        chunks = chunk_text("Some demonstration content for metadata checks.", "Study.md")
        assert all(c.document_name == "Study.md" for c in chunks)

    def test_section_tracking(self):
        text = "## Introduction\n\nBody sentence one about synthetic trials. Body sentence two.\n\n## Results\n\nResults body sentence with more demonstration content follows here now."
        chunks = chunk_text(text, "doc.md")
        sections = {c.section for c in chunks}
        assert "Introduction" in sections or "Results" in sections

    def test_page_metadata_propagates(self):
        # 5 text lines (incl. the blank separator) -> 5 page entries, mirroring
        # the per-line page map produced by the PDF extractor. Small chunk_size
        # forces each paragraph into its own chunk.
        text = (
            "First page sentence about wearables.\nFollow-up line stays on page three."
            "\n\nSecond page sentence about sensors.\nAnother line on page four."
        )
        pages = [3, 3, None, 4, 4]
        chunks = chunk_text(text, "paper.pdf", pages=pages, chunk_size=80, chunk_overlap=20)
        assert any(c.page == 3 for c in chunks)
        assert any(c.page == 4 for c in chunks)

    def test_tiny_fragment_merged(self):
        text = "A " * 200 + "\n\nend."
        chunks = chunk_text(text, "doc.md")
        assert all(len(c.text) >= MIN_CHUNK for c in chunks)
