"""Tracking / audit store with production database backends.

Backend selection (first available wins):
  1. Azure SQL Database  - AZURE_SQL_CONNECTION_STRING (+ pyodbc + MS ODBC driver)
  2. PostgreSQL          - TRACKING_DATABASE_URL or DATABASE_URL (postgres://...)
                           (+ psycopg or psycopg2). Works with Azure Database for
                           PostgreSQL; can be the SAME server you use for pgvector.
  3. SQLite              - local/dev fallback (AUDIT_DB_PATH, default data/audit.db)

Same tiny interface either way: log() and get_logs(). Never raises; if a chosen
server can't connect it degrades to SQLite so the app keeps working.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _pg_url() -> Optional[str]:
    url = os.getenv("TRACKING_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url and (url.startswith("postgres://") or url.startswith("postgresql://")):
        return url
    return None


class TrackingStore:
    def __init__(self) -> None:
        self.azure_sql_conn = (os.getenv("AZURE_SQL_CONNECTION_STRING")
                               or os.getenv("SQL_CONNECTION_STRING"))
        self.pg_url = _pg_url()
        self.sqlite_path = os.getenv("AUDIT_DB_PATH", "data/audit.db")
        self.backend = "sqlite"
        if self.azure_sql_conn:
            try:
                import pyodbc  # noqa: F401
                self.backend = "azure_sql"
            except Exception:
                self.backend = "sqlite"
        if self.backend == "sqlite" and self.pg_url:
            if self._pg_driver() is not None:
                self.backend = "postgres"
        self._ensure_schema()

    @staticmethod
    def _pg_driver():
        try:
            import psycopg  # psycopg 3
            return psycopg
        except Exception:
            try:
                import psycopg2  # psycopg 2
                return psycopg2
            except Exception:
                return None

    @property
    def _ph(self) -> str:
        # placeholder: postgres uses %s, sqlite/pyodbc use ?
        return "%s" if self.backend == "postgres" else "?"

    def _connect(self):
        if self.backend == "azure_sql":
            import pyodbc
            return pyodbc.connect(self.azure_sql_conn, timeout=5)
        if self.backend == "postgres":
            drv = self._pg_driver()
            return drv.connect(self.pg_url)
        import sqlite3
        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.sqlite_path, timeout=10, check_same_thread=False)

    def _ensure_schema(self) -> None:
        ddl = {
            "azure_sql": (
                "IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='audit_logs' "
                "AND xtype='U') CREATE TABLE audit_logs ("
                " id INT IDENTITY(1,1) PRIMARY KEY,"
                " ts DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),"
                " action NVARCHAR(64), user_id NVARCHAR(128),"
                " session_id NVARCHAR(128), detail NVARCHAR(MAX), confidence FLOAT NULL)"),
            "postgres": (
                "CREATE TABLE IF NOT EXISTS audit_logs ("
                " id SERIAL PRIMARY KEY,"
                " ts TIMESTAMPTZ NOT NULL DEFAULT now(),"
                " action TEXT, user_id TEXT, session_id TEXT,"
                " detail TEXT, confidence DOUBLE PRECISION)"),
            "sqlite": (
                "CREATE TABLE IF NOT EXISTS audit_logs ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " ts TEXT NOT NULL, action TEXT, user_id TEXT, session_id TEXT,"
                " detail TEXT, confidence REAL)"),
        }
        try:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(ddl[self.backend])
                conn.commit()
            finally:
                conn.close()
        except Exception:
            if self.backend != "sqlite":      # server unreachable -> degrade
                self.backend = "sqlite"
                self._ensure_schema()

    def log(self, action: str, user_id: str, session_id: str,
            detail: str = "", confidence: Optional[float] = None) -> None:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        p = self._ph
        sql = (f"INSERT INTO audit_logs (ts, action, user_id, session_id, detail, "
               f"confidence) VALUES ({p},{p},{p},{p},{p},{p})")
        try:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(sql, (ts, action, user_id, session_id,
                                  str(detail)[:3000], confidence))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass   # tracking must never break the request path

    def get_logs(self, limit: int = 300) -> List[Dict[str, Any]]:
        p = self._ph
        if self.backend == "azure_sql":
            sql = ("SELECT TOP (?) ts, action, user_id, detail FROM audit_logs "
                   "ORDER BY ts DESC")
        else:
            sql = (f"SELECT ts, action, user_id, detail FROM audit_logs "
                   f"ORDER BY ts DESC LIMIT {p}")
        try:
            conn = self._connect()
            try:
                cur = conn.cursor()
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
            finally:
                conn.close()
            return [{"time": str(r[0])[:19].replace("T", " "),
                     "action": r[1] or "", "user": r[2] or "", "detail": r[3] or ""}
                    for r in rows]
        except Exception:
            return []

    def describe(self) -> str:
        return {"azure_sql": "Azure SQL Database",
                "postgres": "PostgreSQL (Azure Database for PostgreSQL)",
                "sqlite": f"SQLite ({self.sqlite_path})"}[self.backend]
