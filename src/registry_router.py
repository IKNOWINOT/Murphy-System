"""
BLOCK-A.2.8 — Registry Read Endpoints
====================================

WHAT THIS IS:
  Read-only HTTP API exposing the 5 registries in murphy_registry.db
  (pages/routes/capabilities/actions/cadence) plus the audit_events
  extension in murphy_audit.db.

WHY IT EXISTS:
  Without these endpoints, the 1,278 registry rows are invisible to the
  observatory, founder tooling, and external clients. This is the
  visibility surface for the "Murphy knows itself" foundation.

HOW IT FITS:
  - Mounted via app.include_router(registry_router) in runtime/app.py
  - Read-only in this block. Writes/reseeds come in BLOCK-A.2.9.
  - Auth handled by global middleware (no per-route auth wrappers).
  - Response shape: {"success": bool, "data": {...}, "error": {...}?}
    matches /api/health and /api/mss/* convention.

ENDPOINTS:
  GET  /api/registry/summary               — counts per registry
  GET  /api/registry/gates                 — items with incomplete gates
  GET  /api/registry/search?q=foo          — text search across all 5
  GET  /api/registry/pages                 — list pages (filters)
  GET  /api/registry/pages/{id}            — one page
  GET  /api/registry/routes                — list routes (filters)
  GET  /api/registry/routes/{id}           — one route
  GET  /api/registry/capabilities          — list capabilities (filters)
  GET  /api/registry/capabilities/{id}     — one capability
  GET  /api/registry/actions               — list actions
  GET  /api/registry/actions/{id}          — one action
  GET  /api/registry/cadence               — list cadence sources
  GET  /api/registry/cadence/{id}          — one cadence source

DEPENDENCIES:
  - /var/lib/murphy-production/murphy_registry.db (BLOCK-A.2.7)
  - /var/lib/murphy-production/murphy_audit.db (extended in A.2.6)
  - FastAPI APIRouter + sqlite3 (stdlib)

LAST UPDATED: 2026-05-25 by Murphy/Inoni LLC (BLOCK-A.2.8)
"""

import sqlite3
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

REGISTRY_DB = "/var/lib/murphy-production/murphy_registry.db"
AUDIT_DB    = "/var/lib/murphy-production/murphy_audit.db"

router = APIRouter(prefix="/api/registry", tags=["registry"])

# ── Helpers ────────────────────────────────────────────────────────────────

def _conn(db: str = REGISTRY_DB) -> sqlite3.Connection:
    c = sqlite3.connect(db, timeout=5)
    c.row_factory = sqlite3.Row
    return c

def _ok(data: Any) -> JSONResponse:
    return JSONResponse({"success": True, "data": data})

def _err(code: str, msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": msg}},
        status_code=status,
    )

def _rows_to_dicts(rows) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]

# Map of registry → table name for the generic CRUD pattern
REGISTRY_TABLES = {
    "pages":         "registry_pages",
    "routes":        "registry_routes",
    "capabilities":  "registry_capabilities",
    "actions":       "registry_actions",
    "cadence":       "cadence_registry",
}

# ── Cross-cutting endpoints ────────────────────────────────────────────────

@router.get("/summary")
def summary():
    """Counts per registry — observatory single-pull."""
    try:
        c = _conn()
        out = {}
        for name, table in REGISTRY_TABLES.items():
            # cadence_registry uses lifecycle instead of archived
            if table == "cadence_registry":
                row = c.execute(
                    f"SELECT COUNT(*) AS total, "
                    f"SUM(CASE WHEN lifecycle != 'retired' THEN 1 ELSE 0 END) AS active "
                    f"FROM {table}"
                ).fetchone()
            else:
                row = c.execute(
                    f"SELECT COUNT(*) AS total, "
                    f"SUM(CASE WHEN archived=0 THEN 1 ELSE 0 END) AS active "
                    f"FROM {table}"
                ).fetchone()
            out[name] = {"total": row["total"], "active": row["active"]}

        # Audit row count (separate DB)
        ac = _conn(AUDIT_DB)
        audit_total = ac.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        audit_with_tenant = ac.execute(
            "SELECT COUNT(*) FROM events WHERE tenant_id IS NOT NULL"
        ).fetchone()[0]
        out["audit_events"] = {
            "total": audit_total,
            "with_tenant_id": audit_with_tenant,
        }
        ac.close()
        c.close()
        return _ok(out)
    except Exception as e:
        return _err("SUMMARY_ERROR", str(e), 500)

@router.get("/gates")
def gates(min_gates: int = Query(5, ge=1, le=5)):
    """Items where gate_summary indicates incomplete (less than min_gates of 5)."""
    try:
        c = _conn()
        out = {}
        for name, table in REGISTRY_TABLES.items():
            # cadence_registry has no gate_summary column — skip
            if table == "cadence_registry":
                out[name] = {"count": 0, "items": [], "skipped": "no gates"}
                continue
            # gate_summary is a 5-char string of 0s and 1s
            # Count rows where SUM of digits < min_gates
            rows = c.execute(
                f"SELECT id, gate_summary, "
                f"(CAST(SUBSTR(gate_summary,1,1) AS INTEGER) + "
                f" CAST(SUBSTR(gate_summary,2,1) AS INTEGER) + "
                f" CAST(SUBSTR(gate_summary,3,1) AS INTEGER) + "
                f" CAST(SUBSTR(gate_summary,4,1) AS INTEGER) + "
                f" CAST(SUBSTR(gate_summary,5,1) AS INTEGER)) AS gate_count "
                f"FROM {table} "
                f"WHERE archived=0 "
                f"AND ((CAST(SUBSTR(gate_summary,1,1) AS INTEGER) + "
                f"      CAST(SUBSTR(gate_summary,2,1) AS INTEGER) + "
                f"      CAST(SUBSTR(gate_summary,3,1) AS INTEGER) + "
                f"      CAST(SUBSTR(gate_summary,4,1) AS INTEGER) + "
                f"      CAST(SUBSTR(gate_summary,5,1) AS INTEGER)) < ?) "
                f"ORDER BY gate_count ASC LIMIT 100",
                (min_gates,),
            ).fetchall()
            out[name] = {
                "count": len(rows),
                "items": _rows_to_dicts(rows),
            }
        c.close()
        return _ok({"min_gates": min_gates, "registries": out})
    except Exception as e:
        return _err("GATES_ERROR", str(e), 500)

@router.get("/search")
def search(q: str = Query(..., min_length=2), limit: int = Query(50, le=200)):
    """Text search across all 5 registries."""
    try:
        c = _conn()
        out = {}
        like = f"%{q}%"

        # Each table has different searchable cols
        searches = {
            "pages":        ("registry_pages",        ["path","title","capability"]),
            "routes":       ("registry_routes",       ["path","handler_name","module_file","capability"]),
            "capabilities": ("registry_capabilities", ["capability_id","name","description","provider"]),
            "actions":      ("registry_actions",      ["action_type","name","description"]),
            "cadence":      ("cadence_registry",      ["source_name","display_name","handler_path"]),
        }
        for name, (table, cols) in searches.items():
            where_clause = " OR ".join(f"{col} LIKE ?" for col in cols)
            params = [like] * len(cols)
            # cadence_registry uses lifecycle, others use archived
            arch_clause = ("lifecycle != 'retired'" if table == "cadence_registry"
                           else "archived = 0")
            rows = c.execute(
                f"SELECT * FROM {table} WHERE {arch_clause} AND ({where_clause}) LIMIT ?",
                params + [limit],
            ).fetchall()
            out[name] = _rows_to_dicts(rows)
        c.close()
        return _ok({"query": q, "results": out})
    except Exception as e:
        return _err("SEARCH_ERROR", str(e), 500)

# ── Generic per-registry list + get-by-id ──────────────────────────────────

def _list_registry(
    table: str,
    limit: int,
    offset: int,
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    c = _conn()
    where_parts = ["archived=0"]
    params: List[Any] = []
    for key, val in filters.items():
        if val is None:
            continue
        where_parts.append(f"{key} = ?")
        params.append(val)
    where = " AND ".join(where_parts)

    total = c.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {where}", params
    ).fetchone()[0]

    rows = c.execute(
        f"SELECT * FROM {table} WHERE {where} "
        f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    c.close()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": _rows_to_dicts(rows),
    }

def _get_registry_item(table: str, item_id: str) -> Optional[Dict[str, Any]]:
    c = _conn()
    row = c.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
    c.close()
    return dict(row) if row else None

# ── Pages ──────────────────────────────────────────────────────────────────

@router.get("/pages")
def list_pages(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    page_type: Optional[str] = None,
    tenant_scope: Optional[str] = None,
    capability: Optional[str] = None,
):
    try:
        return _ok(_list_registry(
            "registry_pages", limit, offset,
            {"page_type": page_type, "tenant_scope": tenant_scope, "capability": capability},
        ))
    except Exception as e:
        return _err("PAGES_LIST_ERROR", str(e), 500)

@router.get("/pages/{item_id}")
def get_page(item_id: str):
    row = _get_registry_item("registry_pages", item_id)
    if not row:
        return _err("NOT_FOUND", f"Page {item_id} not found", 404)
    return _ok(row)

# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/routes")
def list_routes(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    method: Optional[str] = None,
    capability: Optional[str] = None,
    tenant_scope: Optional[str] = None,
):
    try:
        filters = {"capability": capability, "tenant_scope": tenant_scope}
        if method:
            filters["method"] = method.upper()
        return _ok(_list_registry("registry_routes", limit, offset, filters))
    except Exception as e:
        return _err("ROUTES_LIST_ERROR", str(e), 500)

@router.get("/routes/{item_id}")
def get_route(item_id: str):
    row = _get_registry_item("registry_routes", item_id)
    if not row:
        return _err("NOT_FOUND", f"Route {item_id} not found", 404)
    return _ok(row)

# ── Capabilities ───────────────────────────────────────────────────────────

@router.get("/capabilities")
def list_capabilities(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    domain: Optional[str] = None,
    risk_class: Optional[str] = None,
):
    try:
        return _ok(_list_registry(
            "registry_capabilities", limit, offset,
            {"source": source, "domain": domain, "risk_class": risk_class},
        ))
    except Exception as e:
        return _err("CAPS_LIST_ERROR", str(e), 500)

@router.get("/capabilities/{item_id}")
def get_capability(item_id: str):
    row = _get_registry_item("registry_capabilities", item_id)
    if not row:
        return _err("NOT_FOUND", f"Capability {item_id} not found", 404)
    return _ok(row)

# ── Actions ────────────────────────────────────────────────────────────────

@router.get("/actions")
def list_actions(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    risk_class: Optional[str] = None,
    hitl_lane: Optional[str] = None,
    reversibility: Optional[str] = None,
):
    try:
        return _ok(_list_registry(
            "registry_actions", limit, offset,
            {"risk_class": risk_class, "hitl_lane": hitl_lane, "reversibility": reversibility},
        ))
    except Exception as e:
        return _err("ACTIONS_LIST_ERROR", str(e), 500)

@router.get("/actions/{item_id}")
def get_action(item_id: str):
    row = _get_registry_item("registry_actions", item_id)
    if not row:
        return _err("NOT_FOUND", f"Action {item_id} not found", 404)
    return _ok(row)

# ── Cadence ────────────────────────────────────────────────────────────────

@router.get("/cadence")
def list_cadence(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = None,
    tier: Optional[str] = None,
    health_status: Optional[str] = None,
):
    try:
        # cadence_registry uses 'lifecycle' instead of 'archived'
        c = _conn()
        where_parts = ["lifecycle != 'retired'"]
        params: List[Any] = []
        for key, val in [("source_type", source_type), ("tier", tier),
                         ("health_status", health_status)]:
            if val:
                where_parts.append(f"{key} = ?")
                params.append(val)
        where = " AND ".join(where_parts)
        total = c.execute(
            f"SELECT COUNT(*) FROM cadence_registry WHERE {where}", params
        ).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM cadence_registry WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        c.close()
        return _ok({
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": _rows_to_dicts(rows),
        })
    except Exception as e:
        return _err("CADENCE_LIST_ERROR", str(e), 500)

@router.get("/cadence/{item_id}")
def get_cadence(item_id: str):
    row = _get_registry_item("cadence_registry", item_id)
    if not row:
        return _err("NOT_FOUND", f"Cadence source {item_id} not found", 404)
    return _ok(row)


# ── BLOCK-A.3.1: Job pipeline endpoints (founder-facing JOB- numbers) ────

CHAIN_DB = "/var/lib/murphy-production/chain_engine.db"

_jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@_jobs_router.get("")
def list_jobs(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
):
    """List jobs by JOB- number, with optional status filter."""
    try:
        c = _conn(CHAIN_DB)
        params = []
        where = "job_number IS NOT NULL"
        if status:
            where += " AND status = ?"
            params.append(status)
        total = c.execute(f"SELECT COUNT(*) FROM chain_requests WHERE {where}", params).fetchone()[0]
        rows = c.execute(
            f"SELECT job_number, id AS chain_id, name, status, "
            f"current_step_index, total_steps, total_cost_usd, created_at, updated_at "
            f"FROM chain_requests WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        c.close()
        return _ok({
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": _rows_to_dicts(rows),
        })
    except Exception as e:
        return _err("JOBS_LIST_ERROR", str(e), 500)

@_jobs_router.get("/{job_number}")
def get_job(job_number: str):
    """Resolve JOB- number to full chain detail."""
    try:
        c = _conn(CHAIN_DB)
        row = c.execute(
            "SELECT * FROM chain_requests WHERE UPPER(job_number) = UPPER(?)", (job_number,)
        ).fetchone()
        if not row:
            return _err("NOT_FOUND", f"Job {job_number} not found", 404)
        result = dict(row)
        # Include step count summary
        steps = c.execute(
            "SELECT COUNT(*) FROM chain_steps WHERE chain_id = ?", (result["id"],)
        ).fetchone()[0]
        result["step_count"] = steps
        # Include file count
        files = c.execute(
            "SELECT COUNT(*) FROM job_files WHERE chain_id = ? AND archived = 0",
            (result["id"],),
        ).fetchone()[0]
        result["file_count"] = files
        c.close()
        return _ok(result)
    except Exception as e:
        return _err("JOB_GET_ERROR", str(e), 500)

@_jobs_router.get("/{job_number}/files")
def list_job_files(job_number: str):
    """List artifact files for a job."""
    try:
        c = _conn(CHAIN_DB)
        chain_row = c.execute(
            "SELECT id FROM chain_requests WHERE UPPER(job_number) = UPPER(?)", (job_number,)
        ).fetchone()
        if not chain_row:
            return _err("NOT_FOUND", f"Job {job_number} not found", 404)
        chain_id = chain_row["id"]
        rows = c.execute(
            "SELECT * FROM job_files WHERE chain_id = ? AND archived = 0 "
            "ORDER BY created_at DESC",
            (chain_id,),
        ).fetchall()
        c.close()
        return _ok({
            "job_number": job_number,
            "chain_id": chain_id,
            "count": len(rows),
            "items": _rows_to_dicts(rows),
        })
    except Exception as e:
        return _err("JOB_FILES_ERROR", str(e), 500)


# ── BLOCK-A.3.2 — Pipeline dashboard (the "status request linked to both" endpoint) ────
# Founder's directive (2026-05-25): "Status request linked to both of you"
# This unifies: (a) my work via build_log + audit_log, (b) Murphy's work via
# rosetta dispatches + chain_log + cycle_log, into one polled endpoint.
#
# Why /api/pipeline/* instead of extending /api/jobs/*:
#   - /api/jobs/* already has BLOCK-A.3.1's job CRUD
#   - Dashboard is a cross-cutting read view, not a job operation
#   - Keeps semantic separation: jobs = data, pipeline = orchestration view

import os as _os_pl

PULSE_DB    = "/var/lib/murphy-production/cadence_pulse.db"
MIND_DB     = "/var/lib/murphy-production/murphy_mind.db"
AUDIT_DB    = "/var/lib/murphy-production/murphy_audit.db"

pipeline_router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _conn_ro(path: str):
    """Read-only connection to prevent any accidental writes from dashboard."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)


@pipeline_router.get("/dashboard")
def pipeline_dashboard(
    window_minutes: int = Query(60, ge=1, le=1440,
                                description="lookback window"),
):
    """
    Unified status view: agent (me) + Murphy + system.

    Returns a snapshot showing:
      - Recent jobs in flight (chain_requests)
      - Murphy mind cycles in window
      - Cadence pulse activity (what is alive)
      - HTTP audit summary (request rate, errors, p95)
      - Recent rosetta dispatches if visible
    """
    from datetime import datetime, timedelta as _td, timezone
    since_iso = (datetime.now(timezone.utc) - _td(minutes=window_minutes)).isoformat()

    out: Dict[str, Any] = {
        "window_minutes": window_minutes,
        "since": since_iso,
        "agent": {},
        "murphy": {},
        "system": {},
    }

    # ── AGENT (me) view: jobs created + audit log activity ──────────────
    try:
        c = _conn_ro(CHAIN_DB)
        rows = c.execute(
            """SELECT job_number, id, name, status,
                      current_step_index, total_steps,
                      SUBSTR(created_at, 1, 19) AS created
               FROM chain_requests
               WHERE job_number IS NOT NULL
                 AND created_at >= ?
               ORDER BY created_at DESC LIMIT 20""",
            (since_iso[:19].replace("T", " "),)
        ).fetchall()
        c.close()
        out["agent"]["jobs_recent"] = [dict(zip(
            ["job_number", "chain_id", "name", "status",
             "step", "total_steps", "created"], r
        )) for r in rows]
    except Exception as e:
        out["agent"]["jobs_recent_error"] = str(e)

    # ── MURPHY view: cycles + priority gaps in window ──────────────────
    try:
        c = _conn_ro(MIND_DB)
        # Murphy cycle_log timestamps are ISO format
        cycles = c.execute(
            """SELECT cycle, timestamp, duration_s, priority_gap, confidence
               FROM cycle_log
               WHERE timestamp >= ?
               ORDER BY cycle DESC LIMIT 30""",
            (since_iso,)
        ).fetchall()
        c.close()

        cycle_rows = [{
            "cycle": r[0],
            "ts": r[1],
            "duration_s": r[2],
            "priority_gap": (r[3] or "")[:200],
            "confidence": r[4]
        } for r in cycles]

        # Aggregate the priority_gap topic — most-frequent first 8 words
        from collections import Counter
        topic_counts = Counter()
        for r in cycle_rows:
            topic = " ".join((r["priority_gap"] or "").split()[:8])
            if topic:
                topic_counts[topic] += 1
        top_topics = topic_counts.most_common(5)

        out["murphy"]["cycles_in_window"] = len(cycle_rows)
        out["murphy"]["latest_cycles"] = cycle_rows[:5]
        out["murphy"]["top_priority_topics"] = [
            {"topic": t, "occurrences": n} for t, n in top_topics
        ]
        if cycle_rows:
            out["murphy"]["latest_cycle_num"] = cycle_rows[0]["cycle"]
            out["murphy"]["avg_confidence"] = round(
                sum(c["confidence"] or 0 for c in cycle_rows) / len(cycle_rows), 3
            )
    except Exception as e:
        out["murphy"]["cycles_error"] = str(e)

    # ── SYSTEM view: cadence pulse alive-ness ──────────────────────────
    try:
        c = _conn_ro(PULSE_DB)
        rows = c.execute(
            """SELECT source_name, COUNT(*) AS ticks, MAX(ts) AS last_tick,
                      AVG(duration_ms) AS avg_dur,
                      SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS failures
               FROM pulse_ticks
               WHERE ts >= ?
               GROUP BY source_name
               ORDER BY last_tick DESC""",
            (since_iso,)
        ).fetchall()
        c.close()
        out["system"]["heartbeats"] = [{
            "source": r[0],
            "ticks": r[1],
            "last_tick": r[2],
            "avg_dur_ms": round(r[3] or 0, 1),
            "failures": r[4],
        } for r in rows]
        out["system"]["heartbeat_sources_alive"] = len(rows)
    except Exception as e:
        out["system"]["heartbeats_error"] = str(e)

    # ── SYSTEM view: HTTP audit summary ────────────────────────────────
    try:
        c = _conn_ro(AUDIT_DB)
        # Status distribution
        status_dist = c.execute(
            """SELECT status, COUNT(*) AS n
               FROM events
               WHERE resource_type='http_request' AND ts >= ?
               GROUP BY status""",
            (since_iso,)
        ).fetchall()
        # Top denied endpoints
        denied = c.execute(
            """SELECT action, COUNT(*) AS n
               FROM events
               WHERE resource_type='http_request' AND status='denied' AND ts >= ?
               GROUP BY action ORDER BY n DESC LIMIT 5""",
            (since_iso,)
        ).fetchall()
        c.close()
        out["system"]["http_status_dist"] = {s: n for s, n in status_dist}
        out["system"]["top_denied_endpoints"] = [
            {"action": a, "count": n} for a, n in denied
        ]
    except Exception as e:
        out["system"]["http_audit_error"] = str(e)

    # ── PIPELINE health: jobs in each status across all time ───────────
    try:
        c = _conn_ro(CHAIN_DB)
        status_counts = c.execute(
            """SELECT status, COUNT(*) FROM chain_requests
               WHERE job_number IS NOT NULL GROUP BY status"""
        ).fetchall()
        stuck_at_zero = c.execute(
            """SELECT COUNT(*) FROM chain_requests
               WHERE job_number IS NOT NULL
                 AND status='active'
                 AND current_step_index = 0
                 AND created_at < datetime('now','-1 hour')"""
        ).fetchone()[0]
        c.close()
        out["agent"]["pipeline_status"] = {s: n for s, n in status_counts}
        out["agent"]["jobs_stuck_at_step_0"] = stuck_at_zero
    except Exception as e:
        out["agent"]["pipeline_status_error"] = str(e)

    return _ok(out)


@pipeline_router.post("/handoff")
def pipeline_handoff(payload: Dict[str, Any]):
    """
    Hand a structured brief to Murphy's swarm.

    Body:
      role: str — agent role (cto, executor, scheduler, hitl, etc.)
      brief: str — detailed task description
      context: dict — files/dbs/risk/rollback structured fields
      job_number: str (optional) — link to existing JOB-

    Returns the rosetta dag_id + the job_number for tracking.
    """
    try:
        import urllib.request
        import urllib.error
        role = payload.get("role", "executor")
        brief = payload.get("brief", "")
        context = payload.get("context", {})
        job_number = payload.get("job_number")
        if not brief:
            return _err("MISSING_BRIEF", "brief is required", 400)

        # Compose the rosetta question
        question = brief
        if job_number:
            question = f"[{job_number}] {question}"

        body = json.dumps({
            "role": role, "question": question, "context": context
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/rosetta/dispatch",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": _os_pl.environ.get(
                    "MURPHY_API_KEY",
                    "founder_ad6b1fade355dc1c6dfa89db96d77608886bf63b01b4fb70"
                ),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())

        return _ok({
            "job_number": job_number,
            "dag_id": result.get("dag_id"),
            "agents": result.get("assigned_agents", []),
            "verdict": result.get("rubix_verdict"),
            "soul_contexts_loaded": result.get("soul_contexts_loaded"),
        })
    except urllib.error.HTTPError as e:
        return _err("HANDOFF_HTTP", f"{e.code}: {e.read()[:200]}", 502)
    except Exception as e:
        return _err("HANDOFF_ERROR", str(e), 500)
