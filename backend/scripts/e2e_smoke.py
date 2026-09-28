"""Local end-to-end smoke test against a running backend (default :8000)."""

from __future__ import annotations

import json
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def main() -> int:
    ok = True
    h = httpx.Client(timeout=90)

    health = h.get(f"{BASE}/health").json()
    print("HEALTH:", json.dumps(health))

    demo = h.post(f"{BASE}/api/documents/demo", json={"filename": "Sleep-Quality-and-Cognition.md"}).json()
    sid = demo["session_id"]
    print("DEMO:", json.dumps(demo["document"]))

    q1 = h.post(f"{BASE}/api/query", json={"session_id": sid, "question": "What happens to attention after short sleep?"}).json()
    print("ANSWER1:", q1["answer"][:220].replace("\n", " "))
    print("SOURCES1:", [(s["citation"], round(s["score"], 3)) for s in q1["sources"]])
    print("DEBUG1 backend:", q1["debug"]["vector_backend"], "| embedder:", q1["debug"]["embedding_model"], "| retrieved:", q1["debug"]["retrieved_count"])

    q2 = h.post(f"{BASE}/api/query", json={"session_id": sid, "question": "What evidence supports that?"}).json()
    print("ANSWER2 (follow-up):", q2["answer"][:160].replace("\n", " "))
    hist = q2["debug"]["conversation_history"]
    print("HISTORY_TURNS:", len(hist))

    oos = h.post(f"{BASE}/api/query", json={"session_id": sid, "question": "What is the first-line drug treatment for type 2 diabetes?"}).json()
    print("OOS_ANSWER:", oos["answer"][:180].replace("\n", " "))
    print("OOS_INSUFFICIENT_FLAG:", oos["insufficient_evidence"])

    reset = h.post(f"{BASE}/api/session/reset", json={"session_id": sid, "question": "reset"}).json()
    print("RESET:", reset["status"])
    after = h.post(f"{BASE}/api/query", json={"session_id": sid, "question": "hello?"})
    print("AFTER_RESET_STATUS:", after.status_code)

    # Upload flow with a synthetic TXT
    sess = h.post(f"{BASE}/api/sessions", json={}).json()
    files = {"file": ("synthetic_notes.txt", b"Wearable sensors recorded synthetic heart rate data during simulated exercise sessions for demonstration purposes only.", "text/plain")}
    up = h.post(f"{BASE}/api/documents/process", files=files, data={"session_id": sess["session_id"]})
    print("UPLOAD:", up.status_code, json.dumps(up.json().get("document", up.json())))

    # Invalid upload
    bad = h.post(f"{BASE}/api/documents/process", files={"file": ("x.exe", b"MZ", "application/octet-stream")}, data={"session_id": sess["session_id"]})
    print("BAD_UPLOAD:", bad.status_code, bad.json()["error"]["code"])

    # Empty question
    eq = h.post(f"{BASE}/api/query", json={"session_id": sid, "question": "   "})
    print("EMPTY_QUESTION:", eq.status_code)

    h.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
