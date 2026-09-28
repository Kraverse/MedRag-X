# MedRAG-X

**Evidence-Grounded Medical Research Assistant**

MedRAG-X is a real Retrieval-Augmented Generation (RAG) application. You provide a safe research document (or pick a preloaded synthetic one), ask questions in plain language, and get answers generated **only** from the most relevant passages of that document — with every claim linked back to its source.

```
Document → Text Extraction → Cleaning → Chunking → Embeddings → Vector Search
        → Relevant Evidence → LLM (strict prompt) → Grounded Answer → Source Citations
```

> **Healthcare disclaimer:** MedRAG-X is an educational research assistant for exploring provided documents. It does not provide medical diagnosis or medical advice. Do not upload real patient records or sensitive personal information.

## Live Demo

| | URL |
|---|---|
| Frontend (Cloudflare Pages) | https://medrag-x.pages.dev |
| Backend API (Render) | https://medrag-x-api.onrender.com |
| Health check | https://medrag-x-api.onrender.com/health |

> The backend runs on Render's free tier and spins down after 15 minutes idle. The **first request after idle takes ~50 seconds** to wake it. Subsequent requests are fast.

## Features

- **Real RAG pipeline** — chunking → BGE-small embeddings → FAISS vector search → grounded generation. No hardcoded answers anywhere; every demo question runs the full pipeline.
- **Grounded generation with anti-hallucination prompt** — the LLM may only answer from the retrieved, numbered evidence, must cite with `[n]` labels, and must state when the documents do not contain the answer.
- **Source citations** — every answer lists the exact retrieved passages with document name and page/chunk. Citations are never fabricated: they come from the retrieval pipeline itself.
- **Three demo documents, 100% synthetic** — sleep & cognition, wearable heart-rate accuracy, and a research-reading primer. No real patient data exists anywhere in this project.
- **Your own uploads** — PDF, TXT, Markdown up to 10 MB, with type validation, magic-byte checks, empty-file detection, and clear structured errors.
- **Follow-up questions** — recent conversation turns are passed to the model so "what evidence supports *that*?" resolves correctly.
- **Technical Details view** — expandable panel showing embedding model, vector backend, top-k, per-chunk similarity scores, and the exact context sent to the LLM.
- **Session reset** — clears document and history server-side.

## How It Works

1. **Pick a demo document** (or upload your own). The file is validated, text is extracted (PDFs page-by-page), cleaned, and split into overlapping 1,200-character chunks that keep page number and section heading as metadata.
2. **Each chunk is embedded** with `BAAI/bge-small-en-v1.5` (33M params, 384-dim, CPU ONNX) and indexed in a FAISS flat index.
3. **Your question is embedded with the same model**; cosine similarity retrieves the top-k chunks (default 4), with a small lexical-overlap bonus for exact-phrase matches.
4. **The retrieved chunks and question go to the LLM** (Groq-hosted `openai/gpt-oss-120b`) behind a strict system prompt: answer only from the evidence, never invent citations, refuse when evidence is insufficient.
5. **You get the answer plus its sources**, each expandable to the full retrieved passage with similarity scores.

See [RAG_DOCUMENTATION.md](RAG_DOCUMENTATION.md) for design decisions and [RAG_EVALUATION.md](RAG_EVALUATION.md) for measured metrics.

## Architecture

```
Browser (Next.js static site on Cloudflare Pages)
   │  fetch
   ▼
FastAPI backend (Render free tier)
   │
   ├─ Document processing  (pypdf / TXT / MD → clean → chunk)
   ├─ Embeddings           (fastembed · BAAI/bge-small-en-v1.5 · ONNX CPU)
   ├─ Vector search        (FAISS IndexFlatIP, NumPy fallback)
   ├─ Session store        (in-memory, TTL 2h)
   └─ LLM                  (Groq API · openai/gpt-oss-120b, extractive fallback without key)
```

## RAG Pipeline

| Stage | Implementation | Key values |
|---|---|---|
| Extraction | `pypdf` (page-wise), UTF-8 text/markdown | 10 MB upload limit |
| Cleaning | NFKC normalize, de-hyphenate, heading lift, whitespace collapse | `documents/cleaning.py` |
| Chunking | Sentence-boundary splits, overlap, tiny-fragment merge | 1200 chars, 200 overlap |
| Embedding | `fastembed` + `BAAI/bge-small-en-v1.5` | 384-dim, CPU-only |
| Index | FAISS `IndexFlatIP` (cosine via L2-normalized vectors) | NumPy fallback included |
| Retrieval | Dense top-k + 0.25× lexical-overlap blend | k=4 default, 1–10 configurable |
| Generation | Strict numbered-evidence prompt, temperature 0.1 | `openai/gpt-oss-120b` via Groq |

## Tech Stack

- **Frontend:** Next.js 15 (static export), TypeScript, Tailwind CSS v4 — deployed to Cloudflare Pages
- **Backend:** Python 3.12, FastAPI, Pydantic v2, uvicorn — deployed to Render
- **RAG:** fastembed (ONNX), faiss-cpu, pypdf, numpy
- **LLM:** Groq Cloud API (`openai/gpt-oss-120b` free tier) with an extractive no-key fallback so the app still demonstrates retrieval without any API key

## Dataset

The bundled demo documents are **synthetic research-style texts written for this project** (sleep/cognition, wearable accuracy, evidence primer). They contain no real patient data and make no real-world claims. Uploaded documents stay in memory for the session (2h TTL) and are never written to disk.

## Evaluation

Measured on the 16-question synthetic eval set (`data/eval/rag_eval_questions.json`) with the production embedding model:

- **Recall@4 = 1.00** · Recall@1 = 0.81 · Precision@4 = 0.35
- **Out-of-scope honest-refusal = 3/3**
- **Extractive-groundedness = 1.00** (verifier-checked spans)
- Retrieval latency ≈ 10 ms average (CPU, demo-sized corpus)

Details, methodology, and limitations: [RAG_EVALUATION.md](RAG_EVALUATION.md).

## Project Structure

```
MedRAG-X/
├── frontend/               # Next.js + TS + Tailwind (static export for Cloudflare Pages)
│   └── src/
│       ├── app/            # / (landing), /demo, /how-it-works
│       ├── components/     # DemoWorkspace (doc picker, Q&A, sources, debug view)
│       └── lib/            # typed API client
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes + Pydantic schemas
│   │   ├── documents/      # extraction, cleaning, chunking, synthetic demo docs
│   │   ├── embeddings/     # fastembed provider + offline fallback
│   │   ├── retrieval/      # vector store (FAISS/NumPy) + retriever
│   │   ├── llm/            # provider abstraction, Groq + mock, strict prompts
│   │   ├── rag/            # pipeline orchestrator + session store
│   │   └── utils/          # logging
│   ├── tests/              # 61 pytest cases
│   └── scripts/            # run_eval.py, e2e_smoke.py
├── data/eval/              # evaluation dataset + latest results
├── docs/                   # (reserved)
├── RAG_DOCUMENTATION.md    # chunking/embedding/retrieval design decisions
├── RAG_EVALUATION.md       # measured metrics + methodology
├── DEPLOYMENT.md           # Cloudflare + Render setup
├── SECURITY.md             # threat model + handling of uploads/keys
├── FREE_TIER_AUDIT.md      # verified limits/costs for every service used
└── render.yaml             # Render blueprint
```

## Local Setup

Prerequisites: Python 3.12, Node 20+.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# Health: http://localhost:8000/health

# Frontend (second terminal)
cd frontend
npm install
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                       # http://localhost:3000

# Tests
cd backend && python -m pytest tests -q

# Retrieval evaluation (downloads model weights on first run)
cd backend && python scripts/run_eval.py
```

Without `LLM_API_KEY` set, the app runs end-to-end with a transparent **extractive fallback** (answers composed from retrieved passages, clearly labeled) so the pipeline is fully demonstrable offline.

## Environment Variables

See `.env.example`, `backend/.env.example`, `frontend/.env.example`.

| Variable | Where | Visibility | Purpose |
|---|---|---|---|
| `LLM_API_KEY` | backend (Render) | **SECRET** | Groq API key |
| `LLM_MODEL` | backend | PUBLIC | Groq model id (default `openai/gpt-oss-120b`) |
| `ALLOWED_ORIGINS` | backend | PUBLIC | Comma-separated CORS origins |
| `NEXT_PUBLIC_API_URL` | frontend (Cloudflare) | PUBLIC | Backend base URL |
| `LOG_LEVEL` | backend | PUBLIC | `INFO` default |

Never commit real keys. The frontend can only hold public variables.

## Deployment

- **Frontend → Cloudflare Pages:** build `npm run build` in `frontend/`, output dir `frontend/out` (static export). `NEXT_PUBLIC_API_URL=https://medrag-x-api.onrender.com`.
- **Backend → Render:** Blueprint from `render.yaml` (Python 3.12, `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`), health check `/health`, `LLM_API_KEY` set as a secret in the Render dashboard.

Step-by-step with screenshots-level detail: [DEPLOYMENT.md](DEPLOYMENT.md).

## Security

- Secrets only in platform dashboards; `.env*` is git-ignored; a pre-push secrets scan is documented in [SECURITY.md](SECURITY.md).
- Uploads: type allow-list + magic-byte sniffing + size cap + empty-file rejection; PDFs never executed, text only.
- No persistence: documents and sessions live in process memory with a 2h TTL. No logs contain document content or keys.
- CORS restricted to the deployed frontend origin(s).

## Limitations

- In-memory sessions: a backend restart (or Render free-tier spin-down) clears them; users simply reload a document.
- PDF text extraction is text-layer only — scanned PDFs without OCR return a clear error.
- Retrieval quality depends on document language/structure; the eval set is synthetic and small (n=16).
- The free-tier LLM has rate limits (30 req/min, 1k req/day on Groq); the UI surfaces provider errors honestly.
- Not clinically validated, not a medical device, not for emergency use.

## Healthcare Disclaimer

MedRAG-X is an educational research assistant for exploring provided documents. It does not provide medical diagnosis or medical advice. Do not upload real patient records or sensitive personal information.
