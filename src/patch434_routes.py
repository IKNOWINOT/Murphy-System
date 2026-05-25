"""
PATCH-434 — /api/policy/autonomy routes
Founder-only writes via X-API-Key match. Public reads for transparency.
"""
import os
import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

DB = "/var/lib/murphy-production/murphy_mail.db"
router = APIRouter()


def _is_founder(request: Request) -> bool:
    key = request.headers.get("X-API-Key") or request.headers.get("x-api-key") or ""
    founder = os.environ.get("FOUNDER_API_KEY") or os.environ.get("MURPHY_API_KEY", "")
    return bool(key and founder and key == founder)


def _emit(event_type: str, payload: dict):
    try:
        import sys
        sys.path.insert(0, "/opt/Murphy-System")
        from src.patch400_event_spine import emit_event
        emit_event(event_type=event_type, source="patch434", payload=payload)
    except Exception:
        pass


@router.get("/api/policy/autonomy")
async def list_policy():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM agent_action_policy ORDER BY role, action_type
    """).fetchall()
    conn.close()
    return JSONResponse({"ok": True, "count": len(rows), "policies": [dict(r) for r in rows]})


@router.get("/api/policy/autonomy/history")
async def policy_history(limit: int = 100):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM agent_action_policy_history ORDER BY changed_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return JSONResponse({"ok": True, "count": len(rows), "history": [dict(r) for r in rows]})


@router.post("/api/policy/autonomy")
async def update_policy(request: Request):
    if not _is_founder(request):
        raise HTTPException(status_code=403, detail="Only the founder can change autonomy policy")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    role = body.get("role")
    action_type = body.get("action_type")
    reason = (body.get("reason") or "").strip()
    if not (role and action_type):
        raise HTTPException(status_code=400, detail="role and action_type required")
    if not reason:
        raise HTTPException(status_code=400, detail="reason required — explain why")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM agent_action_policy WHERE role=? AND action_type=?",
        (role, action_type)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Policy not found for {role}/{action_type}")
    current = dict(row)

    new_master = body.get("master_enabled", current["master_enabled"])
    new_master_int = 1 if (new_master in (True, 1, "true", "True")) else 0
    # PATCH-438-B: relaxed — allow audit_gate OR mfgc_authority
    has_audit = bool(current.get("has_audit_gate", 0))
    has_mfgc  = bool(current.get("has_mfgc_authority", 0))
    if new_master_int == 1 and not (has_audit or has_mfgc):
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Cannot enable autonomy for {action_type} — no audit gate "
                   "AND no MFGC authority. Locked at master_enabled=0 by invariant."
        )

    new_min_conf = float(body.get("min_confidence", current["min_confidence"]))
    new_max_day = int(body.get("max_per_day", current["max_per_day"]))
    if not (0.0 <= new_min_conf <= 1.0):
        conn.close()
        raise HTTPException(status_code=400, detail="min_confidence must be 0.0-1.0")
    if new_max_day < 0:
        conn.close()
        raise HTTPException(status_code=400, detail="max_per_day must be >= 0")

    now = datetime.now(timezone.utc).isoformat()
    changes = []
    for field, old, new in [
        ("master_enabled", current["master_enabled"], new_master_int),
        ("min_confidence", current["min_confidence"], new_min_conf),
        ("max_per_day",    current["max_per_day"],    new_max_day),
    ]:
        if str(old) != str(new):
            conn.execute("""
                INSERT INTO agent_action_policy_history
                (role, action_type, field_name, old_value, new_value, changed_by, reason, changed_at)
                VALUES (?, ?, ?, ?, ?, 'founder', ?, ?)
            """, (role, action_type, field, str(old), str(new), reason, now))
            changes.append({"field": field, "old": old, "new": new})

    conn.execute("""
        UPDATE agent_action_policy
        SET master_enabled=?, min_confidence=?, max_per_day=?,
            last_changed_at=?, last_changed_by='founder', last_change_reason=?
        WHERE role=? AND action_type=?
    """, (new_master_int, new_min_conf, new_max_day, now, reason, role, action_type))
    conn.commit()
    conn.close()

    _emit("policy.autonomy_changed", {
        "role": role, "action_type": action_type,
        "changes": changes, "reason": reason, "changed_at": now,
    })
    return JSONResponse({"ok": True, "role": role, "action_type": action_type,
                         "changes": changes, "changed_at": now})


def init_policy_routes(app):
    app.include_router(router)
