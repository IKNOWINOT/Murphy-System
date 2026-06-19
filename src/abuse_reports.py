"""Ship 31cz.B — abuse_reports: structured record of abuse incidents.

Whenever Murphy detects abuse (credential spray, rate-limit floods,
honeypot trips, fail2ban bans), record one row here with provenance.
The security_dashboard surfaces this alongside fail2ban + security_brain.

Two patterns of use:
  record_abuse(ip=, kind="cred_spray", evidence={...}, source="fail2ban")
  recent_reports(hours=24) -> List[dict]
"""
from __future__ import annotations
import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any, List

LOG = logging.getLogger("murphy.abuse_reports")
DB_PATH = Path("/var/lib/murphy-production/abuse_reports.db")


def _init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=5)
    c.execute("""
        CREATE TABLE IF NOT EXISTS abuse_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ip TEXT,
            kind TEXT NOT NULL,          -- cred_spray|rate_limit|honeypot|ban|sql_probe|other
            source TEXT NOT NULL,        -- fail2ban|nginx|honeypot|rate_limiter|other
            severity TEXT DEFAULT 'medium',
            evidence_json TEXT,
            user_agent TEXT,
            path TEXT,
            country TEXT,
            action_taken TEXT
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_abuse_ts ON abuse_reports(ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_abuse_ip ON abuse_reports(ip)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_abuse_kind ON abuse_reports(kind)")
    c.commit(); c.close()


def record_abuse(
    *,
    ip: Optional[str] = None,
    kind: str = "other",
    source: str = "other",
    severity: str = "medium",
    evidence: Optional[dict] = None,
    user_agent: Optional[str] = None,
    path: Optional[str] = None,
    country: Optional[str] = None,
    action_taken: Optional[str] = None,
) -> Optional[int]:
    """Record one abuse incident. Returns row id, or None on failure.
    Never raises."""
    try:
        _init()
        c = sqlite3.connect(str(DB_PATH), timeout=5)
        cur = c.execute(
            """INSERT INTO abuse_reports
               (ts, ip, kind, source, severity, evidence_json,
                user_agent, path, country, action_taken)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(),
             ip, kind, source, severity,
             json.dumps(evidence or {}, default=str),
             user_agent, path, country, action_taken),
        )
        row_id = cur.lastrowid
        c.commit(); c.close()
        return row_id
    except Exception as e:
        LOG.debug("record_abuse failed: %s", e)
        return None


def recent_reports(hours: int = 24, limit: int = 100) -> List[dict]:
    """List recent reports within window."""
    try:
        _init()
        c = sqlite3.connect(str(DB_PATH), timeout=5)
        c.row_factory = sqlite3.Row
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = c.execute(
            "SELECT * FROM abuse_reports WHERE ts > ? ORDER BY id DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        LOG.debug("recent_reports failed: %s", e)
        return []


def summary_24h() -> dict:
    """Summary stats for the dashboard."""
    try:
        _init()
        c = sqlite3.connect(str(DB_PATH), timeout=5)
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        total = c.execute(
            "SELECT COUNT(*) FROM abuse_reports WHERE ts > ?", (cutoff,)
        ).fetchone()[0]
        by_kind = dict(c.execute(
            "SELECT kind, COUNT(*) FROM abuse_reports WHERE ts > ? GROUP BY kind",
            (cutoff,),
        ).fetchall())
        by_source = dict(c.execute(
            "SELECT source, COUNT(*) FROM abuse_reports WHERE ts > ? GROUP BY source",
            (cutoff,),
        ).fetchall())
        top_ips = c.execute(
            "SELECT ip, COUNT(*) as n FROM abuse_reports "
            "WHERE ts > ? AND ip IS NOT NULL GROUP BY ip ORDER BY n DESC LIMIT 10",
            (cutoff,),
        ).fetchall()
        c.close()
        return {
            "ok": True, "total_24h": total,
            "by_kind": by_kind, "by_source": by_source,
            "top_ips": [{"ip": r[0], "count": r[1]} for r in top_ips],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Initialize on import so the file exists for the walker
try:
    _init()
except Exception:
    pass
