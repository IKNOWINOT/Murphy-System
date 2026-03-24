"""
CRM – Data Models
===================

Core data structures for the CRM Module
(Phase 8 of Monday.com parity).

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


class DealStage(Enum):
    """Default deal pipeline stages."""
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class ContactType(Enum):
    """Contact categorization."""
    LEAD = "lead"
    CUSTOMER = "customer"
    PARTNER = "partner"
    VENDOR = "vendor"


class ActivityType(Enum):
    """CRM activity types."""
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"


@dataclass
class Contact:
    """A CRM contact (person or company)."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    contact_type: ContactType = ContactType.LEAD
    owner_id: str = ""
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "contact_type": self.contact_type.value,
            "owner_id": self.owner_id,
            "tags": self.tags,
            "custom_fields": self.custom_fields,
            "created_at": self.created_at,
        }


@dataclass
class Stage:
    """A pipeline stage definition."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    order: int = 0
    probability: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "order": self.order,
            "probability": self.probability,
        }


@dataclass
class Pipeline:
    """A sales pipeline with ordered stages."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    stages: List[Stage] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "stages": [s.to_dict() for s in self.stages],
            "created_at": self.created_at,
        }


@dataclass
class Deal:
    """A sales deal tracked through a pipeline."""
    id: str = field(default_factory=_new_id)
    title: str = ""
    contact_id: str = ""
    pipeline_id: str = ""
    stage: str = "lead"
    value: float = 0.0
    currency: str = "USD"
    owner_id: str = ""
    expected_close_date: str = ""
    closed_at: str = ""
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "contact_id": self.contact_id,
            "pipeline_id": self.pipeline_id,
            "stage": self.stage,
            "value": self.value,
            "currency": self.currency,
            "owner_id": self.owner_id,
            "expected_close_date": self.expected_close_date,
            "closed_at": self.closed_at,
            "tags": self.tags,
            "custom_fields": self.custom_fields,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class CRMActivity:
    """A logged CRM activity."""
    id: str = field(default_factory=_new_id)
    activity_type: ActivityType = ActivityType.NOTE
    contact_id: str = ""
    deal_id: str = ""
    user_id: str = ""
    summary: str = ""
    details: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "activity_type": self.activity_type.value,
            "contact_id": self.contact_id,
            "deal_id": self.deal_id,
            "user_id": self.user_id,
            "summary": self.summary,
            "details": self.details,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Email interaction tracking
# ---------------------------------------------------------------------------

class EmailDirection(Enum):
    """Whether an email was sent or received."""
    SENT = "sent"
    RECEIVED = "received"


@dataclass
class EmailInteraction:
    """A sent or received email linked to a contact and/or deal.

    Email interactions are distinct from generic :class:`CRMActivity` entries
    so they can be queried, threaded, and analysed separately.
    """
    id: str = field(default_factory=_new_id)
    contact_id: str = ""
    deal_id: str = ""
    user_id: str = ""           # CRM user who sent/received the email
    direction: EmailDirection = EmailDirection.SENT
    subject: str = ""
    body_preview: str = ""      # first 500 chars; full body stored externally
    from_address: str = ""
    to_addresses: List[str] = field(default_factory=list)
    message_id: str = ""        # RFC-2822 Message-ID for threading
    thread_id: str = ""         # optional conversation thread grouping
    opened_at: str = ""         # ISO-8601 if tracked open pixel fired
    clicked_at: str = ""        # ISO-8601 if a tracked link was clicked
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contact_id": self.contact_id,
            "deal_id": self.deal_id,
            "user_id": self.user_id,
            "direction": self.direction.value,
            "subject": self.subject,
            "body_preview": self.body_preview,
            "from_address": self.from_address,
            "to_addresses": self.to_addresses,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "opened_at": self.opened_at,
            "clicked_at": self.clicked_at,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Pipeline templates
# ---------------------------------------------------------------------------

_BUILTIN_PIPELINE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "Standard Sales Pipeline",
        "stages": [
            {"name": "Lead", "order": 0, "probability": 0.1},
            {"name": "Qualified", "order": 1, "probability": 0.3},
            {"name": "Proposal", "order": 2, "probability": 0.5},
            {"name": "Negotiation", "order": 3, "probability": 0.75},
            {"name": "Closed Won", "order": 4, "probability": 1.0},
            {"name": "Closed Lost", "order": 5, "probability": 0.0},
        ],
    },
    {
        "name": "Enterprise Sales Cycle",
        "stages": [
            {"name": "Prospecting", "order": 0, "probability": 0.05},
            {"name": "Discovery", "order": 1, "probability": 0.15},
            {"name": "Demo", "order": 2, "probability": 0.30},
            {"name": "Technical Eval", "order": 3, "probability": 0.45},
            {"name": "Proposal", "order": 4, "probability": 0.60},
            {"name": "Legal / Contract", "order": 5, "probability": 0.80},
            {"name": "Closed Won", "order": 6, "probability": 1.0},
            {"name": "Closed Lost", "order": 7, "probability": 0.0},
        ],
    },
    {
        "name": "SaaS Trial Pipeline",
        "stages": [
            {"name": "Trial Started", "order": 0, "probability": 0.2},
            {"name": "Engaged", "order": 1, "probability": 0.4},
            {"name": "Expansion Talk", "order": 2, "probability": 0.6},
            {"name": "Converted", "order": 3, "probability": 1.0},
            {"name": "Churned", "order": 4, "probability": 0.0},
        ],
    },
]
