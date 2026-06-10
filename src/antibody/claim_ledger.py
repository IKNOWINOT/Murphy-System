"""PCR-090f.1 — Claim ledger (storage layer).

claim_ledger table per spec. Idempotent schema init.
"""
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List

DB_PATH = "/var/lib/murphy-production/claim_ledger.db"


def _ensure_schema():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=2.0)
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS claim_ledger (
            claim_id              TEXT PRIMARY KEY,
            text                  TEXT NOT NULL,
            claim_type            TEXT NOT NULL,
            subject               TEXT,
            predicate             TEXT,
            object_value          TEXT,
            source_agent          TEXT,
            source_call_id        TEXT,
            confidence            REAL DEFAULT 0.5,
            status                TEXT NOT NULL DEFAULT 'pending',
            created_at            REAL NOT NULL,
            last_verified_at      REAL,
            verify_attempts       INTEGER DEFAULT 0,
            ground_truth          TEXT,
            ground_truth_source   TEXT
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON claim_ledger(status, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON claim_ledger(claim_type, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_call ON claim_ledger(source_call_id)")
        conn.commit()
    finally:
        conn.close()


def insert_claim(
    text: str,
    claim_type: str,
    subject: Optional[str] = None,
    predicate: Optional[str] = None,
    object_value: Optional[str] = None,
    source_agent: Optional[str] = None,
    source_call_id: Optional[str] = None,
    confidence: float = 0.5,
) -> str:
    _ensure_schema()
    cid = f"claim_{uuid.uuid4().hex[:12]}"
    now = time.time()
    conn = sqlite3.connect(DB_PATH, timeout=2.0)
    try:
        conn.execute(
            """INSERT INTO claim_ledger
               (claim_id, text, claim_type, subject, predicate, object_value,
                source_agent, source_call_id, confidence, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (cid, text, claim_type, subject, predicate, object_value,
             source_agent, source_call_id, confidence, now),
        )
        conn.commit()
        return cid
    finally:
        conn.close()


def get_pending(limit: int = 100) -> List[Dict[str, Any]]:
    _ensure_schema()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2.0)
    try:
        rows = conn.execute(
            """SELECT claim_id, text, claim_type, subject, predicate, object_value,
               source_agent, confidence FROM claim_ledger
               WHERE status='pending' ORDER BY created_at ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        cols = ['claim_id', 'text', 'claim_type', 'subject', 'predicate',
                'object_value', 'source_agent', 'confidence']
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def get_stats() -> Dict[str, Any]:
    _ensure_schema()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2.0)
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM claim_ledger GROUP BY status"
        ).fetchall()
        by_status = {r[0]: r[1] for r in rows}
        type_rows = conn.execute(
            "SELECT claim_type, COUNT(*) FROM claim_ledger GROUP BY claim_type"
        ).fetchall()
        by_type = {r[0]: r[1] for r in type_rows}
        total = conn.execute("SELECT COUNT(*) FROM claim_ledger").fetchone()[0]
        return {
            "total_claims": total,
            "by_status": by_status,
            "by_type": by_type,
        }
    finally:
        conn.close()
