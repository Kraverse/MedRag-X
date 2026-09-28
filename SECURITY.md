# MedRAG-X — Security Notes

Educational project; threat model is "public portfolio demo," but the handling rules below are real and enforced.

## Secrets handling

- **No secrets in the repo.** All keys live in platform dashboards (Render environment, Cloudflare environment).
- `.gitignore` blocks `.env`, `.env.local`, `backend/.env`, `frontend/.env.local`, `*.pem`, `*.key`.
- Only `.env.example` files (placeholders, no values) are committed.
- The frontend can only hold **public** configuration (`NEXT_PUBLIC_API_URL`); anything in a `NEXT_PUBLIC_` variable is, by definition, world-readable in the JS bundle.
- **Pre-push secret scan** (run before every push; also rerunnable ad hoc):

```bash
git grep -nIE "(sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{30,}|Bearer [A-Za-z0-9._-]{20,})" -- . || echo "no key-like strings"
git grep -nIE "(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9+/_-]{16,}['\"]" -i -- . || echo "no hardcoded credentials"
find . -name ".env" -o -name "*.key" -o -name "*.pem" | grep -v node_modules || echo "no env/key files present"
```

If a secret ever does land in history, rotate it immediately — deletion from `main` does not remove it from git history.

## User uploads

Defense is layered, in `backend/app/documents/loader.py`:

1. **Extension allow-list**: `.pdf`, `.txt`, `.md` only — everything else is rejected with a structured 400 before any parsing.
2. **Magic-byte check**: a `.pdf` must start with `%PDF-` (blocks renamed executables).
3. **Size cap**: 10 MB, enforced at two layers (route check → 413; loader hard ceiling).
4. **Empty-file detection**: zero-byte and whitespace-only files rejected.
5. **Parse, never execute**: pypdf extracts a text layer; no JavaScript/embedded-file execution, no OCR, no shell-outs.
6. **Encrypted PDFs** are rejected explicitly rather than half-processed.
7. Extraction failures become structured errors — raw parser exceptions never reach the client.

**What is intentionally out of scope:** virus scanning (no file is stored or executed; text extraction only), OCR, image PDFs (clear error instead).

## Data flow & persistence

- Uploaded content lives **only in process memory** for the session (2 h TTL, max 500 sessions, then LRU-evicted). Nothing is written to disk. A backend restart or Render spin-down erases everything.
- **Logging:** request logs contain method/path/status only — never document text, questions, answers, or keys.
- **Third-party data flow:** retrieved passages + question are sent to the Groq API to generate answers. That is the only external call. Demo documents are synthetic; users are warned (banner + footer, verbatim disclaimer) not to upload real patient records or sensitive personal data. For a truly zero-egress mode, leave `LLM_API_KEY` unset: the extractive fallback answers entirely in-process.

## API surface

- CORS restricted to configured origins (exact match, no wildcards); only GET/POST/OPTIONS.
- Pydantic validation on every request body; typed error envelopes (`{"error": {"code", "message"}}`) with correct status codes (400/404/409/413/422/500).
- Sessions are unscoped UUIDs — acceptable for a stateless demo, **not** for multi-tenant production. Production would add rate limiting, auth, and per-user session ownership (e.g., signed session tokens + Redis).
- No cookies, no authentication, no third-party scripts on the frontend.

## Known gaps (documented, not hidden)

- No rate limiting on the public API — the Groq quota (30 req/min on free tier) is the only natural brake, and a burst of users can exhaust it (the UI surfaces a clean provider-error message).
- Session IDs are bearer-ish: anyone with the ID can read/reset that session. Fine for a demo; an auth boundary in production.
- In-memory store means horizontal scaling would break sessions by design; see `rag/sessions.py` for the Redis swap-in point.
