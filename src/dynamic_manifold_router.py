"""
dynamic_manifold_router.py — PATCH-184
FastAPI router for the Dynamic Manifold Engine (gap correction + risk mitigation).
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger("murphy.dynamic_manifold_router")
router = APIRouter(prefix="/api/manifold/gaps", tags=["Dynamic Manifold"])


class CloseGapReq(BaseModel):
    closed_by: str = "system"
    resolution_note: str = ""

class EscalateGapReq(BaseModel):
    reason: str = ""
    escalated_by: str = "system"


@router.get("")
async def list_gaps(project_id: Optional[str]=None, status: str="open",
                    tier: Optional[str]=None, limit: int=100):
    from src.dynamic_manifold import get_gaps
    return {"gaps": get_gaps(project_id, status, tier, limit)}

@router.get("/summary")
async def gap_summary(project_id: Optional[str]=None):
    from src.dynamic_manifold import get_gap_summary
    return get_gap_summary(project_id)

@router.get("/exposure")
async def risk_exposure(project_id: Optional[str]=None):
    from src.dynamic_manifold import get_risk_exposure
    return get_risk_exposure(project_id)

@router.post("/scan")
async def trigger_scan(project_id: Optional[str]=None):
    from src.dynamic_manifold import scan_project
    return scan_project(project_id)

@router.get("/status")
async def gap_status():
    from src.dynamic_manifold import get_status
    return get_status()

@router.post("/{prescription_id}/close")
async def close_gap(prescription_id: str, req: CloseGapReq):
    from src.dynamic_manifold import close_gap as _cg
    r = _cg(prescription_id, req.closed_by, req.resolution_note)
    if "error" in r: raise HTTPException(400, r["error"])
    return r

@router.post("/{prescription_id}/escalate")
async def escalate_gap(prescription_id: str, req: EscalateGapReq):
    from src.dynamic_manifold import escalate_gap as _eg
    return _eg(prescription_id, req.reason, req.escalated_by)
