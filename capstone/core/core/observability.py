"""Observability for the agent pipeline (FIAA-style, three pillars in one place).

Every agent call flows through @track_agent, which emits to:
  * structured JSON logs (structlog if present, else stdlib logging) with run_id
  * Prometheus metrics (prometheus_client if present, else a no-op shim)

All dependencies are optional — if a library is missing the corresponding pillar
degrades to a no-op so the pipeline always runs (DEMO-mode friendly).
"""
from __future__ import annotations

import os
import time
import json
import functools
import logging
from pathlib import Path
from contextvars import ContextVar
from typing import Optional

_run_id: ContextVar[str] = ContextVar("run_id", default="-")

LOG_DIR = Path(os.getenv("PF_LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------- logging
try:
    import structlog

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact := (lambda _l, _m, ed: {
                k: ("***redacted***" if any(s in k.lower()
                    for s in ("key", "token", "secret", "password")) else v)
                for k, v in ed.items()}),
            structlog.processors.JSONRenderer(),
        ],
        cache_logger_on_first_use=True,
    )
    _slog = structlog.get_logger("pf")

    def _log(event: str, **kw):
        _slog.info(event, run_id=_run_id.get(), **kw)
except Exception:  # pragma: no cover - fallback path
    logging.basicConfig(level=logging.INFO)
    _stdlog = logging.getLogger("pf")

    def _log(event: str, **kw):
        kw["run_id"] = _run_id.get()
        _stdlog.info("%s %s", event, json.dumps(kw, default=str))


def _write_run_log(record: dict):
    """Append one JSON line to the per-run and global log files."""
    try:
        line = json.dumps(record, default=str)
        (LOG_DIR / f"run_{_run_id.get()}.jsonl").open("a").write(line + "\n")
        (LOG_DIR / "pf.jsonl").open("a").write(line + "\n")
    except Exception:
        pass


def set_run_id(run_id: str):
    _run_id.set(run_id)


def get_run_id() -> str:
    return _run_id.get()


# ------------------------------------------------------------------- metrics
class _NoopMetric:
    def labels(self, *a, **k): return self
    def inc(self, *a, **k): pass
    def observe(self, *a, **k): pass
    def set(self, *a, **k): pass


try:
    from prometheus_client import (Counter, Histogram, Gauge, generate_latest,
                                    CONTENT_TYPE_LATEST, CollectorRegistry)

    _MP_DIR = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if _MP_DIR:
        Path(_MP_DIR).mkdir(parents=True, exist_ok=True)

    # In multiprocess mode, gauges need an aggregation mode across processes.
    _gkw = {"multiprocess_mode": "livemostrecent"} if _MP_DIR else {}
    _gkw_sum = {"multiprocess_mode": "livesum"} if _MP_DIR else {}

    AGENT_CALLS = Counter("pf_agent_calls_total", "Agent calls", ["agent", "status"])
    AGENT_LATENCY = Histogram("pf_agent_latency_seconds", "Agent latency", ["agent"])
    LLM_TOKENS = Counter("pf_llm_tokens_total", "LLM tokens (approx)", ["agent"])
    GUARDRAIL_HITS = Counter("pf_guardrail_hits_total", "Guardrail hits", ["kind"])
    PIPELINE_LATENCY = Histogram("pf_pipeline_latency_seconds", "Pipeline latency")
    LAST_SCORE = Gauge("pf_last_quality_score", "Last report quality score (0-10)", **_gkw)
    ACTIVE_RUNS = Gauge("pf_active_runs", "Active pipeline runs", **_gkw_sum)
    SUPERVISOR_ITERS = Counter("pf_supervisor_iterations_total", "Supervisor iterations")
    RAGAS_FAITHFULNESS = Gauge("pf_ragas_faithfulness", "Last RAGAS faithfulness", **_gkw)
    _PROM = True
except Exception:  # pragma: no cover
    AGENT_CALLS = AGENT_LATENCY = LLM_TOKENS = GUARDRAIL_HITS = _NoopMetric()
    PIPELINE_LATENCY = LAST_SCORE = ACTIVE_RUNS = SUPERVISOR_ITERS = RAGAS_FAITHFULNESS = _NoopMetric()
    _PROM = False

    def generate_latest(*a, **k):  # type: ignore
        return b"# prometheus_client not installed\n"
    CONTENT_TYPE_LATEST = "text/plain"


def prometheus_available() -> bool:
    return _PROM


def metrics_payload():
    """Return (bytes, content_type) for a /metrics endpoint.

    In multiprocess mode (PROMETHEUS_MULTIPROC_DIR set) this aggregates metrics
    written by *all* processes (Streamlit dashboard + FastAPI API), so a pipeline
    run from either one shows up on the scraped endpoint.
    """
    if not _PROM:
        return generate_latest(), CONTENT_TYPE_LATEST
    mp_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if mp_dir:
        try:
            from prometheus_client import multiprocess
            registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(registry)
            return generate_latest(registry), CONTENT_TYPE_LATEST
        except Exception:
            pass
    return generate_latest(), CONTENT_TYPE_LATEST


def record_guardrail(kind: str):
    GUARDRAIL_HITS.labels(kind=kind).inc()


def record_ragas_faithfulness(value: float):
    RAGAS_FAITHFULNESS.set(value)


def record_quality_score(value: float):
    LAST_SCORE.set(value)


# --------------------------------------------------------------- decorator
def track_agent(agent_name: str):
    """Wrap an agent callable: time it, log it, and emit metrics.

    The wrapped function must return a dict; we annotate it with timing/status
    and append a trace entry to the shared `traces` list if one is passed via
    the `_traces` kwarg.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            traces = kwargs.pop("_traces", None)
            start = time.perf_counter()
            status = "ok"
            try:
                result = fn(*args, **kwargs)
                if not isinstance(result, dict):
                    result = {"output": result}
                return result
            except Exception as e:
                status = "error"
                result = {"error": str(e)}
                raise
            finally:
                elapsed = time.perf_counter() - start
                AGENT_CALLS.labels(agent=agent_name, status=status).inc()
                AGENT_LATENCY.labels(agent=agent_name).observe(elapsed)
                tokens = 0
                try:
                    tokens = int(result.get("tokens", 0)) if isinstance(result, dict) else 0
                except Exception:
                    tokens = 0
                if tokens:
                    LLM_TOKENS.labels(agent=agent_name).inc(tokens)
                rec = {"event": "agent_complete", "agent": agent_name,
                       "status": status, "latency_s": round(elapsed, 3),
                       "run_id": _run_id.get()}
                _log("agent_complete", agent=agent_name, status=status,
                     latency_s=round(elapsed, 3))
                _write_run_log(rec)
                if isinstance(result, dict):
                    result.setdefault("_agent", agent_name)
                    result["_latency_s"] = round(elapsed, 3)
                    result["_status"] = status
                    if traces is not None:
                        traces.append({"agent": agent_name, "status": status,
                                       "latency_s": round(elapsed, 3),
                                       "summary": result.get("summary", "")})
        return wrapper
    return decorator
