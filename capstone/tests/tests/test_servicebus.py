"""Service Bus job queue tests (pure logic + offline worker dispatch)."""
import os
os.environ.setdefault("VECTOR_BACKEND", "tfidf")
for _k in ("GROQ_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(_k, None)
import importlib


def test_disabled_without_config(monkeypatch):
    monkeypatch.delenv("SERVICEBUS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("SERVICEBUS_FQDN", raising=False)
    import core.servicebus as SB
    importlib.reload(SB)
    assert SB.is_enabled() is False
    assert SB.enqueue_job("j", "t", "c") is False   # graceful fallback, no raise


def test_message_roundtrip():
    import core.servicebus as SB
    importlib.reload(SB)
    body = SB.build_message("j1", "task here", "some context")
    p = SB.parse_message(body)
    assert p == {"job_id": "j1", "task": "task here", "context": "some context"}


def test_handle_job_runs_pipeline_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.db"))
    import core.servicebus as SB
    importlib.reload(SB)
    payload = {"job_id": "sb-1", "task": "objective and risks?",
               "context": "Subsidy INR 5000 per hectare. Risk: low awareness."}
    result = SB.handle_job(payload)
    assert result["report"]["score"] >= 1
    from core.job_store import JobStore
    job = JobStore().get("sb-1")
    assert job is not None and job["status"] == "done"