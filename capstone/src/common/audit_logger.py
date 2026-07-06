"""Audit logging system for production tracking and compliance."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib


class AuditAction(Enum):
    """Audit action types."""
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_ANALYSIS = "document_analysis"
    USER_QUERY = "user_query"
    SUGGESTION_PROVIDED = "suggestion_provided"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    REPORT_GENERATED = "report_generated"
    REPORT_DOWNLOADED = "report_downloaded"
    GUARDRAIL_TRIGGERED = "guardrail_triggered"
    SYSTEM_ERROR = "system_error"


@dataclass
class AuditLog:
    """Audit log entry."""
    timestamp: str
    action: str
    user_id: str
    session_id: str
    document_id: str
    details: Dict[str, Any]
    confidence_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class AuditLogger:
    """SQLite-based audit logger for production use."""
    
    def __init__(self, db_path: str = None):
        # Precedence: explicit argument > AUDIT_DB_PATH env > default. This lets
        # tests pass an isolated temp DB even when AUDIT_DB_PATH is set in the env.
        chosen = db_path or os.getenv("AUDIT_DB_PATH") or "data/audit.db"
        self.db_path = Path(chosen)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        """Open a connection tuned for concurrent access (WAL + busy timeout)."""
        conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")     # readers don't block writers
        conn.execute("PRAGMA busy_timeout=10000")   # wait up to 10s on a locked db
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """Initialize database schema."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    document_id TEXT,
                    details TEXT NOT NULL,
                    confidence_score REAL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON audit_logs(user_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_action ON audit_logs(action)
            """)
            conn.commit()
    
    def log(self, action: AuditAction, user_id: str, session_id: str, 
           document_id: Optional[str], details: Dict[str, Any],
           confidence_score: Optional[float] = None, 
           metadata: Optional[Dict[str, Any]] = None) -> str:
        """Log an audit event."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO audit_logs 
                (timestamp, action, user_id, session_id, document_id, 
                 details, confidence_score, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                action.value,
                user_id,
                session_id,
                document_id,
                json.dumps(details),
                confidence_score,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()
            
            # Get the last inserted row ID
            cursor = conn.execute("SELECT last_insert_rowid()")
            log_id = cursor.fetchone()[0]
        
        return str(log_id)
    
    def get_logs(self, user_id: Optional[str] = None, 
                action: Optional[str] = None,
                session_id: Optional[str] = None,
                document_id: Optional[str] = None,
                limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve audit logs with filtering."""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if action:
            query += " AND action = ?"
            params.append(action)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if document_id:
            query += " AND document_id = ?"
            params.append(document_id)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_session_logs(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all logs for a specific session."""
        return self.get_logs(session_id=session_id, limit=1000)
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics from audit logs."""
        with self._connect() as conn:
            # Total documents uploaded
            cursor = conn.execute(
                "SELECT COUNT(DISTINCT document_id) as count FROM audit_logs WHERE user_id = ?",
                (user_id,)
            )
            docs_uploaded = cursor.fetchone()[0]
            
            # Total queries
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM audit_logs WHERE user_id = ? AND action = ?",
                (user_id, AuditAction.USER_QUERY.value)
            )
            total_queries = cursor.fetchone()[0]
            
            # Approvals
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM audit_logs WHERE user_id = ? AND action = ?",
                (user_id, AuditAction.APPROVAL_GRANTED.value)
            )
            approvals = cursor.fetchone()[0]
            
            # Guardrail triggers
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM audit_logs WHERE user_id = ? AND action = ?",
                (user_id, AuditAction.GUARDRAIL_TRIGGERED.value)
            )
            guardrails_triggered = cursor.fetchone()[0]
        
        return {
            "user_id": user_id,
            "documents_uploaded": docs_uploaded,
            "total_queries": total_queries,
            "approvals_granted": approvals,
            "guardrails_triggered": guardrails_triggered
        }

    def get_analytics_summary(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get analytics summary including accuracy score."""
        query = "SELECT COUNT(*) as count FROM audit_logs WHERE 1=1"
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        with self._connect() as conn:
            cursor = conn.execute(query, params)
            total_events = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(DISTINCT document_id) as count FROM audit_logs WHERE action = ?" + (" AND user_id = ?" if user_id else ""),
                tuple([AuditAction.DOCUMENT_UPLOAD.value] + ([user_id] if user_id else []))
            )
            total_documents = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM audit_logs WHERE action = ?" + (" AND user_id = ?" if user_id else ""),
                tuple([AuditAction.USER_QUERY.value] + ([user_id] if user_id else []))
            )
            total_queries = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM audit_logs WHERE action = ?" + (" AND user_id = ?" if user_id else ""),
                tuple([AuditAction.GUARDRAIL_TRIGGERED.value] + ([user_id] if user_id else []))
            )
            total_guardrails = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT AVG(confidence_score) as avg_confidence FROM audit_logs WHERE action = ? AND confidence_score IS NOT NULL" + (" AND user_id = ?" if user_id else ""),
                tuple([AuditAction.DOCUMENT_ANALYSIS.value] + ([user_id] if user_id else []))
            )
            avg_analysis_confidence = cursor.fetchone()[0] or 0.0

        # Accuracy is the composite (confidence + groundedness + usefulness)
        # averaged across answered queries. Fall back to analysis confidence
        # when no queries have been evaluated yet.
        evaluation = self.get_evaluation_metrics(user_id)
        if evaluation["sample_count"] > 0:
            accuracy_score = evaluation["accuracy_score"]
        else:
            accuracy_score = round(avg_analysis_confidence, 3)

        return {
            "user_id": user_id,
            "total_events": total_events,
            "total_documents": total_documents,
            "total_queries": total_queries,
            "guardrail_triggers": total_guardrails,
            "average_analysis_confidence": round(avg_analysis_confidence, 3),
            "avg_confidence": evaluation["avg_confidence"],
            "avg_groundedness": evaluation["avg_groundedness"],
            "avg_usefulness": evaluation["avg_usefulness"],
            "evaluated_queries": evaluation["sample_count"],
            "accuracy_score": accuracy_score
        }

    def get_evaluation_metrics(self, user_id: Optional[str] = None,
                               limit: int = 1000) -> Dict[str, Any]:
        """Aggregate per-query evaluation metrics (confidence, groundedness,
        usefulness) and compute a composite accuracy score.

        Accuracy = mean over answered queries of
        (confidence + groundedness + usefulness) / 3.
        """
        query = ("SELECT details, confidence_score, timestamp FROM audit_logs "
                 "WHERE action = ?")
        params: List[Any] = [AuditAction.USER_QUERY.value]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        confidences: List[float] = []
        groundednesses: List[float] = []
        usefulnesses: List[float] = []
        accuracies: List[float] = []
        per_query: List[Dict[str, Any]] = []

        for details_json, conf_score, ts in rows:
            try:
                details = json.loads(details_json) if details_json else {}
            except Exception:
                details = {}

            confidence = details.get("confidence")
            if confidence is None:
                confidence = conf_score
            groundedness = details.get("groundedness", details.get("groundness"))
            usefulness = details.get("usefulness")
            accuracy = details.get("accuracy_score")

            if confidence is not None:
                confidences.append(float(confidence))
            if groundedness is not None:
                groundednesses.append(float(groundedness))
            if usefulness is not None:
                usefulnesses.append(float(usefulness))
            if accuracy is not None:
                accuracies.append(float(accuracy))

            per_query.append({
                "timestamp": ts,
                "query": details.get("query", ""),
                "confidence": confidence,
                "groundedness": groundedness,
                "usefulness": usefulness,
                "accuracy_score": accuracy,
                "mode": details.get("mode"),
            })

        def _avg(values: List[float]) -> float:
            return round(sum(values) / len(values), 3) if values else 0.0

        avg_conf = _avg(confidences)
        avg_ground = _avg(groundednesses)
        avg_use = _avg(usefulnesses)

        if accuracies:
            accuracy_score = _avg(accuracies)
        elif confidences or groundednesses or usefulnesses:
            accuracy_score = round((avg_conf + avg_ground + avg_use) / 3, 3)
        else:
            accuracy_score = 0.0

        return {
            "user_id": user_id,
            "sample_count": len(rows),
            "avg_confidence": avg_conf,
            "avg_groundedness": avg_ground,
            "avg_groundness": avg_ground,  # alias for existing UI readers
            "avg_usefulness": avg_use,
            "accuracy_score": accuracy_score,
            "recent_queries": per_query[:20],
        }


class AuditReport:
    """Generate audit reports for compliance."""
    
    def __init__(self, logger: AuditLogger):
        self.logger = logger
    
    def generate_session_report(self, session_id: str) -> Dict[str, Any]:
        """Generate a comprehensive report for a session."""
        logs = self.logger.get_session_logs(session_id)
        
        actions_count = {}
        for log in logs:
            action = log['action']
            actions_count[action] = actions_count.get(action, 0) + 1
        
        return {
            "session_id": session_id,
            "total_events": len(logs),
            "action_breakdown": actions_count,
            "logs": logs
        }
    
    def generate_user_report(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Generate user activity report."""
        stats = self.logger.get_user_stats(user_id)
        logs = self.logger.get_logs(user_id=user_id, limit=1000)
        
        return {
            "user_id": user_id,
            "statistics": stats,
            "recent_activity": logs[:50],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
