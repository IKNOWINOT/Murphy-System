"""
Guest Collaboration – REST API
================================

FastAPI router for guest invitations, shareable links, client portals,
and external forms.

All endpoints live under ``/api/guest``.

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

from .guest_manager import GuestManager
from .models import GuestPermission, LinkAccess

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class InviteGuestRequest(BaseModel):
        """Invite Guest Request."""
        email: str
        name: str = ""
        permission: str = "view"
        board_ids: List[str] = Field(default_factory=list)
        invited_by: str = ""
        expires_at: str = ""

    class UpdateGuestRequest(BaseModel):
        """Update Guest Request."""
        permission: Optional[str] = None
        board_ids: Optional[List[str]] = None

    class CreateLinkRequest(BaseModel):
        """Create Link Request."""
        board_id: str
        item_id: str = ""
        access: str = "read_only"
        created_by: str = ""
        password: str = ""
        expires_at: str = ""

    class CreatePortalRequest(BaseModel):
        """Create Portal Request."""
        name: str
        owner_id: str
        board_ids: List[str] = Field(default_factory=list)
        logo_url: str = ""
        primary_color: str = "#4A90D9"
        welcome_message: str = ""

    class CreateFormRequest(BaseModel):
        """Create Form Request."""
        name: str
        board_id: str
        group_id: str = ""
        fields: List[Dict[str, Any]] = Field(default_factory=list)

    class SubmitFormRequest(BaseModel):
        """Submit Form Request."""
        data: Dict[str, Any]
        submitter_email: str = ""


def create_guest_router(
    manager: Optional[GuestManager] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the guest collaboration API")
    if manager is None:
        manager = GuestManager()

    router = APIRouter(prefix="/api/guest", tags=["guest"])

    # -- Guest invitations --------------------------------------------------

    @router.post("/invites")
    async def invite_guest(req: InviteGuestRequest):
        try:
            perm = GuestPermission(req.permission)
        except ValueError:
            raise HTTPException(400, f"Invalid permission: {req.permission!r}")
        g = manager.invite_guest(
            req.email, name=req.name, permission=perm,
            board_ids=req.board_ids, invited_by=req.invited_by,
            expires_at=req.expires_at,
        )
        return JSONResponse(g.to_dict(), status_code=201)

    @router.get("/invites")
    async def list_guests(invited_by: str = Query("")):
        return JSONResponse([g.to_dict() for g in manager.list_guests(invited_by)])

    @router.get("/invites/{guest_id}")
    async def get_guest(guest_id: str):
        g = manager.get_guest(guest_id)
        if g is None:
            raise HTTPException(404, "Guest not found")
        return JSONResponse(g.to_dict())

    @router.post("/invites/{guest_id}/accept")
    async def accept_invite(guest_id: str):
        try:
            return JSONResponse(manager.accept_invite(guest_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/invites/{guest_id}/revoke")
    async def revoke_invite(guest_id: str):
        try:
            return JSONResponse(manager.revoke_invite(guest_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.patch("/invites/{guest_id}")
    async def update_guest(guest_id: str, req: UpdateGuestRequest):
        try:
            perm = GuestPermission(req.permission) if req.permission else None
            return JSONResponse(
                manager.update_guest_permissions(
                    guest_id, permission=perm, board_ids=req.board_ids,
                ).to_dict()
            )
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    # -- Shareable links ----------------------------------------------------

    @router.post("/links")
    async def create_link(req: CreateLinkRequest):
        try:
            access = LinkAccess(req.access)
        except ValueError:
            raise HTTPException(400, f"Invalid access: {req.access!r}")
        link = manager.create_shareable_link(
            req.board_id, item_id=req.item_id, access=access,
            created_by=req.created_by, password=req.password,
            expires_at=req.expires_at,
        )
        return JSONResponse(link.to_dict(), status_code=201)

    @router.get("/links")
    async def list_links(board_id: str = Query("")):
        return JSONResponse([l.to_dict() for l in manager.list_links(board_id)])

    @router.get("/links/{link_id}")
    async def get_link(link_id: str):
        l = manager.get_link(link_id)
        if l is None:
            raise HTTPException(404, "Link not found")
        return JSONResponse(l.to_dict())

    @router.post("/links/{link_id}/deactivate")
    async def deactivate_link(link_id: str):
        if not manager.deactivate_link(link_id):
            raise HTTPException(404, "Link not found")
        return JSONResponse({"deactivated": True})

    # -- Client portals -----------------------------------------------------

    @router.post("/portals")
    async def create_portal(req: CreatePortalRequest):
        p = manager.create_portal(
            req.name, req.owner_id, board_ids=req.board_ids,
            logo_url=req.logo_url, primary_color=req.primary_color,
            welcome_message=req.welcome_message,
        )
        return JSONResponse(p.to_dict(), status_code=201)

    @router.get("/portals")
    async def list_portals(owner_id: str = Query("")):
        return JSONResponse([p.to_dict() for p in manager.list_portals(owner_id)])

    @router.get("/portals/{portal_id}")
    async def get_portal(portal_id: str):
        p = manager.get_portal(portal_id)
        if p is None:
            raise HTTPException(404, "Portal not found")
        return JSONResponse(p.to_dict())

    @router.post("/portals/{portal_id}/guests/{guest_id}")
    async def add_guest_to_portal(portal_id: str, guest_id: str):
        try:
            return JSONResponse(manager.add_guest_to_portal(portal_id, guest_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    # -- External forms -----------------------------------------------------

    @router.post("/forms")
    async def create_form(req: CreateFormRequest):
        f = manager.create_form(
            req.name, req.board_id, group_id=req.group_id, fields=req.fields,
        )
        return JSONResponse(f.to_dict(), status_code=201)

    @router.get("/forms")
    async def list_forms(board_id: str = Query("")):
        return JSONResponse([f.to_dict() for f in manager.list_forms(board_id)])

    @router.get("/forms/{form_id}")
    async def get_form(form_id: str):
        f = manager.get_form(form_id)
        if f is None:
            raise HTTPException(404, "Form not found")
        return JSONResponse(f.to_dict())

    @router.post("/forms/{form_id}/submit")
    async def submit_form(form_id: str, req: SubmitFormRequest):
        try:
            s = manager.submit_form(form_id, req.data, submitter_email=req.submitter_email)
            return JSONResponse(s.to_dict(), status_code=201)
        except (KeyError, ValueError) as exc:
            code = 404 if isinstance(exc, KeyError) else 400
            raise HTTPException(code, str(exc))

    @router.get("/forms/{form_id}/submissions")
    async def list_submissions(form_id: str):
        return JSONResponse([s.to_dict() for s in manager.list_submissions(form_id)])

    return router
