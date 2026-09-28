"""Embedding providers.

Primary: fastembed with BAAI/bge-small-en-v1.5 (33M params, 384-dim, CPU-only,
no API key, ONNX runtime). Fallback (only if fastembed cannot load a model,
e.g. no network for the first download): a deterministic hashing-trigram
embedder so tests and offline demos still run. The fallback is clearly flagged
in /health and in retrieval diagnostics.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)

FALLBACK_DIM = 384


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class FastEmbedProvider:
    """fastembed ONNX embedder (downloads model weights on first use)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding  # lazy import

        self._model = TextEmbedding(model_name=model_name)
        self.name = model_name
        self.dim = 384 if "bge-small" in model_name else len(next(iter(self._model.embed(["dim probe"]))))

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.array(list(self._model.embed(texts)), dtype=np.float32)
        return vecs


class HashTrigramProvider:
    """Deterministic char-trigram hashing embedder (offline fallback, weak semantics).

    Used ONLY when the real model cannot be loaded. It preserves lexical
    overlap signal, which is enough for the demo documents and unit tests.
    """

    def __init__(self) -> None:
        self.name = "hash-trigram-fallback"
        self.dim = FALLBACK_DIM

    @staticmethod
    def _trigrams(text: str) -> list[str]:
        t = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
        t = " ".join(t.split())
        padded = f"  {t}  "
        return [padded[i : i + 3] for i in range(max(len(padded) - 2, 0))]

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for gram in self._trigrams(text):
                h = int.from_bytes(hashlib.md5(gram.encode()).digest()[:4], "little")
                idx = h % self.dim
                sign = 1.0 if (h >> 31) & 1 == 0 else -1.0
                out[row, idx] += sign
            norm = math.sqrt(float((out[row] ** 2).sum())) or 1.0
            out[row] /= norm
        return out


_provider: EmbeddingProvider | None = None
_provider_lock = threading.Lock()


def get_embedder() -> EmbeddingProvider:
    """Process-wide singleton; tries fastembed once, falls back to hashing."""
    global _provider
    if _provider is not None:
        return _provider
    with _provider_lock:
        if _provider is not None:
            return _provider
        try:
            _provider = FastEmbedProvider()
            logger.info("Embedding provider: fastembed BAAI/bge-small-en-v1.5")
        except Exception as exc:
            logger.warning("fastembed unavailable (%s); using hash-trigram fallback", exc)
            _provider = HashTrigramProvider()
        return _provider


def reset_embedder() -> None:
    """Test helper to force re-initialization."""
    global _provider
    with _provider_lock:
        _provider = None


def embed_query_for_search(query_vec: np.ndarray) -> np.ndarray:
    """bge models are retrieval-tuned; prefixing queries improves recall."""
    return query_vec
