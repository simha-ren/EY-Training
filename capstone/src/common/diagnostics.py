"""Runtime diagnostics — reports which backends are actually wired and live.

Powers the "System status" panel so you can verify end-to-end wiring on the
deployed app: LLM connector, vector DB, tracing/observability provider, and
Azure Monitor (Application Insights). Everything is best-effort and never raises.
"""
from __future__ import annotations

import os
from typing import Dict, Any


def _llm_status() -> Dict[str, Any]:
    try:
        from src.agents.llm_backend import get_llm_client
        client, backend = get_llm_client()
        return {"backend": backend,
                "online": bool(getattr(client, "online", False)),
                "model": getattr(client, "model", None)}
    except Exception as e:
        return {"backend": "unknown", "online": False, "error": str(e)[:200]}


def _vector_status() -> Dict[str, Any]:
    try:
        from src.retrieval.retriever import get_retriever
        r = get_retriever()
        backend = getattr(r, "backend", type(r).__name__)
        return {"backend": backend,
                "pinecone_key_set": bool(os.getenv("PINECONE_API_KEY")),
                "index": os.getenv("PINECONE_INDEX", "")}
    except Exception as e:
        return {"backend": "unknown", "error": str(e)[:200]}


def _tracing_status() -> Dict[str, Any]:
    try:
        from src.common.tracing import dashboard_url
        d = dashboard_url()
        return {"provider": d.get("provider"), "enabled": bool(d.get("enabled")),
                "project": d.get("project")}
    except Exception as e:
        return {"provider": "unknown", "enabled": False, "error": str(e)[:200]}


def system_status() -> Dict[str, Any]:
    """Snapshot of live backends for the UI / a /status endpoint."""
    app_insights = bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))
    return {
        "llm": _llm_status(),
        "vector_db": _vector_status(),
        "tracing": _tracing_status(),
        "observability": {
            "azure_monitor": app_insights,
            "prometheus_metrics": "/metrics",
            "multiproc_dir": os.getenv("PROMETHEUS_MULTIPROC_DIR", ""),
        },
        "env": os.getenv("APP_ENV", "unknown"),
    }
