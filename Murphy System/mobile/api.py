"""
Mobile App – REST API
=======================

FastAPI router for device registration, push notifications, sync, and config.

All endpoints live under ``/api/mobile``.

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

from .mobile_manager import MobileManager
from .models import NotificationType, Platform

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class RegisterDeviceRequest(BaseModel):
        user_id: str
        platform: str
        device_token: str
        app_version: str = ""
        os_version: str = ""

    class SendNotificationRequest(BaseModel):
        user_id: str
        title: str
        body: str
        notification_type: str = "item_update"
        data: Dict[str, Any] = Field(default_factory=dict)

    class PushChangesRequest(BaseModel):
        changes: List[Dict[str, Any]]

    class ReportConflictRequest(BaseModel):
        item_ids: List[str]

    class UpdateConfigRequest(BaseModel):
        notifications_enabled: Optional[bool] = None
        notification_types: Optional[List[str]] = None
        offline_boards: Optional[List[str]] = None
        quick_add_board_id: Optional[str] = None
        theme: Optional[str] = None


def create_mobile_router(
    manager: Optional[MobileManager] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the mobile API")
    if manager is None:
        manager = MobileManager()

    router = APIRouter(prefix="/api/mobile", tags=["mobile"])

    # -- Devices ------------------------------------------------------------

    @router.post("/devices")
    async def register_device(req: RegisterDeviceRequest):
        try:
            plat = Platform(req.platform)
        except ValueError:
            raise HTTPException(400, f"Invalid platform: {req.platform!r}")
        d = manager.register_device(
            req.user_id, plat, req.device_token,
            app_version=req.app_version, os_version=req.os_version,
        )
        return JSONResponse(d.to_dict(), status_code=201)

    @router.get("/devices")
    async def list_devices(user_id: str = Query("")):
        return JSONResponse([d.to_dict() for d in manager.list_devices(user_id)])

    @router.post("/devices/{device_id}/deactivate")
    async def deactivate_device(device_id: str):
        if not manager.deactivate_device(device_id):
            raise HTTPException(404, "Device not found")
        return JSONResponse({"deactivated": True})

    # -- Notifications ------------------------------------------------------

    @router.post("/notifications")
    async def send_notification(req: SendNotificationRequest):
        try:
            nt = NotificationType(req.notification_type)
        except ValueError:
            raise HTTPException(400, f"Invalid type: {req.notification_type!r}")
        notifs = manager.send_notification(
            req.user_id, req.title, req.body,
            notification_type=nt, data=req.data,
        )
        return JSONResponse(
            [n.to_dict() for n in notifs],
            status_code=201,
        )

    @router.get("/notifications/{user_id}")
    async def list_notifications(user_id: str, unread: bool = Query(False)):
        return JSONResponse(
            [n.to_dict() for n in manager.list_notifications(user_id, unread_only=unread)]
        )

    @router.post("/notifications/{notif_id}/read")
    async def mark_read(notif_id: str):
        if not manager.mark_read(notif_id):
            raise HTTPException(404, "Notification not found")
        return JSONResponse({"read": True})

    @router.post("/notifications/{notif_id}/delivered")
    async def mark_delivered(notif_id: str):
        if not manager.mark_delivered(notif_id):
            raise HTTPException(404, "Notification not found")
        return JSONResponse({"delivered": True})

    # -- Sync ---------------------------------------------------------------

    @router.get("/sync/{device_id}")
    async def get_sync_state(device_id: str):
        return JSONResponse(manager.get_sync_state(device_id).to_dict())

    @router.post("/sync/{device_id}/push")
    async def push_changes(device_id: str, req: PushChangesRequest):
        state = manager.push_changes(device_id, req.changes)
        return JSONResponse(state.to_dict())

    @router.post("/sync/{device_id}/complete")
    async def sync_complete(device_id: str):
        return JSONResponse(manager.sync_complete(device_id).to_dict())

    @router.post("/sync/{device_id}/conflict")
    async def report_conflict(device_id: str, req: ReportConflictRequest):
        return JSONResponse(manager.report_conflict(device_id, req.item_ids).to_dict())

    @router.post("/sync/{device_id}/resolve")
    async def resolve_conflicts(device_id: str):
        return JSONResponse(manager.resolve_conflicts(device_id).to_dict())

    # -- Config -------------------------------------------------------------

    @router.get("/config/{user_id}")
    async def get_config(user_id: str):
        return JSONResponse(manager.get_config(user_id).to_dict())

    @router.patch("/config/{user_id}")
    async def update_config(user_id: str, req: UpdateConfigRequest):
        c = manager.update_config(
            user_id,
            notifications_enabled=req.notifications_enabled,
            notification_types=req.notification_types,
            offline_boards=req.offline_boards,
            quick_add_board_id=req.quick_add_board_id,
            theme=req.theme,
        )
        return JSONResponse(c.to_dict())

    return router
