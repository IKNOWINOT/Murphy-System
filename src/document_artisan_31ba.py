"""
Ship 31ba.DOCUMENT_ARTISAN — Stage 1 (demand logging).

Two future capabilities:
  1. mimic_style(reference_bytes, content_brief) -> finished_bytes
     Take an attached doc, replicate its visual style, fill with new content.
  2. fill_form(blank_bytes, field_values) -> filled_bytes
     Take an attached blank, populate fields, return ready-to-sign.

Stage 1 establishes the API + demand logging. Render path lands in 31bb.
This is honest: don't claim more than the system can do today.
"""
import sqlite3, json
from datetime import datetime, timezone
from typing import Dict, Optional

_DB = "/var/lib/murphy-production/artisan_queue.db"

def _init_db():
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.execute("""CREATE TABLE IF NOT EXISTS artisan_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT NOT NULL, from_addr TEXT, subject TEXT,
        mode TEXT, details TEXT,
        status TEXT DEFAULT 'logged', handled_at TEXT)""")
    conn.commit(); conn.close()

def log_request(from_addr: str, subject: str, mode: str, details: Dict) -> int:
    _init_db()
    conn = sqlite3.connect(_DB, timeout=10.0)
    cur = conn.execute(
        "INSERT INTO artisan_requests (received_at, from_addr, subject, mode, details) VALUES (?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), from_addr or "", subject or "", mode, json.dumps(details or {})))
    rid = cur.lastrowid
    conn.commit(); conn.close()
    return rid

def mimic_style(reference_bytes: bytes, content_brief: str, output_format: str = "pdf") -> Optional[bytes]:
    """STAGE 1 STUB. Returns None until 31bb wires extraction + render."""
    return None

def fill_form(blank_bytes: bytes, field_values: Dict[str, str], output_format: str = "pdf") -> Optional[bytes]:
    """STAGE 1 STUB. Returns None until 31bb wires PDF field detection."""
    return None

def stats() -> Dict:
    _init_db()
    conn = sqlite3.connect(_DB, timeout=10.0)
    by_mode = dict(conn.execute("SELECT mode, COUNT(*) FROM artisan_requests GROUP BY mode").fetchall())
    total = conn.execute("SELECT COUNT(*) FROM artisan_requests").fetchone()[0]
    last_24h = conn.execute("SELECT COUNT(*) FROM artisan_requests WHERE received_at > datetime('now','-24 hours')").fetchone()[0]
    conn.close()
    return {"total_requests": total, "last_24h": last_24h, "by_mode": by_mode, "stage": "1 — demand log; render in 31bb"}

if __name__ == "__main__":
    print(json.dumps(stats(), indent=2))
