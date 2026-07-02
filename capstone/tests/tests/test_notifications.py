"""Notification backend selection + payload tests (webhook path is stdlib-only)."""
import importlib


def test_noop_when_unconfigured(monkeypatch):
    for k in ("ACS_CONNECTION_STRING", "ACS_SENDER", "NOTIFY_EMAIL_TO", "NOTIFY_WEBHOOK_URL"):
        monkeypatch.delenv(k, raising=False)
    import core.core.notifications as N
    importlib.reload(N)
    assert N.get_notifier().provider == "none"
    assert N.get_notifier().notify("e", "t", "m") is False


def test_webhook_selected_and_payload(monkeypatch):
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://logic.azure.com/hook")
    import core.notifications as N
    importlib.reload(N)
    n = N.get_notifier()
    assert n.provider == "webhook"
    p = n.build_payload("pipeline_complete", "Score 8/10", "done", {"run_id": "r1"})
    assert p["event"] == "pipeline_complete" and "Score 8/10" in p["text"]
    assert p["data"]["run_id"] == "r1"


def test_pipeline_complete_helper(monkeypatch):
    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://logic.azure.com/hook")
    import core.notifications as N
    importlib.reload(N)
    captured = {}
    n = N.get_notifier()
    n.notify = lambda e, t, m, d=None: captured.update(title=t, data=d) or True
    ok = N.notify_pipeline_complete({"report": {"score": 9}, "run_id": "r2",
                                     "evaluation": {"gate": {"verdict": "PASS"}},
                                     "backend": "groq", "latency_s": 1.0, "guardrail_hits": 0})
    assert ok and "9/10" in captured["title"]


def test_azure_tracer_selection_graceful(monkeypatch):
    # Without the SDK installed, selecting Azure must fall through gracefully.
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=x")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    import core.tracing as T
    importlib.reload(T)
    t = T.get_tracer()
    assert t.provider in ("azure", "none")  # azure if SDK present, else no-op
    importlib.reload(T)
