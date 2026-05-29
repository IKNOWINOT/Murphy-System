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


@router.get("/progress")
def walker_progress(reviewer: str):
    """Reviewer progress summary."""
    try:
        from src.hitl_review_walker import get_progress
        return {"ok": True, "progress": get_progress(reviewer)}
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
