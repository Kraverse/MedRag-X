# MedRAG-X — RAG Evaluation

All numbers below are **actual measurements** produced by `backend/scripts/run_eval.py` against the committed dataset `data/eval/rag_eval_questions.json`, using the production embedding model (`BAAI/bge-small-en-v1.5` via fastembed) and the production retrieval path (FAISS + lexical blend). Raw results from the latest run are stored in `data/eval/eval_results.json`.

## Methodology

### Evaluation data

- **16 in-scope questions** across the three synthetic demo documents (6 sleep, 4 wearable, 6 evidence-primer). Each question specifies:
  - the target document,
  - an `expected_chunk_hint` — a verbatim string from the gold passage (e.g. `"24 percent higher rate of attention lapses"`),
  - the expected section, as a sanity field.
- **3 out-of-scope questions** (drug treatment, dosage, unrelated history) that the corpus provably cannot answer. These measure whether the system refuses honestly instead of hallucinating.

The dataset is synthetic and hand-written for this project. That is a deliberate, documented choice: real patient data is out of scope for this project by policy, and public QA benchmarks (PubMedQA etc.) test generation breadth rather than retrieval on *user-supplied* documents, which is what this system does.

### Metrics (and why these)

| Metric | Definition | Why meaningful here |
|---|---|---|
| **Recall@K** | Fraction of questions where at least one top-K retrieved chunk contains the gold hint | The core retrieval question: does the right passage reach the LLM's context window? |
| **Hit@1** | Fraction where the **rank-1** chunk contains the gold hint | Measures ranking quality, which drives citation order shown to users |
| **Precision@4** | Average fraction of the 4 retrieved chunks that contain the gold hint | Context-window hygiene: how much of what we send the LLM is on-topic |
| **Honest-refusal rate** | Fraction of out-of-scope questions answered with an insufficiency statement | The anti-hallucination behavior is the product's central safety claim |
| **Groundedness (extractive)** | Fraction of fallback-answer sentences that are verifiable spans of retrieved evidence | Mechanically checkable grounding for the no-key fallback mode |
| **Retrieval latency** | Wall-clock ms for retrieve() on CPU | Confirms free-tier viability |

Per-question results (which section ranked #1, where the hint was found, score) are in `eval_results.json → per_question`.

### Metrics deliberately NOT claimed

- **Generation groundedness for the real LLM** — requires human/LLM-judge review of free-form answers. Not automated here, so it is not reported rather than invented. The strict prompt and citation enforcement constrain it, but no number is claimed.
- **Answer correctness / clinical accuracy** — unmeasurable without expert annotation, and out of scope for an educational demo.

## Results (measured 2026-09-28, local CPU)

```
n_questions:            16
Recall@1:               0.812
Recall@2:               0.938
Recall@4:               1.000
Hit@1:                  0.812
Precision@4:            0.354
Retrieval latency avg:  ~10 ms   (p95 ~15 ms, CPU)
```

**Out-of-scope behavior:** 3/3 honest refusals (1.0) — each drug/dosage/history question produced the explicit insufficiency response rather than an attempted answer.

**Groundedness (extractive fallback):** 18/18 answer sentences (1.0) were verified verbatim spans of retrieved evidence, after excluding the fixed mode-label preamble. The verifier (`run_groundediness_mock`) normalizes whitespace and strips `[n]` markers before substring-checking against source chunks.

### Reading the numbers

- **Recall@4 = 1.0** means the gold passage always reaches the LLM context on this set — the retrieval layer does not bottleneck answer quality here.
- **Hit@1 = 0.81** shows ranking is good but not perfect; the misses cluster on questions whose phrasing is more generic than the gold passage (e.g. "What is the number needed to treat?" ranks the Conclusion paragraph first because it repeats the term densely).
- **Precision@4 = 0.35** is honest but expected: each doc yields few large chunks (9 total across 3 docs), so top-4 covers ~44% of a document and many chunks are only partially relevant. With section-sized corpora this is the natural trade of large chunks; a reranker would improve it at real cost (see RAG_DOCUMENTATION §4).

### Ablations measured during development

| Configuration | Recall@4 | Notes |
|---|---|---|
| chunk 700 / overlap 117 | 0.938 | Splits gold passages across chunks |
| chunk 1000 / overlap 167 | 1.000 | |
| **chunk 1200 / overlap 200 (shipped)** | **1.000** | Smallest chunks at ceiling |
| chunk 1600 / overlap 267 | 1.000 | Larger, no gain |
| Stopwords removed from lexical blend | Hit@1 −1 question | But fixed 3/3 out-of-scope parroting → kept |
| Refusal gate on pure lexical score | refusals 0.0 → 1.0 | Evidence-score bonus had masked irrelevance |

## Limitations

1. **n=16 (+3 OOS) is a smoke-level suite.** It detects regressions and validates design choices; it does not establish general retrieval quality. Direction: grow to 100+ questions with paraphrase variants.
2. **Single gold passage per question.** Real questions can have several valid supporting passages; Precision@4 undercounts when extra retrieved chunks are also legitimately relevant.
3. **Verbatim-hint matching.** A retrieval counts as correct only if the exact hint string survives chunking. Paraphrase-tolerant grading (embedding similarity to a gold answer) would be more realistic but fuzzier to verify.
4. **English-only, synthetic, well-structured documents.** The demo corpus is friendly by construction (clear headings, short sentences). Messy real-world PDFs will score lower.
5. **No LLM-generation metrics.** Answer faithfulness for the Groq path is enforced by prompt contract and citation UI, not measured. An LLM-judge pass (e.g., faithfulness scoring) is the natural next step.
6. **Latency numbers are local-machine numbers** (not the Render free instance), though retrieval cost is CPU-bound and corpus-size-dependent, not network-dependent.

## Reproducing

```bash
cd backend
python scripts/run_eval.py                  # prints summary JSON
python scripts/run_eval.py --json-out ../data/eval/eval_results.json
python scripts/run_eval.py --no-faiss       # NumPy backend ablation
```
