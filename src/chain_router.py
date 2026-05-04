"""
chain_router.py — PATCH-183
FastAPI router for the Workflow Chain Engine.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("murphy.chain_router")
router = APIRouter(prefix="/api/chains", tags=["Chain Engine"])


class CreateChainReq(BaseModel):
    template_id: str
    name: Optional[str] = None
    project_id: Optional[str] = None
    requestor: str = "system"
    context: Optional[Dict[str, Any]] = {}

class AdvanceStepReq(BaseModel):
    step_index: int
    agent_id: str = "system"
    record_ids: Optional[List[str]] = []
    notes: str = ""

class WaiverReq(BaseModel):
    step_index: int
    reason: str
    waived_by: str = "system"


@router.get("/templates")
async def list_templates():
    from src.chain_engine import get_templates
    return {"templates": get_templates()}

@router.post("/requests")
async def create_chain(req: CreateChainReq):
    from src.chain_engine import create_chain as _cc
    r = _cc(req.template_id, req.name, req.project_id, req.requestor, req.context)
    if "error" in r: raise HTTPException(400, r["error"])
    return r

@router.get("/requests")
async def list_chains(project_id: Optional[str]=None, status: Optional[str]=None, limit: int=50):
    from src.chain_engine import list_chains as _lc
    return {"chains": _lc(project_id, status, limit)}

@router.get("/requests/{chain_id}")
async def get_chain(chain_id: str):
    from src.chain_engine import get_chain as _gc
    c = _gc(chain_id)
    if not c: raise HTTPException(404, "Chain not found")
    return c

@router.post("/requests/{chain_id}/advance")
async def advance_step(chain_id: str, req: AdvanceStepReq):
    from src.chain_engine import advance_step as _as
    r = _as(chain_id, req.step_index, req.agent_id, req.record_ids, req.notes)
    if isinstance(r, dict) and "error" in r: raise HTTPException(400, r["error"])
    return r

@router.post("/requests/{chain_id}/waive")
async def raise_waiver(chain_id: str, req: WaiverReq):
    from src.chain_engine import raise_waiver as _rw
    return _rw(chain_id, req.step_index, req.reason, req.waived_by)

@router.post("/requests/{chain_id}/regate")
async def regate_chain(chain_id: str):
    from src.chain_engine import regate_chain as _rg
    return _rg(chain_id)

@router.get("/requests/{chain_id}/summary")
async def info_id_summary(chain_id: str):
    from src.chain_engine import get_info_id_summary as _gs
    return _gs(chain_id)

@router.get("/log")
async def chain_log(chain_id: Optional[str]=None, limit: int=100):
    from src.chain_engine import get_log as _gl
    return {"log": _gl(chain_id, limit)}

@router.get("/status")
async def chain_status():
    from src.chain_engine import get_status
    return get_status()
