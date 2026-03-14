# Copyright © 2020 Inoni Limited Liability Company
"""
Test Suite: Time Tracking – Dashboard Widgets, Summary Statistics & Team Views
================================================================================

Tests for Phase 6C: widget factory, summary statistics service, team view
service, and dashboard API blueprint.
IDs: TT-036 through TT-050.

Uses the storyline-actuals record() pattern consistent with other suites.

Copyright © 2020 Inoni Limited Liability Company
"""

from __future__ import annotations

import sys
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from time_tracking.models import EntryStatus, TimeEntry, _now
from time_tracking.tracker import TimeTracker
from time_tracking.dashboard_widgets import TimeTrackingWidgetFactory
from time_tracking.summary_statistics import SummaryStatisticsService
from time_tracking.team_views import TeamViewService

_UTC = timezone.utc

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

def _make_tracker() -> TimeTracker:
    """Return a tracker pre-populated with a representative set of entries."""
    t = TimeTracker()
    # user1, proj-A, billable
    t.add_entry("user1", 3600, board_id="proj-A", item_id="item-1", billable=True)
    t.add_entry("user1", 1800, board_id="proj-A", item_id="item-2", billable=False)
    # user1, proj-B, billable
    t.add_entry("user1", 7200, board_id="proj-B", item_id="item-3", billable=True)
    # user2, proj-A, billable
    t.add_entry("user2", 3600, board_id="proj-A", item_id="item-1", billable=True)
    # user3, proj-B, non-billable
    t.add_entry("user3", 1800, board_id="proj-B", item_id="item-4", billable=False)
    return t


def _make_factory(tracker: TimeTracker) -> TimeTrackingWidgetFactory:
    lock = threading.Lock()
    return TimeTrackingWidgetFactory(
        tracker._entries, lock, tracker._active_timers
    )


def _make_stats(tracker: TimeTracker) -> SummaryStatisticsService:
    lock = threading.Lock()
    return SummaryStatisticsService(
        tracker._entries, lock, tracker._active_timers
    )


def _make_team_service(tracker: TimeTracker) -> TeamViewService:
    lock = threading.Lock()
    return TeamViewService(
        tracker._entries, lock, tracker._active_timers
    )


# ── TT-036: hours_by_project widget ──────────────────────────────────


class TestHoursByProjectWidget:
    def test_tt036_widget_structure(self):
        """TT-036: hours_by_project widget has required keys and bar_chart type."""
        t = _make_tracker()
        factory = _make_factory(t)
        widget = factory.hours_by_project_widget()
        has_keys = all(
            k in widget for k in ("widget_type", "title", "description", "data", "settings")
        )
        result = record(
            "TT-036",
            "hours_by_project widget has all required keys and type == bar_chart",
            True,
            has_keys and widget["widget_type"] == "bar_chart",
            cause="hours_by_project_widget() called with no filters",
            effect="Returns dict with widget_type=bar_chart and all required keys",
            lesson="Widget factory must return structured dicts with correct widget_type",
        )
        assert result

    def test_tt036_data_includes_projects(self):
        """TT-036b: hours_by_project data lists all projects."""
        t = _make_tracker()
        factory = _make_factory(t)
        widget = factory.hours_by_project_widget()
        labels = widget["data"]["labels"]
        result = record(
            "TT-036b",
            "Both proj-A and proj-B appear in labels",
            True,
            "proj-A" in labels and "proj-B" in labels,
            cause="Entries span proj-A and proj-B",
            effect="Widget labels contain both project IDs",
            lesson="Widget factory must aggregate all projects",
        )
        assert result


# ── TT-037: billable_ratio widget ────────────────────────────────────


class TestBillableRatioWidget:
    def test_tt037_widget_type_and_keys(self):
        """TT-037: billable_ratio widget is a pie chart with correct keys."""
        t = _make_tracker()
        factory = _make_factory(t)
        widget = factory.billable_ratio_widget()
        result = record(
            "TT-037",
            "billable_ratio widget_type == pie_chart",
            "pie_chart",
            widget["widget_type"],
            cause="billable_ratio_widget() called",
            effect="widget_type is pie_chart",
            lesson="Billable ratio must be a pie chart",
        )
        assert result

    def test_tt037_billable_percentage_range(self):
        """TT-037b: billable_percentage is between 0 and 100."""
        t = _make_tracker()
        factory = _make_factory(t)
        widget = factory.billable_ratio_widget()
        pct = widget["data"]["billable_percentage"]
        result = record(
            "TT-037b",
            "billable_percentage is in [0, 100]",
            True,
            0.0 <= pct <= 100.0,
            cause="Entries have mix of billable and non-billable",
            effect="billable_percentage is valid percentage",
            lesson="Billable ratio must produce valid percentages",
        )
        assert result


# ── TT-038: weekly_summary widget ────────────────────────────────────


class TestWeeklySummaryWidget:
    def test_tt038_required_kpi_fields(self):
        """TT-038: weekly_summary widget includes all required KPI fields."""
        t = _make_tracker()
        factory = _make_factory(t)
        widget = factory.weekly_summary_widget(user_id="user1")
        required = {
            "total_hours",
            "billable_hours",
            "entries_count",
            "average_hours_per_day",
        }
        data_keys = set(widget["data"].keys())
        result = record(
            "TT-038",
            "weekly_summary data has all required KPI fields",
            True,
            required.issubset(data_keys),
            cause="weekly_summary_widget() called for user1",
            effect="data dict contains total_hours, billable_hours, entries_count, average_hours_per_day",
            lesson="Weekly summary widget must include all KPI fields",
        )
        assert result

    def test_tt038_widget_type_kpi(self):
        """TT-038b: weekly_summary widget type is kpi."""
        t = _make_tracker()
        factory = _make_factory(t)
        widget = factory.weekly_summary_widget()
        result = record(
            "TT-038b",
            "weekly_summary widget_type == kpi",
            "kpi",
            widget["widget_type"],
            cause="weekly_summary_widget() called",
            effect="widget_type is kpi",
            lesson="Weekly summary must be a KPI/numbers widget",
        )
        assert result


# ── TT-039: overdue_timers widget ────────────────────────────────────


class TestOverdueTimersWidget:
    def test_tt039_detects_overdue_timer(self):
        """TT-039: overdue_timers widget detects timers running longer than threshold."""
        t = TimeTracker()
        entry = TimeEntry(
            user_id="user1",
            board_id="proj-A",
            status=EntryStatus.RUNNING,
            started_at=(datetime.now(tz=_UTC) - timedelta(hours=9)).isoformat(),
        )
        t._entries[entry.id] = entry
        t._active_timers["user1"] = entry.id

        factory = _make_factory(t)
        widget = factory.overdue_timers_widget(threshold_hours=8.0)
        count = widget["data"]["count"]
        result = record(
            "TT-039",
            "overdue_timers widget detects 1 overdue timer",
            1,
            count,
            cause="Timer started 9 hours ago; threshold is 8 hours",
            effect="Overdue timers count == 1",
            lesson="overdue_timers_widget must detect long-running timers",
        )
        assert result

    def test_tt039_no_false_positives(self):
        """TT-039b: Non-overdue timers are not flagged."""
        t = TimeTracker()
        entry = TimeEntry(
            user_id="user1",
            status=EntryStatus.RUNNING,
            started_at=(datetime.now(tz=_UTC) - timedelta(hours=1)).isoformat(),
        )
        t._entries[entry.id] = entry
        t._active_timers["user1"] = entry.id

        factory = _make_factory(t)
        widget = factory.overdue_timers_widget(threshold_hours=8.0)
        result = record(
            "TT-039b",
            "Non-overdue timer is not flagged",
            0,
            widget["data"]["count"],
            cause="Timer started 1 hour ago; threshold is 8 hours",
            effect="Overdue count == 0",
            lesson="overdue_timers_widget must not flag short-running timers",
        )
        assert result


# ── TT-040: team_capacity widget ─────────────────────────────────────


class TestTeamCapacityWidget:
    def test_tt040_utilization_calculation(self):
        """TT-040: team_capacity widget calculates utilization correctly."""
        t = TimeTracker()
        # user1 logged 20 hours this week (target 40 → 50%)
        t.add_entry("user1", 20 * 3600, board_id="proj-A", billable=True)
        factory = _make_factory(t)
        widget = factory.team_capacity_widget(
            team_members=["user1"], target_hours_per_week=40.0
        )
        members = widget["data"]["members"]
        user1_data = next((m for m in members if m["user_id"] == "user1"), None)
        result = record(
            "TT-040",
            "user1 utilization_percentage == 50.0",
            True,
            user1_data is not None and user1_data["utilization_percentage"] == 50.0,
            cause="user1 logged 20h; target is 40h",
            effect="utilization_percentage == 50.0",
            lesson="team_capacity_widget must calculate utilization correctly",
        )
        assert result

    def test_tt040_widget_type_gauge(self):
        """TT-040b: team_capacity widget type is gauge."""
        t = _make_tracker()
        factory = _make_factory(t)
        widget = factory.team_capacity_widget(["user1", "user2"])
        result = record(
            "TT-040b",
            "team_capacity widget_type == gauge",
            "gauge",
            widget["widget_type"],
            cause="team_capacity_widget() called",
            effect="widget_type is gauge",
            lesson="Capacity widget must be a gauge type",
        )
        assert result


# ── TT-041: user summary ─────────────────────────────────────────────


class TestUserSummary:
    def test_tt041_required_fields(self):
        """TT-041: user summary returns all required fields."""
        t = _make_tracker()
        stats = _make_stats(t)
        summary = stats.get_user_summary("user1")
        required = {
            "user_id",
            "today_hours",
            "this_week_hours",
            "this_month_hours",
            "active_timers_count",
            "billable_percentage",
            "average_daily_hours",
            "most_active_project",
            "streak_days",
        }
        result = record(
            "TT-041",
            "user summary has all required fields",
            True,
            required.issubset(set(summary.keys())),
            cause="get_user_summary('user1') called",
            effect="Returns dict with all required stat fields",
            lesson="User summary must include all documented fields",
        )
        assert result

    def test_tt041_today_hours_non_negative(self):
        """TT-041b: today_hours is non-negative."""
        t = _make_tracker()
        stats = _make_stats(t)
        summary = stats.get_user_summary("user1")
        result = record(
            "TT-041b",
            "today_hours >= 0",
            True,
            summary["today_hours"] >= 0,
            cause="Entries may or may not have started today",
            effect="today_hours is non-negative",
            lesson="Summary stats must never return negative hours",
        )
        assert result

    def test_tt041_this_week_includes_today(self):
        """TT-041c: this_week_hours >= today_hours."""
        t = _make_tracker()
        stats = _make_stats(t)
        summary = stats.get_user_summary("user1")
        result = record(
            "TT-041c",
            "this_week_hours >= today_hours",
            True,
            summary["this_week_hours"] >= summary["today_hours"],
            cause="Week always contains today",
            effect="this_week_hours >= today_hours",
            lesson="Weekly hours must be >= daily hours",
        )
        assert result


# ── TT-042: team summary ─────────────────────────────────────────────


class TestTeamSummary:
    def test_tt042_aggregates_across_members(self):
        """TT-042: team summary aggregates hours across all members."""
        t = _make_tracker()
        stats = _make_stats(t)
        summary = stats.get_team_summary(["user1", "user2", "user3"])
        # All entries use current time, so they're all in this week
        total = summary["total_hours_this_week"]
        result = record(
            "TT-042",
            "team total_hours_this_week > 0",
            True,
            total > 0,
            cause="Tracker has entries for user1, user2, user3",
            effect="total_hours_this_week > 0",
            lesson="Team summary must aggregate across all members",
        )
        assert result

    def test_tt042_required_fields(self):
        """TT-042b: team summary includes all required fields."""
        t = _make_tracker()
        stats = _make_stats(t)
        summary = stats.get_team_summary(["user1", "user2"])
        required = {
            "total_hours_this_week",
            "average_per_member",
            "top_contributor",
            "least_active",
            "team_billable_percentage",
            "members_with_active_timers",
        }
        result = record(
            "TT-042b",
            "team summary has all required fields",
            True,
            required.issubset(set(summary.keys())),
            cause="get_team_summary() called",
            effect="Returns dict with all required fields",
            lesson="Team summary must include all documented fields",
        )
        assert result


# ── TT-043: project summary ──────────────────────────────────────────


class TestProjectSummary:
    def test_tt043_unique_contributors(self):
        """TT-043: project summary includes unique contributors count."""
        t = _make_tracker()
        stats = _make_stats(t)
        summary = stats.get_project_summary("proj-A")
        # user1 and user2 both logged time on proj-A
        result = record(
            "TT-043",
            "proj-A has 2 unique contributors",
            2,
            summary["unique_contributors"],
            cause="user1 and user2 both have entries on proj-A",
            effect="unique_contributors == 2",
            lesson="Project summary must count distinct users",
        )
        assert result

    def test_tt043_hours_trend_has_4_weeks(self):
        """TT-043b: hours_trend contains 4 weekly entries."""
        t = _make_tracker()
        stats = _make_stats(t)
        summary = stats.get_project_summary("proj-A")
        result = record(
            "TT-043b",
            "hours_trend has 4 entries",
            4,
            len(summary["hours_trend"]),
            cause="get_project_summary requests last 4 weeks",
            effect="hours_trend list has length 4",
            lesson="Project summary must include 4-week trend data",
        )
        assert result


# ── TT-044: system overview ──────────────────────────────────────────


class TestSystemOverview:
    def test_tt044_global_statistics(self):
        """TT-044: system overview returns global statistics."""
        t = _make_tracker()
        stats = _make_stats(t)
        overview = stats.get_system_overview()
        required = {
            "total_entries",
            "total_hours_all_time",
            "active_users_this_week",
            "active_projects_this_week",
            "global_billable_percentage",
        }
        result = record(
            "TT-044",
            "system overview has all required fields",
            True,
            required.issubset(set(overview.keys())),
            cause="get_system_overview() called",
            effect="Returns dict with all required global stats",
            lesson="System overview must return all documented fields",
        )
        assert result

    def test_tt044_total_entries_count(self):
        """TT-044b: total_entries matches actual entry count."""
        t = _make_tracker()
        stats = _make_stats(t)
        overview = stats.get_system_overview()
        result = record(
            "TT-044b",
            "total_entries == 5",
            5,
            overview["total_entries"],
            cause="Tracker has 5 completed entries",
            effect="total_entries == 5",
            lesson="System overview must count all entries",
        )
        assert result


# ── TT-045: team dashboard ──────────────────────────────────────────


class TestTeamDashboard:
    def test_tt045_combines_sub_views(self):
        """TT-045: team dashboard combines all sub-views."""
        t = _make_tracker()
        svc = _make_team_service(t)
        dashboard = svc.get_team_dashboard("mgr1", ["user1", "user2"])
        required = {
            "manager_id",
            "team_member_ids",
            "team_summary",
            "member_weekly_hours",
            "pending_approvals",
            "overdue_timers",
        }
        result = record(
            "TT-045",
            "team dashboard has all required sections",
            True,
            required.issubset(set(dashboard.keys())),
            cause="get_team_dashboard() called",
            effect="Returns dict with all required sub-view keys",
            lesson="Team dashboard must combine all sub-views",
        )
        assert result

    def test_tt045_manager_id_echoed(self):
        """TT-045b: manager_id is echoed back in result."""
        t = _make_tracker()
        svc = _make_team_service(t)
        dashboard = svc.get_team_dashboard("manager-X", ["user1"])
        result = record(
            "TT-045b",
            "manager_id == 'manager-X'",
            "manager-X",
            dashboard["manager_id"],
            cause="manager_id='manager-X' passed to get_team_dashboard",
            effect="dashboard['manager_id'] == 'manager-X'",
            lesson="Team dashboard must echo manager_id",
        )
        assert result


# ── TT-046: member detail view ───────────────────────────────────────


class TestMemberDetail:
    def test_tt046_returns_entries_and_breakdown(self):
        """TT-046: member detail returns entries and hours breakdown."""
        t = _make_tracker()
        svc = _make_team_service(t)
        detail = svc.get_member_detail("mgr1", "user1")
        has_entries = isinstance(detail.get("entries"), list)
        has_breakdown = "hours_by_project" in detail
        result = record(
            "TT-046",
            "member detail has entries list and hours_by_project breakdown",
            True,
            has_entries and has_breakdown,
            cause="get_member_detail('mgr1', 'user1') called",
            effect="Returns entries list and hours_by_project dict",
            lesson="Member detail must include entries and project breakdown",
        )
        assert result

    def test_tt046_approval_status_distribution(self):
        """TT-046b: member detail includes approval_status_distribution."""
        t = _make_tracker()
        svc = _make_team_service(t)
        detail = svc.get_member_detail("mgr1", "user1")
        result = record(
            "TT-046b",
            "member detail has approval_status_distribution",
            True,
            "approval_status_distribution" in detail,
            cause="get_member_detail called for user1",
            effect="approval_status_distribution key present",
            lesson="Member detail must include approval status breakdown",
        )
        assert result


# ── TT-047: utilization report ───────────────────────────────────────


class TestUtilizationReport:
    def test_tt047_over_flag(self):
        """TT-047: utilization report flags members over target correctly."""
        t = TimeTracker()
        # user1 logged 50 hours this week (target 40 → over)
        t.add_entry("user1", 50 * 3600, board_id="proj-A", billable=True)
        svc = _make_team_service(t)
        report = svc.get_utilization_report(["user1"], target_hours=40.0)
        user1 = next(
            (m for m in report["utilization"] if m["member_id"] == "user1"), None
        )
        result = record(
            "TT-047",
            "user1 over_under == 'over' when actual > target",
            "over",
            user1["over_under"] if user1 else None,
            cause="user1 logged 50h; target is 40h",
            effect="over_under == 'over'",
            lesson="Utilization report must flag members over target",
        )
        assert result

    def test_tt047_under_flag(self):
        """TT-047b: utilization report flags members under target correctly."""
        t = TimeTracker()
        t.add_entry("user2", 20 * 3600, board_id="proj-A", billable=True)
        svc = _make_team_service(t)
        report = svc.get_utilization_report(["user2"], target_hours=40.0)
        user2 = next(
            (m for m in report["utilization"] if m["member_id"] == "user2"), None
        )
        result = record(
            "TT-047b",
            "user2 over_under == 'under' when actual < target",
            "under",
            user2["over_under"] if user2 else None,
            cause="user2 logged 20h; target is 40h",
            effect="over_under == 'under'",
            lesson="Utilization report must flag members under target",
        )
        assert result


# ── TT-048: team comparison ──────────────────────────────────────────


class TestTeamComparison:
    def test_tt048_all_members_present(self):
        """TT-048: team comparison includes all members side-by-side."""
        t = _make_tracker()
        svc = _make_team_service(t)
        comparison = svc.get_team_comparison(["user1", "user2", "user3"])
        member_ids = [c["member_id"] for c in comparison["comparison"]]
        result = record(
            "TT-048",
            "comparison includes user1, user2, user3",
            True,
            all(u in member_ids for u in ["user1", "user2", "user3"]),
            cause="get_team_comparison called with 3 members",
            effect="comparison list contains all 3 member IDs",
            lesson="Team comparison must include all members",
        )
        assert result

    def test_tt048_required_per_member_fields(self):
        """TT-048b: each member entry has required comparison fields."""
        t = _make_tracker()
        svc = _make_team_service(t)
        comparison = svc.get_team_comparison(["user1", "user2"])
        required = {
            "member_id",
            "total_hours",
            "billable_percentage",
            "projects_worked_on",
            "entries_count",
        }
        all_have_fields = all(
            required.issubset(set(m.keys())) for m in comparison["comparison"]
        )
        result = record(
            "TT-048b",
            "each comparison entry has all required fields",
            True,
            all_have_fields,
            cause="get_team_comparison called",
            effect="Each member entry has required comparison fields",
            lesson="Team comparison must include all documented per-member fields",
        )
        assert result


# ── TT-049: dashboard API JSON responses ─────────────────────────────


class TestDashboardAPI:
    @pytest.fixture
    def client(self):
        """Flask test client for the dashboard API."""
        try:
            from flask import Flask
        except ImportError:
            pytest.skip("Flask not available")
        from time_tracking.dashboard_api import create_dashboard_blueprint

        t = _make_tracker()
        app = Flask(__name__)
        bp = create_dashboard_blueprint(t)
        app.register_blueprint(bp)
        app.config["TESTING"] = True
        return app.test_client()

    def test_tt049_hours_by_project_endpoint(self, client):
        """TT-049: GET /api/time/dashboard/widgets/hours_by_project returns JSON."""
        resp = client.get("/api/time/dashboard/widgets/hours_by_project")
        result = record(
            "TT-049",
            "hours_by_project endpoint returns HTTP 200",
            200,
            resp.status_code,
            cause="GET /api/time/dashboard/widgets/hours_by_project called",
            effect="HTTP 200 with JSON body",
            lesson="Dashboard API must return valid JSON for widget endpoints",
        )
        assert result
        data = resp.get_json()
        assert data is not None
        assert data["widget_type"] == "bar_chart"

    def test_tt049_weekly_summary_endpoint(self, client):
        """TT-049b: GET /api/time/dashboard/widgets/weekly_summary returns JSON."""
        resp = client.get("/api/time/dashboard/widgets/weekly_summary")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data
        assert "total_hours" in data["data"]

    def test_tt049_unknown_widget_returns_400(self, client):
        """TT-049c: Unknown widget type returns HTTP 400."""
        resp = client.get("/api/time/dashboard/widgets/unknown_type")
        assert resp.status_code == 400

    def test_tt049_user_summary_endpoint(self, client):
        """TT-049d: GET /api/time/dashboard/summary/user/<id> returns JSON."""
        resp = client.get("/api/time/dashboard/summary/user/user1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user_id"] == "user1"

    def test_tt049_system_overview_endpoint(self, client):
        """TT-049e: GET /api/time/dashboard/summary/system returns JSON."""
        resp = client.get("/api/time/dashboard/summary/system")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_entries" in data


# ── TT-050: team API access validation ───────────────────────────────


class TestTeamAPIAccess:
    @pytest.fixture
    def client_with_teams(self):
        """Flask test client with a manager→team mapping configured."""
        try:
            from flask import Flask
        except ImportError:
            pytest.skip("Flask not available")
        from time_tracking.dashboard_api import create_dashboard_blueprint
        from time_tracking.team_views import TeamViewService

        t = _make_tracker()
        lock = threading.Lock()
        # mgr1 only manages user1; user2 is unauthorized
        team_svc = TeamViewService(
            t._entries, lock, t._active_timers,
            manager_teams={"mgr1": ["user1"]}
        )
        # Build blueprint with a custom team service injected
        app = Flask(__name__)

        from time_tracking.dashboard_widgets import TimeTrackingWidgetFactory
        from time_tracking.summary_statistics import SummaryStatisticsService
        from flask import Blueprint, jsonify, request as flask_request

        bp = Blueprint("time_dashboard_test", __name__)
        factory = TimeTrackingWidgetFactory(t._entries, lock, t._active_timers)
        stats = SummaryStatisticsService(t._entries, lock, t._active_timers)

        @bp.route("/api/time/team/<manager_id>/dashboard")
        def team_dashboard(manager_id: str):
            members_param = flask_request.args.get("team_member_ids", "")
            members = [m.strip() for m in members_param.split(",") if m.strip()]
            try:
                result = team_svc.get_team_dashboard(manager_id, members)
            except PermissionError as exc:
                return jsonify({"error": str(exc)}), 403
            return jsonify(result)

        app.register_blueprint(bp)
        app.config["TESTING"] = True
        return app.test_client()

    def test_tt050_authorized_manager(self, client_with_teams):
        """TT-050: Authorized manager can access their team's dashboard."""
        resp = client_with_teams.get(
            "/api/time/team/mgr1/dashboard?team_member_ids=user1"
        )
        result = record(
            "TT-050",
            "Authorized manager gets HTTP 200",
            200,
            resp.status_code,
            cause="mgr1 managing user1 calls /team/mgr1/dashboard?team_member_ids=user1",
            effect="HTTP 200",
            lesson="Team API must allow authorized manager access",
        )
        assert result

    def test_tt050_unauthorized_member_returns_403(self, client_with_teams):
        """TT-050b: Manager accessing unauthorized member gets 403."""
        resp = client_with_teams.get(
            "/api/time/team/mgr1/dashboard?team_member_ids=user2"
        )
        result = record(
            "TT-050b",
            "Unauthorized member access returns HTTP 403",
            403,
            resp.status_code,
            cause="mgr1 does not manage user2",
            effect="HTTP 403 PermissionError",
            lesson="Team API must validate manager access",
        )
        assert result
