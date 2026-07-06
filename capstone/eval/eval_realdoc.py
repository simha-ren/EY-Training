"""End-to-end evaluation against a REAL uploaded document (not the seed corpus).

Ingests a document from eval/sample_docs/ into a fresh retriever, runs a set of
questions through the full pipeline using the configured LLM connector (Azure
OpenAI / Groq / Claude, or the offline extractive fallback with no key), and
scores each answer for groundedness and whether it contains the expected facts.

Run:
    python eval/eval_realdoc.py
    python eval/eval_realdoc.py --doc eval/sample_docs/sample_proposal.md
Exits non-zero if the aggregate score falls below the threshold, so it can gate
CI. Works with zero credentials (offline mode); richer with an LLM key set.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.retriever import get_retriever
from src.orchestrator.pipeline import run_pipeline
from src.agents.llm_backend import get_llm_client
from src.common.metrics import compute_groundedness

# Questions with the facts a correct, grounded answer should surface.
CHECKS = [
    {"q": "What is the total programme budget and how is it co-funded?",
     "must_include_any": ["48 crore", "48crore", "60%", "40%"]},
    {"q": "Who is eligible and how much input subsidy do they receive?",
     "must_include_any": ["2 hectares", "5,000", "5000", "small and marginal"]},
    {"q": "What are the key risks and how are they mitigated?",
     "must_include_any": ["awareness", "monsoon", "market", "demonstration", "buy-back", "drought"]},
    {"q": "How is success defined in monitoring and evaluation?",
     "must_include_any": ["80%", "mid-term", "kpi", "targets"]},
]

GROUNDEDNESS_MIN = 0.30   # offline extractive proxy; raise when using a real LLM judge
PASS_RATE_MIN = 0.75      # >=75% of checks must pass to gate CI green


def _answer_text(result: dict) -> str:
    """Pull the answer text out of the pipeline result, tolerant of shape."""
    rep = result.get("report")
    if isinstance(rep, dict):
        parts = [rep.get("headline"), rep.get("narrative") or rep.get("summary")]
        for extra in ("objective", "challenges", "solutions", "insights"):
            v = rep.get(extra)
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(x) for x in v)
        text = "\n".join(p for p in parts if p)
        if text.strip():
            return text
    for key in ("answer", "final_answer", "response", "output", "narrative", "summary"):
        v = result.get(key)
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, dict) and isinstance(v.get("text"), str):
            return v["text"]
    inner = result.get("result")
    if isinstance(inner, dict):
        return _answer_text(inner)
    return json.dumps(result)[:2000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default="eval/sample_docs/sample_proposal.md")
    args = ap.parse_args()

    doc_path = Path(args.doc)
    if not doc_path.exists():
        print(f"Document not found: {doc_path}")
        return 2
    content = doc_path.read_text(encoding="utf-8")

    llm, backend = get_llm_client()
    print(f"LLM backend: {backend}    document: {doc_path.name} ({len(content)} chars)\n")

    retriever = get_retriever()
    retriever.build(content, "realdoc", doc_path.name)
    documents = [{"filename": doc_path.name, "content": content,
                  "metadata": {"extension": doc_path.suffix}, "document_id": "realdoc"}]

    passed, rows = 0, []
    for c in CHECKS:
        result = run_pipeline(documents, c["q"], retriever=retriever, llm=llm)
        result = result.get("result", result) if isinstance(result, dict) else result
        answer = _answer_text(result if isinstance(result, dict) else {"answer": str(result)})
        grounded = compute_groundedness(answer, content)
        has_fact = any(tok.lower() in answer.lower() for tok in c["must_include_any"])
        ok = has_fact and grounded >= GROUNDEDNESS_MIN
        passed += int(ok)
        rows.append((ok, grounded, c["q"], answer))
        print(f"[{'PASS' if ok else 'FAIL'}] grounded={grounded:.2f} fact={has_fact}  {c['q']}")
        print(f"        -> {answer[:160].strip().replace(chr(10),' ')}\n")

    rate = passed / len(CHECKS)
    print("-" * 60)
    print(f"E2E real-doc eval: {passed}/{len(CHECKS)} passed  (rate={rate:.2f}, "
          f"threshold={PASS_RATE_MIN})  backend={backend}")
    if rate < PASS_RATE_MIN:
        print("RESULT: FAIL — below threshold.")
        return 1
    print("RESULT: PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
