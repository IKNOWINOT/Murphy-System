"""
Workdocs – REST API
====================

FastAPI router for document CRUD, block editing, versioning, and collaboration.

All endpoints live under ``/api/workdocs``.

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

from .doc_manager import DocManager
from .models import BlockType, DocPermission, DocStatus

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class CreateDocRequest(BaseModel):
        """Create Doc Request."""
        title: str
        owner_id: str = ""
        board_id: str = ""
        permission: str = "private"

    class UpdateDocRequest(BaseModel):
        """Update Doc Request."""
        title: Optional[str] = None
        status: Optional[str] = None
        permission: Optional[str] = None
        user_id: str = ""

    class AddBlockRequest(BaseModel):
        """Add Block Request."""
        block_type: str = "text"
        content: str = ""
        position: int = -1
        metadata: Dict[str, Any] = Field(default_factory=dict)
        indent_level: int = 0

    class UpdateBlockRequest(BaseModel):
        """Update Block Request."""
        content: Optional[str] = None
        checked: Optional[bool] = None
        metadata: Optional[Dict[str, Any]] = None

    class CreateVersionRequest(BaseModel):
        """Create Version Request."""
        editor_id: str = ""
        summary: str = ""

    class CollaboratorRequest(BaseModel):
        """Collaborator Request."""
        user_id: str


def create_workdocs_router(
    manager: Optional[DocManager] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the workdocs API")
    if manager is None:
        manager = DocManager()

    router = APIRouter(prefix="/api/workdocs", tags=["workdocs"])

    @router.post("")
    async def create_document(req: CreateDocRequest):
        try:
            perm = DocPermission(req.permission)
        except ValueError:
            raise HTTPException(400, f"Invalid permission: {req.permission!r}")
        doc = manager.create_document(
            req.title, owner_id=req.owner_id,
            board_id=req.board_id, permission=perm,
        )
        return JSONResponse(doc.to_dict(), status_code=201)

    @router.get("")
    async def list_documents(
        owner_id: str = Query(""), board_id: str = Query(""),
    ):
        docs = manager.list_documents(owner_id=owner_id, board_id=board_id)
        return JSONResponse([d.to_dict() for d in docs])

    @router.get("/{doc_id}")
    async def get_document(doc_id: str):
        doc = manager.get_document(doc_id)
        if doc is None:
            raise HTTPException(404, "Document not found")
        return JSONResponse(doc.to_dict())

    @router.patch("/{doc_id}")
    async def update_document(doc_id: str, req: UpdateDocRequest):
        try:
            status = DocStatus(req.status) if req.status else None
            perm = DocPermission(req.permission) if req.permission else None
            doc = manager.update_document(
                doc_id, user_id=req.user_id,
                title=req.title, status=status, permission=perm,
            )
            return JSONResponse(doc.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.delete("/{doc_id}")
    async def delete_document(doc_id: str, user_id: str = Query("")):
        try:
            ok = manager.delete_document(doc_id, user_id=user_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        if not ok:
            raise HTTPException(404, "Document not found")
        return JSONResponse({"deleted": True})

    # -- Blocks -------------------------------------------------------------

    @router.post("/{doc_id}/blocks")
    async def add_block(doc_id: str, req: AddBlockRequest):
        try:
            bt = BlockType(req.block_type)
        except ValueError:
            raise HTTPException(400, f"Invalid block type: {req.block_type!r}")
        try:
            block = manager.add_block(
                doc_id, bt, req.content,
                position=req.position, metadata=req.metadata,
                indent_level=req.indent_level,
            )
            return JSONResponse(block.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.patch("/{doc_id}/blocks/{block_id}")
    async def update_block(doc_id: str, block_id: str, req: UpdateBlockRequest):
        try:
            block = manager.update_block(
                doc_id, block_id,
                content=req.content, checked=req.checked, metadata=req.metadata,
            )
            return JSONResponse(block.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/{doc_id}/blocks/{block_id}")
    async def delete_block(doc_id: str, block_id: str):
        try:
            ok = manager.delete_block(doc_id, block_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        if not ok:
            raise HTTPException(404, "Block not found")
        return JSONResponse({"deleted": True})

    # -- Versions -----------------------------------------------------------

    @router.post("/{doc_id}/versions")
    async def create_version(doc_id: str, req: CreateVersionRequest):
        try:
            v = manager.create_version(doc_id, editor_id=req.editor_id, summary=req.summary)
            return JSONResponse(v.to_dict(), status_code=201)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.get("/{doc_id}/versions")
    async def list_versions(doc_id: str):
        try:
            versions = manager.get_versions(doc_id)
            return JSONResponse([v.to_dict() for v in versions])
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    # -- Collaborators ------------------------------------------------------

    @router.post("/{doc_id}/collaborators")
    async def add_collaborator(doc_id: str, req: CollaboratorRequest):
        try:
            doc = manager.add_collaborator(doc_id, req.user_id)
            return JSONResponse({"collaborator_ids": doc.collaborator_ids})
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/{doc_id}/collaborators/{user_id}")
    async def remove_collaborator(doc_id: str, user_id: str):
        try:
            ok = manager.remove_collaborator(doc_id, user_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        if not ok:
            raise HTTPException(404, "Collaborator not found")
        return JSONResponse({"removed": True})

    return router
