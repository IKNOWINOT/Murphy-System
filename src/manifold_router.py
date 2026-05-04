"""
manifold_router.py — PATCH-181
FastAPI endpoints for the Manifold Planning Engine.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger("murphy.manifold_router")
router = APIRouter(prefix="/api/manifold", tags=["Manifold"])


# ── Request models ─────────────────────────────────────────────────────────────

class CreateProjectReq(BaseModel):
    name: str
    client: str = ""
    description: str = ""
    budget_usd: float = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    color: str = "#00d4ff"

class UpdateProjectReq(BaseModel):
    name: Optional[str] = None
    client: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    budget_usd: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    color: Optional[str] = None

class CreateBlockReq(BaseModel):
    project_id: str
    name: str
    start_date: str
    end_date: str
    block_type: str = "sprint"
    description: str = ""
    color: Optional[str] = None
    position: int = 0

class CreateMilestoneReq(BaseModel):
    block_id: str
    project_id: str
    name: str
    description: str = ""
    due_date: Optional[str] = None
    priority: str = "medium"
    owner: str = ""
    estimated_hours: float = 0
    estimated_cost_usd: float = 0
    position: int = 0

class UpdateMilestoneReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    owner: Optional[str] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None

class CreateDetailItemReq(BaseModel):
    milestone_id: str
    project_id: str
    block_id: str
    name: str
    item_type: str = "task"
    description: str = ""
    owner: str = ""
    due_date: Optional[str] = None
    estimated_hours: float = 0
    position: int = 0
    parent_item_id: Optional[str] = None

class UpdateDetailItemReq(BaseModel):
    name: Optional[str] = None
    item_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    due_date: Optional[str] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None

class AddManifoldEntryReq(BaseModel):
    detail_item_id: str
    entry_type: str   # assumption | actual | info_gap | decision | known_at
    title: str
    body: str = ""
    depends_on_id: Optional[str] = None
    financial_impact_usd: float = 0
    confidence: float = 0.5
    known_by: str = "user"

class ResolveEntryReq(BaseModel):
    resolved_by: str
    actual_body: Optional[str] = None
    new_financial_impact: Optional[float] = None

class AckChangeReq(BaseModel):
    acknowledged_by: str


# ── Projects ───────────────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects():
    from src.manifold import list_projects as _lp
    return {"projects": _lp()}

@router.post("/projects")
async def create_project(req: CreateProjectReq):
    from src.manifold import create_project as _cp
    return _cp(**req.dict())

@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    from src.manifold import get_project as _gp
    p = _gp(project_id)
    if not p: raise HTTPException(404, "Project not found")
    return p

@router.patch("/projects/{project_id}")
async def update_project(project_id: str, req: UpdateProjectReq):
    from src.manifold import update_project as _up
    fields = {k: v for k, v in req.dict().items() if v is not None}
    return _up(project_id, **fields)

@router.get("/projects/{project_id}/tree")
async def project_tree(project_id: str):
    from src.manifold import get_project_tree as _gpt
    t = _gpt(project_id)
    if "error" in t: raise HTTPException(404, t["error"])
    return t


# ── Calendar Blocks ────────────────────────────────────────────────────────────

@router.get("/blocks")
async def list_blocks(project_id: Optional[str] = None):
    from src.manifold import list_blocks as _lb
    return {"blocks": _lb(project_id)}

@router.post("/blocks")
async def create_block(req: CreateBlockReq):
    from src.manifold import create_block as _cb
    return _cb(req.project_id, req.name, req.start_date, req.end_date,
               req.block_type, req.description, req.color, req.position)

@router.get("/blocks/{block_id}")
async def get_block(block_id: str):
    from src.manifold import get_block as _gb
    b = _gb(block_id)
    if not b: raise HTTPException(404, "Block not found")
    return b


# ── Milestones ─────────────────────────────────────────────────────────────────

@router.post("/milestones")
async def create_milestone(req: CreateMilestoneReq):
    from src.manifold import create_milestone as _cm
    return _cm(req.block_id, req.name, req.project_id, req.description,
               req.due_date, req.priority, req.owner,
               req.estimated_hours, req.estimated_cost_usd, req.position)

@router.get("/milestones/{milestone_id}")
async def get_milestone(milestone_id: str):
    from src.manifold import get_milestone as _gm
    m = _gm(milestone_id)
    if not m: raise HTTPException(404, "Milestone not found")
    return m

@router.patch("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, req: UpdateMilestoneReq):
    from src.manifold import update_milestone as _um
    fields = {k: v for k, v in req.dict().items() if v is not None}
    return _um(milestone_id, **fields)


# ── Detail Items ───────────────────────────────────────────────────────────────

@router.post("/detail-items")
async def create_detail_item(req: CreateDetailItemReq):
    from src.manifold import create_detail_item as _cdi
    return _cdi(req.milestone_id, req.name, req.project_id, req.block_id,
                req.item_type, req.description, req.owner, req.due_date,
                req.estimated_hours, req.position, req.parent_item_id)

@router.get("/detail-items/{item_id}")
async def get_detail_item(item_id: str):
    from src.manifold import get_detail_item as _gdi
    d = _gdi(item_id)
    if not d: raise HTTPException(404, "Detail item not found")
    return d

@router.patch("/detail-items/{item_id}")
async def update_detail_item(item_id: str, req: UpdateDetailItemReq):
    from src.manifold import update_detail_item as _udi
    fields = {k: v for k, v in req.dict().items() if v is not None}
    return _udi(item_id, **fields)


# ── Manifold Entries ───────────────────────────────────────────────────────────

@router.post("/entries")
async def add_entry(req: AddManifoldEntryReq):
    from src.manifold import add_manifold_entry as _ame
    return _ame(req.detail_item_id, req.entry_type, req.title, req.body,
                req.depends_on_id, req.financial_impact_usd, req.confidence,
                req.known_by)

@router.post("/entries/{entry_id}/resolve")
async def resolve_entry(entry_id: str, req: ResolveEntryReq):
    from src.manifold import resolve_entry as _re
    return _re(entry_id, req.resolved_by, req.actual_body, req.new_financial_impact)


# ── Change Events ──────────────────────────────────────────────────────────────

@router.get("/changes")
async def list_changes(project_id: Optional[str] = None,
                       unacked_only: bool = False, limit: int = 100):
    from src.manifold import get_change_events as _gce
    return {"changes": _gce(project_id, unacked_only, limit)}

@router.post("/changes/{event_id}/acknowledge")
async def ack_change(event_id: str, req: AckChangeReq):
    from src.manifold import acknowledge_change as _ac
    return _ac(event_id, req.acknowledged_by)


# ── Public status ──────────────────────────────────────────────────────────────

@router.get("/status")
async def manifold_status():
    try:
        import sqlite3, os
        db = "/var/lib/murphy-production/manifold.db"
        if not os.path.exists(db):
            return {"projects": 0, "blocks": 0, "entries": 0}
        conn = sqlite3.connect(db, timeout=5)
        p = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        b = conn.execute("SELECT COUNT(*) FROM calendar_blocks").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM manifold_entries").fetchone()[0]
        ce = conn.execute("SELECT COUNT(*) FROM change_events WHERE acknowledged=0").fetchone()[0]
        conn.close()
        return {"projects": p, "blocks": b, "entries": e, "pending_changes": ce}
    except Exception as ex:
        return {"projects": 0, "blocks": 0, "entries": 0, "error": str(ex)}
