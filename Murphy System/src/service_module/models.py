"""
Service Module – Data Models
==============================

Core data structures for the Service Module (Phase 10 of management systems parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_UTC = timezone.utc


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TicketStatus(Enum):
    """Service ticket lifecycle."""
    NEW = "new"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(Enum):
    """Ticket priority levels.
    PATCH-008: added MEDIUM as alias for NORMAL for API compatibility.
    """
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    MEDIUM = "medium"   # PATCH-008: alias — maps to same SLA as NORMAL
    LOW = "low"


class SLAStatus(Enum):
    """SLA compliance status."""
    WITHIN = "within"
    WARNING = "warning"
    BREACHED = "breached"


class RoutingStrategy(Enum):
    """Ticket auto-routing strategies."""
    ROUND_ROBIN = "round_robin"
    LOAD_BASED = "load_based"
    SKILL_BASED = "skill_based"


class CSATRating(Enum):
    """Customer satisfaction rating."""
    VERY_DISSATISFIED = 1
    DISSATISFIED = 2
    NEUTRAL = 3
    SATISFIED = 4
    VERY_SATISFIED = 5


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ServiceCatalogItem:
    """A service offering in the catalog."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    category: str = ""
    form_fields: List[Dict[str, Any]] = field(default_factory=list)
    sla_hours: int = 24
    enabled: bool = True
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "form_fields": self.form_fields,
            "sla_hours": self.sla_hours,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


@dataclass
class SLAPolicy:
    """An SLA policy defining response and resolution targets."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    response_hours: int = 4
    resolution_hours: int = 24
    escalation_email: str = ""
    priority: TicketPriority = TicketPriority.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "response_hours": self.response_hours,
            "resolution_hours": self.resolution_hours,
            "escalation_email": self.escalation_email,
            "priority": self.priority.value,
        }


@dataclass
class Ticket:
    """A service desk ticket."""
    id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    requester_id: str = ""
    assignee_id: str = ""
    catalog_item_id: str = ""
    status: TicketStatus = TicketStatus.NEW
    priority: TicketPriority = TicketPriority.NORMAL
    sla_policy_id: str = ""
    sla_status: SLAStatus = SLAStatus.WITHIN
    form_data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    resolved_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "requester_id": self.requester_id,
            "assignee_id": self.assignee_id,
            "catalog_item_id": self.catalog_item_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "sla_policy_id": self.sla_policy_id,
            "sla_status": self.sla_status.value,
            "form_data": self.form_data,
            "tags": self.tags,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


@dataclass
class KBArticle:
    """A knowledge-base article."""
    id: str = field(default_factory=_new_id)
    title: str = ""
    body: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    author_id: str = ""
    published: bool = False
    view_count: int = 0
    helpful_count: int = 0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "tags": self.tags,
            "author_id": self.author_id,
            "published": self.published,
            "view_count": self.view_count,
            "helpful_count": self.helpful_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CSATResponse:
    """A customer satisfaction survey response."""
    id: str = field(default_factory=_new_id)
    ticket_id: str = ""
    rating: int = 3
    comment: str = ""
    respondent_id: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "rating": self.rating,
            "comment": self.comment,
            "respondent_id": self.respondent_id,
            "created_at": self.created_at,
        }
