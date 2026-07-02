"""Unit tests for the retriever (TF-IDF default) and the job store."""
import os

from core.retriever import get_retriever, chunk_text


def test_chunk_text_splits_long_input():
    text = "word " * 500
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(isinstance(c, str) and c for c in chunks)


def test_retriever_build_and_query_returns_relevant_chunk():
    r = get_retriever()
    context = (
        "The Kisan Credit Card scheme offers crop loans up to 3 lakh rupees. "
        "Health insurance covers cashless hospitalization at network hospitals. "
        "Mutual funds carry market risk and are not guaranteed."
    )
    r.build(context, "doc1", "knowledge")
    # The retriever exposes a query/retrieve method; find whichever exists.
    query = "How much can a farmer borrow?"
    results = None
    for method in ("query", "retrieve", "search"):
        fn = getattr(r, method, None)
        if callable(fn):
            results = fn(query)
            break
    assert results is not None, "retriever should expose a query method"
    # Results may be strings or dicts; stringify and check topical relevance.
    joined = " ".join(str(x) for x in results).lower()
    assert "loan" in joined or "kisan" in joined or "3 lakh" in joined


def test_job_store_submit_and_get(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.db"))
    from core.job_store import JobStore
    store = JobStore()
    job_id = store.submit("Analyze this", "Some context about loans.")
    assert isinstance(job_id, str) and job_id
    job = store.get(job_id)
    assert job is not None
    assert job.get("status") in {"queued", "pending", "submitted", "running", "accepted"}


def test_job_store_set_result(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_DB_PATH", str(tmp_path / "jobs.db"))
    from core.job_store import JobStore
    store = JobStore()
    job_id = store.submit("task", "context")
    store.set_result(job_id, {"summary": "done"}, status="done")
    job = store.get(job_id)
    assert job["status"] == "done"
    assert job["result"]["summary"] == "done"
