# Copyright © 2020 Inoni Limited Liability Company
"""
Time Tracking – Settings & Billing API
========================================

Flask Blueprint with settings management and billing endpoints.

Routes
------
GET  /api/time/settings                       — current configuration
PUT  /api/time/settings                       — partial update
GET  /api/time/settings/validate              — validate + return warnings

GET  /api/time/billing/summary                — billable summary (all clients)
GET  /api/time/billing/summary/<client_id>    — billable summary for client
POST /api/time/billing/invoice                — generate invoice from entries
POST /api/time/billing/invoice/preview        — preview invoice (no creation)
GET  /api/time/billing/rates                  — list all client rates
PUT  /api/time/billing/rates/<client_id>      — set client rate
GET  /api/time/billing/audit-log              — billing audit log

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_settings_blueprint(
    billing_service=None,
    hook_manager=None,
    tt_config=None,
):
    """Build and return a Flask Blueprint for time tracking settings & billing.

    Parameters
    ----------
    billing_service:
        A :class:`~.billing_integration.BillingIntegrationService` instance.
        If ``None``, a default one is created.
    hook_manager:
        A :class:`~.invoicing_hooks.InvoicingHookManager` instance.
    tt_config:
        A :class:`~.config.TimeTrackingConfig` instance.
        If ``None``, the singleton is used.
    """
    try:
        from flask import Blueprint, jsonify, request
    except ImportError:
        raise ImportError("Flask is required for the settings API blueprint")

    from .billing_integration import BillingIntegrationService
    from .config import TimeTrackingConfig
    from .invoicing_hooks import InvoicingHookManager, TimeTrackingEvent

    if billing_service is None:
        billing_service = BillingIntegrationService()
    if hook_manager is None:
        hook_manager = InvoicingHookManager(billing_service=billing_service)
    if tt_config is None:
        tt_config = TimeTrackingConfig.get_config()

    bp = Blueprint("time_settings", __name__)

    # ── Settings ──────────────────────────────────────────────────────

    @bp.route("/api/time/settings", methods=["GET"])
    def get_settings():
        return jsonify(tt_config.to_dict())

    @bp.route("/api/time/settings", methods=["PUT"])
    def update_settings():
        body = request.get_json(silent=True) or {}
        if not body:
            return jsonify({"error": "JSON body required"}), 400
        try:
            updated = tt_config.update(body)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 422
        # Emit rate_changed if hourly rate was updated
        if "default_hourly_rate" in body:
            hook_manager.emit(
                TimeTrackingEvent.RATE_CHANGED,
                {"field": "default_hourly_rate", "new_value": body["default_hourly_rate"]},
            )
        return jsonify({"updated": updated, "settings": tt_config.to_dict()})

    @bp.route("/api/time/settings/validate", methods=["GET"])
    def validate_settings():
        warnings = tt_config.validate()
        return jsonify({"valid": len(warnings) == 0, "warnings": warnings})

    # ── Billing summary ───────────────────────────────────────────────

    @bp.route("/api/time/billing/summary", methods=["GET"])
    def billing_summary_all():
        return jsonify(billing_service.get_billable_summary())

    @bp.route("/api/time/billing/summary/<client_id>", methods=["GET"])
    def billing_summary_client(client_id: str):
        start = request.args.get("start", "")
        end = request.args.get("end", "")
        date_range = None
        if start or end:
            date_range = {"start": start, "end": end}
        return jsonify(
            billing_service.get_billable_summary(
                client_id=client_id, date_range=date_range
            )
        )

    # ── Invoice generation ────────────────────────────────────────────

    @bp.route("/api/time/billing/invoice", methods=["POST"])
    def generate_invoice():
        body = request.get_json(silent=True) or {}
        client_id = body.get("client_id", "")
        entry_ids = body.get("entry_ids", [])
        hourly_rate = body.get("hourly_rate")
        if not client_id or not entry_ids:
            return jsonify({"error": "client_id and entry_ids are required"}), 400
        try:
            result = billing_service.generate_invoice_from_entries(
                client_id=client_id,
                entry_ids=entry_ids,
                hourly_rate=hourly_rate,
            )
        except (ValueError, KeyError) as exc:
            return jsonify({"error": str(exc)}), 422
        # Emit hook
        hook_manager.emit(
            TimeTrackingEvent.INVOICE_GENERATED,
            {"invoice_id": result["invoice_id"], "client_id": client_id},
        )
        hook_manager.emit(
            TimeTrackingEvent.ENTRY_INVOICED,
            {"entry_ids": entry_ids, "invoice_id": result["invoice_id"]},
        )
        return jsonify(result), 201

    @bp.route("/api/time/billing/invoice/preview", methods=["POST"])
    def preview_invoice():
        body = request.get_json(silent=True) or {}
        entry_ids = body.get("entry_ids", [])
        client_id = body.get("client_id", "")
        hourly_rate = body.get("hourly_rate")
        if not entry_ids:
            return jsonify({"error": "entry_ids are required"}), 400
        try:
            result = billing_service.calculate_invoice_preview(
                entry_ids=entry_ids,
                client_id=client_id,
                hourly_rate=hourly_rate,
            )
        except KeyError as exc:
            return jsonify({"error": str(exc)}), 422
        return jsonify(result)

    # ── Client rates ──────────────────────────────────────────────────

    @bp.route("/api/time/billing/rates", methods=["GET"])
    def list_rates():
        return jsonify({"rates": billing_service.list_client_rates()})

    @bp.route("/api/time/billing/rates/<client_id>", methods=["PUT"])
    def set_client_rate(client_id: str):
        body = request.get_json(silent=True) or {}
        hourly_rate = body.get("hourly_rate")
        currency = body.get("currency", "USD")
        if hourly_rate is None:
            return jsonify({"error": "hourly_rate is required"}), 400
        try:
            result = billing_service.set_client_rate(
                client_id, float(hourly_rate), currency
            )
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 422
        # Emit hook
        hook_manager.emit(
            TimeTrackingEvent.RATE_CHANGED,
            {"client_id": client_id, "new_rate": hourly_rate, "currency": currency},
        )
        return jsonify(result)

    # ── Audit log ─────────────────────────────────────────────────────

    @bp.route("/api/time/billing/audit-log", methods=["GET"])
    def get_audit_log():
        try:
            limit = int(request.args.get("limit", 100))
        except ValueError:
            limit = 100
        return jsonify({"audit_log": hook_manager.get_audit_log(limit=limit)})

    return bp
