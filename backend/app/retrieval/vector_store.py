"""Vector store: FAISS IndexFlatIP when available, pure-NumPy cosine fallback.

Documents and queries are embedded with the same model; both paths L2-normalize
vectors so inner product == cosine similarity. The chosen backend is reported
in diagnostics ("faiss" or "numpy").
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VectorMatch:
    chunk_id: str
    score: float


@dataclass
class VectorStore:
    dim: int
    backend: str = "numpy"  # "faiss" or "numpy"
    _ids: list[str] = field(default_factory=list)
    _matrix: np.ndarray | None = None
    _faiss_index: object = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, ids: list[str], vectors: np.ndarray) -> None:
        if len(ids) != vectors.shape[0]:
            raise ValueError("ids and vectors length mismatch")
        vectors = _normalize(vectors)
        with self._lock:
            if self.backend == "faiss":
                self._faiss_index.add(vectors)
            else:
                if self._matrix is None:
                    self._matrix = vectors
                else:
                    self._matrix = np.vstack([self._matrix, vectors])
            self._ids.extend(ids)
            self._count = len(self._ids)

    def search(self, query_vec: np.ndarray, top_k: int) -> list[VectorMatch]:
        if not self._ids:
            return []
        q = _normalize(query_vec.reshape(1, -1))
        with self._lock:
            k = min(top_k, len(self._ids))
            if self.backend == "faiss":
                scores, idxs = self._faiss_index.search(q, k)
                pairs = list(zip(idxs[0].tolist(), scores[0].tolist()))
            else:
                sims = (self._matrix @ q.T).ravel()
                top = np.argsort(sims)[::-1][:k]
                pairs = [(int(i), float(sims[i])) for i in top]
        return [VectorMatch(chunk_id=self._ids[i], score=round(float(s), 4)) for i, s in pairs if i >= 0]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def build_store(vectors: np.ndarray, ids: list[str], use_faiss: bool = True) -> VectorStore:
    """Create a store and index the given vectors/ids in one step."""
    dim = int(vectors.shape[1])
    if use_faiss:
        try:
            import faiss  # type: ignore

            index = faiss.IndexFlatIP(dim)
            store = VectorStore(dim=dim, backend="faiss", _faiss_index=index)
            store.add(ids, vectors)
            return store
        except Exception as exc:
            logger.warning("FAISS unavailable (%s); using NumPy cosine fallback", exc)
    store = VectorStore(dim=dim, backend="numpy")
    store.add(ids, vectors)
    return store
