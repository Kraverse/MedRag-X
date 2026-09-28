# MedRAG-X — RAG Design Documentation

This document explains *why* every stage of the pipeline is built the way it is, with the exact values used in production. Companion docs: [RAG_EVALUATION.md](RAG_EVALUATION.md) (measured metrics), [DEPLOYMENT.md](DEPLOYMENT.md), [FREE_TIER_AUDIT.md](FREE_TIER_AUDIT.md).

---

## 1. Why chunking is required

Embedding models encode a fixed-size window of text (bge-small: 512 tokens ≈ 2,000 characters). A full document produces one long vector that averages away the specific facts you want to retrieve — a 10-page paper about sleep becomes a vector "about sleep," useless for finding the one sentence about a 24% attention-lapse increase.

Chunking keeps each vector semantically focused: retrieve the *passage* that answers the question, then let the LLM compose an answer from the handful of best passages. This is the core RAG trade: smaller chunks = sharper retrieval but less surrounding context; bigger chunks = more context but blurrier vectors.

## 2. Chunking implementation

`backend/app/documents/chunking.py`

| Parameter | Value | Reason |
|---|---|---|
| `CHUNK_SIZE` | **1200 chars** (~250–300 tokens) | Measured sweep (below) shows recall@4 saturates ≥1000 chars; 1200 keeps each chunk to roughly one document section |
| `CHUNK_OVERLAP` | **200 chars** (~17% of a chunk) | Sentences straddling a boundary stay fully retrievable from at least one chunk; larger overlap wastes index space |
| `MIN_CHUNK` | **120 chars** | Trailing fragments smaller than this are merged into the previous chunk instead of polluting the index |
| Split unit | Sentence boundaries (regex on `.!?` + whitespace) | Never splits mid-word; falls back to hard character splits only for pathological >1200-char sentences |

**Chunk metadata** (preserved through retrieval into citations):

- `chunk_id` — deterministic, `{document_name}-c{index}` (stable across runs, used in citations when no page exists)
- `document_name`
- `page` — PDF page number propagated from page-wise extraction
- `section` — nearest preceding short markdown heading (e.g. "Results"), lifted by the cleaner so headings never glue to body text

**Chunk-size sweep** (16-question eval set, production embeddings, Recall@4):

| Chunk size | Overlap | Chunks (3 docs) | Recall@4 |
|---|---|---|---|
| 700 | 117 | 16 | 0.938 |
| 1000 | 167 | 12 | 1.000 |
| **1200** | **200** | **9** | **1.000** |
| 1600 | 267 | 7 | 1.000 |

1200/200 gives ceiling recall with the smallest chunks that still carry coherent sections.

### Cleaning (`documents/cleaning.py`)

Ordered steps, deliberately conservative: Unicode NFKC normalization (PDF ligatures/odd spaces) → control-character strip (keep `\n`, `\t`) → de-hyphenate line-wrapped words (`exam-\nple` → `example`) → paragraph reconstruction: short markdown headings lifted onto their own line (become section metadata), soft-wrapped body lines joined → whitespace collapse. Aggressive normalization is avoided because it can destroy meaning (decimal points, units, negations).

## 3. Embedding model

**Model: `BAAI/bge-small-en-v1.5`** via [fastembed](https://github.com/qdrant/fastembed) (ONNX Runtime).

| Property | Value |
|---|---|
| Parameters | 33M |
| Dimensions | 384 |
| Quantized size on disk | ~130 MB (downloaded once, cached) |
| Hardware | CPU-only, no GPU required |
| API key required | No — fully local |
| Query cost | ₹0 / $0 |

**Why this model:** bge-small-en-v1.5 is the strongest quality-per-compute point in the BGE family for English retrieval; it runs comfortably inside Render's free 512 MB instance; and it needs no external service, so the demo has zero marginal cost and no data leaves the server. Larger models (bge-base/large, E5-large) would improve marginal recall on hard corpora but risk memory limits and cold-start time on free infrastructure — a trade not worth it for a 3-document demo. The model is configurable via `EMBEDDING_MODEL`-style swap in `embeddings/provider.py` (single `FastEmbedProvider` constructor argument).

**Fallback:** if fastembed cannot load (e.g., no network for the first download), a deterministic hashing-trigram embedder keeps the pipeline running offline. `/health` and retrieval diagnostics always report which backend is active.

## 4. Vector search

`backend/app/retrieval/vector_store.py` + `retriever.py`

- **Index:** FAISS `IndexFlatIP` — exact (non-approximate) inner product over L2-normalized vectors, i.e. cosine similarity. Flat search is O(n·d), which at demo scale (tens of chunks) is ~10 ms; an ANN index (IVF/HNSW) would add complexity with no measurable benefit at this size.
- **Backend fallback:** a pure-NumPy cosine implementation used automatically if FAISS fails to import. Unit tests assert both backends return identical rankings.
- **Top-K:** default `4`, client-configurable 1–10 per request (`top_k` in `/api/query`), internally the store retrieves `2×k` candidates before the blend, capped at 16.
- **Hybrid blend:** `final = dense_cosine + 0.25 × lexical_overlap` where lexical overlap is stopword-filtered bag-of-words cosine. The bonus sharpens exact-phrase hits (drug names, "Device C") that bag-of-embeddings models can rank loosely. The 0.25 weight was chosen so lexical can reorder near-ties but never rescue an irrelevant chunk; on the eval set the blend lifted Hit@1 by one question versus dense-only.
- **No cross-encoder reranking:** a cross-encoder would add a second model (~400+ MB RAM) and 10× latency for a corpus this small where Recall@4 is already 1.0. Per the project constraints, it was deliberately **not** implemented.

## 5. Generation

`backend/app/llm/prompts.py` + `provider.py`

**Provider interface** (the pipeline depends only on this):

```python
class LLMProvider(Protocol):
    def generate_answer(self, question: str, evidence: list[dict], history_block: str = "") -> GenerationResult
```

Two implementations ship:

1. **`GroqProvider`** — Groq Cloud's OpenAI-compatible chat API. Model `openai/gpt-oss-120b` (current free-tier lineup; note Llama models left Groq's free tier in August 2026). Temperature 0.1, max 700 completion tokens, 429 handling with `retry-after`, one retry, then a transparent fallback message.
2. **`MockLLMProvider`** — used when `LLM_API_KEY` is unset or the API fails. It selects the 1–3 most query-relevant sentences from the retrieved evidence (stopword-filtered lexical ranking + a pure-lexical refusal gate) and labels the output "extractive fallback mode." It never invents content and honestly refuses when overlap is weak — so the app demonstrates real retrieval with zero configuration.

### The strict prompt (anti-hallucination contract)

The system prompt requires, in order:

1. Answer **only** from the numbered evidence passages in the message.
2. If evidence is insufficient, **say exactly that** and name what is missing.
3. Never invent facts, studies, numbers, or citations; never cite outside the evidence.
4. Cite inline with the provided `[n]` labels.
5. Never give diagnosis/treatment/medication advice — the tool only reports what documents say.
6. Concise (2–5 short paragraphs), plain language.
7. When evidence is only weakly related, prefer the insufficiency response over speculation.

The user message carries: the question, optional recent conversation turns (so follow-ups like "what evidence supports *that*?" resolve), and the numbered evidence block where each item includes source filename, page/chunk, and section.

**Insufficiency detection:** the pipeline inspects the answer for insufficiency phrases ("does not contain sufficient", "not enough information", …) and sets `insufficient_evidence: true` for the UI badge; empty retrieval is insufficiency by definition.

## 6. Conversation / follow-ups

Deliberately simple: the last 4 turns (user+assistant) are rendered as a `CONVERSATION SO FAR` block for reference resolution only. Retrieval always uses the **current question** (plus a lexical anaphora assist in the mock provider). There is no long-term memory, no per-user state beyond the 2-hour session, and history is truncated to bound prompt size.

## 7. Known limitations

- Chunking is character-budgeted, not token-budgeted; for non-English or very long-token languages, token-based splitting would be more precise.
- The section heuristic assumes markdown-style headings; plain PDFs without headings fall back to page metadata only.
- The in-memory index is per-session: each processed document rebuilds its own FAISS index (fine at demo scale; a shared persistent index would be the next scaling step).
- bge-small is English-optimized; multilingual corpora would want a multilingual embedder.
