"""Tests for observability helpers."""
from core.observability import (track_agent, set_run_id, get_run_id,
                                metrics_payload, record_guardrail, record_quality_score)


def test_run_id_roundtrip():
    set_run_id("abc123")
    assert get_run_id() == "abc123"


def test_track_agent_adds_metadata_and_trace():
    traces = []

    @track_agent("unit")
    def agent(x):
        return {"value": x, "summary": "ok"}

    out = agent(5, _traces=traces)
    assert out["value"] == 5 and out["_agent"] == "unit" and out["_status"] == "ok"
    assert traces[0]["agent"] == "unit"


def test_metrics_payload_returns_bytes():
    record_guardrail("pii")
    record_quality_score(7)
    payload, ctype = metrics_payload()
    assert isinstance(payload, (bytes, bytearray)) and isinstance(ctype, str)
