"""Retrieval cache/latency + tracing fallback tests."""
import os
os.environ["VECTOR_BACKEND"] = "tfidf"
from core.retriever import get_retriever
from core.tracing import get_tracer

DOCS = [{"id": "1", "name": "d.md", "text": "Subsidy INR 5000 per hectare. Risk: low awareness. " * 5}]


def test_cache_returns_same_and_is_fast():
    r = get_retriever(); r.build_documents(DOCS)
    r.search("subsidy?", top_k=3)            # cold
    first = r.search("subsidy?", top_k=3)
    assert r.last_latency_ms == 0.0          # served from cache
    second = r.search("subsidy?", top_k=3)
    assert first == second


def test_cache_invalidates_on_rebuild():
    r = get_retriever(); r.build_documents(DOCS)
    r.search("subsidy?", top_k=3)
    r.build_documents([{"id": "2", "name": "e.md", "text": "Completely different solar content."}])
    hits = r.search("solar", top_k=1)
    assert hits and hits[0]["source"] == "e.md"


def test_tracer_noop_without_keys(monkeypatch):
    for k in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY",
              "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    import importlib, core.tracing as T
    importlib.reload(T)
    t = T.get_tracer()
    assert t.provider == "none"
    with t.run("x"):
        with t.span("y") as s:
            s.end(outputs={"ok": 1})
    importlib.reload(T)


def test_tracer_handle_sets_outputs():
    from core.tracing import _NoopTracer
    t = _NoopTracer()
    with t.run("r") as run:
        run.set_outputs(score=8, ragas={"overall": 0.7})
        with t.span("s") as sp:
            sp.set_outputs(tokens=100)
            assert sp.outputs["tokens"] == 100
        assert run.outputs["score"] == 8
