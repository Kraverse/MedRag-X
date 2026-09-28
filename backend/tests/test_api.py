"""API tests: health, demo load, upload, query, reset, validation, errors."""

from __future__ import annotations


class TestHealth:
    def test_health_ok(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "embedding_model" in body and "llm_provider" in body

    def test_health_reports_mock_llm_without_key(self, api_client):
        body = api_client.get("/health").json()
        assert body["llm_provider"] == "mock-extractive"
        assert body["llm_configured"] is False


class TestDemoFlow:
    def test_load_demo_document(self, api_client):
        resp = api_client.post("/api/documents/demo", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["document"]["status"] == "ready"
        assert body["document"]["chunk_count"] > 0
        assert body["document"]["document_name"].endswith(".md")
        assert body["session_id"]

    def test_load_specific_demo_document(self, api_client):
        resp = api_client.post(
            "/api/documents/demo", json={"filename": "Wearable-Heart-Rate-Accuracy.md"}
        )
        assert resp.status_code == 200
        assert resp.json()["document"]["document_name"] == "Wearable-Heart-Rate-Accuracy.md"

    def test_unknown_demo_document_404(self, api_client):
        resp = api_client.post("/api/documents/demo", json={"filename": "nope.md"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "DEMO_NOT_FOUND"

    def test_full_demo_query_cycle(self, api_client):
        demo = api_client.post("/api/documents/demo", json={}).json()
        resp = api_client.post(
            "/api/query",
            json={"session_id": demo["session_id"], "question": "What happens to attention after short sleep?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"]
        assert len(body["sources"]) >= 1
        assert body["sources"][0]["document_name"] == body["sources"][0]["document_name"]
        assert "debug" in body and body["debug"]["retrieved_count"] == len(body["sources"])

    def test_follow_up_and_reset(self, api_client):
        demo = api_client.post("/api/documents/demo", json={}).json()
        sid = demo["session_id"]
        r1 = api_client.post("/api/query", json={"session_id": sid, "question": "What does the document say about sleep?"})
        assert r1.status_code == 200
        r2 = api_client.post("/api/query", json={"session_id": sid, "question": "What evidence supports that?"})
        assert r2.status_code == 200
        history = r2.json()["debug"]["conversation_history"]
        assert len(history) >= 3  # prior turn carried into context
        reset = api_client.post("/api/session/reset", json={"session_id": sid, "question": "x"})
        assert reset.status_code == 200
        assert reset.json()["status"] == "reset"
        # Querying after reset returns 409 (document cleared)
        r3 = api_client.post("/api/query", json={"session_id": sid, "question": "hello again"})
        assert r3.status_code == 409


class TestUploadFlow:
    def test_upload_txt(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post(
            "/api/documents/process",
            files={"file": ("study.txt", "Wearable sensors measured synthetic heart rate data.".encode(), "text/plain")},
            data={"session_id": sid},
        )
        assert resp.status_code == 200
        body = resp.json()["document"]
        assert body["document_name"] == "study.txt"
        assert body["document_type"] == "TXT"
        assert body["chunk_count"] >= 1

    def test_upload_rejects_unsupported_type(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post(
            "/api/documents/process",
            files={"file": ("virus.exe", b"MZ fake binary", "application/octet-stream")},
            data={"session_id": sid},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_DOCUMENT"

    def test_upload_empty_file_rejected(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post(
            "/api/documents/process",
            files={"file": ("empty.txt", b"", "text/plain")},
            data={"session_id": sid},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["error"]["message"].lower()

    def test_upload_unknown_session_404(self, api_client):
        resp = api_client.post(
            "/api/documents/process",
            files={"file": ("a.txt", b"hello", "text/plain")},
            data={"session_id": "nonexistent-session"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"

    def test_upload_fake_pdf_rejected(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post(
            "/api/documents/process",
            files={"file": ("fake.pdf", b"this is not a pdf", "application/pdf")},
            data={"session_id": sid},
        )
        assert resp.status_code == 400
        assert "not a valid PDF" in resp.json()["error"]["message"]


class TestValidation:
    def test_empty_question_422(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post("/api/query", json={"session_id": sid, "question": "   "})
        assert resp.status_code == 422

    def test_whitespace_only_stripped_ok(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post("/api/query", json={"session_id": sid, "question": "  sleep  "})
        assert resp.status_code == 200

    def test_question_too_long_422(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post("/api/query", json={"session_id": sid, "question": "a" * 1500})
        assert resp.status_code == 422

    def test_query_unknown_session_404(self, api_client):
        resp = api_client.post("/api/query", json={"session_id": "does-not-exist", "question": "hi"})
        assert resp.status_code == 404

    def test_missing_fields_422(self, api_client):
        resp = api_client.post("/api/query", json={})
        assert resp.status_code == 422

    def test_top_k_out_of_range_422(self, api_client):
        sid = api_client.post("/api/documents/demo", json={}).json()["session_id"]
        resp = api_client.post(
            "/api/query", json={"session_id": sid, "question": "sleep?", "top_k": 99}
        )
        assert resp.status_code == 422
