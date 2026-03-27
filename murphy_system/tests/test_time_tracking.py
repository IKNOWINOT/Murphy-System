"""Tests for Phase 6 – Time Tracking."""

import sys, os

import time
import pytest
from time_tracking.models import EntryStatus, SheetStatus, TimeEntry, TimeSheet
from time_tracking.tracker import TimeTracker


class TestModels:
    def test_time_entry_to_dict(self):
        e = TimeEntry(user_id="u1", duration_seconds=3600)
        r = e.to_dict()
        assert r["duration_seconds"] == 3600

    def test_timesheet_to_dict(self):
        s = TimeSheet(user_id="u1", period_start="2025-01-01")
        r = s.to_dict()
        assert r["status"] == "draft"


class TestTracker:
    def test_start_timer(self):
        t = TimeTracker()
        e = t.start_timer("u1", board_id="b1")
        assert e.status == EntryStatus.RUNNING
        assert t.get_active_timer("u1") is e

    def test_stop_timer(self):
        t = TimeTracker()
        t.start_timer("u1")
        e = t.stop_timer("u1")
        assert e is not None
        assert e.status == EntryStatus.COMPLETED
        assert t.get_active_timer("u1") is None

    def test_stop_timer_none(self):
        t = TimeTracker()
        assert t.stop_timer("u1") is None

    def test_start_stops_existing(self):
        t = TimeTracker()
        e1 = t.start_timer("u1")
        e2 = t.start_timer("u1")
        assert e1.id != e2.id
        assert t._entries[e1.id].status == EntryStatus.COMPLETED

    def test_add_entry(self):
        t = TimeTracker()
        e = t.add_entry("u1", 7200, board_id="b1", item_id="i1")
        assert e.duration_seconds == 7200

    def test_get_entry(self):
        t = TimeTracker()
        e = t.add_entry("u1", 100)
        assert t.get_entry(e.id) is e
        assert t.get_entry("nope") is None

    def test_delete_entry(self):
        t = TimeTracker()
        e = t.add_entry("u1", 100)
        assert t.delete_entry(e.id)
        assert not t.delete_entry(e.id)

    def test_list_entries(self):
        t = TimeTracker()
        t.add_entry("u1", 100, board_id="b1")
        t.add_entry("u2", 200, board_id="b1")
        t.add_entry("u1", 300, board_id="b2")
        assert len(t.list_entries()) == 3
        assert len(t.list_entries(user_id="u1")) == 2
        assert len(t.list_entries(board_id="b1")) == 2

    def test_total_time(self):
        t = TimeTracker()
        t.add_entry("u1", 100, board_id="b1", billable=True)
        t.add_entry("u1", 200, board_id="b1", billable=False)
        assert t.total_time(user_id="u1") == 300
        assert t.total_time(user_id="u1", billable_only=True) == 100

    def test_time_by_item(self):
        t = TimeTracker()
        t.add_entry("u1", 100, board_id="b1", item_id="i1")
        t.add_entry("u1", 200, board_id="b1", item_id="i1")
        t.add_entry("u1", 300, board_id="b1", item_id="i2")
        result = t.time_by_item("b1")
        assert result["i1"] == 300
        assert result["i2"] == 300

    def test_create_timesheet(self):
        t = TimeTracker()
        e = t.add_entry("u1", 3600)
        sheet = t.create_timesheet("u1", "2025-01-01", "2025-01-07", [e.id])
        assert sheet.total_seconds == 3600

    def test_submit_timesheet(self):
        t = TimeTracker()
        sheet = t.create_timesheet("u1", "2025-01-01", "2025-01-07")
        sub = t.submit_timesheet(sheet.id)
        assert sub.status == SheetStatus.SUBMITTED

    def test_approve_timesheet(self):
        t = TimeTracker()
        sheet = t.create_timesheet("u1", "2025-01-01", "2025-01-07")
        t.submit_timesheet(sheet.id)
        app = t.approve_timesheet(sheet.id, "manager1")
        assert app.status == SheetStatus.APPROVED
        assert app.approved_by == "manager1"

    def test_list_timesheets(self):
        t = TimeTracker()
        t.create_timesheet("u1", "2025-01-01", "2025-01-07")
        t.create_timesheet("u2", "2025-01-01", "2025-01-07")
        assert len(t.list_timesheets()) == 2
        assert len(t.list_timesheets("u1")) == 1


class TestAPIRouter:
    def test_create_router(self):
        from time_tracking.api import create_time_tracking_router
        router = create_time_tracking_router()
        assert router is not None
