"""Persistent chat sessionization (free, SQLite WAL).

Stores each user's chat sessions and their message history so conversations
survive page refresh, logout, and process restarts. Keyed by user, so sessions
are private per authenticated account.
"""
from __future__ import annotations

import os
import json
import time
import uuid
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(os.getenv("CHAT_DB_PATH", "data/chat.db"))


class ChatStore:
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
            conn.execute("""CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY, user TEXT, title TEXT,
                messages TEXT, created_at REAL, updated_at REAL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_sessions(user)")

    def create_session(self, user: str, title: str = "New chat") -> str:
        sid = "chat-" + uuid.uuid4().hex[:10]
        now = time.time()
        with self._connect() as conn:
            conn.execute("INSERT INTO chat_sessions (id, user, title, messages, created_at, updated_at)"
                         " VALUES (?,?,?,?,?,?)",
                         (sid, (user or "anon").lower(), title, "[]", now, now))
        return sid

    def list_sessions(self, user: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, messages, created_at, updated_at FROM chat_sessions"
                " WHERE user=? ORDER BY updated_at DESC", ((user or "anon").lower(),)).fetchall()
        out = []
        for r in rows:
            try:
                n = len(json.loads(r[2] or "[]"))
            except Exception:
                n = 0
            out.append({"id": r[0], "title": r[1], "message_count": n,
                        "created_at": r[3], "updated_at": r[4]})
        return out

    def load_messages(self, session_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT messages FROM chat_sessions WHERE id=?",
                               (session_id,)).fetchone()
        if not row:
            return []
        try:
            return json.loads(row[0] or "[]")
        except Exception:
            return []

    def save_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        with self._connect() as conn:
            conn.execute("UPDATE chat_sessions SET messages=?, updated_at=? WHERE id=?",
                         (json.dumps(messages, default=str), time.time(), session_id))

    def rename_session(self, session_id: str, title: str):
        with self._connect() as conn:
            conn.execute("UPDATE chat_sessions SET title=?, updated_at=? WHERE id=?",
                         (title[:80], time.time(), session_id))

    def delete_session(self, session_id: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))

    @staticmethod
    def derive_title(messages: List[Dict[str, Any]]) -> str:
        """Use the first user message as the session title."""
        for m in messages:
            if m.get("role") == "user" and m.get("content"):
                return m["content"][:48]
        return "New chat"
