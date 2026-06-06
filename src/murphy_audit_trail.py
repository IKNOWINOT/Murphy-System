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


# ── BLOCK-A.5.3 — HTTP-request audit log endpoints ─────────────────────────────
# Why a new router instead of extending audit_router above?
#   nginx routes /api/audit/* to ops:8003 (PATCH-407 security scanner).
#   PATCH-089d's audit_router IS mounted on monolith but nginx never reaches it.
#   To expose HTTP-request audit data publicly without breaking PATCH-407's
#   security scanner endpoints (which live on ops), we use a different prefix:
#     /api/auditlog/recent       — paginated HTTP request log
#     /api/auditlog/chain-verify — hash chain integrity validator
#     /api/auditlog/by-tenant    — per-tenant view
#     /api/auditlog/by-actor     — per-actor view
#     /api/auditlog/summary      — recent activity counts
#
# Uses the same murphy_audit.db.events table that BLOCK-A.5.1 audit middleware
# writes to. Read-only — no INSERT endpoints here (middleware is sole writer).

auditlog_router = APIRouter(prefix="/api/auditlog", tags=["auditlog"])


def _auditlog_conn() -> sqlite3.Connection:
    """Read connection to the audit DB. Read-only mode for safety."""
    return sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=2)


def _row_to_event(cols: list, row: tuple) -> dict:
    """Map a SELECT row into a JSON-serializable dict, parsing metadata JSON."""
    d = dict(zip(cols, row))
    raw_meta = d.get("metadata")
    if raw_meta and isinstance(raw_meta, str):
        try:
            d["metadata"] = json.loads(raw_meta)
        except json.JSONDecodeError:
            pass
    return d


@auditlog_router.get("/recent")
async def auditlog_recent(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    resource_type: Optional[str] = Query(None, description="e.g. 'http_request'"),
    status: Optional[str] = Query(None, description="ok|denied|error"),
    tenant_id: Optional[str] = None,
    actor: Optional[str] = None,
    since_ts: Optional[str] = Query(None, description="ISO timestamp lower bound"),
):
    """
    Most recent audit events with optional filters.

    Returns:
        {success, data: {events: [...], total, limit, offset, has_more}}
    """
    where = []
    params: List[Any] = []
    if resource_type:
        where.append("resource_type = ?")
        params.append(resource_type)
    if status:
        where.append("status = ?")
        params.append(status)
    if tenant_id:
        where.append("tenant_id = ?")
        params.append(tenant_id)
    if actor:
        where.append("actor = ?")
        params.append(actor)
    if since_ts:
        where.append("ts >= ?")
        params.append(since_ts)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    try:
        with _auditlog_conn() as conn:
            cur = conn.execute(
                f"SELECT COUNT(*) FROM events {where_sql}", params
            )
            total = cur.fetchone()[0]
            cur = conn.execute(
                f"""SELECT id, ts, actor, actor_type, action,
                          resource_type, resource_id,
                          input_summary, output_summary, status,
                          metadata, ip_address, session_id, tenant_id,
                          prompt_hash, prev_event_hash, event_hash
                   FROM events {where_sql}
                   ORDER BY id DESC LIMIT ? OFFSET ?""",
                params + [limit, offset]
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            events = [_row_to_event(cols, r) for r in rows]
        return {
            "success": True,
            "data": {
                "events": events,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(events)) < total,
            },
        }
    except sqlite3.Error as e:
        return {"success": False, "error": {"code": "DB_ERROR", "message": str(e)}}


@auditlog_router.get("/chain-verify")
async def auditlog_chain_verify(
    limit: int = Query(100, ge=1, le=5000, description="How many recent events to verify"),
):
    """
    Verify the hash chain integrity over the last N events.

    For each event with a prev_event_hash, checks that it matches the
    event_hash of the prior event (when scanning by id). Genesis events
    (no prev) are skipped as expected. Reports broken links by id range.

    Returns:
        {success, data: {checked, valid, broken, broken_ids[], coverage_range}}
    """
    try:
        with _auditlog_conn() as conn:
            cur = conn.execute(
                """
                WITH chained AS (
                    SELECT id, prev_event_hash, event_hash,
                           LAG(event_hash) OVER (ORDER BY id) AS expected_prev
                    FROM events
                    WHERE event_hash IS NOT NULL
                    ORDER BY id DESC
                    LIMIT ?
                )
                SELECT id, prev_event_hash, expected_prev,
                       CASE
                         WHEN prev_event_hash IS NULL THEN 'genesis'
                         WHEN expected_prev IS NULL THEN 'window_edge'
                         WHEN prev_event_hash = expected_prev THEN 'valid'
                         ELSE 'broken'
                       END AS chain_state
                FROM chained
                ORDER BY id
                """,
                (limit,)
            )
            rows = cur.fetchall()

        checked = len(rows)
        valid = sum(1 for r in rows if r[3] == "valid")
        broken = [r[0] for r in rows if r[3] == "broken"]
        genesis = sum(1 for r in rows if r[3] == "genesis")
        edges = sum(1 for r in rows if r[3] == "window_edge")

        first_id = rows[0][0] if rows else None
        last_id = rows[-1][0] if rows else None

        return {
            "success": True,
            "data": {
                "checked": checked,
                "valid": valid,
                "genesis": genesis,
                "window_edge": edges,
                "broken_count": len(broken),
                "broken_ids": broken[:20],  # cap response size
                "coverage_range": [first_id, last_id],
                "integrity": "intact" if not broken else "BROKEN",
            },
        }
    except sqlite3.Error as e:
        return {"success": False, "error": {"code": "DB_ERROR", "message": str(e)}}


@auditlog_router.get("/by-tenant/{tenant_id}")
async def auditlog_by_tenant(
    tenant_id: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """All audit events for a specific tenant, newest first."""
    try:
        with _auditlog_conn() as conn:
            cur = conn.execute(
                """SELECT id, ts, actor, action, status,
                          json_extract(metadata,'$.latency_ms') AS latency_ms,
                          json_extract(metadata,'$.status_code') AS http_status
                   FROM events
                   WHERE tenant_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (tenant_id, limit)
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return {
            "success": True,
            "data": {"tenant_id": tenant_id, "count": len(rows), "events": rows},
        }
    except sqlite3.Error as e:
        return {"success": False, "error": {"code": "DB_ERROR", "message": str(e)}}


@auditlog_router.get("/by-actor/{actor}")
async def auditlog_by_actor(
    actor: str,
    limit: int = Query(100, ge=1, le=1000),
):
    """All audit events for a specific actor."""
    try:
        with _auditlog_conn() as conn:
            cur = conn.execute(
                """SELECT id, ts, action, status, tenant_id,
                          json_extract(metadata,'$.latency_ms') AS latency_ms
                   FROM events
                   WHERE actor = ?
                   ORDER BY id DESC LIMIT ?""",
                (actor, limit)
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return {
            "success": True,
            "data": {"actor": actor, "count": len(rows), "events": rows},
        }
    except sqlite3.Error as e:
        return {"success": False, "error": {"code": "DB_ERROR", "message": str(e)}}


@auditlog_router.get("/summary")
async def auditlog_summary(
    window_minutes: int = Query(60, ge=1, le=10080, description="lookback in minutes"),
):
    """
    Rolling activity summary: requests-per-actor, requests-per-tenant,
    p95 latency, error rate, denied requests.
    """
    from datetime import timedelta as _td
    since = (datetime.now(timezone.utc) - _td(minutes=window_minutes)).isoformat()
    try:
        with _auditlog_conn() as conn:
            # Top actors
            # summary: removed incorrect resource_type filter to count all events
            top_actors = conn.execute(
                """SELECT actor, COUNT(*) AS n
                   FROM events
                   WHERE ts >= ?
                   GROUP BY actor ORDER BY n DESC LIMIT 10""",
                (since,)
            ).fetchall()

            # Top tenants
            top_tenants = conn.execute(
                """SELECT COALESCE(tenant_id,'<null>') AS t, COUNT(*) AS n
                   FROM events
                   WHERE resource_type='http_request' AND ts >= ?
                   GROUP BY t ORDER BY n DESC LIMIT 10""",
                (since,)
            ).fetchall()

            # Status distribution
            status_dist = conn.execute(
                """SELECT status, COUNT(*) AS n
                   FROM events
                   WHERE resource_type='http_request' AND ts >= ?
                   GROUP BY status""",
                (since,)
            ).fetchall()

            # Latency stats (extract latency_ms from metadata JSON)
            lat_rows = conn.execute(
                """SELECT CAST(json_extract(metadata,'$.latency_ms') AS INTEGER) AS l
                   FROM events
                   WHERE resource_type='http_request' AND ts >= ?
                     AND json_extract(metadata,'$.latency_ms') IS NOT NULL""",
                (since,)
            ).fetchall()
            latencies = sorted([r[0] for r in lat_rows if r[0] is not None])
            n_lat = len(latencies)
            def _pct(p):
                if not latencies: return 0
                idx = max(0, min(n_lat - 1, int(n_lat * p / 100)))
                return latencies[idx]

            total_reqs = sum(n for _, n in status_dist)
            errors = sum(n for s, n in status_dist if s == "error")
            denied = sum(n for s, n in status_dist if s == "denied")

        return {
            "success": True,
            "data": {
                "window_minutes": window_minutes,
                "since_ts": since,
                "total_requests": total_reqs,
                "error_count": errors,
                "denied_count": denied,
                "error_rate": (errors / total_reqs) if total_reqs else 0,
                "latency_p50_ms": _pct(50),
                "latency_p95_ms": _pct(95),
                "latency_p99_ms": _pct(99),
                "top_actors": [{"actor": a, "requests": n} for a, n in top_actors],
                "top_tenants": [{"tenant_id": t, "requests": n} for t, n in top_tenants],
                "status_distribution": {s: n for s, n in status_dist},
            },
        }
    except sqlite3.Error as e:
        return {"success": False, "error": {"code": "DB_ERROR", "message": str(e)}}
