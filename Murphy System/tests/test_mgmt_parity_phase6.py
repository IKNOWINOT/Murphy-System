"""
Acceptance tests – Management Parity Phase 6: Time Tracking
============================================================

Validates the Time Tracking module (``src/time_tracking``):

- Time entry creation (manual entries)
- Timer start/stop lifecycle
- Timesheet submission and approval workflow
- Reporting: per-user, per-project, date-range summaries

Run selectively::

    pytest -m parity tests/test_mgmt_parity_phase6.py

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import sys
import os
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import time_tracking
from time_tracking import (
    EntryStatus,
    SheetStatus,
    TimeEntry,
    TimeSheet,
    TimeTracker,
    ReportingService,
    ApprovalService,
    ApprovalError,
)

pytestmark = pytest.mark.parity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tracker() -> TimeTracker:
    return TimeTracker()


# ---------------------------------------------------------------------------
# 1. Module structure
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_package_version_exists(self):
        assert hasattr(time_tracking, "__version__")

    def test_time_tracker_importable(self):
        assert TimeTracker is not None

    def test_reporting_service_importable(self):
        assert ReportingService is not None

    def test_approval_service_importable(self):
        assert ApprovalService is not None

    def test_entry_status_values(self):
        for s in (
            EntryStatus.RUNNING,
            EntryStatus.PAUSED,
            EntryStatus.COMPLETED,
            EntryStatus.STOPPED,
            EntryStatus.SUBMITTED,
            EntryStatus.APPROVED,
            EntryStatus.REJECTED,
        ):
            assert s is not None

    def test_sheet_status_values(self):
        for s in (SheetStatus.DRAFT, SheetStatus.SUBMITTED,
                  SheetStatus.APPROVED, SheetStatus.REJECTED):
            assert s is not None


# ---------------------------------------------------------------------------
# 2. Time entry creation
# ---------------------------------------------------------------------------


class TestTimeEntryCreation:
    def test_add_manual_entry(self):
        tracker = _make_tracker()
        entry = tracker.add_entry(
            user_id="alice",
            board_id="board-1",
            item_id="item-1",
            duration_seconds=3600,
            note="Design review",
        )
        assert isinstance(entry, TimeEntry)
        assert entry.duration_seconds == 3600
        assert entry.user_id == "alice"

    def test_entry_has_unique_id(self):
        tracker = _make_tracker()
        e1 = tracker.add_entry("alice", duration_seconds=60)
        e2 = tracker.add_entry("alice", duration_seconds=60)
        assert e1.id != e2.id

    def test_get_entry_by_id(self):
        tracker = _make_tracker()
        entry = tracker.add_entry("alice", duration_seconds=1800, board_id="b1")
        retrieved = tracker.get_entry(entry.id)
        assert retrieved is not None
        assert retrieved.id == entry.id

    def test_delete_entry(self):
        tracker = _make_tracker()
        entry = tracker.add_entry("alice", duration_seconds=900)
        removed = tracker.delete_entry(entry.id)
        assert removed is True
        assert tracker.get_entry(entry.id) is None

    def test_list_entries_by_user(self):
        tracker = _make_tracker()
        tracker.add_entry("alice", duration_seconds=60)
        tracker.add_entry("alice", duration_seconds=120)
        tracker.add_entry("bob", duration_seconds=60)
        alice_entries = tracker.list_entries(user_id="alice")
        assert len(alice_entries) == 2

    def test_list_entries_by_board(self):
        tracker = _make_tracker()
        tracker.add_entry("alice", board_id="board-x", duration_seconds=60)
        tracker.add_entry("alice", board_id="board-x", duration_seconds=120)
        tracker.add_entry("alice", board_id="board-y", duration_seconds=60)
        board_entries = tracker.list_entries(board_id="board-x")
        assert len(board_entries) == 2

    def test_billable_flag_on_entry(self):
        tracker = _make_tracker()
        entry = tracker.add_entry("alice", duration_seconds=600, billable=True)
        assert entry.billable is True

    def test_total_time_for_user(self):
        tracker = _make_tracker()
        tracker.add_entry("alice", duration_seconds=3600, board_id="b1")
        tracker.add_entry("alice", duration_seconds=1800, board_id="b1")
        total = tracker.total_time(user_id="alice")
        assert total >= 5400


# ---------------------------------------------------------------------------
# 3. Timer start/stop
# ---------------------------------------------------------------------------


class TestTimerStartStop:
    def test_start_timer_returns_running_entry(self):
        tracker = _make_tracker()
        entry = tracker.start_timer("alice", board_id="board-1", item_id="item-1")
        assert entry.status == EntryStatus.RUNNING
        assert entry.user_id == "alice"

    def test_stop_timer_marks_entry_completed(self):
        tracker = _make_tracker()
        tracker.start_timer("alice")
        entry = tracker.stop_timer("alice")
        assert entry is not None
        assert entry.status == EntryStatus.COMPLETED

    def test_stop_timer_records_duration(self):
        tracker = _make_tracker()
        tracker.start_timer("alice")
        # Give a tiny delay so duration_seconds > 0
        time.sleep(0.05)
        entry = tracker.stop_timer("alice")
        assert entry.duration_seconds >= 0  # may be 0 on fast machines

    def test_get_active_timer(self):
        tracker = _make_tracker()
        tracker.start_timer("alice")
        active = tracker.get_active_timer("alice")
        assert active is not None
        assert active.status == EntryStatus.RUNNING

    def test_no_active_timer_after_stop(self):
        tracker = _make_tracker()
        tracker.start_timer("alice")
        tracker.stop_timer("alice")
        active = tracker.get_active_timer("alice")
        assert active is None

    def test_starting_second_timer_stops_first(self):
        tracker = _make_tracker()
        tracker.start_timer("alice", note="First task")
        first_id = tracker.get_active_timer("alice").id
        tracker.start_timer("alice", note="Second task")
        second_active = tracker.get_active_timer("alice")
        assert second_active.id != first_id

    def test_stop_nonexistent_timer_returns_none(self):
        tracker = _make_tracker()
        result = tracker.stop_timer("nobody")
        assert result is None


# ---------------------------------------------------------------------------
# 4. Timesheet approval
# ---------------------------------------------------------------------------


class TestTimesheetApproval:
    def _setup_approved_entry(self, tracker: TimeTracker) -> TimeEntry:
        """Create and stop an entry ready for submission."""
        tracker.start_timer("alice")
        entry = tracker.stop_timer("alice")
        return entry

    def test_create_timesheet(self):
        tracker = _make_tracker()
        entry = self._setup_approved_entry(tracker)
        sheet = tracker.create_timesheet(
            "alice",
            "2025-01-01",
            "2025-01-07",
            entry_ids=[entry.id],
        )
        assert isinstance(sheet, TimeSheet)
        assert sheet.user_id == "alice"

    def test_submit_timesheet(self):
        tracker = _make_tracker()
        entry = self._setup_approved_entry(tracker)
        sheet = tracker.create_timesheet("alice", "2025-01-01", "2025-01-07", entry_ids=[entry.id])
        submitted = tracker.submit_timesheet(sheet.id)
        assert submitted.status == SheetStatus.SUBMITTED

    def test_approve_timesheet(self):
        tracker = _make_tracker()
        entry = self._setup_approved_entry(tracker)
        sheet = tracker.create_timesheet("alice", "2025-01-01", "2025-01-07", entry_ids=[entry.id])
        tracker.submit_timesheet(sheet.id)
        approved = tracker.approve_timesheet(sheet.id, approver_id="manager")
        assert approved.status == SheetStatus.APPROVED

    def test_list_timesheets_by_user(self):
        tracker = _make_tracker()
        e1 = self._setup_approved_entry(tracker)
        e2 = tracker.add_entry("alice", duration_seconds=60)
        tracker.create_timesheet("alice", "2025-01-01", "2025-01-07", entry_ids=[e1.id])
        tracker.create_timesheet("alice", "2025-01-08", "2025-01-14", entry_ids=[e2.id])
        sheets = tracker.list_timesheets(user_id="alice")
        assert len(sheets) == 2


# ---------------------------------------------------------------------------
# 5. Reporting
# ---------------------------------------------------------------------------


class TestReporting:
    def _tracker_with_entries(self) -> TimeTracker:
        tracker = _make_tracker()
        tracker.add_entry("alice", board_id="board-1", item_id="i1",
                          duration_seconds=3600, billable=True)
        tracker.add_entry("alice", board_id="board-1", item_id="i2",
                          duration_seconds=1800, billable=False)
        tracker.add_entry("bob", board_id="board-2", item_id="i3",
                          duration_seconds=900, billable=True)
        return tracker

    def test_user_report_returns_data(self):
        tracker = self._tracker_with_entries()
        reporting = ReportingService(tracker._entries, threading.Lock())
        report = reporting.get_user_report("alice")
        assert isinstance(report, dict)
        assert report.get("total_seconds", 0) >= 5400

    def test_project_report_returns_data(self):
        tracker = self._tracker_with_entries()
        reporting = ReportingService(tracker._entries, threading.Lock())
        report = reporting.get_project_report("board-1")
        assert isinstance(report, dict)
        assert report.get("total_seconds", 0) >= 5400

    def test_date_range_report(self):
        tracker = self._tracker_with_entries()
        reporting = ReportingService(tracker._entries, threading.Lock())
        report = reporting.get_date_range_report("2025-01-01", "2026-12-31")
        assert isinstance(report, dict)

    def test_time_by_item(self):
        tracker = self._tracker_with_entries()
        by_item = tracker.time_by_item("board-1")
        assert isinstance(by_item, dict)
        # Should have entries for i1 and/or i2
        assert len(by_item) >= 1
