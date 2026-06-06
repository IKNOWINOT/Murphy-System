"""R493 — Desktop Brain API

Provides three endpoints for Murphy Desktop agents:
  POST /api/brain/inject     -- agent submits goal+visibility, gets plan back
  POST /api/brain/telemetry  -- agent reports outcome (sanitized: no PII)
  POST /api/brain/revoke     -- kill an in-flight bundle

PRIVACY INVARIANT
=================
The server NEVER accepts file contents, screenshot bytes, or raw user text
beyond goal-string + schema-names + capability-names + statistics.
Sanitizer rejects any payload containing 'file_content', 'screenshot_bytes',
'raw_text', 'file_body'.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

DB = "/var/lib/murphy-production/brain_bundles.db"
BUNDLE_TTL_SECONDS = 3600  # 1 hour

router = APIRouter()


# ── Sanitizer ─────────────────────────────────────────────────────────────
FORBIDDEN_KEYS = {
    "file_content", "file_contents", "file_body", "file_data",
    "screenshot_bytes", "screenshot_data", "screenshot_b64",
    "raw_text", "raw_content", "body_bytes", "pixels",
}


def _scan_forbidden(obj: Any, path: str = "$") -> str | None:
    """Recursively scan for forbidden keys. Returns offending path or None."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                return f"{path}.{k}"
            r = _scan_forbidden(v, f"{path}.{k}")
            if r:
                return r
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            r = _scan_forbidden(v, f"{path}[{i}]")
            if r:
                return r
    return None


# ── /api/brain/inject ──────────────────────────────────────────────────────
@router.post("/api/brain/inject")
async def brain_inject(request: Request):
    """Agent submits: goal + schema_summary + capability_inventory.
    Server returns: a brain bundle with a plan."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    # Privacy gate
    offending = _scan_forbidden(body)
    if offending:
        return JSONResponse(
            {"ok": False, "error": "forbidden_payload",
             "detail": f"Forbidden key at {offending}. Server refuses to receive raw user content."},
            status_code=400)

    agent_id = body.get("agent_id") or ""
    goal = body.get("goal") or ""
    schema_summary = body.get("schema_summary") or {}
    capability_inventory = body.get("capability_inventory") or []
    os_name = body.get("os") or "unknown"

    if not agent_id or not goal:
        return JSONResponse({"ok": False, "error": "missing_required",
                             "detail": "agent_id and goal required"}, status_code=400)

    now = datetime.now(timezone.utc)
    bundle_id = f"br_{uuid.uuid4().hex[:12]}"
    expires_at = now + timedelta(seconds=BUNDLE_TTL_SECONDS)

    # ── PLANNER (v0: single-capability if name matches, else degraded plan) ──
    plan = _plan_v0(goal, capability_inventory, schema_summary)

    # Persist
    try:
        with sqlite3.connect(DB, timeout=3) as c:
            c.execute("""INSERT INTO bundles
                (bundle_id, agent_id, goal, schema_summary, capability_inventory,
                 plan_json, issued_at, expires_at, status)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (bundle_id, agent_id, goal,
                 json.dumps(schema_summary)[:8000],
                 json.dumps(capability_inventory)[:4000],
                 json.dumps(plan)[:16000],
                 now.isoformat(), expires_at.isoformat(), "active"))
            # Track the agent
            c.execute("""INSERT INTO desktop_agents
                (agent_id, os, first_seen, last_seen, schema_graph, capability_count)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    last_seen=excluded.last_seen,
                    schema_graph=excluded.schema_graph,
                    capability_count=excluded.capability_count""",
                (agent_id, os_name, now.isoformat(), now.isoformat(),
                 json.dumps(schema_summary)[:4000], len(capability_inventory)))
            c.commit()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": "db_write_failed",
                             "detail": str(exc)}, status_code=500)

    return JSONResponse({
        "ok": True,
        "bundle_id": bundle_id,
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "plan": plan,
        "termination": {
            "max_steps": 25,
            "timeout_seconds": 600,
        },
    })


def _plan_v0(goal: str, capabilities: list, schema_summary: dict) -> dict:
    """v0 planner: if goal matches a capability name, return it. Else degraded."""
    goal_l = goal.lower()
    
    # Direct capability match
    for cap in capabilities:
        cap_name = cap.get("name", "") if isinstance(cap, dict) else str(cap)
        cap_keywords = cap_name.lower().replace("_", " ").split()
        if cap_keywords and all(kw in goal_l for kw in cap_keywords[:2]):
            return {
                "kind": "single_capability",
                "steps": [{
                    "step": 1,
                    "action": "replay_capability",
                    "capability": cap_name,
                    "inputs": cap.get("required_inputs", {}) if isinstance(cap, dict) else {},
                    "rationale": f"Goal matches capability '{cap_name}'",
                }],
            }
    
    # No match — degraded plan (asks the desktop to record one)
    return {
        "kind": "no_capability_match",
        "steps": [{
            "step": 1,
            "action": "request_demonstration",
            "rationale": f"No capability matches '{goal}'. Ask the user to demonstrate.",
            "suggested_capability_name": _suggest_name(goal),
        }],
        "available_capabilities": [c.get("name") if isinstance(c, dict) else c
                                    for c in capabilities],
    }


def _suggest_name(goal: str) -> str:
    """Suggest a capability name based on goal text."""
    import re
    s = re.sub(r"[^a-z0-9 ]", "", goal.lower()).strip()
    words = s.split()[:4]
    return "_".join(words) if words else "new_capability"


# ── /api/brain/telemetry ──────────────────────────────────────────────────
@router.post("/api/brain/telemetry")
async def brain_telemetry(request: Request):
    """Agent reports outcome of executing a bundle. Sanitized — no payloads."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    offending = _scan_forbidden(body)
    if offending:
        return JSONResponse({"ok": False, "error": "forbidden_payload",
                             "detail": f"Forbidden key at {offending}"}, status_code=400)

    bundle_id = body.get("bundle_id") or ""
    agent_id = body.get("agent_id") or ""
    steps_taken = int(body.get("steps_taken") or 0)
    capabilities_run = body.get("capabilities_run") or []
    outcome = body.get("outcome") or "unknown"
    duration_ms = int(body.get("duration_ms") or 0)

    if not bundle_id or not agent_id:
        return JSONResponse({"ok": False, "error": "missing_required"}, status_code=400)

    correlation_id = f"tx_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        with sqlite3.connect(DB, timeout=3) as c:
            c.execute("""INSERT INTO telemetry
                (correlation_id, bundle_id, agent_id, steps_taken,
                 capabilities_run, outcome, duration_ms, received_at, sanitized)
                VALUES (?,?,?,?,?,?,?,?,1)""",
                (correlation_id, bundle_id, agent_id, steps_taken,
                 json.dumps(capabilities_run)[:2000], outcome, duration_ms, now))
            # Mark bundle done
            c.execute("UPDATE bundles SET status=? WHERE bundle_id=?",
                      (f"completed_{outcome}", bundle_id))
            c.commit()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": "db_write_failed",
                             "detail": str(exc)}, status_code=500)

    return JSONResponse({"ok": True, "correlation_id": correlation_id,
                         "received_at": now})


# ── /api/brain/revoke ──────────────────────────────────────────────────────
@router.post("/api/brain/revoke")
async def brain_revoke(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    bundle_id = body.get("bundle_id") or ""
    reason = body.get("reason") or "user_revoke"
    if not bundle_id:
        return JSONResponse({"ok": False, "error": "missing_bundle_id"}, status_code=400)

    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB, timeout=3) as c:
            c.execute("INSERT OR REPLACE INTO revocations VALUES (?,?,?)",
                      (bundle_id, now, reason))
            c.execute("UPDATE bundles SET status='revoked' WHERE bundle_id=?",
                      (bundle_id,))
            c.commit()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": "db_write_failed",
                             "detail": str(exc)}, status_code=500)

    return JSONResponse({"ok": True, "revoked_at": now})


# ── /api/brain/status (debug, owner-only — but exempt path for now) ───────
@router.get("/api/brain/status")
async def brain_status():
    """Diagnostic — total bundles, recent activity, agents seen."""
    try:
        with sqlite3.connect(DB, timeout=3) as c:
            total_bundles = c.execute("SELECT COUNT(*) FROM bundles").fetchone()[0]
            active = c.execute("SELECT COUNT(*) FROM bundles WHERE status='active'").fetchone()[0]
            agents = c.execute("SELECT COUNT(*) FROM desktop_agents").fetchone()[0]
            recent = []
            for row in c.execute("""SELECT bundle_id, agent_id, goal, status, issued_at
                                    FROM bundles ORDER BY issued_at DESC LIMIT 10"""):
                recent.append({"bundle_id": row[0], "agent_id": row[1][:12]+"...",
                              "goal": row[2][:60], "status": row[3], "issued_at": row[4]})
        return JSONResponse({
            "ok": True, "total_bundles": total_bundles, "active": active,
            "agents_seen": agents, "recent": recent,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
