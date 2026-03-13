"""
Dev Module – REST API
=======================

FastAPI router for sprints, bugs, releases, git feed, and roadmap.

All endpoints live under ``/api/dev``.

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

from .dev_manager import DevManager
from .models import BugPriority, BugSeverity, RoadmapItemStatus

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class CreateSprintRequest(BaseModel):
        """Create Sprint Request."""
        name: str
        board_id: str
        start_date: str = ""
        end_date: str = ""
        goal: str = ""

    class AddSprintItemRequest(BaseModel):
        """Add Sprint Item Request."""
        item_id: str
        story_points: int = 0

    class CreateBugRequest(BaseModel):
        """Create Bug Request."""
        title: str
        board_id: str = ""
        description: str = ""
        severity: str = "medium"
        priority: str = "p2"
        reporter_id: str = ""
        assignee_id: str = ""

    class CreateReleaseRequest(BaseModel):
        """Create Release Request."""
        version: str
        name: str = ""
        sprint_ids: List[str] = Field(default_factory=list)
        release_notes: str = ""

    class AddChecklistRequest(BaseModel):
        """Add Checklist Request."""
        label: str

    class LogGitActivityRequest(BaseModel):
        """Log Git Activity Request."""
        board_id: str
        event_type: str
        author: str = ""
        message: str = ""
        ref: str = ""
        url: str = ""

    class CreateRoadmapItemRequest(BaseModel):
        """Create Roadmap Item Request."""
        title: str
        description: str = ""
        quarter: str = ""
        owner_id: str = ""
        tags: List[str] = Field(default_factory=list)

    class UpdateRoadmapItemRequest(BaseModel):
        """Update Roadmap Item Request."""
        status: Optional[str] = None
        quarter: Optional[str] = None


def create_dev_router(
    manager: Optional[DevManager] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the dev module API")
    if manager is None:
        manager = DevManager()

    router = APIRouter(prefix="/api/dev", tags=["dev"])

    # -- Sprints ------------------------------------------------------------

    @router.post("/sprints")
    async def create_sprint(req: CreateSprintRequest):
        s = manager.create_sprint(
            req.name, req.board_id,
            start_date=req.start_date, end_date=req.end_date, goal=req.goal,
        )
        return JSONResponse(s.to_dict(), status_code=201)

    @router.get("/sprints")
    async def list_sprints(board_id: str = Query("")):
        return JSONResponse([s.to_dict() for s in manager.list_sprints(board_id)])

    @router.get("/sprints/{sprint_id}")
    async def get_sprint(sprint_id: str):
        s = manager.get_sprint(sprint_id)
        if s is None:
            raise HTTPException(404, "Sprint not found")
        return JSONResponse(s.to_dict())

    @router.post("/sprints/{sprint_id}/start")
    async def start_sprint(sprint_id: str):
        try:
            return JSONResponse(manager.start_sprint(sprint_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/sprints/{sprint_id}/complete")
    async def complete_sprint(sprint_id: str):
        try:
            return JSONResponse(manager.complete_sprint(sprint_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/sprints/{sprint_id}/items")
    async def add_sprint_item(sprint_id: str, req: AddSprintItemRequest):
        try:
            si = manager.add_sprint_item(sprint_id, req.item_id, req.story_points)
            return JSONResponse(si.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/sprints/{sprint_id}/items/{item_id}/complete")
    async def complete_sprint_item(sprint_id: str, item_id: str):
        try:
            ok = manager.complete_sprint_item(sprint_id, item_id)
            if not ok:
                raise HTTPException(404, "Item not found in sprint")
            return JSONResponse({"completed": True})
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.get("/sprints/{sprint_id}/burndown")
    async def burndown(sprint_id: str):
        try:
            return JSONResponse(manager.burndown(sprint_id))
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.get("/velocity/{board_id}")
    async def velocity(board_id: str, limit: int = Query(10, ge=1)):
        return JSONResponse(manager.velocity_history(board_id, limit))

    # -- Bugs ---------------------------------------------------------------

    @router.post("/bugs")
    async def create_bug(req: CreateBugRequest):
        try:
            sev = BugSeverity(req.severity)
            pri = BugPriority(req.priority)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        b = manager.create_bug(
            req.title, board_id=req.board_id, description=req.description,
            severity=sev, priority=pri,
            reporter_id=req.reporter_id, assignee_id=req.assignee_id,
        )
        return JSONResponse(b.to_dict(), status_code=201)

    @router.get("/bugs")
    async def list_bugs(board_id: str = Query("")):
        return JSONResponse([b.to_dict() for b in manager.list_bugs(board_id=board_id)])

    @router.get("/bugs/{bug_id}")
    async def get_bug(bug_id: str):
        b = manager.get_bug(bug_id)
        if b is None:
            raise HTTPException(404, "Bug not found")
        return JSONResponse(b.to_dict())

    @router.post("/bugs/{bug_id}/resolve")
    async def resolve_bug(bug_id: str):
        try:
            return JSONResponse(manager.resolve_bug(bug_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/bugs/{bug_id}/close")
    async def close_bug(bug_id: str):
        try:
            return JSONResponse(manager.close_bug(bug_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    # -- Releases -----------------------------------------------------------

    @router.post("/releases")
    async def create_release(req: CreateReleaseRequest):
        r = manager.create_release(
            req.version, req.name,
            sprint_ids=req.sprint_ids, release_notes=req.release_notes,
        )
        return JSONResponse(r.to_dict(), status_code=201)

    @router.get("/releases")
    async def list_releases():
        return JSONResponse([r.to_dict() for r in manager.list_releases()])

    @router.get("/releases/{release_id}")
    async def get_release(release_id: str):
        r = manager.get_release(release_id)
        if r is None:
            raise HTTPException(404, "Release not found")
        return JSONResponse(r.to_dict())

    @router.post("/releases/{release_id}/checklist")
    async def add_checklist(release_id: str, req: AddChecklistRequest):
        try:
            ci = manager.add_checklist_item(release_id, req.label)
            return JSONResponse(ci.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/releases/{release_id}/publish")
    async def publish_release(release_id: str):
        try:
            return JSONResponse(manager.publish_release(release_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    # -- Git feed -----------------------------------------------------------

    @router.post("/git")
    async def log_git_activity(req: LogGitActivityRequest):
        a = manager.log_git_activity(
            req.board_id, req.event_type,
            author=req.author, message=req.message, ref=req.ref, url=req.url,
        )
        return JSONResponse(a.to_dict(), status_code=201)

    @router.get("/git")
    async def git_feed(board_id: str = Query(""), limit: int = Query(50, ge=1)):
        return JSONResponse([a.to_dict() for a in manager.git_feed(board_id, limit)])

    # -- Roadmap ------------------------------------------------------------

    @router.post("/roadmap")
    async def create_roadmap_item(req: CreateRoadmapItemRequest):
        i = manager.create_roadmap_item(
            req.title, description=req.description,
            quarter=req.quarter, owner_id=req.owner_id, tags=req.tags,
        )
        return JSONResponse(i.to_dict(), status_code=201)

    @router.get("/roadmap")
    async def list_roadmap(quarter: str = Query("")):
        return JSONResponse([i.to_dict() for i in manager.list_roadmap(quarter)])

    @router.patch("/roadmap/{item_id}")
    async def update_roadmap_item(item_id: str, req: UpdateRoadmapItemRequest):
        try:
            status = RoadmapItemStatus(req.status) if req.status else None
            i = manager.update_roadmap_item(item_id, status=status, quarter=req.quarter)
            return JSONResponse(i.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    return router
