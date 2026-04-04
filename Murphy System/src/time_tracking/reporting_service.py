# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Reporting Service
====================================

Per-user, per-project, and date-range aggregation reports.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import EntryStatus, TimeEntry

_UTC = timezone.utc

# Statuses that represent "completed" work for reporting purposes
_REPORTABLE_STATUSES = {
    EntryStatus.COMPLETED,
    EntryStatus.STOPPED,
    EntryStatus.SUBMITTED,
    EntryStatus.APPROVED,
    EntryStatus.REJECTED,
}


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse ISO date string; return None on failure."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _entry_in_range(
    entry: TimeEntry,
    start_date: Optional[str],
    end_date: Optional[str],
) -> bool:
    """Return True when the entry's started_at falls within [start_date, end_date]."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start is None and end is None:
        return True
    entry_dt = _parse_date(entry.started_at)
    if entry_dt is None:
        return True
    if start is not None and entry_dt < start:
        return False
    if end is not None and entry_dt > end:
        return False
    return True


def _build_summary(entries: List[TimeEntry]) -> Dict[str, Any]:
    """Build a summary dict from a list of entries."""
    total = sum(e.duration_seconds for e in entries)
    billable = sum(e.duration_seconds for e in entries if e.billable)
    non_billable = total - billable
    return {
        "total_seconds": total,
        "billable_seconds": billable,
        "non_billable_seconds": non_billable,
        "entries_count": len(entries),
    }


class ReportingService:
    """Aggregation reports built over a shared entries dictionary."""

    def __init__(self, entries: Dict[str, TimeEntry], lock: threading.Lock) -> None:
        self._entries = entries
        self._lock = lock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_user_report(
        self,
        user_id: str,
        start_date: str = "",
        end_date: str = "",
    ) -> Dict[str, Any]:
        """Total hours for *user_id* with billable/non-billable breakdown
        and per-project summary."""
        with self._lock:
            entries = [
                e for e in self._entries.values()
                if e.user_id == user_id
                and e.status in _REPORTABLE_STATUSES
                and _entry_in_range(e, start_date, end_date)
            ]

        summary = _build_summary(entries)

        # Per-project breakdown (board_id == project_id)
        projects: Dict[str, List[TimeEntry]] = {}
        for e in entries:
            projects.setdefault(e.board_id or "_none", []).append(exc)

        summary["by_project"] = {
            pid: _build_summary(elist)
            for pid, elist in projects.items()
        }
        summary["user_id"] = user_id
        summary["start_date"] = start_date
        summary["end_date"] = end_date
        return summary

    def get_project_report(
        self,
        project_id: str,
        start_date: str = "",
        end_date: str = "",
    ) -> Dict[str, Any]:
        """Total hours on *project_id* (board_id) with per-user breakdown."""
        with self._lock:
            entries = [
                e for e in self._entries.values()
                if e.board_id == project_id
                and e.status in _REPORTABLE_STATUSES
                and _entry_in_range(e, start_date, end_date)
            ]

        summary = _build_summary(entries)

        # Per-user breakdown
        users: Dict[str, List[TimeEntry]] = {}
        for e in entries:
            users.setdefault(e.user_id or "_none", []).append(exc)

        summary["by_user"] = {
            uid: _build_summary(ulist)
            for uid, ulist in users.items()
        }
        summary["project_id"] = project_id
        summary["start_date"] = start_date
        summary["end_date"] = end_date
        return summary

    def get_date_range_report(
        self,
        start_date: str = "",
        end_date: str = "",
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Aggregated report across all users/projects with optional filters.

        Supported filters: ``user_id``, ``project_id``, ``billable``.
        """
        filters = filters or {}
        filter_user = filters.get("user_id", "")
        filter_project = filters.get("project_id", "")
        filter_billable = filters.get("billable", None)

        with self._lock:
            entries = [
                e for e in self._entries.values()
                if e.status in _REPORTABLE_STATUSES
                and _entry_in_range(e, start_date, end_date)
                and (not filter_user or e.user_id == filter_user)
                and (not filter_project or e.board_id == filter_project)
                and (
                    filter_billable is None
                    or e.billable == bool(filter_billable)
                )
            ]

        summary = _build_summary(entries)

        # Per-user breakdown
        users: Dict[str, List[TimeEntry]] = {}
        for e in entries:
            users.setdefault(e.user_id or "_none", []).append(exc)
        summary["by_user"] = {
            uid: _build_summary(ulist)
            for uid, ulist in users.items()
        }

        # Per-project breakdown
        projects: Dict[str, List[TimeEntry]] = {}
        for e in entries:
            projects.setdefault(e.board_id or "_none", []).append(exc)
        summary["by_project"] = {
            pid: _build_summary(plist)
            for pid, plist in projects.items()
        }

        summary["start_date"] = start_date
        summary["end_date"] = end_date
        summary["filters"] = filters
        return summary
