"""
PATCH-072b: Management AI Activation Router

Exposes all 9 management_systems engines as REST API endpoints.

Endpoints:
  -- Boards --
  POST   /api/mgmt/boards                    — create board
  GET    /api/mgmt/boards                    — list boards
  GET    /api/mgmt/boards/{board_id}         — get board
  DELETE /api/mgmt/boards/{board_id}         — delete board
  POST   /api/mgmt/boards/{board_id}/items   — add item to board
  PATCH  /api/mgmt/boards/{board_id}/items/{item_id} — update item
  DELETE /api/mgmt/boards/{board_id}/items/{item_id} — delete item

  -- Status Engine --
  GET    /api/mgmt/status/columns            — list status columns
  POST   /api/mgmt/status/columns            — create status column
  POST   /api/mgmt/status/set               — set item status
  GET    /api/mgmt/status/progress/{column_id} — progress bar

  -- Workspaces --
  GET    /api/mgmt/workspaces               — list workspaces
  POST   /api/mgmt/workspaces               — create workspace
  GET    /api/mgmt/workspaces/{ws_id}       — get workspace
  POST   /api/mgmt/workspaces/bootstrap     — bootstrap Murphy default workspaces

  -- Dashboard --
  GET    /api/mgmt/dashboards/templates     — list dashboard templates
  POST   /api/mgmt/dashboards/report        — generate report
  POST   /api/mgmt/dashboards/standup       — generate standup
  POST   /api/mgmt/dashboards/weekly        — generate weekly report

  -- Automation Recipes --
  GET    /api/mgmt/recipes                  — list recipes
  POST   /api/mgmt/recipes                  — create recipe
  GET    /api/mgmt/recipes/templates        — list recipe templates
  POST   /api/mgmt/recipes/from-template    — create from template
  POST   /api/mgmt/recipes/event            — process an event through recipes

  -- Timeline --
  GET    /api/mgmt/timeline                 — list timeline items
  POST   /api/mgmt/timeline                 — add timeline item
  PATCH  /api/mgmt/timeline/{item_id}/progress — update progress
  GET    /api/mgmt/timeline/critical-path   — calculate critical path

  -- Health --
  GET    /api/mgmt/health                   — management systems health check

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
PATCH-072b
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mgmt", tags=["management-ai"])

# ── Lazy singletons ───────────────────────────────────────────────────────────
_board = _status = _ws = _dash = _recipe = _timeline = None

def _B():
    global _board
    if _board is None:
        from management_systems.board_engine import BoardEngine
        _board = BoardEngine()
        logger.info("PATCH-072b: BoardEngine initialised")
    return _board

def _S():
    global _status
    if _status is None:
        from management_systems.status_engine import StatusEngine
        _status = StatusEngine()
        logger.info("PATCH-072b: StatusEngine initialised")
    return _status

def _W():
    global _ws
    if _ws is None:
        from management_systems.workspace_manager import WorkspaceManager
        _ws = WorkspaceManager()
        logger.info("PATCH-072b: WorkspaceManager initialised")
    return _ws

def _D():
    global _dash
    if _dash is None:
        from management_systems.dashboard_generator import DashboardGenerator
        _dash = DashboardGenerator()
        logger.info("PATCH-072b: DashboardGenerator initialised")
    return _dash

def _R():
    global _recipe
    if _recipe is None:
        from management_systems.automation_recipes import RecipeEngine
        _recipe = RecipeEngine()
        logger.info("PATCH-072b: RecipeEngine initialised")
    return _recipe

def _T():
    global _timeline
    if _timeline is None:
        from management_systems.timeline_engine import TimelineEngine
        _timeline = TimelineEngine()
        logger.info("PATCH-072b: TimelineEngine initialised")
    return _timeline

# ── Schemas ──────────────────────────────────────────────────────────────────
class BoardCreate(BaseModel):
    name: str
    description: str = ""
    template: str = "kanban"

class ItemCreate(BaseModel):
    name: str
    description: str = ""
    assignee: str = ""
    status: str = "todo"
    priority: str = "medium"

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None

class StatusSet(BaseModel):
    column_id: str
    item_id: str
    status_key: str
    actor: str = "system"

class StatusColumnCreate(BaseModel):
    name: str
    labels: List[str] = ["todo", "in_progress", "done"]

class WorkspaceCreate(BaseModel):
    name: str
    domain: str = "general"
    description: str = ""

class ReportRequest(BaseModel):
    template_id: str = "project_status"
    context: Dict[str, Any] = {}

class RecipeCreate(BaseModel):
    name: str
    trigger_type: str = "status_change"
    trigger_value: str = ""
    action_type: str = "notify"
    action_config: Dict[str, Any] = {}

class RecipeFromTemplate(BaseModel):
    template_id: str
    name: str = ""
    config: Dict[str, Any] = {}

class RecipeEvent(BaseModel):
    event_type: str
    payload: Dict[str, Any] = {}

class TimelineItem(BaseModel):
    name: str
    start_date: str
    end_date: str
    assignee: str = ""
    priority: str = "medium"
    description: str = ""

class ProgressUpdate(BaseModel):
    progress_pct: float
    note: str = ""

# ── Board routes ─────────────────────────────────────────────────────────────
@router.post("/boards")
def create_board(req: BoardCreate):
    try:
        board = _B().create_board(name=req.name, description=req.description)
        return {"ok": True, "board": _ser(board)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.get("/boards")
def list_boards():
    try:
        boards = _B().list_boards()
        return {"ok": True, "boards": [_ser(b) for b in boards], "total": len(boards)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.get("/boards/{board_id}")
def get_board(board_id: str):
    b = _B().get_board(board_id)
    if b is None:
        raise HTTPException(404, f"Board {board_id} not found")
    return {"ok": True, "board": _ser(b)}

@router.delete("/boards/{board_id}")
def delete_board(board_id: str):
    ok = _B().delete_board(board_id)
    return {"ok": ok}

@router.post("/boards/{board_id}/items")
def add_item(board_id: str, req: ItemCreate):
    try:
        # Get or create default group
        board = _B().get_board(board_id)
        if board is None:
            raise HTTPException(404, "Board not found")
        groups = getattr(board, "groups", None) or []
        group_id = groups[0].id if groups and hasattr(groups[0], "id") else (
                   list(groups.keys())[0] if isinstance(groups, dict) else "default")
        cell_values = {"status": req.status, "priority": req.priority,
                       "assignee": req.assignee, "description": req.description}
        item = _B().add_item(board_id=board_id, group_id=str(group_id),
                             name=req.name, cell_values=cell_values,
                             created_by=req.assignee or "system")
        return {"ok": True, "item": _ser(item)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.patch("/boards/{board_id}/items/{item_id}")
def update_item(board_id: str, item_id: str, req: ItemUpdate):
    try:
        updates = {k: v for k, v in req.dict().items() if v is not None}
        item = _B().update_item(board_id=board_id, item_id=item_id, **updates)
        return {"ok": True, "item": _ser(item)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.delete("/boards/{board_id}/items/{item_id}")
def delete_item(board_id: str, item_id: str):
    ok = _B().delete_item(board_id=board_id, item_id=item_id)
    return {"ok": ok}

# ── Status Engine routes ──────────────────────────────────────────────────────
@router.get("/status/columns")
def list_status_columns():
    columns = _S().list_columns()
    return {"ok": True, "columns": [_ser(c) for c in columns]}

@router.post("/status/columns")
def create_status_column(req: StatusColumnCreate):
    col = _S().create_column(name=req.name, labels=req.labels)
    return {"ok": True, "column": _ser(col)}

@router.post("/status/set")
def set_status(req: StatusSet):
    try:
        result = _S().set_status(column_id=req.column_id, item_id=req.item_id,
                                  status_key=req.status_key, actor=req.actor)
        return {"ok": True, "result": _ser(result)}
    except Exception as exc:
        raise HTTPException(400, str(exc))

@router.get("/status/progress/{column_id}")
def get_progress(column_id: str):
    pct = _S().calculate_progress(column_id)
    bar = _S().render_progress_bar(column_id)
    return {"ok": True, "column_id": column_id, "progress_pct": pct, "bar": bar}

# ── Workspace routes ─────────────────────────────────────────────────────────
@router.get("/workspaces")
def list_workspaces():
    ws = _W().list_workspaces()
    return {"ok": True, "workspaces": [_ser(w) for w in ws], "total": len(ws)}

@router.post("/workspaces")
def create_workspace(req: WorkspaceCreate):
    ws = _W().create_workspace(name=req.name, domain=req.domain,
                               description=req.description)
    return {"ok": True, "workspace": _ser(ws)}

@router.get("/workspaces/{ws_id}")
def get_workspace(ws_id: str):
    ws = _W().get_workspace(ws_id)
    if ws is None:
        raise HTTPException(404, f"Workspace {ws_id} not found")
    return {"ok": True, "workspace": _ser(ws)}

@router.post("/workspaces/bootstrap")
def bootstrap_workspaces():
    result = _W().bootstrap_murphy_workspaces()
    return {"ok": True, "bootstrapped": _ser(result)}

# ── Dashboard routes ─────────────────────────────────────────────────────────
@router.get("/dashboards/templates")
def list_dashboard_templates():
    templates = _D().list_templates()
    return {"ok": True, "templates": [_ser(t) for t in templates]}

@router.post("/dashboards/report")
def generate_report(req: ReportRequest):
    try:
        from management_systems.dashboard_generator import DashboardTemplateType
        try:
            ttype = DashboardTemplateType(req.template_id)
        except ValueError:
            ttype = DashboardTemplateType.PROJECT_STATUS
        board_data = req.context or {}
        report = _D().generate_report(template_type=ttype, board_data=board_data,
                                      title=board_data.get("title"))
        return {"ok": True, "report": report}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.post("/dashboards/standup")
def generate_standup(req: ReportRequest):
    try:
        ctx = req.context or {}
        report = _D().generate_standup(
            team_name=ctx.get("team_name", "Murphy Team"),
            completed_items=ctx.get("completed", []),
            in_progress_items=ctx.get("in_progress", []),
            blocked_items=ctx.get("blocked", []),
        )
        return {"ok": True, "standup": report}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.post("/dashboards/weekly")
def generate_weekly(req: ReportRequest):
    try:
        ctx = req.context or {}
        report = _D().generate_weekly_report(
            workspace_name=ctx.get("workspace_name", "Murphy"),
            stats=ctx,
        )
        return {"ok": True, "weekly": report}
    except Exception as exc:
        raise HTTPException(500, str(exc))

# ── Recipe routes ─────────────────────────────────────────────────────────────
@router.get("/recipes")
def list_recipes():
    recipes = _R().list_recipes()
    return {"ok": True, "recipes": [_ser(r) for r in recipes]}

@router.post("/recipes")
def create_recipe(req: RecipeCreate):
    try:
        from management_systems.automation_recipes import TriggerType, ActionType, AutomationTrigger
        trigger = AutomationTrigger(
            trigger_type=TriggerType(req.trigger_type),
            value=req.trigger_value
        )
        recipe = _R().create_recipe(name=req.name, trigger=trigger,
                                     action_type=ActionType(req.action_type),
                                     action_config=req.action_config)
        return {"ok": True, "recipe": _ser(recipe)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.get("/recipes/templates")
def list_recipe_templates():
    templates = _R().list_templates()
    return {"ok": True, "templates": [_ser(t) for t in templates]}

@router.post("/recipes/from-template")
def recipe_from_template(req: RecipeFromTemplate):
    try:
        recipe = _R().create_from_template(template_id=req.template_id,
                                            name=req.name or None,
                                            config=req.config)
        return {"ok": True, "recipe": _ser(recipe)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.post("/recipes/event")
def process_recipe_event(req: RecipeEvent):
    results = _R().process_event(event_type=req.event_type, payload=req.payload)
    return {"ok": True, "results": [_ser(r) for r in (results or [])]}

# ── Timeline routes ─────────────────────────────────────────────────────────
@router.get("/timeline")
def list_timeline():
    items = _T().list_items()
    return {"ok": True, "items": [_ser(i) for i in items], "total": len(items)}

@router.post("/timeline")
def add_timeline_item(req: TimelineItem):
    try:
        item = _T().add_item(name=req.name, start_date=req.start_date,
                              end_date=req.end_date, assignee=req.assignee)
        return {"ok": True, "item": _ser(item)}
    except Exception as exc:
        raise HTTPException(500, str(exc))

@router.patch("/timeline/{item_id}/progress")
def update_timeline_progress(item_id: str, req: ProgressUpdate):
    try:
        item = _T().update_progress(item_id=item_id,
                                    progress_pct=req.progress_pct, note=req.note)
        return {"ok": True, "item": _ser(item)}
    except Exception as exc:
        raise HTTPException(400, str(exc))

@router.get("/timeline/critical-path")
def critical_path():
    path = _T().calculate_critical_path()
    return {"ok": True, "critical_path": [_ser(i) for i in (path or [])]}

# ── Health ───────────────────────────────────────────────────────────────────
@router.get("/health")
def mgmt_health():
    checks = {}
    for name, fn in [("board", _B), ("status", _S), ("workspace", _W),
                     ("dashboard", _D), ("recipes", _R), ("timeline", _T)]:
        try:
            fn()
            checks[name] = "ok"
        except Exception as exc:
            checks[name] = f"error: {exc}"
    all_ok = all(v == "ok" for v in checks.values())
    return {"ok": all_ok, "engines": checks}

# ── Helper ───────────────────────────────────────────────────────────────────
def _ser(obj) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items()
                if not k.startswith("_") and isinstance(v, (str, int, float, bool, list, dict, type(None)))}
    return str(obj)
