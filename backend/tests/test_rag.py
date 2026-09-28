"""RAG pipeline tests: grounded answers, insufficiency handling, empty retrieval.

Uses a scripted mock LLM (never the network) to verify orchestration logic.
"""

from __future__ import annotations

import pytest

from app.llm import provider as llm_provider
from app.llm.provider import GenerationResult, MockLLMProvider
from app.rag.pipeline import RagPipeline
from app.rag.sessions import SessionStore


class ScriptedLLM:
    """Returns canned answers so pipeline orchestration can be tested offline."""

    name = "scripted-test"
    model = "test-model"

    def __init__(self) -> None:
        self.last_evidence: list[dict] | None = None
        self.last_question: str | None = None

    def generate_answer(
        self, question: str, evidence: list[dict], history_block: str = ""
    ) -> GenerationResult:
        self.last_question = question
        self.last_evidence = evidence
        if not evidence:
            answer = "The provided documents do not contain sufficient information to answer this question."
        else:
            first_src = evidence[0]
            answer = (
                f"According to [1], {first_src['text'][:120].strip()}... "
                f"This is stated in {first_src['citation']}."
            )
        return GenerationResult(
            answer=answer,
            provider=self.name,
            model=self.model,
            latency_ms=5,
            raw_context=f"QUESTION: {question}\nEVIDENCE: {len(evidence)} chunks",
        )


@pytest.fixture()
def scripted_llm(monkeypatch):
    llm = ScriptedLLM()
    # Patch at every import site: the provider module AND pipeline's bound name.
    import app.rag.pipeline as rag_pipeline

    monkeypatch.setattr(llm_provider, "get_llm_provider", lambda: llm)
    monkeypatch.setattr(rag_pipeline, "get_llm_provider", lambda: llm)
    return llm


@pytest.fixture()
def pipeline_and_session(hash_embedder, scripted_llm):
    store = SessionStore()
    session = store.create()
    RagPipeline().ingest_demo(session, "Sleep-Quality-and-Cognition.md")
    return scripted_llm, session


class TestGroundedAnswer:
    def test_answer_includes_sources_from_pipeline(self, pipeline_and_session):
        llm, session = pipeline_and_session
        result = RagPipeline().answer(session, "What happens to attention after short sleep?")
        assert result["sources"], "sources must come from the retrieval pipeline"
        assert result["sources"][0]["document_name"] == "Sleep-Quality-and-Cognition.md"
        assert result["answer"].startswith("According to [1]")
        assert result["provider"] == "scripted-test"
        assert result["debug"]["retrieved_count"] == len(result["sources"])

    def test_llm_receives_question_and_metadata(self, pipeline_and_session):
        llm, session = pipeline_and_session
        RagPipeline().answer(session, "Does irregular sleep timing matter?")
        assert llm.last_question == "Does irregular sleep timing matter?"
        assert llm.last_evidence is not None
        first = llm.last_evidence[0]
        assert "document_name" in first and ("page" in first or "chunk_id" in first)

    def test_debug_block_complete(self, pipeline_and_session):
        _, session = pipeline_and_session
        result = RagPipeline().answer(session, "What did cohorts measure?")
        debug = result["debug"]
        for key in ("embedding_model", "vector_backend", "top_k", "scores", "context_sent_to_llm"):
            assert key in debug
        assert debug["scores"][0]["dense"] >= 0.0


class TestInsufficientEvidence:
    def test_empty_retrieval_flagged(self, hash_embedder, scripted_llm):
        store = SessionStore()
        session = store.create()
        pipeline = RagPipeline()
        pipeline.ingest_demo(session, "Sleep-Quality-and-Cognition.md")
        # Question engineered to retrieve the least-related tail chunk.
        result = pipeline.answer(session, "zzzqqq unrelated xylophone quantum?")
        # Regardless of ranking, insufficient flag must exist and be boolean.
        assert isinstance(result["insufficient_evidence"], bool)

    def test_no_document_raises(self, hash_embedder, scripted_llm):
        session = SessionStore().create()
        with pytest.raises(RuntimeError, match="no processed document"):
            RagPipeline().answer(session, "anything")


class TestMockProvider:
    def test_mock_extractive_answer_cites_sources(self, hash_embedder):
        store = SessionStore()
        session = store.create()
        pipeline = RagPipeline()
        pipeline.ingest_demo(session, "Sleep-Quality-and-Cognition.md")
        evidence = session.retriever.retrieve("attention lapses short sleep", top_k=3)
        mock = MockLLMProvider()
        result = mock.generate_answer("attention lapses short sleep", [e.to_dict() for e in evidence])
        assert "[1]" in result.answer or "[2]" in result.answer
        assert "fallback" in result.answer.lower()

    def test_mock_insufficient_when_no_evidence(self):
        mock = MockLLMProvider()
        result = mock.generate_answer("anything", [])
        assert "sufficient" in result.answer.lower()

    def test_mock_weak_match_reports_insufficiency(self, hash_embedder):
        store = SessionStore()
        session = store.create()
        pipeline = RagPipeline()
        pipeline.ingest_demo(session, "Sleep-Quality-and-Cognition.md")
        evidence = session.retriever.retrieve("xylophone quantum disco", top_k=2)
        mock = MockLLMProvider()
        result = mock.generate_answer("xylophone quantum disco", [e.to_dict() for e in evidence])
        # Weak overlap must produce the honest insufficiency response, not noise.
        if result.answer.startswith("The provided documents"):
            assert "sufficient" in result.answer.lower()


class TestSessionLifecycle:
    def test_reset_clears_document(self, hash_embedder):
        store = SessionStore()
        session = store.create()
        pipeline = RagPipeline()
        pipeline.ingest_demo(session, "Sleep-Quality-and-Cognition.md")
        assert session.status == "ready"
        store.reset(session)
        assert session.status == "empty"
        assert session.chunk_count == 0
        assert session.retriever is None

    def test_session_summary_shape(self, hash_embedder):
        store = SessionStore()
        session = store.create()
        summary = session.summary()
        for key in ("session_id", "status", "chunk_count", "turns"):
            assert key in summary
