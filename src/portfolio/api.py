"""
Portfolio – REST API
=====================

FastAPI router for Gantt, dependencies, milestones, baselines, and
critical path endpoints.

All endpoints live under ``/api/portfolio``.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment,misc]

from .gantt import GanttEngine
from .models import DependencyType, MilestoneStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------

if APIRouter is not None:

    class AddBarRequest(BaseModel):
        """Add Bar Request."""
        item_id: str
        item_name: str
        start_date: str
        end_date: str
        board_id: str = ""
        group_id: str = ""
        progress: float = 0.0
        assignee_ids: List[str] = Field(default_factory=list)

    class UpdateBarRequest(BaseModel):
        """Update Bar Request."""
        start_date: Optional[str] = None
        end_date: Optional[str] = None
        progress: Optional[float] = None

    class AddDependencyRequest(BaseModel):
        """Add Dependency Request."""
        predecessor_id: str
        successor_id: str
        dependency_type: str = "fs"
        lag_days: int = 0

    class AddMilestoneRequest(BaseModel):
        """Add Milestone Request."""
        name: str
        target_date: str
        board_id: str = ""
        owner_id: str = ""
        linked_item_ids: List[str] = Field(default_factory=list)

    class UpdateMilestoneRequest(BaseModel):
        """Update Milestone Request."""
        status: Optional[str] = None
        target_date: Optional[str] = None

    class CreateBaselineRequest(BaseModel):
        """Create Baseline Request."""
        name: str
        board_id: str = ""
        created_by: str = ""


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_portfolio_router(
    engine: Optional[GanttEngine] = None,
) -> "APIRouter":
    """Build and return a FastAPI :class:`APIRouter` for portfolio management."""
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the portfolio API")

    if engine is None:
        engine = GanttEngine()

    router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

    # -- Gantt bars ---------------------------------------------------------

    @router.post("/bars")
    async def add_bar(req: AddBarRequest):
        bar = engine.add_bar(
            req.item_id, req.item_name, req.start_date, req.end_date,
            board_id=req.board_id, group_id=req.group_id,
            progress=req.progress, assignee_ids=req.assignee_ids,
        )
        return JSONResponse(bar.to_dict(), status_code=201)

    @router.get("/bars")
    async def list_bars(board_id: str = Query("")):
        bars = engine.get_bars(board_id)
        return JSONResponse([b.to_dict() for b in bars])

    @router.patch("/bars/{item_id}")
    async def update_bar(item_id: str, req: UpdateBarRequest):
        try:
            bar = engine.update_bar(
                item_id, start_date=req.start_date,
                end_date=req.end_date, progress=req.progress,
            )
            return JSONResponse(bar.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/bars/{item_id}")
    async def remove_bar(item_id: str):
        ok = engine.remove_bar(item_id)
        if not ok:
            raise HTTPException(404, "Bar not found")
        return JSONResponse({"deleted": True})

    # -- Dependencies -------------------------------------------------------

    @router.post("/dependencies")
    async def add_dependency(req: AddDependencyRequest):
        try:
            dt = DependencyType(req.dependency_type)
        except ValueError:
            raise HTTPException(400, f"Invalid dependency type: {req.dependency_type!r}")
        try:
            dep = engine.deps.add_dependency(
                req.predecessor_id, req.successor_id,
                dependency_type=dt, lag_days=req.lag_days,
            )
            return JSONResponse(dep.to_dict(), status_code=201)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @router.get("/dependencies/{item_id}")
    async def get_dependencies(item_id: str):
        deps = engine.deps.get_dependencies(item_id)
        return JSONResponse([d.to_dict() for d in deps])

    @router.delete("/dependencies/{dependency_id}")
    async def remove_dependency(dependency_id: str):
        ok = engine.deps.remove_dependency(dependency_id)
        if not ok:
            raise HTTPException(404, "Dependency not found")
        return JSONResponse({"deleted": True})

    # -- Milestones ---------------------------------------------------------

    @router.post("/milestones")
    async def add_milestone(req: AddMilestoneRequest):
        ms = engine.add_milestone(
            req.name, req.target_date,
            board_id=req.board_id, owner_id=req.owner_id,
            linked_item_ids=req.linked_item_ids,
        )
        return JSONResponse(ms.to_dict(), status_code=201)

    @router.get("/milestones")
    async def list_milestones(board_id: str = Query("")):
        milestones = engine.get_milestones(board_id)
        return JSONResponse([m.to_dict() for m in milestones])

    @router.patch("/milestones/{milestone_id}")
    async def update_milestone(milestone_id: str, req: UpdateMilestoneRequest):
        try:
            status = MilestoneStatus(req.status) if req.status else None
            ms = engine.update_milestone(
                milestone_id, status=status, target_date=req.target_date,
            )
            return JSONResponse(ms.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    # -- Baselines ----------------------------------------------------------

    @router.post("/baselines")
    async def create_baseline(req: CreateBaselineRequest):
        bl = engine.create_baseline(
            req.name, req.board_id, created_by=req.created_by,
        )
        return JSONResponse(bl.to_dict(), status_code=201)

    @router.get("/baselines")
    async def list_baselines(board_id: str = Query("")):
        baselines = engine.get_baselines(board_id)
        return JSONResponse([bl.to_dict() for bl in baselines])

    @router.get("/baselines/{baseline_id}")
    async def get_baseline(baseline_id: str):
        bl = engine.get_baseline(baseline_id)
        if bl is None:
            raise HTTPException(404, "Baseline not found")
        return JSONResponse(bl.to_dict())

    # -- Critical path & full render ----------------------------------------

    @router.get("/critical-path")
    async def critical_path(board_id: str = Query("")):
        result = engine.compute_critical_path(board_id)
        return JSONResponse(result)

    @router.get("/gantt")
    async def render_gantt(board_id: str = Query("")):
        data = engine.render_gantt(board_id)
        return JSONResponse(data)

    return router
