"""
Time Tracking – Tracker Engine
================================

Start/stop timers, manual entries, and time reporting.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import EntryStatus, SheetStatus, TimeEntry, TimeSheet, _new_id, _now

logger = logging.getLogger(__name__)
_UTC = timezone.utc


class TimeTracker:
    """In-memory time tracking engine."""

    def __init__(self) -> None:
        self._entries: Dict[str, TimeEntry] = {}
        self._sheets: Dict[str, TimeSheet] = {}
        self._active_timers: Dict[str, str] = {}  # user_id → entry_id

    # -- Timer operations ---------------------------------------------------

    def start_timer(
        self,
        user_id: str,
        *,
        board_id: str = "",
        item_id: str = "",
        note: str = "",
        billable: bool = True,
    ) -> TimeEntry:
        """Start a new timer for *user_id*. Stops any existing timer first."""
        if user_id in self._active_timers:
            self.stop_timer(user_id)

        entry = TimeEntry(
            user_id=user_id,
            board_id=board_id,
            item_id=item_id,
            note=note,
            status=EntryStatus.RUNNING,
            billable=billable,
        )
        self._entries[entry.id] = entry
        self._active_timers[user_id] = entry.id
        logger.info("Timer started for %s: %s", user_id, entry.id)
        return entry

    def stop_timer(self, user_id: str) -> Optional[TimeEntry]:
        """Stop the active timer for *user_id*."""
        entry_id = self._active_timers.pop(user_id, None)
        if entry_id is None:
            return None
        entry = self._entries.get(entry_id)
        if entry is None:
            return None
        entry.status = EntryStatus.COMPLETED
        entry.ended_at = _now()
        try:
            start = datetime.fromisoformat(entry.started_at)
            end = datetime.fromisoformat(entry.ended_at)
            entry.duration_seconds = max(0, int((end - start).total_seconds()))
        except (ValueError, TypeError):  # PROD-HARD A2: malformed started_at — duration stays unset, but log
            logger.debug("Time entry %s: cannot compute duration (started_at=%r)", entry.id, entry.started_at)
        return entry

    def get_active_timer(self, user_id: str) -> Optional[TimeEntry]:
        entry_id = self._active_timers.get(user_id)
        return self._entries.get(entry_id) if entry_id else None

    # -- Manual entries -----------------------------------------------------

    def add_entry(
        self,
        user_id: str,
        duration_seconds: int,
        *,
        board_id: str = "",
        item_id: str = "",
        note: str = "",
        started_at: str = "",
        billable: bool = True,
        tags: Optional[List[str]] = None,
    ) -> TimeEntry:
        entry = TimeEntry(
            user_id=user_id,
            board_id=board_id,
            item_id=item_id,
            note=note,
            status=EntryStatus.COMPLETED,
            started_at=started_at or _now(),
            duration_seconds=duration_seconds,
            billable=billable,
            tags=tags or [],
        )
        self._entries[entry.id] = entry
        return entry

    def get_entry(self, entry_id: str) -> Optional[TimeEntry]:
        return self._entries.get(entry_id)

    def delete_entry(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    def list_entries(
        self,
        *,
        user_id: str = "",
        board_id: str = "",
        item_id: str = "",
    ) -> List[TimeEntry]:
        entries = list(self._entries.values())
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]
        if board_id:
            entries = [e for e in entries if e.board_id == board_id]
        if item_id:
            entries = [e for e in entries if e.item_id == item_id]
        return entries

    # -- Reporting ----------------------------------------------------------

    def total_time(
        self,
        *,
        user_id: str = "",
        board_id: str = "",
        billable_only: bool = False,
    ) -> int:
        entries = self.list_entries(user_id=user_id, board_id=board_id)
        if billable_only:
            entries = [e for e in entries if e.billable]
        return sum(e.duration_seconds for e in entries)

    def time_by_item(self, board_id: str) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for e in self.list_entries(board_id=board_id):
            result[e.item_id] = result.get(e.item_id, 0) + e.duration_seconds
        return result

    # -- Timesheets ---------------------------------------------------------

    def create_timesheet(
        self,
        user_id: str,
        period_start: str,
        period_end: str,
        entry_ids: Optional[List[str]] = None,
    ) -> TimeSheet:
        ids = entry_ids or []
        total = sum(
            self._entries[eid].duration_seconds
            for eid in ids if eid in self._entries
        )
        sheet = TimeSheet(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            entry_ids=ids,
            total_seconds=total,
        )
        self._sheets[sheet.id] = sheet
        return sheet

    def submit_timesheet(self, sheet_id: str) -> TimeSheet:
        sheet = self._sheets.get(sheet_id)
        if sheet is None:
            raise KeyError(f"Timesheet not found: {sheet_id!r}")
        sheet.status = SheetStatus.SUBMITTED
        sheet.submitted_at = _now()
        return sheet

    def approve_timesheet(self, sheet_id: str, approver_id: str) -> TimeSheet:
        sheet = self._sheets.get(sheet_id)
        if sheet is None:
            raise KeyError(f"Timesheet not found: {sheet_id!r}")
        sheet.status = SheetStatus.APPROVED
        sheet.approved_by = approver_id
        return sheet

    def get_timesheet(self, sheet_id: str) -> Optional[TimeSheet]:
        return self._sheets.get(sheet_id)

    def list_timesheets(self, user_id: str = "") -> List[TimeSheet]:
        sheets = list(self._sheets.values())
        if user_id:
            sheets = [s for s in sheets if s.user_id == user_id]
        return sheets
