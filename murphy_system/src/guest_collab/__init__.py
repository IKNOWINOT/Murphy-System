"""
Guest Collaboration
=====================

Phase 11 of management systems feature parity for the Murphy System.

Provides external collaboration including:

- **Guest invitations** with scoped permissions
- **Shareable links** (read-only or edit) with optional password
- **Client portals** with branded views
- **External forms** with form-to-item ingestion
- **REST API** at ``/api/guest``

Quick start::

    from guest_collab import GuestManager, GuestPermission

    mgr = GuestManager()
    guest = mgr.invite_guest("client@example.com", permission=GuestPermission.VIEW,
                             board_ids=["board1"])
    link = mgr.create_shareable_link("board1", created_by="u1")
    form = mgr.create_form("Feedback", "board1", fields=[
        {"label": "Name", "field_type": "text", "required": True},
    ])

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "GuestCollab"

from .guest_manager import GuestManager
from .models import (
    ClientPortal,
    ExternalForm,
    FormField,
    FormFieldType,
    FormSubmission,
    GuestPermission,
    GuestUser,
    InviteStatus,
    LinkAccess,
    ShareableLink,
)

try:
    from .api import create_guest_router
except Exception:  # pragma: no cover
    create_guest_router = None  # type: ignore[assignment]

__all__ = [
    "ClientPortal",
    "ExternalForm",
    "FormField",
    "FormFieldType",
    "FormSubmission",
    "GuestPermission",
    "GuestUser",
    "InviteStatus",
    "LinkAccess",
    "ShareableLink",
    "GuestManager",
    "create_guest_router",
]
