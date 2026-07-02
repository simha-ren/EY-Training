"""LLM observability via LangSmith (primary) or Langfuse, with a no-op fallback.

This is the app's observability layer (replacing Prometheus/Grafana). Every
pipeline run and each agent becomes a traced span carrying real signal -
latency, token usage, RAGAS scores, the quality gate, and guardrail hits - so
you can inspect and debug runs as trace trees in LangSmith.

Enable LangSmith:
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=ls-...
    LANGCHAIN_PROJECT=proposalforge      # optional
Enable Langfuse (open-source, self-hostable) instead:
    LANGFUSE_PUBLIC_KEY=pk-...  LANGFUSE_SECRET_KEY=sk-...  [LANGFUSE_HOST=...]
With neither set, tracing is a no-op so the app still runs.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict, Any


class _Handle:
    """A span/run handle that accumulates outputs; .end() flushes them."""
    def __init__(self, sink=None):
        self._sink = sink
        self.outputs: Dict[str, Any] = {}
        self.url = None

    def set_outputs(self, **kw):
        self.outputs.update(kw)

    def end(self, **kw):
        self.outputs.update(kw)
        if self._sink:
            try:
                self._sink(self.outputs)
            except Exception:
                pass
            self._sink = None


class _NoopTracer:
    provider = "none"
    enabled = False

    @contextmanager
    def run(self, name, run_id=None, metadata=None):
        yield _Handle()

    @contextmanager
    def span(self, name, inputs=None, metadata=None):
        yield _Handle()


class _LangSmithTracer:
    provider = "langsmith"
    enabled = True

    def __init__(self):
        from langsmith import Client  # noqa: F401
        self.client = Client()
        self.project = os.getenv("LANGCHAIN_PROJECT", "proposalforge")

    @contextmanager
    def run(self, name, run_id=None, metadata=None):
        from langsmith.run_trees import RunTree
        rt = RunTree(name=name, run_type="chain",
                     inputs={"run_id": run_id, **(metadata or {})},
                     project_name=self.project)
        rt.post()
        h = _Handle(sink=lambda o: (rt.end(outputs=o), rt.patch()))
        try:
            h.url = self.client.get_run_url(run=rt)
        except Exception:
            h.url = None
        try:
            yield h
        finally:
            h.end()

    @contextmanager
    def span(self, name, inputs=None, metadata=None):
        from langsmith.run_trees import RunTree
        rt = RunTree(name=name, run_type="tool", inputs=inputs or {},
                     extra={"metadata": metadata or {}}, project_name=self.project)
        rt.post()
        h = _Handle(sink=lambda o: (rt.end(outputs=o), rt.patch()))
        try:
            yield h
        finally:
            h.end()


class _LangfuseTracer:
    provider = "langfuse"
    enabled = True

    def __init__(self):
        from langfuse import Langfuse  # noqa: F401
        self.client = Langfuse()
        self._trace = None

    @contextmanager
    def run(self, name, run_id=None, metadata=None):
        self._trace = self.client.trace(name=name, id=run_id, metadata=metadata or {})
        h = _Handle(sink=lambda o: self._trace.update(output=o))
        try:
            yield h
        finally:
            h.end()
            try:
                self.client.flush()
            except Exception:
                pass

    @contextmanager
    def span(self, name, inputs=None, metadata=None):
        sp = self._trace.span(name=name, input=inputs or {}, metadata=metadata or {}) \
            if self._trace is not None else None
        h = _Handle(sink=lambda o: sp.end(output=o) if sp else None)
        try:
            yield h
        finally:
            h.end()


class _AzureMonitorTracer:
    """Azure Application Insights via OpenTelemetry.

    Sends spans (and their attributes) to Azure Monitor. Selected when
    APPLICATIONINSIGHTS_CONNECTION_STRING is set.
    """
    provider = "azure"
    enabled = True

    def __init__(self):
        from azure.monitor.opentelemetry import configure_azure_monitor  # lazy
        from opentelemetry import trace
        configure_azure_monitor(
            connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))
        self._trace = trace
        self._tracer = trace.get_tracer("proposalforge")

    def _apply(self, span, d):
        for k, v in (d or {}).items():
            try:
                span.set_attribute(f"pf.{k}", v if isinstance(v, (str, int, float, bool)) else str(v))
            except Exception:
                pass

    @contextmanager
    def run(self, name, run_id=None, metadata=None):
        with self._tracer.start_as_current_span(name) as span:
            self._apply(span, {"run_id": run_id, **(metadata or {})})
            h = _Handle(sink=lambda o: self._apply(span, o))
            try:
                yield h
            finally:
                h.end()

    @contextmanager
    def span(self, name, inputs=None, metadata=None):
        with self._tracer.start_as_current_span(name) as span:
            self._apply(span, {**(inputs or {}), **(metadata or {})})
            h = _Handle(sink=lambda o: self._apply(span, o))
            try:
                yield h
            finally:
                h.end()


_TRACER = None


def dashboard_url() -> dict:
    """Return {'provider','url','project','enabled'} for a UI link to the traces.

    Always returns a valid clickable URL for the active provider; when tracing is
    off it points at the LangSmith site with enabled=False so the UI can hint.
    """
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        url = os.getenv("AZURE_MONITOR_URL", "https://portal.azure.com/#blade/HubsExtension/"
                                             "BrowseResource/resourceType/microsoft.insights%2Fcomponents")
        return {"provider": "azure", "url": url, "project": "Application Insights", "enabled": True}
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true") and \
            os.getenv("LANGCHAIN_API_KEY"):
        project = os.getenv("LANGCHAIN_PROJECT", "proposalforge")
        base = os.getenv("LANGCHAIN_UI_URL", "https://smith.langchain.com")
        return {"provider": "langsmith", "url": base, "project": project, "enabled": True}
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        base = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        return {"provider": "langfuse", "url": base, "project": "proposalforge", "enabled": True}
    return {"provider": "none", "url": "https://smith.langchain.com",
            "project": "proposalforge", "enabled": False}


def get_tracer():
    """Singleton tracer chosen from the environment (LangSmith > Langfuse > none)."""
    global _TRACER
    if _TRACER is not None:
        return _TRACER
    try:
        if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
            _TRACER = _AzureMonitorTracer()
            return _TRACER
    except Exception as e:
        print(f"Azure Monitor unavailable ({e}); trying LangSmith.")
    try:
        if os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true") and \
                os.getenv("LANGCHAIN_API_KEY"):
            _TRACER = _LangSmithTracer()
            return _TRACER
    except Exception as e:
        print(f"LangSmith unavailable ({e}); continuing without it.")
    try:
        if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            _TRACER = _LangfuseTracer()
            return _TRACER
    except Exception as e:
        print(f"Langfuse unavailable ({e}); continuing without it.")
    _TRACER = _NoopTracer()
    return _TRACER
