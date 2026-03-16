# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Approval Service
====================================

Submit → approve / reject lifecycle for time entries.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations
import logging

import threading
from typing import Any, Dict, List, Optional

from .models import EntryStatus, TimeEntry, _now

# Statuses that are eligible to be submitted
_SUBMITTABLE_STATUSES = {EntryStatus.COMPLETED, EntryStatus.STOPPED}


class ApprovalError(ValueError):
    """Raised when an approval operation is not permitted."""


class ApprovalService:
    """Manages the submit → approve/reject workflow for time entries."""

    def __init__(self, entries: Dict[str, TimeEntry], lock: threading.Lock) -> None:
        self._entries = entries
        self._lock = lock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit_timesheet(
        self, user_id: str, entry_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Batch-submit *entry_ids* for approval.

        Only entries with status COMPLETED / STOPPED may be submitted.
        Raises :class:`ApprovalError` if any entry is ineligible.
        """
        with self._lock:
            entries = self._resolve_entries(entry_ids, owner=user_id)
            for entry in entries:
                if entry.status not in _SUBMITTABLE_STATUSES:
                    raise ApprovalError(
                        f"Entry {entry.id!r} has status {entry.status.value!r}; "
                        "only stopped/completed entries can be submitted."
                    )
            for entry in entries:
                entry.status = EntryStatus.SUBMITTED
            return [e.to_dict() for e in entries]

    def approve_entries(
        self, approver_id: str, entry_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Approve *entry_ids*.

        Only entries with status SUBMITTED may be approved.
        """
        with self._lock:
            entries = self._resolve_entries(entry_ids)
            for entry in entries:
                if entry.status != EntryStatus.SUBMITTED:
                    raise ApprovalError(
                        f"Entry {entry.id!r} has status {entry.status.value!r}; "
                        "only submitted entries can be approved."
                    )
            now = _now()
            for entry in entries:
                entry.status = EntryStatus.APPROVED
                entry.approved_by = approver_id
                entry.approved_at = now
                entry.rejection_reason = ""
            return [e.to_dict() for e in entries]

    def reject_entries(
        self, approver_id: str, entry_ids: List[str], reason: str
    ) -> List[Dict[str, Any]]:
        """Reject *entry_ids* with *reason*.

        Only entries with status SUBMITTED may be rejected.
        """
        with self._lock:
            entries = self._resolve_entries(entry_ids)
            for entry in entries:
                if entry.status != EntryStatus.SUBMITTED:
                    raise ApprovalError(
                        f"Entry {entry.id!r} has status {entry.status.value!r}; "
                        "only submitted entries can be rejected."
                    )
            now = _now()
            for entry in entries:
                entry.status = EntryStatus.REJECTED
                entry.approved_by = approver_id
                entry.approved_at = now
                entry.rejection_reason = reason
            return [e.to_dict() for e in entries]

    def get_pending_approvals(
        self, approver_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return all entries awaiting approval (status == SUBMITTED).

        *approver_id* is accepted for future ACL use but currently unused.
        """
        with self._lock:
            return [
                e.to_dict()
                for e in self._entries.values()
                if e.status == EntryStatus.SUBMITTED
            ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_entries(
        self, entry_ids: List[str], owner: Optional[str] = None
    ) -> List[TimeEntry]:
        """Look up entries by ID; raise KeyError when any are missing."""
        result: List[TimeEntry] = []
        for eid in entry_ids:
            entry = self._entries.get(eid)
            if entry is None:
                raise KeyError(f"Entry not found: {eid!r}")
            if owner and entry.user_id != owner:
                raise ApprovalError(
                    f"Entry {eid!r} does not belong to user {owner!r}."
                )
            result.append(entry)
        return result
