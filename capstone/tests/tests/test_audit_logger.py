import tempfile, os
from core.core.audit_logger import AuditLogger, AuditAction

def _logger():
    return AuditLogger(db_path=tempfile.mktemp(suffix=".db"))

def test_log_and_evaluation_metrics():
    al = _logger()
    al.log(AuditAction.USER_QUERY, "u1", "s1", "d1",
           {"query": "q", "confidence": 0.8, "groundedness": 0.6,
            "usefulness": 0.7, "accuracy_score": 0.7, "mode": "offline"},
           confidence_score=0.8)
    ev = al.get_evaluation_metrics("u1")
    assert ev["sample_count"] == 1
    assert 0.0 <= ev["accuracy_score"] <= 1.0
    assert ev["avg_confidence"] == 0.8

def test_analytics_summary_uses_composite():
    al = _logger()
    al.log(AuditAction.USER_QUERY, "u1", "s1", "d1",
           {"query": "q", "confidence": 0.5, "groundedness": 0.5,
            "usefulness": 0.5, "accuracy_score": 0.5}, confidence_score=0.5)
    summ = al.get_analytics_summary("u1")
    assert "accuracy_score" in summ and summ["evaluated_queries"] == 1

def test_wal_mode_enabled():
    al = _logger()
    with al._connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
