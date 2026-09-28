"""Shared pytest fixtures.

The deterministic hash-trigram embedder is injected at every import site
(pipeline, retriever, main) so tests never download the ONNX model or touch
the network. The scripted LLM keeps generation offline and deterministic.
"""

from __future__ import annotations

import pytest

from app.embeddings import provider as emb_provider


@pytest.fixture()
def hash_embedder(monkeypatch):
    """Force the deterministic hash-trigram embedder for unit tests."""
    emb_provider.reset_embedder()
    fake = emb_provider.HashTrigramProvider()

    import app.rag.pipeline as rag_pipeline
    import app.retrieval.retriever as retriever_mod

    monkeypatch.setattr(emb_provider, "get_embedder", lambda: fake)
    monkeypatch.setattr(rag_pipeline, "get_embedder", lambda: fake)
    monkeypatch.setattr(retriever_mod, "get_embedder", lambda: fake)
    yield fake
    emb_provider.reset_embedder()


@pytest.fixture()
def api_client(hash_embedder, monkeypatch):
    """TestClient with offline embedder and mock LLM wired into app.main."""
    from fastapi.testclient import TestClient

    from app import main as main_mod
    from app.llm.provider import MockLLMProvider

    monkeypatch.setattr(main_mod, "get_embedder", lambda: hash_embedder)
    monkeypatch.setattr(main_mod, "get_llm_provider", lambda: MockLLMProvider())
    with TestClient(main_mod.app, raise_server_exceptions=False) as client:
        yield client
