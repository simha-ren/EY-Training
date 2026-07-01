"""Tests for the multi-agent pipeline, agents, RAGAS gate and observability."""
import os
os.environ["VECTOR_BACKEND"] = "tfidf"
import pytest
from core.retriever import get_retriever
from core.pipeline import run_pipeline
from core.ragas_eval import evaluate_ragas, quality_gate
from core.observability import metrics_payload, track_agent

DOCS = [
    {"filename": "millet.md", "document_id": "d1", "metadata": {"extension": ".md"},
     "content": "Scheme objective: promote millet. Subsidy INR 5000 per hectare. "
                "Risk: low awareness among farmers."},
    {"filename": "solar.md", "document_id": "d2", "metadata": {"extension": ".md"},
     "content": "Rooftop solar. Capital subsidy 40 percent up to 3 kW."},
]


@pytest.fixture
def retriever():
    r = get_retriever()
    r.build_documents([{"id": d["document_id"], "name": d["filename"], "text": d["content"]}
                       for d in DOCS])
    return r


def test_pipeline_runs_demo_mode(retriever, monkeypatch):
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = run_pipeline(DOCS, "What is the subsidy and the risks?", retriever=retriever)
    assert res["run_id"]
    assert {t["agent"] for t in res["traces"]} == {
        "intake", "retrieval", "research", "report", "evaluator"}
    assert 1 <= res["report"]["score"] <= 10
    assert "overall" in res["evaluation"]["ragas"]
    assert isinstance(res["evaluation"]["gate"]["passed"], bool)


def test_ragas_scores_in_range():
    r = evaluate_ragas("subsidy INR 5000 per hectare", ["subsidy INR 5000 per hectare"], "subsidy?")
    for k in ("faithfulness", "answer_relevance", "context_recall", "overall"):
        assert 0.0 <= r[k] <= 1.0


def test_quality_gate_flags_low_faithfulness():
    gate = quality_gate({"faithfulness": 0.1, "answer_relevance": 0.9,
                         "context_recall": 0.9, "overall": 0.6}, 8, 0)
    assert gate["passed"] is False


def test_metrics_payload_bytes():
    payload, ctype = metrics_payload()
    assert isinstance(payload, (bytes, bytearray))


def test_track_agent_records_trace():
    traces = []

    @track_agent("dummy")
    def agent():
        return {"summary": "did a thing"}

    out = agent(_traces=traces)
    assert out["_agent"] == "dummy" and out["_status"] == "ok"
    assert traces and traces[0]["agent"] == "dummy"


def test_llm_backend_local_path(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    from core.llm_backend import get_llm_client
    client, backend = get_llm_client()
    assert backend == "offline"  # nothing configured -> offline
