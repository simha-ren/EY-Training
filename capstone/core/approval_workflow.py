"""Human approval workflow for production compliance."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import sqlite3
from pathlib import Path


class ApprovalStatus(Enum):
    """Approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class ApprovalRequest:
    """Approval request for document analysis."""
    
    def __init__(self, document_id: str, user_id: str, analysis: Dict):
        self.request_id = f"{document_id}_{datetime.now().timestamp()}"
        self.document_id = document_id
        self.user_id = user_id
        self.analysis = analysis
        self.created_at = datetime.now()
        self.status = ApprovalStatus.PENDING
        self.approved_by = None
        self.approval_time = None
        self.comments = ""


class ApprovalWorkflow:
    """Manage document analysis approval workflow."""
    
    def __init__(self, db_path: str = "data/approvals.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize approval database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    analysis TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    approved_by TEXT,
                    approval_time TIMESTAMP,
                    comments TEXT,
                    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON approval_requests(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON approval_requests(user_id)
            """)
            conn.commit()
    
    def create_request(self, document_id: str, user_id: str, analysis: Dict) -> str:
        """Create a new approval request."""
        import json
        
        request_id = f"{document_id}_{int(datetime.now().timestamp() * 1000)}"
        created_at = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO approval_requests 
                (request_id, document_id, user_id, analysis, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request_id,
                document_id,
                user_id,
                json.dumps(analysis),
                ApprovalStatus.PENDING.value,
                created_at
            ))
            conn.commit()
        
        return request_id
    
    def get_pending_requests(self, user_id: Optional[str] = None) -> List[Dict]:
        """Get pending approval requests."""
        query = "SELECT * FROM approval_requests WHERE status = ?"
        params = [ApprovalStatus.PENDING.value]
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        query += " ORDER BY created_at DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def approve_request(self, request_id: str, approved_by: str, 
                       comments: str = "") -> bool:
        """Approve an analysis request."""
        approval_time = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,)
            )
            request = cursor.fetchone()
            
            if not request:
                return False
            
            conn.execute("""
                UPDATE approval_requests 
                SET status = ?, approved_by = ?, approval_time = ?, comments = ?
                WHERE request_id = ?
            """, (
                ApprovalStatus.APPROVED.value,
                approved_by,
                approval_time,
                comments,
                request_id
            ))
            conn.commit()
        
        return True
    
    def reject_request(self, request_id: str, approved_by: str,
                      comments: str = "") -> bool:
        """Reject an analysis request."""
        approval_time = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,)
            )
            request = cursor.fetchone()
            
            if not request:
                return False
            
            conn.execute("""
                UPDATE approval_requests 
                SET status = ?, approved_by = ?, approval_time = ?, comments = ?
                WHERE request_id = ?
            """, (
                ApprovalStatus.REJECTED.value,
                approved_by,
                approval_time,
                comments,
                request_id
            ))
            conn.commit()
        
        return True
    
    def get_request(self, request_id: str) -> Optional[Dict]:
        """Get a specific request."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,)
            )
            row = cursor.fetchone()
        
        if row:
            import json
            result = dict(row)
            result['analysis'] = json.loads(result['analysis'])
            return result
        
        return None
    
    def get_approval_history(self, user_id: str) -> List[Dict]:
        """Get approval history for a user."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
        
        import json
        results = []
        for row in rows:
            result = dict(row)
            result['analysis'] = json.loads(result['analysis'])
            results.append(result)
        
        return results
