"""Shared job store (webhook <-> dashboard), FIAA-style.

The FastAPI webhook writes pipeline jobs here; the Streamlit dashboard polls and
displays finished ones. SQLite in WAL mode is the cross-process channel, exactly
like FIAA's store. Self-contained jobs carry their own task + context, so the
background worker can run the pipeline without the dashboard's session state.
"""
from __future__ import annotations

import os
import json
import time
import uuid
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(os.getenv("JOB_DB_PATH", "data/jobs.db"))


class JobStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    task TEXT,
                    context TEXT,
                    status TEXT,
                    created_at REAL,
                    updated_at REAL,
                    result TEXT
                )
            """)

    def submit(self, task: str, context: str) -> str:
        job_id = "job-" + uuid.uuid4().hex[:10]
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, task, context, status, created_at, updated_at, result)"
                " VALUES (?,?,?,?,?,?,?)",
                (job_id, task, context, "queued", now, now, None),
            )
        return job_id

    def set_status(self, job_id: str, status: str):
        with self._connect() as conn:
            conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?",
                         (status, time.time(), job_id))

    def set_result(self, job_id: str, result: Dict[str, Any], status: str = "done"):
        with self._connect() as conn:
            conn.execute("UPDATE jobs SET status=?, result=?, updated_at=? WHERE id=?",
                         (status, json.dumps(result, default=str), time.time(), job_id))

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, task, status, created_at, updated_at, result FROM jobs WHERE id=?",
                (job_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, task, status, created_at, updated_at, result FROM jobs"
                " ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r) -> Dict[str, Any]:
        result = None
        if r[5]:
            try:
                result = json.loads(r[5])
            except Exception:
                result = None
        return {"id": r[0], "task": r[1], "status": r[2],
                "created_at": r[3], "updated_at": r[4], "result": result}
