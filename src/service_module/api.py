"""
Service Module – REST API
===========================

FastAPI router for service catalog, tickets, SLA, knowledge base, and CSAT.

All endpoints live under ``/api/service``.

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

from .models import RoutingStrategy, TicketPriority, TicketStatus
from .service_manager import ServiceManager

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class CreateCatalogRequest(BaseModel):
        """Create Catalog Request."""
        name: str
        description: str = ""
        category: str = ""
        form_fields: List[Dict[str, Any]] = Field(default_factory=list)
        sla_hours: int = 24

    class CreateSLARequest(BaseModel):
        """Create S L A Request."""
        name: str
        response_hours: int = 4
        resolution_hours: int = 24
        escalation_email: str = ""
        priority: str = "normal"

    class CreateTicketRequest(BaseModel):
        """Create Ticket Request."""
        title: str
        description: str = ""
        requester_id: str = ""
        catalog_item_id: str = ""
        priority: str = "normal"
        form_data: Dict[str, Any] = Field(default_factory=dict)

    class UpdateTicketStatusRequest(BaseModel):
        """Update Ticket Status Request."""
        status: str

    class AssignTicketRequest(BaseModel):
        """Assign Ticket Request."""
        assignee_id: str

    class CreateArticleRequest(BaseModel):
        """Create Article Request."""
        title: str
        body: str
        category: str = ""
        author_id: str = ""
        tags: List[str] = Field(default_factory=list)

    class SubmitCSATRequest(BaseModel):
        """Submit C S A T Request."""
        ticket_id: str
        rating: int
        comment: str = ""
        respondent_id: str = ""


def create_service_router(
    manager: Optional[ServiceManager] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the service module API")
    if manager is None:
        manager = ServiceManager()

    router = APIRouter(prefix="/api/service", tags=["service"])

    # -- Catalog ------------------------------------------------------------

    @router.post("/catalog")
    async def create_catalog_item(req: CreateCatalogRequest):
        item = manager.create_catalog_item(
            req.name, description=req.description, category=req.category,
            form_fields=req.form_fields, sla_hours=req.sla_hours,
        )
        return JSONResponse(item.to_dict(), status_code=201)

    @router.get("/catalog")
    async def list_catalog(category: str = Query("")):
        return JSONResponse([i.to_dict() for i in manager.list_catalog(category)])

    # -- SLA policies -------------------------------------------------------

    @router.post("/sla")
    async def create_sla(req: CreateSLARequest):
        try:
            pri = TicketPriority(req.priority)
        except ValueError:
            raise HTTPException(400, f"Invalid priority: {req.priority!r}")
        policy = manager.create_sla_policy(
            req.name, response_hours=req.response_hours,
            resolution_hours=req.resolution_hours,
            escalation_email=req.escalation_email, priority=pri,
        )
        return JSONResponse(policy.to_dict(), status_code=201)

    @router.get("/sla")
    async def list_sla():
        return JSONResponse([p.to_dict() for p in manager.list_sla_policies()])

    # -- Tickets ------------------------------------------------------------

    @router.post("/tickets")
    async def create_ticket(req: CreateTicketRequest):
        try:
            pri = TicketPriority(req.priority)
        except ValueError:
            raise HTTPException(400, f"Invalid priority: {req.priority!r}")
        t = manager.create_ticket(
            req.title, description=req.description,
            requester_id=req.requester_id,
            catalog_item_id=req.catalog_item_id,
            priority=pri, form_data=req.form_data,
        )
        return JSONResponse(t.to_dict(), status_code=201)

    @router.get("/tickets")
    async def list_tickets(assignee_id: str = Query("")):
        return JSONResponse([t.to_dict() for t in manager.list_tickets(assignee_id=assignee_id)])

    @router.get("/tickets/{ticket_id}")
    async def get_ticket(ticket_id: str):
        t = manager.get_ticket(ticket_id)
        if t is None:
            raise HTTPException(404, "Ticket not found")
        return JSONResponse(t.to_dict())

    @router.patch("/tickets/{ticket_id}/status")
    async def update_status(ticket_id: str, req: UpdateTicketStatusRequest):
        try:
            status = TicketStatus(req.status)
            return JSONResponse(manager.update_ticket_status(ticket_id, status).to_dict())
        except (ValueError, KeyError) as exc:
            raise HTTPException(400 if isinstance(exc, ValueError) else 404, str(exc))

    @router.post("/tickets/{ticket_id}/assign")
    async def assign_ticket(ticket_id: str, req: AssignTicketRequest):
        try:
            return JSONResponse(manager.assign_ticket(ticket_id, req.assignee_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/tickets/{ticket_id}/route")
    async def auto_route(ticket_id: str):
        try:
            return JSONResponse(manager.auto_route(ticket_id).to_dict())
        except (KeyError, ValueError) as exc:
            code = 404 if isinstance(exc, KeyError) else 400
            raise HTTPException(code, str(exc))

    # -- Knowledge base -----------------------------------------------------

    @router.post("/kb")
    async def create_article(req: CreateArticleRequest):
        a = manager.create_article(
            req.title, req.body, category=req.category,
            author_id=req.author_id, tags=req.tags,
        )
        return JSONResponse(a.to_dict(), status_code=201)

    @router.get("/kb")
    async def list_articles(category: str = Query(""), published: bool = Query(False)):
        return JSONResponse([a.to_dict() for a in manager.list_articles(category, published)])

    @router.get("/kb/{article_id}")
    async def get_article(article_id: str):
        a = manager.get_article(article_id)
        if a is None:
            raise HTTPException(404, "Article not found")
        manager.record_article_view(article_id)
        return JSONResponse(a.to_dict())

    @router.post("/kb/{article_id}/publish")
    async def publish_article(article_id: str):
        try:
            return JSONResponse(manager.publish_article(article_id).to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/kb/{article_id}/helpful")
    async def mark_helpful(article_id: str):
        manager.mark_article_helpful(article_id)
        return JSONResponse({"ok": True})

    # -- CSAT ---------------------------------------------------------------

    @router.post("/csat")
    async def submit_csat(req: SubmitCSATRequest):
        try:
            r = manager.submit_csat(
                req.ticket_id, req.rating,
                comment=req.comment, respondent_id=req.respondent_id,
            )
            return JSONResponse(r.to_dict(), status_code=201)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @router.get("/csat/average")
    async def csat_average():
        return JSONResponse({"average": manager.csat_average()})

    @router.get("/csat")
    async def list_csat(ticket_id: str = Query("")):
        return JSONResponse([r.to_dict() for r in manager.list_csat(ticket_id)])

    return router
