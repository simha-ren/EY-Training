"""Integration tests — exercise the real FastAPI app end to end (offline)."""
import io

from tests.conftest import SAMPLE_CONTEXT


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "service" in body


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert len(r.text) > 0  # Prometheus exposition text


def test_pipeline_run_synchronous(client):
    r = client.post("/api/v1/pipeline/run", json={
        "query": "How much can a farmer borrow?",
        "context": SAMPLE_CONTEXT,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "result" in body
    assert body["result"]["task"] == "How much can a farmer borrow?"


def test_pipeline_submit_and_poll(client):
    r = client.post("/api/v1/pipeline/submit", json={
        "query": "Summarize the loan scheme.",
        "context": SAMPLE_CONTEXT,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "accepted"
    job_id = body["job_id"]
    assert job_id

    # The background task runs in-process with TestClient; the job should be
    # listed (status may be running or done depending on timing).
    r2 = client.get("/api/v1/pipeline/jobs")
    assert r2.status_code == 200
    jobs = r2.json()["jobs"]
    assert any(j["id"] == job_id for j in jobs)


def test_pipeline_job_not_found(client):
    r = client.get("/api/v1/pipeline/jobs/does-not-exist")
    assert r.status_code == 404


def test_query_document(client):
    r = client.post("/api/v1/documents/doc-123/query", json={
        "document_id": "doc-123",
        "query": "What interest rate applies?",
        "context": SAMPLE_CONTEXT,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "answer" in body
    assert "evaluation" in body
    assert "guardrails" in body


def test_upload_rejects_unsupported_type(client):
    files = {"file": ("bad.zip", io.BytesIO(b"PK\x03\x04"), "application/zip")}
    r = client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 400


def test_upload_accepts_txt(client):
    files = {"file": ("note.txt", io.BytesIO(b"crop loans at 4 percent"), "text/plain")}
    r = client.post("/api/v1/documents/upload", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["document_id"]


def test_analytics_summary(client):
    r = client.get("/api/v1/analytics/summary")
    assert r.status_code == 200
    assert r.json()["success"] is True
