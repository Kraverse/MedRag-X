# MedRAG-X — Deployment Guide

Architecture:

```
GitHub (source of truth)
   ├─▶ Cloudflare Pages  ── builds frontend/ (Next.js static export → out/)
   └─▶ Render            ── builds backend/  (FastAPI + RAG pipeline)
                                   ▲
                    Browser calls API directly (CORS-restricted)
```

## 1. GitHub

1. Repository: `https://github.com/Kraverse/MedRAG-X` (branch `main`).
2. Push all code (frontend, backend, docs, `render.yaml`). Never commit `.env` or keys — see SECURITY.md.
3. Both Cloudflare and Render deploy **from this repo**; every push to `main` triggers autodeploy.

## 2. Backend — Render

**One-time setup (dashboard):**

1. Render dashboard → **New → Blueprint** → select the `Kraverse/MedRAG-X` repo. Render reads `render.yaml`:
   - service type: web, name `medrag-x-api`, runtime `python`, plan `free`, root dir `backend`
   - build: `pip install -r requirements.txt`
   - start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - health check path: `/health`
2. Set the secret env var **`LLM_API_KEY`** (Groq key) in the service's *Environment* tab. `sync: false` in `render.yaml` intentionally leaves it to the dashboard.
3. Verify the non-secret vars rendered from the blueprint: `LLM_MODEL=openai/gpt-oss-120b`, `ALLOWED_ORIGINS=https://medrag-x.pages.dev`, `LOG_LEVEL=INFO`, `PYTHON_VERSION=3.12.4`.
   - **If your Pages subdomain differs** (Cloudflare assigns `<project>.pages.dev`), update `ALLOWED_ORIGINS` to the exact origin — CORS failures look like "Cannot reach the MedRAG-X backend" in the UI.
4. Deploy, then **verify the live API — a green build is not a verified deploy:**

```bash
curl https://medrag-x-api.onrender.com/health
# expect: {"status":"ok",...,"llm_provider":"groq","llm_configured":true}

curl -X POST https://medrag-x-api.onrender.com/api/documents/demo \
  -H "Content-Type: application/json" -d '{}'
# expect: {"session_id":"...","document":{"status":"ready","chunk_count":...}}
```

Then run the full cycle: `python backend/scripts/e2e_smoke.py https://medrag-x-api.onrender.com`.

**Free-tier behavior:** the instance spins down after 15 min idle; the next request takes ~50 s to wake. Render grants 750 free instance-hours/month — one always-on-ish service fits comfortably. Plan restarts clear in-memory sessions (users just reload a document).

## 3. Frontend — Cloudflare Pages

1. Cloudflare dashboard → **Workers & Pages → Create → Pages → Connect to Git** → select `Kraverse/MedRAG-X`.
2. Production branch: `main`. Build settings:

| Setting | Value |
|---|---|
| Framework preset | Next.js (Static HTML export works too) |
| Build command | `cd frontend && npm ci && npm run build` |
| Build output directory | `frontend/out` |
| Root directory | *(leave empty — output path includes `frontend/`)* |

3. Environment variables (Production **and** Preview):

| Variable | Value | Visibility |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://medrag-x-api.onrender.com` | Public (baked into the JS bundle at build time) |

4. Deploy. Because `next.config.ts` sets `output: "export"`, `npm run build` emits the fully static `out/` directory that Pages serves.

**Verify the live site (do not skip):**

```text
Open https://medrag-x.pages.dev
  → hero renders, disclaimer visible
  → Try Demo → pick "Sleep Quality & Cognition"
  → status shows ready with chunk count
  → ask "What happens to attention after short sleep?"
  → answer appears with [1]-style citation chips + Sources + Technical Details
  → ask follow-up "What evidence supports that?"
  → Reset session → document picker returns
  → also test: upload a .txt, upload a .exe (must show a friendly error),
    empty question (Ask stays disabled), phone viewport, hard refresh
```

First question after backend idle can take ~50 s (Render cold start) — the UI explains this in its error copy if the wake-up races a request timeout; retry.

## 4. Environment variables summary

| Variable | Lives on | Visibility | Notes |
|---|---|---|---|
| `LLM_API_KEY` | Render dashboard | **SECRET** | Groq key; unset = extractive fallback mode |
| `LLM_MODEL` | `render.yaml` | PUBLIC | Groq model id |
| `ALLOWED_ORIGINS` | `render.yaml` | PUBLIC | Must exactly match the Pages origin(s), comma-separated |
| `NEXT_PUBLIC_API_URL` | Cloudflare Pages | PUBLIC | Backend base URL, no trailing slash |
| `LOG_LEVEL`, `PYTHON_VERSION` | `render.yaml` | PUBLIC | Infra tuning |

## 5. CORS

The backend allows only the origins listed in `ALLOWED_ORIGINS`. Local development needs `http://localhost:3000` (and `http://127.0.0.1:3000` if you browse via 127.0.0.1). Production needs the exact `https://<your-project>.pages.dev` origin. Method allow-list: GET, POST, OPTIONS.

## 6. Production API URL

`https://medrag-x-api.onrender.com` (update if you rename the Render service; the URL derives from the service name).

## 7. Frontend API URL

Baked in at **build time** — changing `NEXT_PUBLIC_API_URL` requires a rebuild/redeploy of Pages, not a restart.

## 8. Post-deploy test checklist

- [ ] `GET /health` returns 200 with `llm_configured: true`
- [ ] Demo load → ready (chunk count > 0)
- [ ] Query → answer + ≥1 source + citation chips
- [ ] Follow-up question resolves "that"
- [ ] Out-of-scope question → honest insufficiency response
- [ ] Reset → picker returns; query then 409s
- [ ] Invalid upload (.exe) → friendly 400 error in UI
- [ ] Empty question → Ask disabled
- [ ] Mobile viewport (390px): no horizontal overflow
- [ ] Hard refresh on /demo rehydrates or cleanly returns to picker
