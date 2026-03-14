"""
Guest Collaboration – Guest Manager
======================================

Guest invitations, shareable links, client portals, external forms.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

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
    _now,
)

logger = logging.getLogger(__name__)


class GuestManager:
    """In-memory guest collaboration manager."""

    def __init__(self) -> None:
        self._guests: Dict[str, GuestUser] = {}
        self._links: Dict[str, ShareableLink] = {}
        self._portals: Dict[str, ClientPortal] = {}
        self._forms: Dict[str, ExternalForm] = {}
        self._submissions: List[FormSubmission] = []

    # -- Guest invitations --------------------------------------------------

    def invite_guest(
        self,
        email: str,
        *,
        name: str = "",
        permission: GuestPermission = GuestPermission.VIEW,
        board_ids: Optional[List[str]] = None,
        invited_by: str = "",
        expires_at: str = "",
    ) -> GuestUser:
        guest = GuestUser(
            email=email,
            name=name,
            permission=permission,
            board_ids=board_ids or [],
            invited_by=invited_by,
            expires_at=expires_at,
        )
        self._guests[guest.id] = guest
        logger.info("Guest invited: %s (%s)", email, guest.id)
        return guest

    def get_guest(self, guest_id: str) -> Optional[GuestUser]:
        return self._guests.get(guest_id)

    def list_guests(self, invited_by: str = "") -> List[GuestUser]:
        guests = list(self._guests.values())
        if invited_by:
            guests = [g for g in guests if g.invited_by == invited_by]
        return guests

    def accept_invite(self, guest_id: str) -> GuestUser:
        guest = self._guests.get(guest_id)
        if guest is None:
            raise KeyError(f"Guest not found: {guest_id!r}")
        guest.status = InviteStatus.ACCEPTED
        return guest

    def revoke_invite(self, guest_id: str) -> GuestUser:
        guest = self._guests.get(guest_id)
        if guest is None:
            raise KeyError(f"Guest not found: {guest_id!r}")
        guest.status = InviteStatus.REVOKED
        return guest

    def update_guest_permissions(
        self,
        guest_id: str,
        *,
        permission: Optional[GuestPermission] = None,
        board_ids: Optional[List[str]] = None,
    ) -> GuestUser:
        guest = self._guests.get(guest_id)
        if guest is None:
            raise KeyError(f"Guest not found: {guest_id!r}")
        if permission is not None:
            guest.permission = permission
        if board_ids is not None:
            guest.board_ids = board_ids
        return guest

    # -- Shareable links ----------------------------------------------------

    def create_shareable_link(
        self,
        board_id: str,
        *,
        item_id: str = "",
        access: LinkAccess = LinkAccess.READ_ONLY,
        created_by: str = "",
        password: str = "",
        expires_at: str = "",
    ) -> ShareableLink:
        link = ShareableLink(
            board_id=board_id,
            item_id=item_id,
            access=access,
            created_by=created_by,
            password=password,
            expires_at=expires_at,
        )
        self._links[link.id] = link
        return link

    def get_link(self, link_id: str) -> Optional[ShareableLink]:
        return self._links.get(link_id)

    def get_link_by_token(self, token: str) -> Optional[ShareableLink]:
        for link in self._links.values():
            if link.token == token and link.active:
                return link
        return None

    def deactivate_link(self, link_id: str) -> bool:
        link = self._links.get(link_id)
        if link is None:
            return False
        link.active = False
        return True

    def record_link_view(self, link_id: str) -> None:
        link = self._links.get(link_id)
        if link is not None:
            link.view_count += 1

    def list_links(self, board_id: str = "") -> List[ShareableLink]:
        links = list(self._links.values())
        if board_id:
            links = [l for l in links if l.board_id == board_id]
        return links

    # -- Client portals -----------------------------------------------------

    def create_portal(
        self,
        name: str,
        owner_id: str,
        *,
        board_ids: Optional[List[str]] = None,
        logo_url: str = "",
        primary_color: str = "#4A90D9",
        welcome_message: str = "",
    ) -> ClientPortal:
        portal = ClientPortal(
            name=name,
            owner_id=owner_id,
            board_ids=board_ids or [],
            logo_url=logo_url,
            primary_color=primary_color,
            welcome_message=welcome_message,
        )
        self._portals[portal.id] = portal
        return portal

    def get_portal(self, portal_id: str) -> Optional[ClientPortal]:
        return self._portals.get(portal_id)

    def list_portals(self, owner_id: str = "") -> List[ClientPortal]:
        portals = list(self._portals.values())
        if owner_id:
            portals = [p for p in portals if p.owner_id == owner_id]
        return portals

    def add_guest_to_portal(self, portal_id: str, guest_id: str) -> ClientPortal:
        portal = self._portals.get(portal_id)
        if portal is None:
            raise KeyError(f"Portal not found: {portal_id!r}")
        if guest_id not in portal.guest_ids:
            portal.guest_ids.append(guest_id)
        return portal

    # -- External forms -----------------------------------------------------

    def create_form(
        self,
        name: str,
        board_id: str,
        *,
        group_id: str = "",
        fields: Optional[List[Dict[str, Any]]] = None,
    ) -> ExternalForm:
        form_fields = []
        for f in (fields or []):
            try:
                ft = FormFieldType(f.get("field_type", "text"))
            except ValueError:
                ft = FormFieldType.TEXT
            form_fields.append(FormField(
                label=f.get("label", ""),
                field_type=ft,
                required=f.get("required", False),
                options=f.get("options", []),
            ))
        form = ExternalForm(
            name=name,
            board_id=board_id,
            group_id=group_id,
            fields=form_fields,
        )
        self._forms[form.id] = form
        return form

    def get_form(self, form_id: str) -> Optional[ExternalForm]:
        return self._forms.get(form_id)

    def get_form_by_token(self, token: str) -> Optional[ExternalForm]:
        for form in self._forms.values():
            if form.token == token and form.active:
                return form
        return None

    def list_forms(self, board_id: str = "") -> List[ExternalForm]:
        forms = list(self._forms.values())
        if board_id:
            forms = [f for f in forms if f.board_id == board_id]
        return forms

    def submit_form(
        self,
        form_id: str,
        data: Dict[str, Any],
        *,
        submitter_email: str = "",
    ) -> FormSubmission:
        form = self._forms.get(form_id)
        if form is None:
            raise KeyError(f"Form not found: {form_id!r}")
        if not form.active:
            raise ValueError("Form is not active")
        # Validate required fields
        for ff in form.fields:
            if ff.required and ff.label not in data:
                raise ValueError(f"Missing required field: {ff.label!r}")
        submission = FormSubmission(
            form_id=form_id,
            data=data,
            submitter_email=submitter_email,
        )
        capped_append(self._submissions, submission)
        form.submission_count += 1
        return submission

    def list_submissions(self, form_id: str = "") -> List[FormSubmission]:
        subs = self._submissions
        if form_id:
            subs = [s for s in subs if s.form_id == form_id]
        return subs
