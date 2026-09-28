"""RAG pipeline orchestrator.

answer(question, session) = retrieve -> build evidence -> generate -> package.
ingest(name, bytes, session) = validate -> extract -> clean -> chunk -> embed -> index.

Sessions are in-memory (single-instance demo deployment); each holds one
indexed document and short conversational history.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

import numpy as np

from app.documents.chunking import CHUNK_OVERLAP, CHUNK_SIZE, Chunk, chunk_text
from app.documents.demo_documents import DEMO_DOCUMENTS, load_demo_document
from app.documents.loader import DocumentError, extract_document
from app.embeddings.provider import get_embedder
from app.llm.provider import get_llm_provider
from app.retrieval.retriever import Evidence, Retriever
from app.retrieval.vector_store import build_store
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Session:
    session_id: str
    document_name: str | None = None
    document_type: str | None = None
    status: str = "empty"  # empty | processing | ready | error
    chunk_count: int = 0
    error: str | None = None
    chunks_by_id: dict[str, dict] = field(default_factory=dict)
    store: object | None = None
    retriever: Retriever | None = None
    history: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "session_id": self.session_id,
            "document_name": self.document_name,
            "document_type": self.document_type,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "error": self.error,
            "turns": len(self.history) // 2,
        }


class RagPipeline:
    chunk_params = {"chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP}

    # ---------- ingestion ----------

    def ingest_document(self, session: Session, filename: str, data: bytes) -> dict:
        session.status = "processing"
        try:
            text, filetype, line_pages = extract_document(filename, data)
            chunks = self._index_text(session, text, filename, line_pages)
        except DocumentError as exc:
            session.status = "error"
            session.error = str(exc)
            raise
        except Exception as exc:  # unexpected — structured 500
            session.status = "error"
            session.error = f"Processing failed: {exc}"
            logger.exception("Ingest failed")
            raise DocumentError("Failed to process the document. It may be corrupt or unsupported.") from exc
        session.status = "ready"
        session.error = None
        return {
            "document_name": filename,
            "document_type": self._pretty_type(filename),
            "chunk_count": len(chunks),
            "chunk_params": self.chunk_params,
        }

    def ingest_demo(self, session: Session, filename: str | None = None) -> dict:
        filename = filename or next(iter(DEMO_DOCUMENTS))
        if filename not in DEMO_DOCUMENTS:
            raise KeyError(f"Unknown demo document: {filename}")
        text, filetype, line_pages = load_demo_document(filename)
        chunks = self._index_text(session, text, filename, line_pages)
        session.status = "ready"
        return {
            "document_name": filename,
            "document_type": self._pretty_type(filename),
            "chunk_count": len(chunks),
            "chunk_params": self.chunk_params,
        }

    def _index_text(
        self, session: Session, text: str, document_name: str, line_pages: list[int | None] | None
    ) -> list[Chunk]:
        chunks = chunk_text(text, document_name, pages=line_pages)
        if not chunks:
            raise DocumentError("Document produced no usable chunks (too little text).")
        if len(chunks) > settings.max_chunks_per_doc:
            raise DocumentError(
                f"Document is too large for the demo ({len(chunks)} chunks > {settings.max_chunks_per_doc})."
            )
        embedder = get_embedder()
        vectors = embedder.embed([c.text for c in chunks])
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)

        store = build_store(vectors, [c.chunk_id for c in chunks], use_faiss=True)
        chunks_by_id = {c.chunk_id: c.to_dict() for c in chunks}

        session.document_name = document_name
        session.document_type = self._pretty_type(document_name)
        session.chunk_count = len(chunks)
        session.chunks_by_id = chunks_by_id
        session.store = store
        session.retriever = Retriever(store, chunks_by_id)
        session.history = []  # new document resets conversation
        return chunks

    @staticmethod
    def _pretty_type(filename: str) -> str:
        low = filename.lower()
        if low.endswith(".pdf"):
            return "PDF"
        if low.endswith(".md"):
            return "Markdown"
        return "TXT"

    # ---------- answering ----------

    def answer(self, session: Session, question: str, top_k: int | None = None) -> dict:
        if session.status != "ready" or session.retriever is None:
            raise RuntimeError("Session has no processed document.")

        k = top_k or settings.top_k
        evidence: list[Evidence] = session.retriever.retrieve(question, top_k=k)

        # Follow-up context: prepend recent turns so "that" pronouns resolve.
        history_block = ""
        for turn in session.history[-4:]:
            role = "User" if turn["role"] == "user" else "Assistant"
            history_block += f"{role}: {turn['content']}\n"

        provider = get_llm_provider()
        result = provider.generate_answer(
            question, [e.to_dict() for e in evidence], history_block=history_block
        )

        session.history.append({"role": "user", "content": question})
        session.history.append({"role": "assistant", "content": result.answer})

        return {
            "session_id": session.session_id,
            "question": question,
            "answer": result.answer,
            "sources": [e.to_dict() for e in evidence],
            "insufficient_evidence": _looks_insufficient(result.answer, evidence),
            "provider": result.provider,
            "model": result.model,
            "used_fallback": result.used_fallback,
            "latency_ms": result.latency_ms,
            "debug": {
                "embedding_model": get_embedder().name,
                "embedding_backend": type(get_embedder()).__name__,
                "vector_backend": getattr(session.store, "backend", "unknown"),
                "top_k": k,
                "retrieved_count": len(evidence),
                "scores": [
                    {
                        "chunk_id": e.chunk_id,
                        "final": e.score,
                        "dense": e.dense_score,
                        "lexical": e.lexical_score,
                    }
                    for e in evidence
                ],
                "context_sent_to_llm": result.raw_context,
                "prompt_chars": result.prompt_chars,
                "conversation_history": session.history[-8:],
            },
        }


def _looks_insufficient(answer: str, evidence: list[Evidence]) -> bool:
    from app.llm.provider import INSUFFICIENT_PHRASES

    low = answer.lower()
    if any(p in low for p in INSUFFICIENT_PHRASES):
        return True
    # Empty/absent retrieval is insufficiency by definition.
    return len(evidence) == 0


def new_session() -> Session:
    return Session(session_id=str(uuid.uuid4()))
