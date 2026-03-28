"""
Dashboards – REST API
======================

FastAPI router for dashboard CRUD, widget management, and rendering.

All endpoints live under ``/api/dashboards``.

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

from .dashboard_manager import DashboardManager
from .models import DashboardPermission, WidgetType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------

if APIRouter is not None:

    class CreateDashboardRequest(BaseModel):
        """Create Dashboard Request."""
        name: str
        description: str = ""
        owner_id: str = ""
        workspace_id: str = ""
        permission: str = "private"

    class UpdateDashboardRequest(BaseModel):
        """Update Dashboard Request."""
        name: Optional[str] = None
        description: Optional[str] = None
        permission: Optional[str] = None
        user_id: str = ""

    class AddWidgetRequest(BaseModel):
        """Add Widget Request."""
        widget_type: str = "chart"
        title: str
        data_sources: List[Dict[str, Any]] = Field(default_factory=list)
        settings: Dict[str, Any] = Field(default_factory=dict)
        position: Optional[Dict[str, int]] = None

    class UpdateWidgetRequest(BaseModel):
        """Update Widget Request."""
        title: Optional[str] = None
        settings: Optional[Dict[str, Any]] = None
        position: Optional[Dict[str, int]] = None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_dashboard_router(
    manager: Optional[DashboardManager] = None,
) -> "APIRouter":
    """Build and return a FastAPI :class:`APIRouter` for dashboards."""
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the dashboards API")

    if manager is None:
        manager = DashboardManager()

    router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])

    @router.post("")
    async def create_dashboard(req: CreateDashboardRequest):
        try:
            perm = DashboardPermission(req.permission)
        except ValueError:
            raise HTTPException(400, f"Invalid permission: {req.permission!r}")
        dash = manager.create_dashboard(
            name=req.name,
            description=req.description,
            owner_id=req.owner_id,
            workspace_id=req.workspace_id,
            permission=perm,
        )
        return JSONResponse(dash.to_dict(), status_code=201)

    @router.get("")
    async def list_dashboards(
        owner_id: str = Query(""),
        workspace_id: str = Query(""),
    ):
        dashboards = manager.list_dashboards(owner_id=owner_id, workspace_id=workspace_id)
        return JSONResponse([d.to_dict() for d in dashboards])

    @router.get("/{dashboard_id}")
    async def get_dashboard(dashboard_id: str):
        dash = manager.get_dashboard(dashboard_id)
        if dash is None:
            raise HTTPException(404, "Dashboard not found")
        return JSONResponse(dash.to_dict())

    @router.patch("/{dashboard_id}")
    async def update_dashboard(dashboard_id: str, req: UpdateDashboardRequest):
        try:
            perm = DashboardPermission(req.permission) if req.permission else None
            dash = manager.update_dashboard(
                dashboard_id, user_id=req.user_id,
                name=req.name, description=req.description, permission=perm,
            )
            return JSONResponse(dash.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.delete("/{dashboard_id}")
    async def delete_dashboard(dashboard_id: str, user_id: str = Query("")):
        try:
            ok = manager.delete_dashboard(dashboard_id, user_id=user_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        if not ok:
            raise HTTPException(404, "Dashboard not found")
        return JSONResponse({"deleted": True})

    # -- Widgets ------------------------------------------------------------

    @router.post("/{dashboard_id}/widgets")
    async def add_widget(dashboard_id: str, req: AddWidgetRequest):
        try:
            wt = WidgetType(req.widget_type)
        except ValueError:
            raise HTTPException(400, f"Invalid widget type: {req.widget_type!r}")
        from .models import DataSource
        sources = [DataSource(**ds) for ds in req.data_sources]
        try:
            widget = manager.add_widget(
                dashboard_id, wt, req.title,
                data_sources=sources,
                settings=req.settings,
                position=req.position,
            )
            return JSONResponse(widget.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.patch("/{dashboard_id}/widgets/{widget_id}")
    async def update_widget(dashboard_id: str, widget_id: str, req: UpdateWidgetRequest):
        try:
            widget = manager.update_widget(
                dashboard_id, widget_id,
                title=req.title, settings=req.settings, position=req.position,
            )
            return JSONResponse(widget.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/{dashboard_id}/widgets/{widget_id}")
    async def remove_widget(dashboard_id: str, widget_id: str):
        try:
            ok = manager.remove_widget(dashboard_id, widget_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        if not ok:
            raise HTTPException(404, "Widget not found")
        return JSONResponse({"deleted": True})

    # -- Rendering ----------------------------------------------------------

    @router.get("/{dashboard_id}/render")
    async def render_dashboard(dashboard_id: str):
        try:
            data = manager.render_dashboard(dashboard_id)
            return JSONResponse(data)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.get("/{dashboard_id}/widgets/{widget_id}/render")
    async def render_widget_endpoint(dashboard_id: str, widget_id: str):
        try:
            data = manager.render_widget(dashboard_id, widget_id)
            return JSONResponse(data)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    return router
