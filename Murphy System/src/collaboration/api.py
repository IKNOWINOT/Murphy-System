"""
Collaboration System – REST API
=================================

FastAPI router exposing comment CRUD, notifications, and activity feed
endpoints.

All endpoints live under ``/api/collaboration``.

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

from .comment_manager import CommentManager
from .models import CommentEntityType, NotificationStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------

if APIRouter is not None:

    class AddCommentRequest(BaseModel):
        """Add Comment Request."""
        entity_type: str = "item"
        entity_id: str
        board_id: str = ""
        author_id: str = ""
        author_name: str = ""
        body: str
        parent_id: str = ""

    class EditCommentRequest(BaseModel):
        """Edit Comment Request."""
        body: str
        editor_id: str = ""

    class ReactionRequest(BaseModel):
        """Reaction Request."""
        emoji: str
        user_id: str


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_collaboration_router(
    manager: Optional[CommentManager] = None,
) -> "APIRouter":
    """Build and return a FastAPI :class:`APIRouter` for the collaboration system."""
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the collaboration API")

    if manager is None:
        manager = CommentManager()

    router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])

    # -- Comments -----------------------------------------------------------

    @router.post("/comments")
    async def add_comment(req: AddCommentRequest):
        try:
            etype = CommentEntityType(req.entity_type)
        except ValueError:
            raise HTTPException(400, f"Invalid entity type: {req.entity_type!r}")
        comment = manager.add_comment(
            etype, req.entity_id,
            board_id=req.board_id,
            author_id=req.author_id,
            author_name=req.author_name,
            body=req.body,
            parent_id=req.parent_id,
        )
        return JSONResponse(comment.to_dict(), status_code=201)

    @router.get("/comments/{entity_id}")
    async def list_comments(entity_id: str, limit: int = Query(50, ge=1, le=500)):
        comments = manager.list_comments(entity_id, limit=limit)
        return JSONResponse([c.to_dict() for c in comments])

    @router.get("/comments/detail/{comment_id}")
    async def get_comment(comment_id: str):
        comment = manager.get_comment(comment_id)
        if comment is None:
            raise HTTPException(404, "Comment not found")
        return JSONResponse(comment.to_dict())

    @router.patch("/comments/{comment_id}")
    async def edit_comment(comment_id: str, req: EditCommentRequest):
        try:
            comment = manager.edit_comment(comment_id, body=req.body,
                                           editor_id=req.editor_id)
            return JSONResponse(comment.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @router.delete("/comments/{comment_id}")
    async def delete_comment(comment_id: str, deleter_id: str = Query("")):
        try:
            ok = manager.delete_comment(comment_id, deleter_id=deleter_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        if not ok:
            raise HTTPException(404, "Comment not found")
        return JSONResponse({"deleted": True})

    @router.get("/comments/{comment_id}/thread")
    async def get_thread(comment_id: str):
        replies = manager.get_thread(comment_id)
        return JSONResponse([c.to_dict() for c in replies])

    # -- Reactions ----------------------------------------------------------

    @router.post("/comments/{comment_id}/reactions")
    async def add_reaction(comment_id: str, req: ReactionRequest):
        try:
            comment = manager.add_reaction(comment_id, req.emoji, req.user_id)
            return JSONResponse(comment.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/comments/{comment_id}/reactions/{emoji}")
    async def remove_reaction(comment_id: str, emoji: str,
                              user_id: str = Query("")):
        try:
            ok = manager.remove_reaction(comment_id, emoji, user_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        if not ok:
            raise HTTPException(404, "Reaction not found")
        return JSONResponse({"removed": True})

    # -- Notifications ------------------------------------------------------

    @router.get("/notifications/{user_id}")
    async def list_notifications(
        user_id: str,
        status: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ):
        ns = None
        if status:
            try:
                ns = NotificationStatus(status)
            except ValueError:
                raise HTTPException(400, f"Invalid status: {status!r}")
        notifs = manager.notifications.list_notifications(user_id, status=ns, limit=limit)
        return JSONResponse([n.to_dict() for n in notifs])

    @router.get("/notifications/{user_id}/count")
    async def unread_count(user_id: str):
        count = manager.notifications.unread_count(user_id)
        return JSONResponse({"unread_count": count})

    @router.post("/notifications/{user_id}/read/{notification_id}")
    async def mark_read(user_id: str, notification_id: str):
        ok = manager.notifications.mark_read(user_id, notification_id)
        if not ok:
            raise HTTPException(404, "Notification not found")
        return JSONResponse({"marked_read": True})

    @router.post("/notifications/{user_id}/read-all")
    async def mark_all_read(user_id: str):
        count = manager.notifications.mark_all_read(user_id)
        return JSONResponse({"marked_read": count})

    # -- Activity feed ------------------------------------------------------

    @router.get("/feed/board/{board_id}")
    async def board_feed(board_id: str, limit: int = Query(50, ge=1, le=500)):
        entries = manager.feed.get_board_feed(board_id, limit=limit)
        return JSONResponse([e.to_dict() for e in entries])

    @router.get("/feed/user/{user_id}")
    async def user_feed(user_id: str, limit: int = Query(50, ge=1, le=500)):
        entries = manager.feed.get_user_feed(user_id, limit=limit)
        return JSONResponse([e.to_dict() for e in entries])

    @router.get("/feed/global")
    async def global_feed(limit: int = Query(50, ge=1, le=500)):
        entries = manager.feed.get_global_feed(limit=limit)
        return JSONResponse([e.to_dict() for e in entries])

    @router.get("/feed/item/{item_id}")
    async def item_feed(item_id: str, limit: int = Query(50, ge=1, le=500)):
        entries = manager.feed.get_item_feed(item_id, limit=limit)
        return JSONResponse([e.to_dict() for e in entries])

    return router
