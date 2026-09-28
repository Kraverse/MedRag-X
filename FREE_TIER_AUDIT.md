# MedRAG-X — Free-Tier Audit

Verified against vendor documentation in September 2026. **No guarantee of ₹0 / $0 is made where a service can charge after limit overage** — noted per service. "Portfolio usage" here means: one deployed demo, a handful of recruiters/curious users per day, no scheduled traffic.

## Cloudflare Pages (frontend)

| Item | Finding |
|---|---|
| Free tier | 500 builds/month, 1 concurrent build, unlimited static requests, unlimited bandwidth |
| Card required | No |
| Auto-billing risk | **No** — free plan hard-stops at build quota; paid features are opt-in |
| Cold start | None (static files on CDN) |
| Portfolio cost | **₹0 / $0** — a docs site uses a handful of builds per month |

## Render (backend)

| Item | Finding |
|---|---|
| Free tier | Free web service instances: 750 instance-hours/workspace/month; 512 MB RAM |
| Behavior | **Spins down after 15 min idle; ~50 s cold start on next request** |
| Card required | No for free services (card may be requested for identity verification in some regions/accounts — if asked, decide before proceeding) |
| Auto-billing risk | **No** — free instance hours simply run out (service pauses) rather than converting to paid; paid plans are manual upgrades |
| Bandwidth | Free tier includes limited egress (order of 100 GB/mo); a text-only API uses trivial amounts |
| Portfolio cost | **₹0 / $0**. One free service ≈ 720 h < 750 h even running all month; the 15-min spin-down actually conserves hours |
| Practical notes | 512 MB comfortably fits the 130 MB ONNX model + FAISS index at demo scale. In-memory sessions reset on spin-down — documented UX behavior, not a billing risk |

## Groq Cloud (LLM)

| Item | Finding |
|---|---|
| Free tier | Yes — current lineup includes `openai/gpt-oss-120b` and `openai/gpt-oss-20b` |
| Rate limits (free tier, per docs) | ~**30 requests/min, ~1,000 requests/day, ~8K tokens/min, ~200K tokens/day** for the gpt-oss models |
| Card required | **No** |
| Auto-billing risk | **No on free tier** — billing requires explicitly adding payment method / upgrading to Developer plan |
| Overage behavior | HTTP 429 with `retry-after`; MedRAG-X honors the header, retries once, then degrades to the extractive fallback with a clear message |
| Portfolio cost | **₹0 / $0**. 1k requests/day is far above portfolio traffic (each question = 1 request) |
| Model note | Llama models left Groq's free/developer tiers in Aug 2026; `LLM_MODEL` is configurable, so a model change is a one-variable edit |

## Embedding model — BAAI/bge-small-en-v1.5 (via fastembed)

| Item | Finding |
|---|---|
| Cost | **₹0 / $0. No API, no key, no quota.** Runs in-process on CPU (ONNX) |
| Resource use | ~130 MB weights on disk (downloaded once at deploy), modest CPU/RAM at demo scale |
| Auto-billing risk | None — it is an open-weights model executing locally |
| Cold start | Model loads at service boot (warmup hook), not per-request |

## FAISS (vector search)

Open-source library (Meta), MIT-licensed, runs in-process. No service, no quota, no cost. `IndexFlatIP` is exact search — at demo scale, ~10 ms/query on CPU.

## pypdf / FastAPI / NumPy / Next.js / Tailwind

Open-source libraries; no service quotas or costs.

## Total expected cost for portfolio usage

**₹0 / $0/month**, with these honest caveats:

1. **Render free hours:** one web service fits inside 750 h/month even with zero spin-down; a second long-running free service in the same workspace could exhaust the pool and pause services (a pause, not a charge).
2. **Groq free tier** is share-rate-limited per organization; a viral traffic spike → 429s → extractive fallback answers until quota resets. No bill, degraded answers.
3. **Cloudflare build quota** (500/mo) could be hit only by pathological commit volume.
4. Nothing in this stack can silently auto-charge: every paid tier requires an explicit dashboard upgrade.

## Upgrade triggers (if this project ever outgrows free)

- Render → $7/mo starter: no spin-down, persistent disk for sessions.
- Groq Developer plan or any paid OpenAI-compatible provider: one `LLM_API_KEY`/`LLM_MODEL` change.
- Cloudflare: only if build minutes become a constraint (unlikely for a static site).
