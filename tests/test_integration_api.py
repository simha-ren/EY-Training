"""Integration tests for the FastAPI service (real ASGI via TestClient).

Covers health, metrics, synchronous pipeline, and the async webhook + job store.
Runs fully offline (DEMO mode) so it's safe in CI.
"""
import os
os.environ.setdefault("VECTOR_BACKEND", "tfidf")
for _k in ("GROQ_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(_k, None)

import pytest
from fastapi.testclient import TestClient
import api_server

client = TestClient(api_server.app)

CTX = ("Scheme objective: promote millet cultivation. Subsidy INR 5000 per hectare. "
       "Key risk: low awareness among farmers. Recommended action: awareness drives.")


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_metrics_endpoint():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "pf_" in r.text or "python_" in r.text


def test_pipeline_run_sync():
    r = client.post("/api/v1/pipeline/run", json={"query": "objective and risks?", "context": CTX})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    res = body["result"]
    assert {t["agent"] for t in res["traces"]} == {
        "intake", "retrieval", "research", "report", "evaluator"}
    assert 1 <= res["report"]["score"] <= 10


def test_webhook_submit_then_poll():
    r = client.post("/api/v1/pipeline/submit", json={"query": "summarize", "context": CTX})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    assert r.json()["status"] == "accepted"
    # BackgroundTasks in TestClient run synchronously after the response, so the
    # job should be retrievable and completed.
    got = client.get(f"/api/v1/pipeline/jobs/{job_id}")
    assert got.status_code == 200
    assert got.json()["job"]["id"] == job_id
    listing = client.get("/api/v1/pipeline/jobs")
    assert any(j["id"] == job_id for j in listing.json()["jobs"])


def test_unknown_job_404():
    assert client.get("/api/v1/pipeline/jobs/does-not-exist").status_code == 404
