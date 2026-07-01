"""Evaluation harness (doc Section 7) - RAGAS-aligned, offline proxies.

The real project gates releases on RAGAS metrics. RAGAS itself needs an LLM
judge, so here we compute transparent, deterministic *proxies* that track the
same intent and can run with zero credentials:

  routing_accuracy   - did the router pick the labelled domain?         (KPI: routing >= 0.95)
  retrieval_hit@k    - was the expected source document retrieved?      (Context Precision/Recall)
  context_recall     - fraction of reference terms present in context   (Context Recall >= 0.90)
  citation_coverage  - did the grounded answer carry >=1 citation?      (Faithfulness/coverage >= 0.95)

When an LLM key is configured these can be swapped for true RAGAS scoring.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from core.config import EVAL_DIR
from core.engine import Engine


def _context_recall(terms: List[str], context: str) -> float:
    if not terms:
        return 1.0
    low = context.lower()
    hit = sum(1 for t in terms if t.lower() in low)
    return hit / len(terms)


def run_eval(engine: Engine | None = None) -> Dict:
    engine = engine or Engine()
    samples = json.loads((EVAL_DIR / "golden_set.json").read_text())["samples"]

    rows, route_ok, hit_ok, recall_sum, cite_ok = [], 0, 0, 0.0, 0
    for s in samples:
        # routing measured WITHOUT a pin (pure classifier behaviour)
        r = engine.router.route(s["user_input"])
        routed = r.domain or (r.suggestions[0] if r.suggestions else None)
        routed_correct = routed == s["domain"]
        route_ok += int(routed_correct)

        # retrieval + answer measured WITH the gold domain (isolate retrieval)
        retrieved = engine.store.retrieve(s["user_input"], s["domain"])
        sources = [c.source for c, _ in retrieved]
        context = " ".join(c.text for c, _ in retrieved)
        hit = s["expected_source"] in sources
        hit_ok += int(hit)

        recall = _context_recall(s.get("reference_terms", []), context)
        recall_sum += recall

        from core.generation import compose
        ans = compose(s["user_input"], engine.domains[s["domain"]], retrieved, engine.llm)
        has_cite = len(ans.citations) > 0
        cite_ok += int(has_cite)

        rows.append({
            "question": s["user_input"],
            "gold_domain": s["domain"],
            "routed_domain": routed,
            "routing_ok": routed_correct,
            "retrieval_hit": hit,
            "context_recall": round(recall, 2),
            "citation": has_cite,
        })

    n = len(samples)
    summary = {
        "n": n,
        "routing_accuracy": round(route_ok / n, 3),
        "retrieval_hit@k": round(hit_ok / n, 3),
        "context_recall": round(recall_sum / n, 3),
        "citation_coverage": round(cite_ok / n, 3),
    }
    return {"summary": summary, "rows": rows}


if __name__ == "__main__":
    res = run_eval()
    print(json.dumps(res["summary"], indent=2))
    print()
    for row in res["rows"]:
        flag = "OK " if row["routing_ok"] and row["retrieval_hit"] else "!! "
        print(f"{flag}{row['gold_domain']:11s} hit={row['retrieval_hit']!s:5s} "
              f"recall={row['context_recall']:.2f}  {row['question'][:46]}")
