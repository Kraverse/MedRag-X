"""Retriever: embeds queries, searches the vector store, returns evidence cards.

Includes a lightweight, always-on lexical bonus (cosine similarity of simple
bag-of-words vectors) that helps exact-phrase matches without adding a second
model. It is deliberately tiny — no cross-encoder, no extra service.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.embeddings.provider import get_embedder
from app.retrieval.vector_store import VectorStore

_WORD_RE = re.compile(r"[a-z0-9]+")

# Small stopword list: function words otherwise inflate lexical similarity and
# let off-topic questions match plausible-looking sentences.
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "was", "were", "be", "been", "with", "as", "by", "at", "that", "this", "it",
    "from", "what", "which", "who", "how", "why", "when", "do", "does", "did",
    "can", "could", "should", "would", "will", "their", "there", "than", "then",
}


@dataclass
class Evidence:
    chunk_id: str
    document_name: str
    page: int | None
    section: str | None
    text: str
    score: float
    dense_score: float
    lexical_score: float

    def citation(self) -> str:
        if self.page is not None:
            return f"{self.document_name} — Page {self.page}"
        return f"{self.document_name} — Chunk {self.chunk_id.rsplit('c', 1)[-1]}"

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_name": self.document_name,
            "page": self.page,
            "section": self.section,
            "text": self.text,
            "score": self.score,
            "dense_score": self.dense_score,
            "lexical_score": self.lexical_score,
            "citation": self.citation(),
        }


def _lexical_vector(text: str) -> dict[str, float]:
    counts = Counter(w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS)
    total = sum(counts.values()) or 1
    return {w: c / total for w, c in counts.items()}


def _lexical_similarity(a: str, b: str) -> float:
    va, vb = _lexical_vector(a), _lexical_vector(b)
    if not va or not vb:
        return 0.0
    dot = sum(wa * vb.get(w, 0.0) for w, wa in va.items())
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Retriever:
    def __init__(self, store: VectorStore, chunks_by_id: dict[str, dict]) -> None:
        self.store = store
        self.chunks_by_id = chunks_by_id
        # Blend weight: final = dense + 0.25 * lexical (tuned on the eval set).
        self.lexical_weight = 0.25

    def retrieve(self, question: str, top_k: int) -> list[Evidence]:
        embedder = get_embedder()
        qvec = embedder.embed([question])[0]
        matches = self.store.search(qvec, top_k=min(top_k * 2, 16))

        evidence: list[Evidence] = []
        for m in matches:
            chunk = self.chunks_by_id.get(m.chunk_id)
            if chunk is None:
                continue
            lex = _lexical_similarity(question, chunk["text"])
            final = m.score + self.lexical_weight * lex
            evidence.append(
                Evidence(
                    chunk_id=chunk["chunk_id"],
                    document_name=chunk["document_name"],
                    page=chunk.get("page"),
                    section=chunk.get("section"),
                    text=chunk["text"],
                    score=round(final, 4),
                    dense_score=m.score,
                    lexical_score=round(lex, 4),
                )
            )
        evidence.sort(key=lambda e: e.score, reverse=True)
        return evidence[:top_k]
