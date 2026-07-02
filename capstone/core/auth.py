"""Authentication & sessionization (free, no external dependency).

Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib hashlib) + per-user salt.
Users and sessions live in SQLite (WAL), so this works across the Streamlit and
FastAPI processes. A default admin is seeded on first run (change it!).
"""
from __future__ import annotations

import os
import hmac
import hashlib
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any

DB_PATH = Path(os.getenv("AUTH_DB_PATH", "data/auth.db"))
_PBKDF2_ROUNDS = 200_000
SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", str(8 * 3600)))  # 8h


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)


class AuthStore:
    def __init__(self, db_path: Optional[str] = None, seed_default: bool = True):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()
        if seed_default:
            self._seed_default_admin()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, salt BLOB, pwd_hash BLOB,
                role TEXT DEFAULT 'user', created_at REAL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, username TEXT, created_at REAL,
                last_seen REAL, expires_at REAL)""")

    def _seed_default_admin(self):
        if not self.get_user("admin"):
            self.create_user("admin", os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123"),
                             role="admin")

    # ---- users ----
    def create_user(self, username: str, password: str, role: str = "user") -> bool:
        username = (username or "").strip().lower()
        if not username or not password:
            return False
        salt = secrets.token_bytes(16)
        pwd_hash = _hash_password(password, salt)
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO users (username, salt, pwd_hash, role, created_at)"
                             " VALUES (?,?,?,?,?)",
                             (username, salt, pwd_hash, role, time.time()))
            return True
        except sqlite3.IntegrityError:
            return False  # already exists

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT username, salt, pwd_hash, role FROM users WHERE username=?",
                               ((username or "").strip().lower(),)).fetchone()
        if not row:
            return None
        return {"username": row[0], "salt": row[1], "pwd_hash": row[2], "role": row[3]}

    def verify_password(self, username: str, password: str) -> bool:
        u = self.get_user(username)
        if not u:
            return False
        candidate = _hash_password(password, u["salt"])
        return hmac.compare_digest(candidate, u["pwd_hash"])

    # ---- sessions ----
    def create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._connect() as conn:
            conn.execute("INSERT INTO sessions (token, username, created_at, last_seen, expires_at)"
                         " VALUES (?,?,?,?,?)",
                         (token, username.lower(), now, now, now + SESSION_TTL))
        return token

    def validate_session(self, token: str) -> Optional[str]:
        if not token:
            return None
        now = time.time()
        with self._connect() as conn:
            row = conn.execute("SELECT username, expires_at FROM sessions WHERE token=?",
                               (token,)).fetchone()
            if not row or row[1] < now:
                return None
            conn.execute("UPDATE sessions SET last_seen=? WHERE token=?", (now, token))
        return row[0]

    def end_session(self, token: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))

    def login(self, username: str, password: str) -> Optional[str]:
        """Verify credentials and return a session token, or None."""
        if self.verify_password(username, password):
            return self.create_session(username.lower())
        return None
