"""
Board System – REST API
========================

FastAPI router exposing board CRUD, item management, column operations,
view rendering, and activity log endpoints.

All endpoints live under ``/api/boards``.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover – allow import without fastapi
    APIRouter = None  # type: ignore[assignment,misc]

from .board_manager import BoardManager
from .models import BoardKind, ColumnType, ViewType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic request/response schemas
# ---------------------------------------------------------------------------

if APIRouter is not None:

    class CreateBoardRequest(BaseModel):
        """Create Board Request."""
        name: str = ""\
        description: str = ""
        kind: str = "public"
        workspace_id: str = ""
        owner_id: str = ""

    class UpdateBoardRequest(BaseModel):
        """Update Board Request."""
        name: Optional[str] = None
        description: Optional[str] = None
        kind: Optional[str] = None
        user_id: str = ""

    class CreateGroupRequest(BaseModel):
        """Create Group Request."""
        title: str = "New Group"
        color: str = "#579bfc"
        user_id: str = ""

    class UpdateGroupRequest(BaseModel):
        """Update Group Request."""
        title: Optional[str] = None
        color: Optional[str] = None
        user_id: str = ""

    class CreateItemRequest(BaseModel):
        """Create Item Request."""
        name: str
        group_id: str
        user_id: str = ""
        cell_values: Dict[str, Any] = Field(default_factory=dict)

    class UpdateItemRequest(BaseModel):
        """Update Item Request."""
        name: Optional[str] = None
        user_id: str = ""

    class MoveItemRequest(BaseModel):
        """Move Item Request."""
        target_group_id: str
        user_id: str = ""

    class CreateColumnRequest(BaseModel):
        """Create Column Request."""
        title: str
        column_type: str = "text"
        description: str = ""
        settings: Dict[str, Any] = Field(default_factory=dict)
        user_id: str = ""

    class UpdateColumnRequest(BaseModel):
        """Update Column Request."""
        title: Optional[str] = None
        settings: Optional[Dict[str, Any]] = None
        user_id: str = ""

    class UpdateCellRequest(BaseModel):
        """Update Cell Request."""
        value: Any
        user_id: str = ""

    class CreateViewRequest(BaseModel):
        """Create View Request."""
        name: str
        view_type: str = "table"
        settings: Dict[str, Any] = Field(default_factory=dict)
        user_id: str = ""


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_board_router(manager: Optional[BoardManager] = None) -> "APIRouter":
    """Build and return a FastAPI :class:`APIRouter` for the board system.

    If *manager* is ``None`` a fresh :class:`BoardManager` instance is created.
    """
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the board system API")

    if manager is None:
        manager = BoardManager()

    router = APIRouter(prefix="/api/boards", tags=["boards"])

    # -- Board CRUD ---------------------------------------------------------

    @router.post("")
    async def create_board(req: CreateBoardRequest):
        try:
            kind = BoardKind(req.kind)
        except ValueError:
            raise HTTPException(400, f"Invalid board kind: {req.kind!r}")
        board = manager.create_board(
            name=req.name,
            description=req.description,
            kind=kind,
            workspace_id=req.workspace_id,
            owner_id=req.owner_id,
        )
        return JSONResponse(board.to_dict(), status_code=201)

    @router.get("")
    async def list_boards(workspace_id: str = Query("")):
        boards = manager.list_boards(workspace_id)
        return JSONResponse([b.to_dict() for b in boards])

    @router.get("/{board_id}")
    async def get_board(board_id: str):
        board = manager.get_board(board_id)
        if board is None:
            raise HTTPException(404, "Board not found")
        return JSONResponse(board.to_dict())

    @router.patch("/{board_id}")
    async def update_board(board_id: str, req: UpdateBoardRequest):
        try:
            kind = BoardKind(req.kind) if req.kind else None
            board = manager.update_board(
                board_id, user_id=req.user_id,
                name=req.name, description=req.description, kind=kind,
            )
            return JSONResponse(board.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.delete("/{board_id}")
    async def delete_board(board_id: str, user_id: str = Query("")):
        try:
            ok = manager.delete_board(board_id, user_id=user_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        if not ok:
            raise HTTPException(404, "Board not found")
        return JSONResponse({"deleted": True})

    # -- Groups -------------------------------------------------------------

    @router.post("/{board_id}/groups")
    async def create_group(board_id: str, req: CreateGroupRequest):
        try:
            group = manager.create_group(board_id, title=req.title,
                                         user_id=req.user_id, color=req.color)
            return JSONResponse(group.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.patch("/{board_id}/groups/{group_id}")
    async def update_group(board_id: str, group_id: str, req: UpdateGroupRequest):
        try:
            group = manager.update_group(board_id, group_id, user_id=req.user_id,
                                         title=req.title, color=req.color)
            return JSONResponse(group.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.delete("/{board_id}/groups/{group_id}")
    async def delete_group(board_id: str, group_id: str, user_id: str = Query("")):
        try:
            ok = manager.delete_group(board_id, group_id, user_id=user_id)
        except (KeyError, PermissionError) as exc:
            code = 404 if isinstance(exc, KeyError) else 403
            raise HTTPException(code, str(exc))
        if not ok:
            raise HTTPException(404, "Group not found")
        return JSONResponse({"deleted": True})

    # -- Items --------------------------------------------------------------

    @router.post("/{board_id}/items")
    async def create_item(board_id: str, req: CreateItemRequest):
        try:
            item = manager.create_item(board_id, req.group_id, req.name,
                                       user_id=req.user_id,
                                       cell_values=req.cell_values or None)
            return JSONResponse(item.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.patch("/{board_id}/items/{item_id}")
    async def update_item(board_id: str, item_id: str, req: UpdateItemRequest):
        try:
            item = manager.update_item(board_id, item_id, user_id=req.user_id,
                                       name=req.name)
            return JSONResponse(item.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.delete("/{board_id}/items/{item_id}")
    async def delete_item(board_id: str, item_id: str, user_id: str = Query("")):
        try:
            ok = manager.delete_item(board_id, item_id, user_id=user_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        if not ok:
            raise HTTPException(404, "Item not found")
        return JSONResponse({"deleted": True})

    @router.post("/{board_id}/items/{item_id}/move")
    async def move_item(board_id: str, item_id: str, req: MoveItemRequest):
        try:
            item = manager.move_item(board_id, item_id, req.target_group_id,
                                     user_id=req.user_id)
            return JSONResponse(item.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    # -- Columns ------------------------------------------------------------

    @router.post("/{board_id}/columns")
    async def create_column(board_id: str, req: CreateColumnRequest):
        try:
            ct = ColumnType(req.column_type)
        except ValueError:
            raise HTTPException(400, f"Invalid column type: {req.column_type!r}")
        try:
            col = manager.create_column(board_id, req.title, ct,
                                        user_id=req.user_id,
                                        settings=req.settings,
                                        description=req.description)
            return JSONResponse(col.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.patch("/{board_id}/columns/{column_id}")
    async def update_column(board_id: str, column_id: str, req: UpdateColumnRequest):
        try:
            col = manager.update_column(board_id, column_id, user_id=req.user_id,
                                        title=req.title, settings=req.settings)
            return JSONResponse(col.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.delete("/{board_id}/columns/{column_id}")
    async def delete_column(board_id: str, column_id: str, user_id: str = Query("")):
        try:
            ok = manager.delete_column(board_id, column_id, user_id=user_id)
        except (KeyError, PermissionError) as exc:
            code = 404 if isinstance(exc, KeyError) else 403
            raise HTTPException(code, str(exc))
        if not ok:
            raise HTTPException(404, "Column not found")
        return JSONResponse({"deleted": True})

    # -- Cell values --------------------------------------------------------

    @router.patch("/{board_id}/items/{item_id}/cells/{column_id}")
    async def update_cell(board_id: str, item_id: str, column_id: str,
                          req: UpdateCellRequest):
        try:
            item = manager.update_cell(board_id, item_id, column_id, req.value,
                                       user_id=req.user_id)
            return JSONResponse(item.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    # -- Views --------------------------------------------------------------

    @router.post("/{board_id}/views")
    async def create_view(board_id: str, req: CreateViewRequest):
        try:
            vt = ViewType(req.view_type)
        except ValueError:
            raise HTTPException(400, f"Invalid view type: {req.view_type!r}")
        try:
            view = manager.create_view(board_id, req.name, vt,
                                       user_id=req.user_id, settings=req.settings)
            return JSONResponse(view.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.get("/{board_id}/views/{view_id}/render")
    async def render_view_endpoint(board_id: str, view_id: str):
        try:
            data = manager.render_board_view(board_id, view_id)
            return JSONResponse(data)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    # -- Activity log -------------------------------------------------------

    @router.get("/{board_id}/activity")
    async def get_activity(board_id: str, limit: int = Query(50, ge=1, le=500)):
        board = manager.get_board(board_id)
        if board is None:
            raise HTTPException(404, "Board not found")
        return JSONResponse(manager.get_activity_log(board_id, limit=limit))

    return router
