"""The specialist agents for the proposal-analysis pipeline (FIAA-style).

Hub-and-spoke: a Supervisor (in pipeline.py) routes work to these agents. Each is
wrapped with @track_agent so it emits logs + Prometheus metrics and contributes a
trace entry. Every agent degrades gracefully so the pipeline runs with zero keys
(DEMO mode) using the offline LLM client + TF-IDF retriever.
"""
from __future__ import annotations

from typing import List, Dict, Any

from .observability import track_agent
from .metrics import evaluate_answer
from .ragas_eval import evaluate_ragas, quality_gate


@track_agent("intake")
def intake_agent(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse & classify the incoming documents."""
    kinds = {}
    total_chars = 0
    for d in documents:
        ext = d.get("metadata", {}).get("extension", "?")
        kinds[ext] = kinds.get(ext, 0) + 1
        total_chars += len(d.get("content", ""))
    names = [d["filename"] for d in documents]
    return {
        "document_count": len(documents),
        "documents": names,
        "kinds": kinds,
        "total_chars": total_chars,
        "summary": f"Classified {len(documents)} document(s): {', '.join(names) or '—'}",
    }


@track_agent("retrieval")
def retrieval_agent(retriever, task: str, top_k: int = 5) -> Dict[str, Any]:
    """RAG: pull the most relevant chunks across all documents."""
    hits = []
    if retriever is not None:
        try:
            hits = retriever.search(task, top_k=top_k)
        except Exception:
            hits = []
    chunks = [h["text"] for h in hits]
    sources = []
    for h in hits:
        if h["source"] not in sources:
            sources.append(h["source"])
    return {
        "chunks": chunks,
        "sources": sources,
        "hit_count": len(hits),
        "summary": f"Retrieved {len(hits)} chunk(s) from {len(sources)} source(s)",
    }


@track_agent("research")
def research_agent(task: str, online: bool = False) -> Dict[str, Any]:
    """External research. Offline stub by default (no network dependency)."""
    notes = [
        "Benchmark the proposal against comparable industry initiatives.",
        "Confirm regulatory / compliance constraints relevant to the domain.",
        "Validate cost and timeline assumptions against market norms.",
    ]
    return {
        "notes": notes,
        "online": online,
        "summary": "Compiled 3 external research note(s) (offline knowledge stub)",
    }


@track_agent("report")
def report_agent(llm, retrieved_chunks: List[str], sources: List[str],
                 task: str, research_notes: List[str]) -> Dict[str, Any]:
    """Produce the structured report + a 1-10 quality/priority score."""
    context = "\n\n".join(f"[Source: {s}]\n{c}" for s, c in
                          zip(sources + [""] * len(retrieved_chunks), retrieved_chunks))
    if not context:
        context = "\n\n".join(retrieved_chunks)

    answer = llm.answer_question(context, task, allow_general_knowledge=True)
    narrative = answer.get("answer", "")
    confidence = answer.get("confidence", 0.5)
    mode = answer.get("mode", "offline")

    analysis = llm.analyze_document(context[:5000]) if context else {}

    metrics = evaluate_answer(narrative, context, confidence)
    score = max(1, min(10, round(metrics["accuracy_score"] * 10)))

    evidence = [{"source": s, "snippet": (c[:160] + "…") if len(c) > 160 else c}
                for s, c in zip(sources, retrieved_chunks)]

    actions = [
        "Review the highlighted objective and confirm scope with stakeholders.",
        "Address the identified challenges before approval.",
        "Validate the proposed solutions against the research notes.",
    ]

    # Real token usage from the LLM when available; else approximate.
    real_tokens = answer.get("tokens") or 0
    approx_tokens = len(context.split()) + len(narrative.split())

    return {
        "headline": f"Proposal analysis — score {score}/10",
        "narrative": narrative,
        "objective": analysis.get("objective", ""),
        "challenges": analysis.get("challenges", []),
        "solutions": analysis.get("proposed_solutions", []),
        "insights": analysis.get("insights", []),
        "actions": actions,
        "evidence": evidence,
        "score": score,
        "mode": mode,
        "metrics": metrics,
        "tokens": real_tokens or approx_tokens,
        "summary": f"Drafted report (score {score}/10, mode {mode})",
    }


@track_agent("evaluator")
def evaluator_agent(report: Dict[str, Any], retrieved_chunks: List[str],
                    task: str, guardrail_hits: int) -> Dict[str, Any]:
    """RAGAS quality gate over the report."""
    report_text = " ".join([
        report.get("narrative", ""),
        report.get("objective", ""),
        " ".join(report.get("challenges", []) or []),
        " ".join(report.get("solutions", []) or []),
    ])
    ragas = evaluate_ragas(report_text, retrieved_chunks, task)
    gate = quality_gate(ragas, report.get("score", 0), guardrail_hits)
    return {
        "ragas": ragas,
        "gate": gate,
        "summary": f"RAGAS overall {ragas['overall']:.0%} · {gate['verdict']}",
    }
