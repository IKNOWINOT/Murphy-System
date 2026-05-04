"""
workflow_ops_router.py — PATCH-180
FastAPI router for WorkOps endpoints.
"""

import logging
import io
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("murphy.workflow_ops_router")

router = APIRouter(prefix="/api/ops", tags=["WorkOps"])


# ── Request Models ─────────────────────────────────────────────────────────────

class StartWorkflowRequest(BaseModel):
    template_id: str
    account_id: str = "system"
    priority: Optional[str] = None
    context: Optional[Dict[str, Any]] = {}


class PickupRequest(BaseModel):
    instance_id: str
    step_index: int
    agent_id: str
    pickup_data: Optional[Dict[str, Any]] = {}


class PutdownRequest(BaseModel):
    instance_id: str
    step_index: int
    agent_id: str
    putdown_data: Optional[Dict[str, Any]] = {}
    handoff_notes: str = ""
    next_agent_id: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    """List all 9 workflow templates with their step definitions."""
    try:
        from src.workflow_ops import get_templates
        return {"templates": get_templates()}
    except Exception as e:
        logger.error("list_templates error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/workflow/start")
async def start_workflow(req: StartWorkflowRequest):
    """Start a new workflow instance from a template."""
    try:
        from src.workflow_ops import start_workflow
        result = start_workflow(req.template_id, req.account_id, req.priority, req.context)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("start_workflow error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/step/pickup")
async def pickup_step(req: PickupRequest):
    """Agent picks up a workflow step."""
    try:
        from src.workflow_ops import pickup_step
        result = pickup_step(req.instance_id, req.step_index, req.agent_id, req.pickup_data)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/step/putdown")
async def putdown_step(req: PutdownRequest):
    """Agent completes and hands off a workflow step."""
    try:
        from src.workflow_ops import putdown_step
        result = putdown_step(req.instance_id, req.step_index, req.agent_id,
                              req.putdown_data, req.handoff_notes, req.next_agent_id)
        if "error" in result:
            raise HTTPException(404, result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/workflows")
async def list_instances(status: Optional[str] = None, limit: int = 50):
    """List workflow instances with step progress."""
    try:
        from src.workflow_ops import get_instances
        return {"instances": get_instances(status, limit)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/orgchart")
async def orgchart_overlay():
    """Org chart with live workflow overlay data."""
    try:
        from src.workflow_ops import get_orgchart_overlay
        return get_orgchart_overlay()
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/log")
async def activity_log(limit: int = Query(100, le=500)):
    """Recent workflow activity log."""
    try:
        from src.workflow_ops import get_recent_log
        return {"log": get_recent_log(limit)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/export/excel")
async def export_excel():
    """Download Excel workbook — 4 tabs: Ops Log, Org View, Plan vs Active, KPIs."""
    try:
        from src.workflow_ops import export_excel
        data = export_excel()
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=murphy_ops.xlsx"}
        )
    except Exception as e:
        logger.error("export_excel error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/status")
async def ops_status():
    """Public status endpoint — counts only."""
    try:
        import sqlite3, os
        db = "/var/lib/murphy-production/workflow_ops.db"
        if not os.path.exists(db):
            return {"active": 0, "complete": 0, "templates": 9}
        conn = sqlite3.connect(db, timeout=5)
        active = conn.execute("SELECT COUNT(*) FROM workflow_instances WHERE status=\'active\'").fetchone()[0]
        complete = conn.execute("SELECT COUNT(*) FROM workflow_instances WHERE status=\'complete\'").fetchone()[0]
        conn.close()
        return {"active": active, "complete": complete, "templates": 9}
    except Exception as e:
        return {"active": 0, "complete": 0, "templates": 9, "note": str(e)}
