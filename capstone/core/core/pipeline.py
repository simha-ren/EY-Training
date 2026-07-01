"""Supervisor pipeline — orchestrates the agents hub-and-spoke (FIAA-style).

run_pipeline() takes the uploaded documents + a task/question and runs:
  intake → retrieval + research → report → (guardrails) → evaluator (RAGAS gate)
emitting metrics/logs throughout, and returns one structured result the
dashboard renders: per-agent traces, the report, RAGAS scores, the gate verdict,
guardrail audit, and timing.

Runs with zero API keys (offline LLM + TF-IDF retriever) = DEMO MODE.
"""
from __future__ import annotations

import time
import uuid
from typing import List, Dict, Any, Optional

from .observability import (track_agent, set_run_id, PIPELINE_LATENCY, ACTIVE_RUNS,
                            SUPERVISOR_ITERS, record_quality_score,
                            record_ragas_faithfulness, record_guardrail)
from .agents import (intake_agent, retrieval_agent, research_agent,
                     report_agent, evaluator_agent)
from .llm_backend import get_llm_client
from .guardrails import Guardrails
from .tracing import get_tracer

_guardrails = Guardrails()


def run_pipeline(documents: List[Dict[str, Any]], task: str,
                 retriever=None, llm=None) -> Dict[str, Any]:
    """Run the full multi-agent investigation and return a structured result."""
    run_id = uuid.uuid4().hex[:12]
    set_run_id(run_id)
    tracer = get_tracer()
    if llm is None:
        llm, backend = get_llm_client()
    else:
        backend = getattr(llm, "provider", None) or getattr(llm, "backend", None) or \
            ("claude" if getattr(llm, "online", False) else "offline")

    traces: List[Dict[str, Any]] = []
    started = time.perf_counter()
    ACTIVE_RUNS.inc()

    with tracer.run("proposalforge_pipeline", run_id=run_id,
                    metadata={"task": task, "backend": backend,
                              "documents": [d.get("filename") for d in documents]}) as run_span:
        try:
            # 1) Intake (supervisor -> incident)
            SUPERVISOR_ITERS.inc()
            with tracer.span("agent:intake") as sp:
                intake = intake_agent(documents, _traces=traces)
                sp.end(outputs={"summary": intake.get("summary")})

            # 2) Retrieval + research (supervisor fans out)
            SUPERVISOR_ITERS.inc()
            with tracer.span("agent:retrieval", inputs={"task": task}) as sp:
                retrieval = retrieval_agent(retriever, task, _traces=traces)
                sp.end(outputs={"sources": retrieval.get("sources"),
                                "hits": retrieval.get("hit_count")})
            with tracer.span("agent:research") as sp:
                research = research_agent(task, online=getattr(llm, "online", False), _traces=traces)
                sp.end(outputs={"summary": research.get("summary")})

            # 3) Report (converge)
            SUPERVISOR_ITERS.inc()
            with tracer.span("agent:report", inputs={"task": task}) as sp:
                report = report_agent(llm, retrieval["chunks"], retrieval["sources"],
                                      task, research["notes"], _traces=traces)
                sp.end(outputs={"score": report.get("score"), "mode": report.get("mode"),
                                "tokens": report.get("tokens"),
                                "narrative": (report.get("narrative") or "")[:500]})

            # 3b) Guardrails on the produced narrative
            guardrail_results = _guardrails.run_all_checks(
                report.get("narrative", ""), query=task,
                confidence=report.get("metrics", {}).get("confidence", 0.5),
                domain="general")
            triggered = [r for r in guardrail_results if r.triggered]
            for r in triggered:
                record_guardrail(getattr(r.guardrail_type, "value", "unknown"))
            guardrail_audit = [{
                "type": getattr(r.guardrail_type, "value", "unknown"),
                "triggered": r.triggered,
                "severity": getattr(r, "severity", "info"),
                "message": r.message,
            } for r in guardrail_results]

            # 4) Evaluator + RAGAS gate
            SUPERVISOR_ITERS.inc()
            with tracer.span("agent:evaluator") as sp:
                evaluation = evaluator_agent(report, retrieval["chunks"], task,
                                             len(triggered), _traces=traces)
                sp.end(outputs=evaluation.get("ragas"))

            record_quality_score(report.get("score", 0))
            record_ragas_faithfulness(evaluation["ragas"]["faithfulness"])

            elapsed = time.perf_counter() - started
            PIPELINE_LATENCY.observe(elapsed)

            # Roll up the run's key signal onto the LangSmith trace.
            run_span.set_outputs(
                backend=backend,
                demo_mode=not getattr(llm, "online", False),
                quality_score=report.get("score"),
                tokens=report.get("tokens"),
                ragas=evaluation["ragas"],
                gate=evaluation["gate"]["verdict"],
                guardrail_hits=len(triggered),
                latency_s=round(elapsed, 3),
            )

            return {
                "run_id": run_id,
                "task": task,
                "backend": backend,
                "demo_mode": not getattr(llm, "online", False),
                "tracing": tracer.provider,
                "intake": intake,
                "retrieval": retrieval,
                "research": research,
                "report": report,
                "guardrail_audit": guardrail_audit,
                "guardrail_hits": len(triggered),
                "evaluation": evaluation,
                "traces": traces,
                "trace_url": getattr(run_span, "url", None),
                "latency_s": round(elapsed, 3),
            }
        finally:
            ACTIVE_RUNS.dec()
