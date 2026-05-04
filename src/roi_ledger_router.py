"""
roi_ledger_router.py — PATCH-180b
FastAPI endpoints for ROI ledger.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("murphy.roi_ledger_router")
router = APIRouter(prefix="/api/roi", tags=["ROI Ledger"])


class LogActionRequest(BaseModel):
    agent_id: str
    action_type: str
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    step_name: Optional[str] = None
    time_spent_s: Optional[float] = None
    money_value_usd: Optional[float] = None
    notes: str = ""
    context: Optional[Dict[str, Any]] = {}


class SetTargetRequest(BaseModel):
    period: str
    name: str
    target_value_usd: float
    target_time_s: float = 0
    lane: Optional[str] = None


@router.post("/log")
async def log_action(req: LogActionRequest):
    from src.roi_ledger import log_action as _log
    result = _log(req.agent_id, req.action_type, req.workflow_id,
                  req.workflow_name, req.step_name, req.time_spent_s,
                  req.money_value_usd, req.notes, req.context)
    return result


@router.get("/summary")
async def roi_summary(days: int = Query(7, ge=1, le=90)):
    from src.roi_ledger import get_summary
    return get_summary(days)


@router.get("/entries")
async def roi_entries(limit: int = Query(100, le=500)):
    from src.roi_ledger import get_recent_entries
    return {"entries": get_recent_entries(limit)}


@router.get("/targets")
async def roi_targets(period: Optional[str] = None):
    from src.roi_ledger import get_targets_vs_actual
    return {"targets": get_targets_vs_actual(period)}


@router.post("/targets")
async def set_target(req: SetTargetRequest):
    from src.roi_ledger import set_target as _set
    return _set(req.period, req.name, req.target_value_usd, req.target_time_s, req.lane)


@router.get("/catalog")
async def action_catalog():
    from src.roi_ledger import ACTION_CATALOG, AGENT_LANE
    return {"catalog": ACTION_CATALOG, "agent_lanes": AGENT_LANE}


@router.get("/status")
async def roi_status():
    """Public summary — no auth."""
    try:
        import sqlite3, os
        db = "/var/lib/murphy-production/roi_ledger.db"
        if not os.path.exists(db):
            return {"total_value_usd": 0, "total_actions": 0, "status": "empty"}
        conn = sqlite3.connect(db, timeout=5)
        row = conn.execute(
            "SELECT COUNT(*) as c, SUM(money_value_usd) as v FROM roi_entries"
        ).fetchone()
        conn.close()
        return {"total_actions": row[0], "total_value_usd": round(row[1] or 0, 2)}
    except Exception as e:
        return {"total_value_usd": 0, "total_actions": 0, "error": str(e)}
