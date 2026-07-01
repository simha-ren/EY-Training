"""Tests for the approval workflow."""
import tempfile
from core.approval_workflow import ApprovalWorkflow


def test_create_and_fetch_request():
    wf = ApprovalWorkflow(db_path=tempfile.mktemp(suffix=".db"))
    rid = wf.create_request("doc1", "user1", {"summary": "needs review"})
    assert rid
    req = wf.get_request(rid)
    assert req is not None
