"""RAGAS evaluation with LLM-graded metrics.

Three layers, chosen automatically:
  1. **Real `ragas` library** — used when `ragas` imports cleanly AND a LangChain
     LLM can be built (OpenAI or Anthropic key). Note: `ragas` currently pins an
     older `langchain-core` that conflicts with `langgraph`; in that case this
     layer is skipped and layer 2 is used instead.
  2. **LLM-graded via the app's own Claude/Groq client** — the model judges
     faithfulness, answer relevancy, context precision and context recall with a
     structured rubric. Genuinely LLM-graded, no extra dependencies, no conflict.
  3. **Heuristic** — the key-free lexical fallback (see ragas_eval.py).

Every layer returns the same shape:
    {faithfulness, answer_relevance, context_precision, context_recall,
     overall, mode}
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

METRIC_KEYS = ["faithfulness", "answer_relevance", "context_precision", "context_recall"]


def _clamp01(v) -> float:
    try:
        return round(max(0.0, min(1.0, float(v))), 3)
    except (TypeError, ValueError):
        return 0.0


def _pack(f, r, p, rec, mode) -> Dict[str, float]:
    vals = {"faithfulness": _clamp01(f), "answer_relevance": _clamp01(r),
            "context_precision": _clamp01(p), "context_recall": _clamp01(rec)}
    vals["overall"] = round(sum(vals[k] for k in METRIC_KEYS) / len(METRIC_KEYS), 3)
    vals["mode"] = mode
    return vals


# --------------------------------------------------------------------------- #
# Layer 1 — real ragas library (guarded; auto-skips on version conflict)
# --------------------------------------------------------------------------- #
def ragas_available() -> bool:
    try:
        import ragas  # noqa: F401
        from ragas import evaluate  # noqa: F401
        from ragas.dataset_schema import SingleTurnSample, EvaluationDataset  # noqa
        return True
    except Exception:
        return False


def _build_ragas_llm():
    """Wrap an available LangChain chat model for ragas. Returns None if none."""
    try:
        from ragas.llms import LangchainLLMWrapper
        if os.getenv("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI
            return LangchainLLMWrapper(ChatOpenAI(model=os.getenv(
                "RAGAS_OPENAI_MODEL", "gpt-4o-mini"), temperature=0))
        key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if key:
            from langchain_anthropic import ChatAnthropic
            return LangchainLLMWrapper(ChatAnthropic(
                model=os.getenv("RAGAS_ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
                temperature=0, api_key=key))
    except Exception:
        return None
    return None


def _build_ragas_embeddings():
    try:
        from ragas.embeddings import LangchainEmbeddingsWrapper
        if os.getenv("OPENAI_API_KEY"):
            from langchain_openai import OpenAIEmbeddings
            return LangchainEmbeddingsWrapper(OpenAIEmbeddings())
        from langchain_huggingface import HuggingFaceEmbeddings
        return LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(
            model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")))
    except Exception:
        return None


def _try_real_ragas(question: str, answer: str,
                    contexts: List[str]) -> Optional[Dict[str, float]]:
    if not ragas_available():
        return None
    llm = _build_ragas_llm()
    if llm is None:
        return None
    try:
        from ragas import evaluate
        from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
        from ragas.metrics import (Faithfulness, ResponseRelevancy,
                                    LLMContextPrecisionWithoutReference)
        emb = _build_ragas_embeddings()
        sample = SingleTurnSample(user_input=question, response=answer,
                                  retrieved_contexts=contexts or [""])
        metrics = [Faithfulness(llm=llm),
                   ResponseRelevancy(llm=llm, embeddings=emb),
                   LLMContextPrecisionWithoutReference(llm=llm)]
        res = evaluate(EvaluationDataset([sample]), metrics=metrics)
        df = res.to_pandas()
        row = df.iloc[0].to_dict()

        def g(*names):
            for n in names:
                if n in row and row[n] == row[n]:   # not NaN
                    return row[n]
            return 0.0
        return _pack(g("faithfulness"),
                     g("answer_relevancy", "response_relevancy"),
                     g("llm_context_precision_without_reference", "context_precision"),
                     g("context_recall", "llm_context_recall"),
                     mode="ragas library (LLM)")
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Layer 2 — LLM-graded via the app's own client
# --------------------------------------------------------------------------- #
_JUDGE_SYS = ("You are a strict RAG evaluation judge. You score four metrics from "
              "0.0 to 1.0 based only on the evidence provided. Return ONLY JSON.")


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _llm_graded(question: str, answer: str, contexts: List[str],
                client) -> Optional[Dict[str, float]]:
    if client is None or not hasattr(client, "complete"):
        return None
    ctx = "\n\n".join(contexts or [])[:6000]
    user = (
        f"Question:\n{question}\n\nRetrieved context:\n{ctx or '(none)'}\n\n"
        f"Answer:\n{answer or '(empty)'}\n\n"
        "Score these RAGAS metrics from 0.0 to 1.0:\n"
        "- faithfulness: is the answer supported by the retrieved context "
        "(no hallucination)?\n"
        "- answer_relevancy: does the answer directly address the question?\n"
        "- context_precision: how much of the retrieved context is relevant to "
        "the question?\n"
        "- context_recall: does the retrieved context cover what's needed to "
        "answer the question?\n\n"
        'Return ONLY this JSON with numeric values: '
        '{"faithfulness":0.0,"answer_relevancy":0.0,'
        '"context_precision":0.0,"context_recall":0.0}')
    try:
        raw = client.complete(_JUDGE_SYS, user)
    except Exception:
        raw = None
    data = _extract_json(raw or "")
    if not data:
        return None
    return _pack(data.get("faithfulness"), data.get("answer_relevancy"),
                 data.get("context_precision"), data.get("context_recall"),
                 mode="LLM-graded (Claude/Groq)")


# --------------------------------------------------------------------------- #
# Layer 3 — heuristic fallback
# --------------------------------------------------------------------------- #
def _heuristic(question: str, answer: str, contexts: List[str]) -> Dict[str, float]:
    from src.retrieval.ragas_eval import evaluate_ragas
    base = evaluate_ragas(answer, contexts, question)
    # derive a simple context_precision: overlap of context terms with the answer
    ans_terms = set(re.findall(r"[a-z]{4,}", (answer or "").lower()))
    prec_vals = []
    for c in (contexts or []):
        cterms = set(re.findall(r"[a-z]{4,}", c.lower()))
        if cterms:
            prec_vals.append(len(cterms & ans_terms) / len(cterms))
    precision = sum(prec_vals) / len(prec_vals) if prec_vals else base.get("context_recall", 0.0)
    return _pack(base.get("faithfulness", 0.0), base.get("answer_relevance", 0.0),
                 precision, base.get("context_recall", 0.0), mode="heuristic (offline)")


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def evaluate_metrics(question: str, answer: str, contexts: List[str],
                     client=None, online: bool = False) -> Dict[str, float]:
    """Return RAGAS metrics using the best available layer."""
    if online:
        r = _try_real_ragas(question, answer, contexts)
        if r is not None:
            return r
        r = _llm_graded(question, answer, contexts, client)
        if r is not None:
            return r
    return _heuristic(question, answer, contexts)
