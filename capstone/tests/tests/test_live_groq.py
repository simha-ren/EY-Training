"""LIVE production tests — real Groq API (no DEMO mode).

These are skipped unless GROQ_API_KEY is set, so normal/offline CI stays green.
Run the real path with:  GROQ_API_KEY=gsk_... pytest tests/test_live_groq.py -v
They prove the app runs fully online with real LLM answers, real token usage,
and the pipeline reporting backend 'groq' (demo_mode False).
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="GROQ_API_KEY not set — live Groq tests skipped")

CTX = ("Scheme objective: promote millet cultivation. Subsidy INR 5000 per hectare. "
       "Key risk: low awareness among farmers.")


def test_groq_client_is_online():
    from core.core.groq_llm import GroqLLMClient
    c = GroqLLMClient()
    assert c.online is True


def test_answer_is_real_online_with_tokens():
    from core.core.groq_llm import GroqLLMClient
    r = GroqLLMClient().answer_question(CTX, "What subsidy is offered and to whom?")
    assert r["mode"] == "groq"           # real online, not offline fallback
    assert r["used_fallback"] is False
    assert r["answer"]
    assert r.get("tokens", 0) > 0        # real usage from the API


def test_backend_selector_picks_groq():
    from core.core.llm_backend import get_llm_client
    client, backend = get_llm_client()
    assert backend == "groq" and client.online is True


def test_pipeline_runs_online_no_demo():
    from core.core.retriever import get_retriever
    from core.core.pipeline import run_pipeline
    r = get_retriever(); r.build_documents([{"id": "d1", "name": "m.md", "text": CTX}])
    docs = [{"filename": "m.md", "content": CTX, "metadata": {"extension": ".md"},
             "document_id": "d1"}]
    res = run_pipeline(docs, "Summarize objective and risks.", retriever=r)
    assert res["backend"] == "groq"
    assert res["demo_mode"] is False
    assert res["report"]["mode"] == "groq"
    assert res["report"]["tokens"] > 0
