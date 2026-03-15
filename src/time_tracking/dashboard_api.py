# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Dashboard API
================================

Flask Blueprint exposing dashboard widget and summary statistics endpoints.

Endpoints
---------
GET  /api/time/dashboard/widgets/<widget_type>           — render a widget
GET  /api/time/dashboard/summary/user/<user_id>         — user summary
GET  /api/time/dashboard/summary/team                   — team summary
GET  /api/time/dashboard/summary/project/<project_id>   — project summary
GET  /api/time/dashboard/summary/system                 — system overview

GET  /api/time/team/<manager_id>/dashboard              — team dashboard
GET  /api/time/team/<manager_id>/member/<member_id>     — member detail
GET  /api/time/team/<manager_id>/utilization            — utilization report
GET  /api/time/team/<manager_id>/comparison             — team comparison

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .dashboard_widgets import TimeTrackingWidgetFactory
from .summary_statistics import SummaryStatisticsService
from .team_views import TeamViewService
from .tracker import TimeTracker

logger = logging.getLogger(__name__)

_WIDGET_TYPES = {
    "hours_by_project",
    "hours_by_user",
    "daily_hours",
    "billable_ratio",
    "weekly_summary",
    "overdue_timers",
    "team_capacity",
}


def create_dashboard_blueprint(tracker: Optional[TimeTracker] = None):
    """Build and return a Flask Blueprint for dashboard widgets and summaries."""
    try:
        from flask import Blueprint, jsonify, request
    except ImportError:
        raise ImportError("Flask is required for the dashboard API blueprint")

    if tracker is None:
        tracker = TimeTracker()

    _lock = threading.Lock()

    widget_factory = TimeTrackingWidgetFactory(
        tracker._entries, _lock, tracker._active_timers
    )
    stats_service = SummaryStatisticsService(
        tracker._entries, _lock, tracker._active_timers
    )
    team_service = TeamViewService(
        tracker._entries, _lock, tracker._active_timers
    )

    bp = Blueprint("time_dashboard", __name__)

    # ── Widget endpoints ──────────────────────────────────────────────

    @bp.route("/api/time/dashboard/widgets/<widget_type>", methods=["GET"])
    def get_widget(widget_type: str):
        if widget_type not in _WIDGET_TYPES:
            return jsonify(
                {"error": f"Unknown widget type: {widget_type!r}. "
                          f"Valid types: {sorted(_WIDGET_TYPES)}"}
            ), 400

        user_id = request.args.get("user_id") or None
        project_id = request.args.get("project_id") or None
        start = request.args.get("start") or None
        end = request.args.get("end") or None
        date_range: Optional[Dict[str, str]] = None
        if start or end:
            date_range = {}
            if start:
                date_range["start"] = start
            if end:
                date_range["end"] = end

        try:
            if widget_type == "hours_by_project":
                result = widget_factory.hours_by_project_widget(
                    user_id=user_id, date_range=date_range
                )
            elif widget_type == "hours_by_user":
                result = widget_factory.hours_by_user_widget(
                    project_id=project_id, date_range=date_range
                )
            elif widget_type == "daily_hours":
                days = int(request.args.get("days", 14))
                result = widget_factory.daily_hours_widget(
                    user_id=user_id, days=days
                )
            elif widget_type == "billable_ratio":
                result = widget_factory.billable_ratio_widget(
                    user_id=user_id, date_range=date_range
                )
            elif widget_type == "weekly_summary":
                result = widget_factory.weekly_summary_widget(user_id=user_id)
            elif widget_type == "overdue_timers":
                threshold = float(request.args.get("threshold_hours", 8.0))
                result = widget_factory.overdue_timers_widget(
                    threshold_hours=threshold
                )
            elif widget_type == "team_capacity":
                members_param = request.args.get("team_members", "")
                members = [m.strip() for m in members_param.split(",") if m.strip()]
                target = float(request.args.get("target_hours_per_week", 40.0))
                result = widget_factory.team_capacity_widget(
                    team_members=members,
                    target_hours_per_week=target,
                )
            else:
                return jsonify({"error": "Unhandled widget type"}), 500
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(result)

    # ── Summary endpoints ─────────────────────────────────────────────

    @bp.route("/api/time/dashboard/summary/user/<user_id>", methods=["GET"])
    def user_summary(user_id: str):
        return jsonify(stats_service.get_user_summary(user_id))

    @bp.route("/api/time/dashboard/summary/team", methods=["GET"])
    def team_summary():
        members_param = request.args.get("team_member_ids", "")
        members = [m.strip() for m in members_param.split(",") if m.strip()]
        if not members:
            return jsonify({"error": "team_member_ids query parameter is required"}), 400
        return jsonify(stats_service.get_team_summary(members))

    @bp.route("/api/time/dashboard/summary/project/<project_id>", methods=["GET"])
    def project_summary(project_id: str):
        return jsonify(stats_service.get_project_summary(project_id))

    @bp.route("/api/time/dashboard/summary/system", methods=["GET"])
    def system_overview():
        return jsonify(stats_service.get_system_overview())

    # ── Team / Manager endpoints ──────────────────────────────────────

    @bp.route("/api/time/team/<manager_id>/dashboard", methods=["GET"])
    def team_dashboard(manager_id: str):
        members_param = request.args.get("team_member_ids", "")
        members = [m.strip() for m in members_param.split(",") if m.strip()]
        if not members:
            return jsonify({"error": "team_member_ids query parameter is required"}), 400
        try:
            result = team_service.get_team_dashboard(manager_id, members)
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        return jsonify(result)

    @bp.route("/api/time/team/<manager_id>/member/<member_id>", methods=["GET"])
    def member_detail(manager_id: str, member_id: str):
        start = request.args.get("start") or None
        end = request.args.get("end") or None
        date_range: Optional[Dict[str, str]] = None
        if start or end:
            date_range = {}
            if start:
                date_range["start"] = start
            if end:
                date_range["end"] = end
        try:
            result = team_service.get_member_detail(
                manager_id, member_id, date_range=date_range
            )
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        return jsonify(result)

    @bp.route("/api/time/team/<manager_id>/utilization", methods=["GET"])
    def utilization_report(manager_id: str):
        members_param = request.args.get("team_member_ids", "")
        members = [m.strip() for m in members_param.split(",") if m.strip()]
        if not members:
            return jsonify({"error": "team_member_ids query parameter is required"}), 400
        target = float(request.args.get("target_hours", 40.0))
        start = request.args.get("start") or None
        end = request.args.get("end") or None
        date_range: Optional[Dict[str, str]] = None
        if start or end:
            date_range = {}
            if start:
                date_range["start"] = start
            if end:
                date_range["end"] = end
        try:
            result = team_service.get_utilization_report(
                members, target_hours=target, date_range=date_range
            )
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        return jsonify(result)

    @bp.route("/api/time/team/<manager_id>/comparison", methods=["GET"])
    def team_comparison(manager_id: str):
        members_param = request.args.get("team_member_ids", "")
        members = [m.strip() for m in members_param.split(",") if m.strip()]
        if not members:
            return jsonify({"error": "team_member_ids query parameter is required"}), 400
        start = request.args.get("start") or None
        end = request.args.get("end") or None
        date_range: Optional[Dict[str, str]] = None
        if start or end:
            date_range = {}
            if start:
                date_range["start"] = start
            if end:
                date_range["end"] = end
        try:
            result = team_service.get_team_comparison(
                members, date_range=date_range
            )
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        return jsonify(result)

    return bp
