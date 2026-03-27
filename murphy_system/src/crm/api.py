"""
CRM – REST API
================

FastAPI router for contacts, deals, pipelines, and activities.

All endpoints live under ``/api/crm``.

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

from .crm_manager import CRMManager
from .models import ActivityType, ContactType

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class CreateContactRequest(BaseModel):
        """Create Contact Request."""
        name: str
        email: str = ""
        phone: str = ""
        company: str = ""
        contact_type: str = "lead"
        owner_id: str = ""
        tags: List[str] = Field(default_factory=list)

    class UpdateContactRequest(BaseModel):
        """Update Contact Request."""
        name: Optional[str] = None
        email: Optional[str] = None
        phone: Optional[str] = None
        company: Optional[str] = None
        contact_type: Optional[str] = None

    class CreateDealRequest(BaseModel):
        """Create Deal Request."""
        title: str
        contact_id: str = ""
        pipeline_id: str = ""
        stage: str = "lead"
        value: float = 0.0
        currency: str = "USD"
        owner_id: str = ""
        expected_close_date: str = ""

    class UpdateDealRequest(BaseModel):
        """Update Deal Request."""
        title: Optional[str] = None
        stage: Optional[str] = None
        value: Optional[float] = None

    class CreatePipelineRequest(BaseModel):
        """Create Pipeline Request."""
        name: str
        stages: List[Dict[str, Any]] = Field(default_factory=list)

    class LogActivityRequest(BaseModel):
        """Log Activity Request."""
        activity_type: str = "note"
        contact_id: str = ""
        deal_id: str = ""
        user_id: str = ""
        summary: str = ""
        details: str = ""


def create_crm_router(
    manager: Optional[CRMManager] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the CRM API")
    if manager is None:
        manager = CRMManager()

    router = APIRouter(prefix="/api/crm", tags=["crm"])

    # -- Contacts -----------------------------------------------------------

    @router.post("/contacts")
    async def create_contact(req: CreateContactRequest):
        try:
            ct = ContactType(req.contact_type)
        except ValueError:
            raise HTTPException(400, f"Invalid contact type: {req.contact_type!r}")
        contact = manager.create_contact(
            req.name, email=req.email, phone=req.phone,
            company=req.company, contact_type=ct,
            owner_id=req.owner_id, tags=req.tags,
        )
        return JSONResponse(contact.to_dict(), status_code=201)

    @router.get("/contacts")
    async def list_contacts(owner_id: str = Query("")):
        contacts = manager.list_contacts(owner_id=owner_id)
        return JSONResponse([c.to_dict() for c in contacts])

    @router.get("/contacts/{contact_id}")
    async def get_contact(contact_id: str):
        c = manager.get_contact(contact_id)
        if c is None:
            raise HTTPException(404, "Contact not found")
        return JSONResponse(c.to_dict())

    @router.patch("/contacts/{contact_id}")
    async def update_contact(contact_id: str, req: UpdateContactRequest):
        try:
            ct = ContactType(req.contact_type) if req.contact_type else None
            c = manager.update_contact(
                contact_id, name=req.name, email=req.email,
                phone=req.phone, company=req.company, contact_type=ct,
            )
            return JSONResponse(c.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/contacts/{contact_id}")
    async def delete_contact(contact_id: str):
        if not manager.delete_contact(contact_id):
            raise HTTPException(404, "Contact not found")
        return JSONResponse({"deleted": True})

    # -- Pipelines ----------------------------------------------------------

    @router.post("/pipelines")
    async def create_pipeline(req: CreatePipelineRequest):
        p = manager.create_pipeline(req.name, req.stages)
        return JSONResponse(p.to_dict(), status_code=201)

    @router.get("/pipelines")
    async def list_pipelines():
        return JSONResponse([p.to_dict() for p in manager.list_pipelines()])

    @router.get("/pipelines/{pipeline_id}")
    async def get_pipeline(pipeline_id: str):
        p = manager.get_pipeline(pipeline_id)
        if p is None:
            raise HTTPException(404, "Pipeline not found")
        return JSONResponse(p.to_dict())

    @router.get("/pipelines/{pipeline_id}/value")
    async def pipeline_value(pipeline_id: str):
        return JSONResponse(manager.pipeline_value(pipeline_id))

    # -- Deals --------------------------------------------------------------

    @router.post("/deals")
    async def create_deal(req: CreateDealRequest):
        deal = manager.create_deal(
            req.title, contact_id=req.contact_id,
            pipeline_id=req.pipeline_id, stage=req.stage,
            value=req.value, currency=req.currency,
            owner_id=req.owner_id, expected_close_date=req.expected_close_date,
        )
        return JSONResponse(deal.to_dict(), status_code=201)

    @router.get("/deals")
    async def list_deals(
        pipeline_id: str = Query(""), stage: str = Query(""),
        owner_id: str = Query(""),
    ):
        deals = manager.list_deals(
            pipeline_id=pipeline_id, stage=stage, owner_id=owner_id,
        )
        return JSONResponse([d.to_dict() for d in deals])

    @router.get("/deals/{deal_id}")
    async def get_deal(deal_id: str):
        d = manager.get_deal(deal_id)
        if d is None:
            raise HTTPException(404, "Deal not found")
        return JSONResponse(d.to_dict())

    @router.patch("/deals/{deal_id}")
    async def update_deal(deal_id: str, req: UpdateDealRequest):
        try:
            d = manager.update_deal(
                deal_id, title=req.title, stage=req.stage, value=req.value,
            )
            return JSONResponse(d.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/deals/{deal_id}/move/{stage}")
    async def move_deal(deal_id: str, stage: str):
        try:
            d = manager.move_deal(deal_id, stage)
            return JSONResponse(d.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.delete("/deals/{deal_id}")
    async def delete_deal(deal_id: str):
        if not manager.delete_deal(deal_id):
            raise HTTPException(404, "Deal not found")
        return JSONResponse({"deleted": True})

    # -- Activities ---------------------------------------------------------

    @router.post("/activities")
    async def log_activity(req: LogActivityRequest):
        try:
            at = ActivityType(req.activity_type)
        except ValueError:
            raise HTTPException(400, f"Invalid activity type: {req.activity_type!r}")
        act = manager.log_activity(
            at, contact_id=req.contact_id, deal_id=req.deal_id,
            user_id=req.user_id, summary=req.summary, details=req.details,
        )
        return JSONResponse(act.to_dict(), status_code=201)

    @router.get("/activities")
    async def list_activities(
        contact_id: str = Query(""), deal_id: str = Query(""),
    ):
        acts = manager.list_activities(contact_id=contact_id, deal_id=deal_id)
        return JSONResponse([a.to_dict() for a in acts])

    return router
