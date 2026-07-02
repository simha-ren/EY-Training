"""Tests for the webhook job store (cross-process channel)."""
import tempfile
from core.core.job_store import JobStore


def _store():
    return JobStore(db_path=tempfile.mktemp(suffix=".db"))


def test_submit_creates_queued_job():
    s = _store()
    jid = s.submit("analyze risks", "some context")
    job = s.get(jid)
    assert job["status"] == "queued" and job["task"] == "analyze risks"


def test_set_result_marks_done():
    s = _store()
    jid = s.submit("t", "c")
    s.set_result(jid, {"report": {"score": 7}})
    job = s.get(jid)
    assert job["status"] == "done" and job["result"]["report"]["score"] == 7


def test_list_orders_recent_first():
    s = _store()
    a = s.submit("first", "c")
    b = s.submit("second", "c")
    ids = [j["id"] for j in s.list()]
    assert ids.index(b) < ids.index(a)


def test_wal_mode():
    s = _store()
    with s._connect() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
