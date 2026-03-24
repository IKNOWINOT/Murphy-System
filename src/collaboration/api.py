"""
Collaboration System – REST API
=================================

FastAPI router exposing comment CRUD, notifications, activity feed, and
WebSocket real-time push endpoints.

All endpoints live under ``/api/collaboration``.  WebSocket connections are
accepted at ``/api/collaboration/ws/{board_id}`` and receive JSON-encoded
push events whenever a comment is posted, an item is updated, or a
notification is sent for that board.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Set

try:
    from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment,misc]
    WebSocket = None  # type: ignore[assignment,misc,misc]
    WebSocketDisconnect = Exception  # type: ignore[assignment,misc]

from .comment_manager import CommentManager
from .models import CommentEntityType, NotificationStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections per board.

    Allows broadcasting JSON-serialisable event dicts to all clients
    subscribed to a board, without requiring an external message broker.
    """

    def __init__(self) -> None:
        # board_id → set of live websockets
        self._connections: Dict[str, Set["WebSocket"]] = {}

    async def connect(self, board_id: str, websocket: "WebSocket") -> None:
        """Accept the handshake and register the connection."""
        await websocket.accept()
        self._connections.setdefault(board_id, set()).add(websocket)
        logger.debug("WS connect board=%s total=%d", board_id,
                     len(self._connections[board_id]))

    def disconnect(self, board_id: str, websocket: "WebSocket") -> None:
        """Remove a disconnected websocket."""
        board_conns = self._connections.get(board_id, set())
        board_conns.discard(websocket)
        if not board_conns:
            self._connections.pop(board_id, None)
        logger.debug("WS disconnect board=%s", board_id)

    async def broadcast(self, board_id: str, event: Dict[str, Any]) -> None:
        """Send *event* to every client subscribed to *board_id*."""
        payload = json.dumps(event)
        dead: List["WebSocket"] = []
        for ws in list(self._connections.get(board_id, set())):
            try:
                await ws.send_text(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(board_id, ws)

    def subscriber_count(self, board_id: str) -> int:
        """Return the number of active connections for a board."""
        return len(self._connections.get(board_id, set()))

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

_default_ws_manager: Optional[ConnectionManager] = None


def get_ws_manager() -> ConnectionManager:
    """Return the module-level :class:`ConnectionManager` singleton."""
    global _default_ws_manager
    if _default_ws_manager is None:
        _default_ws_manager = ConnectionManager()
    return _default_ws_manager


def create_collaboration_router(
    manager: Optional[CommentManager] = None,
    ws_manager: Optional[ConnectionManager] = None,
) -> "APIRouter":
    """Build and return a FastAPI :class:`APIRouter` for the collaboration system."""
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the collaboration API")

    if manager is None:
        manager = CommentManager()

    if ws_manager is None:
        ws_manager = get_ws_manager()

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

    # -- WebSocket real-time push -------------------------------------------

    @router.websocket("/ws/{board_id}")
    async def board_websocket(board_id: str, websocket: "WebSocket"):
        """WebSocket endpoint for real-time board event push.

        Clients connect to ``/api/collaboration/ws/{board_id}`` and receive
        JSON messages whenever a comment is added or updated for that board.
        The server sends a ``{"type": "ping"}`` keepalive every 30 s.
        Clients may send any text frame to keep the connection alive; the
        server echoes back ``{"type": "pong"}``.
        """
        await ws_manager.connect(board_id, websocket)
        try:
            # Send a welcome handshake so the client knows the connection is live
            await websocket.send_text(json.dumps({
                "type": "connected",
                "board_id": board_id,
                "subscribers": ws_manager.subscriber_count(board_id),
            }))
            while True:
                try:
                    # Wait up to 30 s for a client message; send keepalive if none arrives
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    await websocket.send_text(json.dumps({"type": "pong"}))
                except asyncio.TimeoutError:
                    await websocket.send_text(json.dumps({"type": "ping"}))
        except WebSocketDisconnect:
            ws_manager.disconnect(board_id, websocket)

    @router.post("/ws/{board_id}/broadcast")
    async def broadcast_event(board_id: str, event: Dict[str, Any]):
        """Push a custom JSON event to all WebSocket subscribers of a board.

        This endpoint is used internally (e.g. by the board system) to
        notify connected clients of mutations.  The ``event`` body must be
        a JSON object; a ``board_id`` key is injected automatically.
        """
        event.setdefault("board_id", board_id)
        await ws_manager.broadcast(board_id, event)
        return JSONResponse({
            "broadcasted": True,
            "subscribers": ws_manager.subscriber_count(board_id),
        })

    return router
