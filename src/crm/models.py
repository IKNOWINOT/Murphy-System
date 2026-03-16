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
