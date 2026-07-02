"""Lightweight RAGAS-style evaluation + a quality gate for the report.

No external RAGAS package required — these are transparent, dependency-free
heuristics over the report text, the retrieved context, and the task:
  * faithfulness     - is the report grounded in the retrieved context?
  * answer_relevance - does the report address the task/question?
  * context_recall   - did retrieval surface enough of the source?

The quality gate combines these with the report's own score to decide
APPROVE (human review) vs FLAG (needs attention), mirroring FIAA's gate.
"""
from __future__ import annotations

from typing import List, Dict, Any

from .metrics import compute_groundedness, _content_tokens


def _relevance(report_text: str, task: str) -> float:
    task_terms = set(_content_tokens(task))
    if not task_terms:
        return 0.7
    report_terms = set(_content_tokens(report_text))
    hits = len(task_terms & report_terms)
    return round(min(1.0, 0.4 + 0.6 * (hits / max(1, len(task_terms)))), 3)


def _context_recall(retrieved: List[str], report_text: str) -> float:
    if not retrieved:
        return 0.0
    report_terms = set(_content_tokens(report_text))
    used = 0
    for chunk in retrieved:
        chunk_terms = set(_content_tokens(chunk))
        if chunk_terms and len(chunk_terms & report_terms) / len(chunk_terms) > 0.05:
            used += 1
    return round(used / len(retrieved), 3)


def evaluate_ragas(report_text: str, retrieved_chunks: List[str], task: str) -> Dict[str, float]:
    context = "\n".join(retrieved_chunks)
    faithfulness = compute_groundedness(report_text, context) if context else 0.5
    relevance = _relevance(report_text, task)
    recall = _context_recall(retrieved_chunks, report_text)
    overall = round((faithfulness + relevance + recall) / 3, 3)
    return {
        "faithfulness": faithfulness,
        "answer_relevance": relevance,
        "context_recall": recall,
        "overall": overall,
    }


def quality_gate(ragas: Dict[str, float], report_score: float,
                 guardrail_hits: int, threshold: float = 0.6) -> Dict[str, Any]:
    """Decide whether the report passes. report_score is 0-10."""
    reasons: List[str] = []
    passed = True

    if ragas["faithfulness"] < threshold:
        passed = False
        reasons.append(f"Low faithfulness ({ragas['faithfulness']:.0%}) — "
                       "report not well grounded in sources.")
    if ragas["answer_relevance"] < threshold:
        passed = False
        reasons.append(f"Low relevance ({ragas['answer_relevance']:.0%}) — "
                       "report may not address the task.")
    if guardrail_hits > 0:
        passed = False
        reasons.append(f"{guardrail_hits} guardrail hit(s) flagged.")
    if report_score < 5:
        reasons.append(f"Report self-score is low ({report_score}/10).")

    verdict = "APPROVE — route to human review" if passed else "FLAG — needs attention"
    return {
        "passed": passed,
        "verdict": verdict,
        "reasons": reasons or ["All checks passed."],
        "threshold": threshold,
    }
