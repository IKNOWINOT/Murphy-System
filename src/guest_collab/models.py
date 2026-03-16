"""
Guest Collaboration – Data Models
====================================

Core data structures for the Guest / External Collaboration system
(Phase 11 of management systems parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations
import logging

import secrets
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


def _new_token() -> str:
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class GuestPermission(Enum):
    """Guest access levels."""
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"


class LinkAccess(Enum):
    """Shareable link access levels."""
    READ_ONLY = "read_only"
    EDIT = "edit"


class InviteStatus(Enum):
    """Guest invitation status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class FormFieldType(Enum):
    """External form field types."""
    TEXT = "text"
    EMAIL = "email"
    NUMBER = "number"
    SELECT = "select"
    DATE = "date"
    FILE = "file"
    TEXTAREA = "textarea"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GuestUser:
    """A guest user with scoped access."""
    id: str = field(default_factory=_new_id)
    email: str = ""
    name: str = ""
    permission: GuestPermission = GuestPermission.VIEW
    board_ids: List[str] = field(default_factory=list)
    invited_by: str = ""
    status: InviteStatus = InviteStatus.PENDING
    token: str = field(default_factory=_new_token)
    expires_at: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "permission": self.permission.value,
            "board_ids": self.board_ids,
            "invited_by": self.invited_by,
            "status": self.status.value,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }


@dataclass
class ShareableLink:
    """A shareable board/item link."""
    id: str = field(default_factory=_new_id)
    board_id: str = ""
    item_id: str = ""
    access: LinkAccess = LinkAccess.READ_ONLY
    token: str = field(default_factory=_new_token)
    created_by: str = ""
    password: str = ""
    expires_at: str = ""
    view_count: int = 0
    active: bool = True
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "board_id": self.board_id,
            "item_id": self.item_id,
            "access": self.access.value,
            "token": self.token,
            "created_by": self.created_by,
            "has_password": bool(self.password),
            "expires_at": self.expires_at,
            "view_count": self.view_count,
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class ClientPortal:
    """A branded client portal configuration."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    owner_id: str = ""
    board_ids: List[str] = field(default_factory=list)
    logo_url: str = ""
    primary_color: str = "#4A90D9"
    welcome_message: str = ""
    guest_ids: List[str] = field(default_factory=list)
    active: bool = True
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "board_ids": self.board_ids,
            "logo_url": self.logo_url,
            "primary_color": self.primary_color,
            "welcome_message": self.welcome_message,
            "guest_ids": self.guest_ids,
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class FormField:
    """A field definition in an external form."""
    id: str = field(default_factory=_new_id)
    label: str = ""
    field_type: FormFieldType = FormFieldType.TEXT
    required: bool = False
    options: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "field_type": self.field_type.value,
            "required": self.required,
            "options": self.options,
        }


@dataclass
class ExternalForm:
    """An external form for collecting submissions from non-users."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    board_id: str = ""
    group_id: str = ""
    fields: List[FormField] = field(default_factory=list)
    token: str = field(default_factory=_new_token)
    active: bool = True
    submission_count: int = 0
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "board_id": self.board_id,
            "group_id": self.group_id,
            "fields": [f.to_dict() for f in self.fields],
            "token": self.token,
            "active": self.active,
            "submission_count": self.submission_count,
            "created_at": self.created_at,
        }


@dataclass
class FormSubmission:
    """A submission received via an external form."""
    id: str = field(default_factory=_new_id)
    form_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    submitter_email: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "form_id": self.form_id,
            "data": self.data,
            "submitter_email": self.submitter_email,
            "created_at": self.created_at,
        }
