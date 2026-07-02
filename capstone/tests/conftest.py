"""Shared pytest fixtures for the ProposalForge Pro test suite.

All tests run fully offline: no LLM API key is required. The app falls back to
a grounded, extractive answer path when no backend key is configured, which is
deterministic enough to assert on.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make sure the project root (this file's parent's parent) is importable so
# `import api_server`, `import core...` work regardless of the CWD pytest uses.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force offline / no-auth mode for the whole session BEFORE any app import.
os.environ.setdefault("REQUIRE_AUTH", "false")
# Ensure no stray keys from a developer's shell leak into the test run and
# cause outbound calls (which would be flaky / blocked in CI).
for _k in ("GROQ_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_API_KEY",
           "LLM_BASE_URL", "OPENAI_API_KEY"):
    os.environ.pop(_k, None)
os.environ["VECTOR_BACKEND"] = "tfidf"  # deterministic, no heavy deps
os.environ["LANGCHAIN_TRACING_V2"] = "false"


@pytest.fixture(scope="session")
def client():
    """A FastAPI TestClient bound to the real application."""
    from fastapi.testclient import TestClient
    import api_server
    with TestClient(api_server.app) as c:
        yield c


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect the various SQLite stores to a throwaway directory."""
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setenv("AUDIT_DB_PATH", str(d / "audit.db"))
    monkeypatch.setenv("APPROVAL_DB_PATH", str(d / "approvals.db"))
    monkeypatch.setenv("AUTH_DB_PATH", str(d / "auth.db"))
    monkeypatch.setenv("JOB_DB_PATH", str(d / "jobs.db"))
    return d


SAMPLE_CONTEXT = (
    "Under the Kisan Credit Card scheme, farmers can get crop loans up to "
    "3 lakh rupees at 4% interest. The scheme covers seasonal agricultural "
    "operations and post-harvest expenses. Applicants must own or lease land."
)
