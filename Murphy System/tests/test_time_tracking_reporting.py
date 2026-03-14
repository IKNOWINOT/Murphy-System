# Copyright © 2020 Inoni Limited Liability Company
"""
Test Suite: Time Tracking – Reporting, Approvals & Export
===========================================================

Tests for Phase 6B: reporting service, approval workflow, and export service.
IDs: TT-020 through TT-035.

Uses the storyline-actuals record() pattern consistent with other suites.

Copyright © 2020 Inoni Limited Liability Company
"""

from __future__ import annotations

import sys
import os
import threading
from dataclasses import dataclass, field
from typing import Any, List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from time_tracking.models import EntryStatus, TimeEntry, _now
from time_tracking.tracker import TimeTracker
from time_tracking.reporting_service import ReportingService
from time_tracking.approval_service import ApprovalError, ApprovalService
from time_tracking.export_service import ExportService

# ── storyline-actuals helper ──────────────────────────────────────────


@dataclass
class CheckResult:
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str
    effect: str
    lesson: str


_results: List[CheckResult] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str,
    effect: str,
    lesson: str,
) -> bool:
    passed = expected == actual
    _results.append(
        CheckResult(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    return passed


# ── fixtures ──────────────────────────────────────────────────────────


def _make_tracker_with_entries():
    """Return a tracker pre-populated with a small set of entries."""
    t = TimeTracker()
    # user1, project-A, billable
    t.add_entry("user1", 3600, board_id="proj-A", item_id="item-1", billable=True)
    t.add_entry("user1", 1800, board_id="proj-A", item_id="item-2", billable=False)
    # user1, project-B
    t.add_entry("user1", 7200, board_id="proj-B", item_id="item-3", billable=True)
    # user2, project-A
    t.add_entry("user2", 3600, board_id="proj-A", item_id="item-1", billable=True)
    return t


def _make_services(tracker=None):
    t = tracker or _make_tracker_with_entries()
    lock = threading.Lock()
    rep = ReportingService(t._entries, lock)
    apr = ApprovalService(t._entries, lock)
    exp = ExportService()
    return t, rep, apr, exp


# ── TT-020: user report totals ────────────────────────────────────────


class TestUserReport:
    def test_tt020_total_seconds(self):
        """TT-020: User report sums all entry durations for the user."""
        t, rep, _, _ = _make_services()
        report = rep.get_user_report("user1")
        result = record(
            "TT-020",
            "user1 total seconds == 3600+1800+7200",
            12600,
            report["total_seconds"],
            cause="Three entries for user1 with durations 3600+1800+7200",
            effect="total_seconds == 12600",
            lesson="Reporting service must aggregate all user entries",
        )
        assert result

    def test_tt021_billable_breakdown(self):
        """TT-021: Billable vs non-billable breakdown is correct."""
        t, rep, _, _ = _make_services()
        report = rep.get_user_report("user1")
        result = record(
            "TT-021",
            "billable_seconds == 10800, non_billable_seconds == 1800",
            (10800, 1800),
            (report["billable_seconds"], report["non_billable_seconds"]),
            cause="user1 has 3600+7200 billable and 1800 non-billable",
            effect="billable=10800, non_billable=1800",
            lesson="Reporting must split billable and non-billable correctly",
        )
        assert result

    def test_tt022_by_project_breakdown(self):
        """TT-022: Per-project breakdown included in user report."""
        t, rep, _, _ = _make_services()
        report = rep.get_user_report("user1")
        by_proj = report["by_project"]
        result = record(
            "TT-022",
            "proj-A total == 5400, proj-B total == 7200",
            (5400, 7200),
            (by_proj["proj-A"]["total_seconds"], by_proj["proj-B"]["total_seconds"]),
            cause="user1 has proj-A(3600+1800) and proj-B(7200)",
            effect="per-project totals match",
            lesson="User report must include per-project breakdown",
        )
        assert result

    def test_tt023_date_filter_excludes_old_entries(self):
        """TT-023: Date filtering limits report to the given range."""
        t, rep, _, _ = _make_services()
        # Entries use current time; future dates should return 0
        report = rep.get_user_report("user1", start_date="2099-01-01")
        result = record(
            "TT-023",
            "total_seconds == 0 when start_date is in far future",
            0,
            report["total_seconds"],
            cause="All entries have timestamps before 2099-01-01",
            effect="Filtered report returns zero seconds",
            lesson="Date filters must restrict entries correctly",
        )
        assert result


# ── TT-024: project report ────────────────────────────────────────────


class TestProjectReport:
    def test_tt024_total_seconds(self):
        """TT-024: Project report sums all users' entries."""
        t, rep, _, _ = _make_services()
        report = rep.get_project_report("proj-A")
        result = record(
            "TT-024",
            "proj-A total == 3600+1800+3600",
            9000,
            report["total_seconds"],
            cause="proj-A: user1(3600+1800) + user2(3600)",
            effect="total_seconds == 9000",
            lesson="Project report must aggregate all users",
        )
        assert result

    def test_tt025_by_user_breakdown(self):
        """TT-025: Per-user breakdown is correct in project report."""
        t, rep, _, _ = _make_services()
        report = rep.get_project_report("proj-A")
        by_user = report["by_user"]
        result = record(
            "TT-025",
            "user1==5400, user2==3600",
            (5400, 3600),
            (by_user["user1"]["total_seconds"], by_user["user2"]["total_seconds"]),
            cause="user1 has 3600+1800 on proj-A; user2 has 3600",
            effect="per-user totals match",
            lesson="Project report must include per-user breakdown",
        )
        assert result


# ── TT-026: date-range report ─────────────────────────────────────────


class TestDateRangeReport:
    def test_tt026_no_filters(self):
        """TT-026: Date-range report aggregates all entries."""
        t, rep, _, _ = _make_services()
        report = rep.get_date_range_report()
        result = record(
            "TT-026",
            "total entries_count == 4",
            4,
            report["entries_count"],
            cause="4 entries added across users and projects",
            effect="entries_count == 4",
            lesson="Date-range report without filters counts all entries",
        )
        assert result

    def test_tt027_filter_by_user(self):
        """TT-027: Filtering by user_id works in date-range report."""
        t, rep, _, _ = _make_services()
        report = rep.get_date_range_report(filters={"user_id": "user2"})
        result = record(
            "TT-027",
            "entries_count == 1 for user2",
            1,
            report["entries_count"],
            cause="user2 has exactly 1 entry",
            effect="filtered count == 1",
            lesson="Date-range report must respect user_id filter",
        )
        assert result


# ── TT-028: approval submit ───────────────────────────────────────────


class TestApprovalSubmit:
    def test_tt028_submit_completed_entry(self):
        """TT-028: Submitting a completed entry changes its status to SUBMITTED."""
        t = TimeTracker()
        e = t.add_entry("user1", 3600)
        assert e.status == EntryStatus.COMPLETED
        _, _, apr, _ = _make_services(t)
        result_list = apr.submit_timesheet("user1", [e.id])
        result = record(
            "TT-028",
            "entry status after submit == 'submitted'",
            "submitted",
            result_list[0]["status"],
            cause="Entry was COMPLETED; submit_timesheet called",
            effect="status changes to SUBMITTED",
            lesson="Only completed/stopped entries can be submitted",
        )
        assert result

    def test_tt029_cannot_submit_running_entry(self):
        """TT-029: Submitting a running entry raises ApprovalError."""
        t = TimeTracker()
        e = t.start_timer("user1")
        _, _, apr, _ = _make_services(t)
        with pytest.raises(ApprovalError):
            apr.submit_timesheet("user1", [e.id])
        result = record(
            "TT-029",
            "ApprovalError raised for running entry",
            True,
            True,
            cause="Entry is still RUNNING",
            effect="ApprovalError raised",
            lesson="Cannot submit entries that are not stopped",
        )
        assert result

    def test_tt030_cannot_submit_wrong_owner(self):
        """TT-030: User cannot submit another user's entry."""
        t = TimeTracker()
        e = t.add_entry("user1", 3600)
        _, _, apr, _ = _make_services(t)
        with pytest.raises(ApprovalError):
            apr.submit_timesheet("user2", [e.id])
        result = record(
            "TT-030",
            "ApprovalError raised when user_id mismatch",
            True,
            True,
            cause="Entry belongs to user1 but user2 tries to submit",
            effect="ApprovalError raised",
            lesson="Ownership must be validated on submit",
        )
        assert result


# ── TT-031: approval approve / reject ────────────────────────────────


class TestApproveReject:
    def _submitted_entry(self):
        t = TimeTracker()
        e = t.add_entry("user1", 3600)
        _, _, apr, _ = _make_services(t)
        apr.submit_timesheet("user1", [e.id])
        return t, e, apr

    def test_tt031_approve_submitted_entry(self):
        """TT-031: Approving a submitted entry changes status to APPROVED."""
        t, e, apr = self._submitted_entry()
        result_list = apr.approve_entries("manager1", [e.id])
        result = record(
            "TT-031",
            "status after approve == 'approved'",
            "approved",
            result_list[0]["status"],
            cause="Entry was SUBMITTED; approve_entries called",
            effect="status == APPROVED, approved_by == 'manager1'",
            lesson="Approved entries must record the approver",
        )
        assert result
        assert result_list[0]["approved_by"] == "manager1"

    def test_tt032_reject_submitted_entry(self):
        """TT-032: Rejecting a submitted entry records reason and status REJECTED."""
        t, e, apr = self._submitted_entry()
        result_list = apr.reject_entries("manager1", [e.id], "Overtime not pre-approved")
        result = record(
            "TT-032",
            "status after reject == 'rejected'",
            "rejected",
            result_list[0]["status"],
            cause="Entry was SUBMITTED; reject_entries called with reason",
            effect="status == REJECTED, rejection_reason recorded",
            lesson="Rejected entries must capture the rejection reason",
        )
        assert result
        assert result_list[0]["rejection_reason"] == "Overtime not pre-approved"

    def test_tt033_cannot_approve_non_submitted(self):
        """TT-033: Approving a non-submitted entry raises ApprovalError."""
        t = TimeTracker()
        e = t.add_entry("user1", 3600)
        _, _, apr, _ = _make_services(t)
        with pytest.raises(ApprovalError):
            apr.approve_entries("manager1", [e.id])
        result = record(
            "TT-033",
            "ApprovalError when approving non-submitted entry",
            True,
            True,
            cause="Entry has status COMPLETED, not SUBMITTED",
            effect="ApprovalError raised",
            lesson="Only SUBMITTED entries can be approved",
        )
        assert result

    def test_tt034_pending_approvals_list(self):
        """TT-034: get_pending_approvals returns only SUBMITTED entries."""
        t, e, apr = self._submitted_entry()
        pending = apr.get_pending_approvals()
        result = record(
            "TT-034",
            "pending count == 1",
            1,
            len(pending),
            cause="One entry was submitted, none approved/rejected",
            effect="Pending list has exactly 1 entry",
            lesson="Pending approvals must filter on SUBMITTED status",
        )
        assert result
        assert pending[0]["id"] == e.id


# ── TT-035: export ────────────────────────────────────────────────────


class TestExport:
    def test_tt035_csv_headers(self):
        """TT-035: CSV export includes all required column headers."""
        t, _, _, exp = _make_services()
        entries = list(t._entries.values())
        csv_str = exp.export_to_csv(entries)
        first_line = csv_str.splitlines()[0]
        required = [
            "Date", "User", "Project", "Item", "Description",
            "Start", "End", "Duration (hours)", "Billable", "Status",
        ]
        missing = [h for h in required if h not in first_line]
        result = record(
            "TT-035",
            "All required CSV headers present",
            [],
            missing,
            cause="ExportService.export_to_csv called with 4 entries",
            effect="First line contains all required column headers",
            lesson="CSV export must include the full header row",
        )
        assert result

    def test_tt036_csv_row_count(self):
        """TT-036: CSV row count equals number of entries + 1 header."""
        t, _, _, exp = _make_services()
        entries = list(t._entries.values())
        csv_str = exp.export_to_csv(entries)
        lines = [ln for ln in csv_str.splitlines() if ln.strip()]
        result = record(
            "TT-036",
            "CSV has 5 lines (1 header + 4 data rows)",
            5,
            len(lines),
            cause="4 entries in tracker",
            effect="CSV has 4 data rows + 1 header",
            lesson="Each entry must produce exactly one CSV row",
        )
        assert result

    def test_tt037_duration_decimal_hours(self):
        """TT-037: Duration column uses decimal hours (e.g. 1.5 for 5400s)."""
        t = TimeTracker()
        t.add_entry("u1", 5400)  # 1.5 hours
        _, _, _, exp = _make_services(t)
        entries = list(t._entries.values())
        csv_str = exp.export_to_csv(entries)
        data_line = csv_str.splitlines()[1]
        result = record(
            "TT-037",
            "Duration column == '1.5'",
            True,
            "1.5" in data_line,
            cause="Entry has duration_seconds=5400 (1.5 h)",
            effect="CSV row duration cell == '1.5'",
            lesson="Duration must be formatted as decimal hours",
        )
        assert result

    def test_tt038_excel_export_bytes(self):
        """TT-038: Excel export returns non-empty bytes."""
        t, _, _, exp = _make_services()
        entries = list(t._entries.values())
        data = exp.export_to_excel(entries)
        result = record(
            "TT-038",
            "Excel export returns bytes with len > 0",
            True,
            isinstance(data, bytes) and len(data) > 0,
            cause="export_to_excel called with 4 entries",
            effect="Non-empty bytes returned",
            lesson="Excel export must return valid bytes (xlsx or csv fallback)",
        )
        assert result
