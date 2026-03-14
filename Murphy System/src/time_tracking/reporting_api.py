# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Reporting, Approvals & Export API
====================================================

Flask Blueprint exposing reporting, approval-workflow, and export endpoints.

Endpoints
---------
GET  /api/time/reports/user/<user_id>    — per-user report
GET  /api/time/reports/project/<proj_id> — per-project report
GET  /api/time/reports/range             — date-range report

POST /api/time/approvals/submit          — submit entries for approval
POST /api/time/approvals/approve         — approve entries
POST /api/time/approvals/reject          — reject entries
GET  /api/time/approvals/pending         — list pending approvals

GET  /api/time/export/csv                — download CSV
GET  /api/time/export/excel              — download Excel / CSV fallback

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from .approval_service import ApprovalError, ApprovalService
from .export_service import ExportService
from .models import EntryStatus, TimeEntry
from .reporting_service import ReportingService
from .tracker import TimeTracker

logger = logging.getLogger(__name__)


def create_reporting_blueprint(tracker: Optional[TimeTracker] = None):
    """Build and return a Flask Blueprint for reporting/approvals/export."""
    try:
        from flask import Blueprint, Response, jsonify, request
    except ImportError:
        raise ImportError("Flask is required for the reporting API blueprint")

    if tracker is None:
        tracker = TimeTracker()

    # Share the tracker's in-memory store with the new services so that
    # all services operate on the same set of entries.
    _lock = threading.Lock()

    # Wrap tracker entries dict with services
    reporting = ReportingService(tracker._entries, _lock)
    approval = ApprovalService(tracker._entries, _lock)
    export = ExportService()

    bp = Blueprint("time_reporting", __name__)

    # ── Reporting ─────────────────────────────────────────────────────

    @bp.route("/api/time/reports/user/<user_id>", methods=["GET"])
    def user_report(user_id: str):
        start = request.args.get("start_date", "")
        end = request.args.get("end_date", "")
        return jsonify(reporting.get_user_report(user_id, start, end))

    @bp.route("/api/time/reports/project/<project_id>", methods=["GET"])
    def project_report(project_id: str):
        start = request.args.get("start_date", "")
        end = request.args.get("end_date", "")
        return jsonify(reporting.get_project_report(project_id, start, end))

    @bp.route("/api/time/reports/range", methods=["GET"])
    def date_range_report():
        start = request.args.get("start_date", "")
        end = request.args.get("end_date", "")
        filters: Dict[str, Any] = {}
        if request.args.get("user_id"):
            filters["user_id"] = request.args["user_id"]
        if request.args.get("project_id"):
            filters["project_id"] = request.args["project_id"]
        if request.args.get("billable") is not None:
            filters["billable"] = request.args.get("billable", "").lower() == "true"
        return jsonify(reporting.get_date_range_report(start, end, filters))

    # ── Approvals ─────────────────────────────────────────────────────

    @bp.route("/api/time/approvals/submit", methods=["POST"])
    def submit_entries():
        body = request.get_json(silent=True) or {}
        user_id = body.get("user_id", "")
        entry_ids = body.get("entry_ids", [])
        if not user_id or not entry_ids:
            return jsonify({"error": "user_id and entry_ids are required"}), 400
        try:
            result = approval.submit_timesheet(user_id, entry_ids)
        except (ApprovalError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 422
        return jsonify({"submitted": result}), 200

    @bp.route("/api/time/approvals/approve", methods=["POST"])
    def approve_entries():
        body = request.get_json(silent=True) or {}
        approver_id = body.get("approver_id", "")
        entry_ids = body.get("entry_ids", [])
        if not approver_id or not entry_ids:
            return jsonify({"error": "approver_id and entry_ids are required"}), 400
        try:
            result = approval.approve_entries(approver_id, entry_ids)
        except (ApprovalError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 422
        return jsonify({"approved": result}), 200

    @bp.route("/api/time/approvals/reject", methods=["POST"])
    def reject_entries():
        body = request.get_json(silent=True) or {}
        approver_id = body.get("approver_id", "")
        entry_ids = body.get("entry_ids", [])
        reason = body.get("reason", "")
        if not approver_id or not entry_ids:
            return jsonify({"error": "approver_id and entry_ids are required"}), 400
        try:
            result = approval.reject_entries(approver_id, entry_ids, reason)
        except (ApprovalError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 422
        return jsonify({"rejected": result}), 200

    @bp.route("/api/time/approvals/pending", methods=["GET"])
    def pending_approvals():
        approver_id = request.args.get("approver_id")
        return jsonify({"pending": approval.get_pending_approvals(approver_id)})

    # ── Export ────────────────────────────────────────────────────────

    def _filtered_entries():
        """Return entries filtered by query params: user_id, project_id."""
        with _lock:
            entries = list(tracker._entries.values())
        uid = request.args.get("user_id", "")
        pid = request.args.get("project_id", "")
        if uid:
            entries = [e for e in entries if e.user_id == uid]
        if pid:
            entries = [e for e in entries if e.board_id == pid]
        return entries

    @bp.route("/api/time/export/csv", methods=["GET"])
    def export_csv():
        entries = _filtered_entries()
        csv_data = export.export_to_csv(entries)
        return Response(
            csv_data,
            status=200,
            mimetype="text/csv",
            headers={"Content-Disposition": 'attachment; filename="time_entries.csv"'},
        )

    @bp.route("/api/time/export/excel", methods=["GET"])
    def export_excel():
        entries = _filtered_entries()
        data = export.export_to_excel(entries)
        # Detect whether openpyxl was used (real XLSX) or CSV fallback
        from .export_service import _OPENPYXL_AVAILABLE
        if _OPENPYXL_AVAILABLE:
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "time_entries.xlsx"
        else:
            mimetype = "text/csv"
            filename = "time_entries.csv"
        return Response(
            data,
            status=200,
            mimetype=mimetype,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return bp
