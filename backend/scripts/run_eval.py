"""Retrieval + groundedness evaluation.

Run from backend/:  python scripts/run_eval.py

Metrics (all real, computed from the synthetic dataset in
data/eval/rag_eval_questions.json):

- Recall@K : fraction of questions whose expected passage is inside the top-K
             retrieved chunks (hint string appears in at least one chunk).
- Hit@1    : fraction where the #1 ranked chunk contains the hint.
- Precision@K : fraction of retrieved chunks that contain the hint (only
             meaningful for questions with a single gold passage; reported as
             such).
- Groundedness (mock pipeline): fraction of generated sentences that are
             extractive spans of retrieved evidence (1.0 by construction for
             the extractive fallback; real-LLM runs require human review and
             are NOT claimed here).

Usage:
    python scripts/run_eval.py [--with-numpy-fallback]  # ablation without FAISS
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.documents.chunking import chunk_text  # noqa: E402
from app.documents.demo_documents import DEMO_DOCUMENTS, load_demo_document  # noqa: E402
from app.embeddings.provider import get_embedder  # noqa: E402
from app.rag.pipeline import RagPipeline  # noqa: E402
from app.rag.sessions import SessionStore  # noqa: E402
from app.retrieval.retriever import Retriever  # noqa: E402
from app.retrieval.vector_store import build_store  # noqa: E402

EVAL_PATH = ROOT / "data" / "eval" / "rag_eval_questions.json"


def load_dataset() -> tuple[list[dict], list[dict]]:
    data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    return data["questions"], data["out_of_scope"]


def index_document(text: str, name: str, line_pages):
    chunks = chunk_text(text, name, pages=line_pages)
    embedder = get_embedder()
    vectors = embedder.embed([c.text for c in chunks])
    store = build_store(vectors, use_faiss=True)
    retriever = Retriever(store, {c.chunk_id: c.to_dict() for c in chunks})
    return chunks, retriever


def run_retrieval_eval(with_faiss: bool = True):
    questions, oos = load_dataset()
    embedder = get_embedder()

    # Chunk each demo doc once.
    index: dict[str, tuple[list, Retriever]] = {}
    for name in DEMO_DOCUMENTS:
        text, _ftype, line_pages = load_demo_document(name)
        chunks = chunk_text(text, name, pages=line_pages)
        vectors = embedder.embed([c.text for c in chunks])
        store = build_store(vectors, [c.chunk_id for c in chunks], use_faiss=with_faiss)
        retriever = Retriever(store, {c.chunk_id: c.to_dict() for c in chunks})
        index[name] = (chunks, retriever)

    ks = [1, 2, 4]
    results = {k: {"recall": 0, "hits1": 0} for k in ks}
    precisionsum = 0.0
    latencies: list[float] = []
    per_question: list[dict] = []

    for q in questions:
        _chunks, retriever = index[q["document"]]
        start = time.perf_counter()
        evidence = retriever.retrieve(q["question"], top_k=4)
        latencies.append((time.perf_counter() - start) * 1000)

        texts = [e.text for e in evidence]
        hint = q["expected_chunk_hint"].lower()
        hit_positions = [i for i, t in enumerate(texts) if hint in t.lower()]

        for k in ks:
            if any(i < k for i in hit_positions):
                results[k]["recall"] += 1
        if hit_positions and hit_positions[0] == 0:
            results[1]["hits1"] += 1
        if texts:
            precisionsum += (len([t for t in texts if hint in t.lower()]) / len(texts)) if hit_positions else 0.0

        per_question.append(
            {
                "id": q["id"],
                "top1_section": evidence[0].section if evidence else None,
                "expected_section": q["expected_section"],
                "hint_found_at": hit_positions[0] if hit_positions else None,
                "top1_score": evidence[0].score if evidence else None,
            }
        )

    n = len(questions)
    summary = {
        "n_questions": n,
        "recall_at_k": {f"@{k}": round(results[k]["recall"] / n, 3) for k in ks},
        "hit_at_1": round(results[1]["hits1"] / n, 3),
        "precision_at_4": round(precisionsum / n, 3),
        "retrieval_latency_ms_avg": round(sum(latencies) / len(latencies), 1),
        "retrieval_latency_ms_p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1),
    }

    # Out-of-scope behavior: retrieve, then confirm honest insufficiency path.
    oos_results = []
    for q in oos:
        _chunks, retriever = index[q["document"]]
        evidence = retriever.retrieve(q["question"], top_k=4)
        from app.llm.provider import MockLLMProvider

        answer = MockLLMProvider().generate_answer(q["question"], [e.to_dict() for e in evidence])
        refused = "sufficient" in answer.answer.lower()
        oos_results.append({"id": q["id"], "refused": refused})
    summary["out_of_scope"] = {
        "n": len(oos),
        "honest_refusal_rate": round(sum(r["refused"] for r in oos_results) / len(oos), 3),
        "detail": oos_results,
    }
    summary["per_question"] = per_question
    return summary


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def run_groundediness_mock() -> dict:
    """Groundedness of the extractive fallback: every output sentence must be
    a span of the retrieved evidence (verifiable mechanically)."""
    questions, _oos = load_dataset()
    pipeline = RagPipeline()
    store = SessionStore()
    grounded = 0
    total = 0
    for q in questions[:8]:
        session = store.create()
        pipeline.ingest_demo(session, q["document"])
        result = pipeline.answer(session, q["question"])
        ev_texts = [_norm(t) for t in (s["text"] for s in result["sources"])]
        answer_sentences = [
            s.strip()
            for s in result["answer"].split("\n")
            if len(s.strip()) > 40 and "extractive fallback mode" not in s
        ]
        for sent in answer_sentences:
            total += 1
            core = _norm(re.sub(r"^\[\d+\]\s*", "", sent))
            if any(core in t for t in ev_texts):
                grounded += 1
    return {"n_answers": total, "grounded_fraction": round(grounded / total, 3) if total else None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-faiss", action="store_true", help="Ablation: NumPy backend")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    summary = run_retrieval_eval(with_faiss=not args.no_faiss)
    summary["groundedness_mock_extractive"] = run_groundediness_mock()
    print(json.dumps(summary, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
