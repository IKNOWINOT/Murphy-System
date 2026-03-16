"""
Service Module
================

Phase 10 of management systems feature parity for the Murphy System.

Provides IT service management including:

- **Service catalog** with request forms
- **SLA tracking** with escalation rules
- **Ticket routing** (round-robin, load-based, skill-based)
- **Knowledge base** articles with CRUD
- **CSAT** collection and reporting
- **REST API** at ``/api/service``

Quick start::

    from service_module import ServiceManager, TicketPriority

    mgr = ServiceManager()
    item = mgr.create_catalog_item("Password Reset", category="IT")
    ticket = mgr.create_ticket("Can't login", requester_id="u1", priority=TicketPriority.HIGH)
    mgr.register_agent("agent1")
    mgr.auto_route(ticket.id)

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "ServiceModule"

from .models import (
    CSATResponse,
    KBArticle,
    RoutingStrategy,
    ServiceCatalogItem,
    SLAPolicy,
    SLAStatus,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from .service_manager import ServiceManager

try:
    from .api import create_service_router
except Exception as exc:  # pragma: no cover
    create_service_router = None  # type: ignore[assignment]

__all__ = [
    "CSATResponse",
    "KBArticle",
    "RoutingStrategy",
    "SLAPolicy",
    "SLAStatus",
    "ServiceCatalogItem",
    "Ticket",
    "TicketPriority",
    "TicketStatus",
    "ServiceManager",
    "create_service_router",
]
