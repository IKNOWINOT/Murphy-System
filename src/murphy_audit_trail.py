"""
PATCH-089d — Murphy System Audit Trail
AUDIT-001

Append-only SQLite log of every significant system action.
Who did what, when, with what input, and what happened.

DB: /var/lib/murphy-production/murphy_audit.db
Schema: events(id, ts, actor, actor_type, action, resource_type,
               resource_id, input_summary, output_summary,
               status, metadata, ip_address, session_id)

actor_type: user | agent | system | automation
action: examples — login, logout, llm_call, tool_invoke, api_call,
        board_create, dossier_update, scan_start, patch_apply, ...
"""
from __future__ import annotations
import json, logging, sqlite3, threading, pathlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, Request

logger = logging.getLogger(__name__)

_DB_PATH = pathlib.Path("/var/lib/murphy-production/murphy_audit.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    actor         TEXT NOT NULL,
    actor_type    TEXT NOT NULL DEFAULT 'system',
    action        TEXT NOT NULL,
    resource_type TEXT,
    resource_id   TEXT,
    input_summary TEXT,
    output_summary TEXT,
    status        TEXT DEFAULT 'ok',
    metadata      TEXT DEFAULT '{}',
    ip_address    TEXT,
    session_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts     ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_actor  ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
"""


class AuditTrail:
    """Thread-safe append-only audit log."""

    def __init__(self, db_path: pathlib.Path = _DB_PATH):
        self._db = db_path
        self._lock = threading.Lock()
        self._init_db()
        logger.info("PATCH-089d: Audit trail initialised at %s", db_path)
        self.emit("system", "system", "audit_trail_start", status="ok",
                  output_summary="Murphy audit trail initialised")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._conn() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def emit(self, actor: str, actor_type: str, action: str, *,
             resource_type: str = None, resource_id: str = None,
             input_summary: str = None, output_summary: str = None,
             status: str = "ok", metadata: Dict = None,
             ip_address: str = None, session_id: str = None):
        """Append one audit event. Never raises — failures are logged."""
        try:
            ts = datetime.now(timezone.utc).isoformat()
            with self._lock, self._conn() as conn:
                conn.execute(
                    "INSERT INTO events (ts, actor, actor_type, action, resource_type, "
                    "resource_id, input_summary, output_summary, status, metadata, "
                    "ip_address, session_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ts, actor, actor_type, action, resource_type, resource_id,
                     input_summary[:500] if input_summary else None,
                     output_summary[:500] if output_summary else None,
                     status, json.dumps(metadata or {}), ip_address, session_id)
                )
                conn.commit()
        except Exception as e:
            logger.warning("AUDIT: emit failed: %s", e)

    def query(self, *, actor: str = None, action: str = None,
              status: str = None, limit: int = 100,
              offset: int = 0) -> List[Dict]:
        clauses, params = [], []
        if actor:  clauses.append("actor=?");  params.append(actor)
        if action: clauses.append("action=?"); params.append(action)
        if status: clauses.append("status=?"); params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            with self._lock, self._conn() as conn:
                rows = conn.execute(
                    f"SELECT * FROM events {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                    params + [limit, offset]
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            return [{"error": str(e)}]

    def stats(self) -> Dict:
        try:
            with self._lock, self._conn() as conn:
                total  = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                errors = conn.execute("SELECT COUNT(*) FROM events WHERE status!='ok'").fetchone()[0]
                actors = conn.execute(
                    "SELECT actor, COUNT(*) as n FROM events GROUP BY actor ORDER BY n DESC LIMIT 10"
                ).fetchall()
                actions = conn.execute(
                    "SELECT action, COUNT(*) as n FROM events GROUP BY action ORDER BY n DESC LIMIT 10"
                ).fetchall()
            return {
                "total_events": total,
                "error_events": errors,
                "top_actors":  [dict(r) for r in actors],
                "top_actions": [dict(r) for r in actions],
            }
        except Exception as e:
            return {"error": str(e)}


# Global singleton (set by app.py)
_trail: Optional[AuditTrail] = None

def get_trail() -> AuditTrail:
    global _trail
    if _trail is None:
        _trail = AuditTrail()
    return _trail

def audit(actor: str, actor_type: str, action: str, **kwargs):
    """Module-level convenience — call from anywhere."""
    get_trail().emit(actor, actor_type, action, **kwargs)


# ── REST API ─────────────────────────────────────────────────────────────
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])

@audit_router.get("/events")
async def list_events(actor: str = None, action: str = None,
                      status: str = None, limit: int = Query(50, le=500),
                      offset: int = 0):
    return {"events": get_trail().query(actor=actor, action=action,
                                        status=status, limit=limit, offset=offset)}

@audit_router.get("/stats")
async def audit_stats():
    return get_trail().stats()

@audit_router.post("/emit")
async def emit_event(request: Request):
    body = await request.json()
    get_trail().emit(
        actor=body.get("actor", "api"),
        actor_type=body.get("actor_type", "system"),
        action=body.get("action", "manual"),
        resource_type=body.get("resource_type"),
        resource_id=body.get("resource_id"),
        input_summary=body.get("input_summary"),
        output_summary=body.get("output_summary"),
        status=body.get("status", "ok"),
        metadata=body.get("metadata", {}),
    )
    return {"ok": True}
