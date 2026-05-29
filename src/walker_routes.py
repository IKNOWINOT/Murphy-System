"""
PATCH-WALKER-ROUTES-001 (2026-05-28 R75 Part B) — HITL walker HTTP API

WHAT:
  Exposes hitl_review_walker (R74) as 4 HTTP endpoints so the walker is
  reachable from outside Python.

WHY:
  R74 walker has Python API only. Phase D UI needs HTTP. R75 ships the
  thin transport layer separately so app.py mount is single-line + risk
  to monolith is contained per Corey's R75 mount-point insight.

ENDPOINTS:
  GET  /api/hitl/walker/next?reviewer=X        → get_next
  POST /api/hitl/walker/decision                → record_decision (body: reviewer, item_id, action, note)
  GET  /api/hitl/walker/progress?reviewer=X     → get_progress
  POST /api/hitl/walker/rewind                  → rewind (body: reviewer, items)

MOUNT:
  In app.py: from src.walker_routes import router as walker_router
             app.include_router(walker_router)

LAST UPDATED: 2026-05-28 R75
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("walker_routes")

router = APIRouter(prefix="/api/hitl/walker", tags=["hitl-walker"])


class DecisionBody(BaseModel):
    reviewer: str
    item_id: str
    action: str  # verify | flag | suggest | skip | snooze
    note: Optional[str] = None


class RewindBody(BaseModel):
    reviewer: str
    items: int = 1


@router.get("/next")
def walker_next(reviewer: str):
    """Get the next review item for this reviewer (chronologically next)."""
    try:
        from src.hitl_review_walker import get_next
        item = get_next(reviewer)
        if item is None:
            return {"ok": True, "item": None, "message": "no items pending"}
        return {"ok": True, "item": item}
    except Exception as e:
        logger.exception("walker_next failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decision")
def walker_decision(body: DecisionBody):
    """Record a reviewer decision + advance cursor + return next item."""
    try:
        from src.hitl_review_walker import record_decision
        result = record_decision(body.reviewer, body.item_id, body.action, body.note)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "bad action"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("walker_decision failed")
        raise HTTPException(status_code=500, detail=str(e))


# PATCH-WALKER-PROGRESS-R80 — thin COUNT-based progress (no 1000-row scan)
import sqlite3 as _sql_r80
import os as _os_r80


def _thin_progress(reviewer: str) -> dict:
    """Compute progress via SELECT COUNT(*), not by materializing a list."""
    walker_db = "/var/lib/murphy-production/hitl_provenance.db"
    audit_db = "/var/lib/murphy-production/murphy_audit.db"

    # Fetch cursor (creates row if absent)
    from src.hitl_review_walker import _get_cursor
    cursor = _get_cursor(reviewer)
    cursor_ts = cursor.get("last_item_ts", "1970-01-01T00:00:00Z")

    remaining = 0
    try:
        conn = _sql_r80.connect(walker_db, timeout=3)
        r = conn.execute(
            "SELECT COUNT(*) FROM provenance_trails WHERE captured_at > ?",
            (cursor_ts,)
        ).fetchone()
        remaining += (r[0] if r else 0)
        conn.close()
    except Exception:
        pass

    try:
        if _os_r80.path.exists(audit_db):
            conn2 = _sql_r80.connect(audit_db, timeout=3)
            r2 = conn2.execute(
                "SELECT COUNT(*) FROM gfo_augmentations WHERE ts > ? AND refusal_detected = 1",
                (cursor_ts,)
            ).fetchone()
            remaining += (r2[0] if r2 else 0)
            conn2.close()
    except Exception:
        pass

    return {
        "reviewer_id": reviewer,
        "items_reviewed": cursor.get("items_reviewed", 0),
        "items_flagged": cursor.get("items_flagged", 0),
        "items_skipped": cursor.get("items_skipped", 0),
        "remaining": remaining,
        "cursor_at": cursor_ts,
        "last_active": cursor.get("last_active_at"),
    }


@router.get("/progress")
async def walker_progress(reviewer: str):
    """Reviewer progress summary — thin COUNT-only (R80 surgical)."""
    from fastapi.concurrency import run_in_threadpool
    try:
        progress = await run_in_threadpool(_thin_progress, reviewer)
        return {"ok": True, "progress": progress}
    except Exception as e:
        logger.exception("walker_progress failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rewind")
def walker_rewind(body: RewindBody):
    """Move cursor backward N items."""
    try:
        from src.hitl_review_walker import rewind
        return rewind(body.reviewer, body.items)
    except Exception as e:
        logger.exception("walker_rewind failed")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# PATCH-DRILL-EVIDENCE-R82 (R82) — Drill-down: trail → underlying evidence
# Corey R82 insight: every visible token should drill DOWN to source.
# evidence_snapshots was built R64 but never exposed via HTTP.
# This is the first drill-down endpoint.
# ═══════════════════════════════════════════════════════════════════

import sqlite3 as _sql_r82
import os as _os_r82
import json as _json_r82


def _fetch_evidence_for_trail(trail_id: str) -> dict:
    """PATCH-DRILL-EVIDENCE-R83-FIX — fetch evidence using REAL schema.

    evidence_snapshots schema: (evidence_id, label, method, raw_data, captured_at, wire_version)
    No trail_id column — link by matching label against trail source_hint.
    """
    walker_db = "/var/lib/murphy-production/hitl_provenance.db"
    if not _os_r82.path.exists(walker_db):
        return {"ok": False, "reason": "hitl_provenance.db not present"}
    try:
        conn = _sql_r82.connect(walker_db, timeout=3)
        conn.row_factory = _sql_r82.Row
        # Trail itself
        trail_row = conn.execute(
            "SELECT trail_id, command_module, command_function, source_kind, "
            "source_hint, hitl_status, captured_at FROM provenance_trails WHERE trail_id = ?",
            (trail_id,)
        ).fetchone()
        if not trail_row:
            conn.close()
            return {"ok": False, "reason": "trail " + trail_id + " not found"}
        trail = dict(trail_row)

        # PATCH-DRILL-R84-FK — use trail.evidence_id FK directly (correct schema)
        evidence_id_fk = trail.get("evidence_id")
        if evidence_id_fk:
            evidence_rows = conn.execute(
                "SELECT evidence_id, label, method, raw_data, captured_at "
                "FROM evidence_snapshots WHERE evidence_id = ?",
                (evidence_id_fk,)
            ).fetchall()
        else:
            # Fallback: best-effort label match
            source_hint = trail.get("source_hint", "") or ""
            evidence_rows = conn.execute(
                "SELECT evidence_id, label, method, raw_data, captured_at "
                "FROM evidence_snapshots WHERE label LIKE ? LIMIT 5",
                ("%" + source_hint[:30] + "%",)
            ).fetchall()
        conn.close()

        evidence = [dict(e) for e in evidence_rows]
        for e in evidence:
            try:
                e["data_parsed"] = _json_r82.loads(e["raw_data"])
            except Exception:
                pass

        prose = (
            "Trail " + trail_id[:12] + " came from " + str(trail["command_module"]) + "."
            + str(trail["command_function"]) + " reading the "
            + str(trail["source_kind"]) + " source: " + source_hint + ". "
            + "Status: " + str(trail["hitl_status"]) + ". "
            + "Captured: " + str(trail["captured_at"]) + ". "
        )
        if evidence:
            prose += "Found " + str(len(evidence)) + " evidence snapshot(s) matching the source hint."
        else:
            prose += "No evidence snapshots match this trail's source hint."

        return {
            "ok": True,
            "trail": trail,
            "evidence_snapshots": evidence,
            "evidence_count": len(evidence),
            "prose": prose,
        }
    except Exception as e:
        return {"ok": False, "reason": "db error: " + type(e).__name__ + ": " + str(e)}


@router.get("/evidence/{trail_id}")
async def walker_evidence(trail_id: str):
    """Drill from a trail_id down to its underlying evidence snapshots."""
    from fastapi.concurrency import run_in_threadpool
    try:
        result = await run_in_threadpool(_fetch_evidence_for_trail, trail_id)
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result.get("reason", "not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("walker_evidence failed")
        raise HTTPException(status_code=500, detail=str(e))

