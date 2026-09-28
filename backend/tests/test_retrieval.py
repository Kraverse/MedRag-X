"""Retrieval tests: relevant chunk retrieval, Top-K, vector store backends."""

from __future__ import annotations

import numpy as np
import pytest

from app.embeddings import provider as emb_provider
from app.retrieval.retriever import Retriever, _lexical_similarity
from app.rag.pipeline import RagPipeline
from app.retrieval.vector_store import _normalize, build_store


class TestVectorStore:
    def test_numpy_backend_matches_faiss(self, hash_embedder):
        rng = np.random.default_rng(42)
        vecs = rng.normal(size=(20, 16)).astype(np.float32)
        ids = [f"doc-c{i}" for i in range(20)]
        faiss_store = build_store(vecs, ids, use_faiss=True)
        numpy_store = build_store(vecs, ids, use_faiss=False)
        q = rng.normal(size=(16,)).astype(np.float32)
        faiss_hits = [m.chunk_id for m in faiss_store.search(q, 5)]
        numpy_hits = [m.chunk_id for m in numpy_store.search(q, 5)]
        assert faiss_hits == numpy_hits

    def test_top_k_respected(self, hash_embedder):
        rng = np.random.default_rng(7)
        vecs = rng.normal(size=(30, 8)).astype(np.float32)
        ids = [f"d-c{i}" for i in range(30)]
        store = build_store(vecs, ids, use_faiss=False)
        hits = store.search(rng.normal(size=(8,)).astype(np.float32), top_k=4)
        assert len(hits) == 4

    def test_scores_sorted_desc(self, hash_embedder):
        rng = np.random.default_rng(3)
        vecs = _normalize(rng.normal(size=(15, 8)).astype(np.float32))
        store = build_store(vecs, [f"d-c{i}" for i in range(15)], use_faiss=False)
        hits = store.search(rng.normal(size=(8,)).astype(np.float32), top_k=5)
        scores = [m.score for m in hits]
        assert scores == sorted(scores, reverse=True)


class TestLexicalBlend:
    def test_identical_text_is_one(self):
        assert _lexical_similarity("sleep duration affects memory", "sleep duration affects memory") > 0.99

    def test_disjoint_text_is_zero(self):
        assert _lexical_similarity("quantum flux capacitor", "sleep study cohort") < 0.01


class TestEndToEndRetrieval:
    def test_relevant_chunk_retrieved(self, hash_embedder):
        pipeline = RagPipeline()
        from app.rag.sessions import SessionStore

        session = SessionStore().create()
        pipeline.ingest_demo(session, "Sleep-Quality-and-Cognition.md")
        assert session.retriever is not None
        evidence = session.retriever.retrieve("How does short sleep affect attention lapses?", top_k=4)
        assert 1 <= len(evidence) <= 4
        top = evidence[0]
        assert top.section in {"Results", "Abstract", "Introduction", "Discussion"}
        combined = " ".join(e.text.lower() for e in evidence)
        assert "attention" in combined
        assert "lapses" in combined or "laps" in combined

    def test_top_k_parameter(self, hash_embedder):
        pipeline = RagPipeline()
        from app.rag.sessions import SessionStore

        session = SessionStore().create()
        pipeline.ingest_demo(session, "Wearable-Heart-Rate-Accuracy.md")
        evidence = session.retriever.retrieve("heart rate accuracy during exercise", top_k=2)
        assert len(evidence) == 2

    def test_citation_format_with_page(self):
        from app.retrieval.retriever import Evidence

        ev = Evidence(
            chunk_id="x-c3",
            document_name="Paper.pdf",
            page=4,
            section=None,
            text="t",
            score=0.5,
            dense_score=0.5,
            lexical_score=0.1,
        )
        assert ev.citation() == "Paper.pdf — Page 4"

    def test_citation_format_without_page(self):
        from app.retrieval.retriever import Evidence

        ev = Evidence(
            chunk_id="paper.md-c12",
            document_name="paper.md",
            page=None,
            section=None,
            text="t",
            score=0.5,
            dense_score=0.5,
            lexical_score=0.1,
        )
        assert ev.citation() == "paper.md — Chunk 12"
