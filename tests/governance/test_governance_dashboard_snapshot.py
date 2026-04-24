"""
Murphy System — Governance Dashboard Snapshot Tests
PROD-HARD-GOV-001: Rewritten to import MurphySystem directly from
src.runtime.murphy_system_core instead of exec_module()'ing the full
1.0 runtime wrapper, which triggers a transformers→squad.py import
chain that exceeds the 15s CI timeout.

Design intent: _build_governance_dashboard_snapshot() normalises
governance component statuses into a unified summary dict. These
tests verify that summary counts and normalized_status values are
correct across the "needs_wiring" and "ready" scenarios.
"""
import pytest
from src.runtime.murphy_system_core import MurphySystem


def test_governance_dashboard_snapshot_defaults():
    # PROD-HARD-GOV-001: uses direct import, not exec_module() of full runtime
    murphy = MurphySystem.create_test_instance()

    snapshot = murphy._build_governance_dashboard_snapshot(
        {"delivery_readiness": "needs_info"},
        [{"owner": "operations_director", "status": "pending", "description": "ops task"}],
        {"status": "needs_info", "compliance_status": "clear"},
        {"status": "pending_review"}
    )

    summary = snapshot["summary"]
    assert summary["total"] == 6
    assert summary["needs_wiring"] == 1
    assert snapshot["status"] == "needs_wiring"
    assert snapshot["components"]["operations"]["normalized_status"] == "pending"


def test_governance_dashboard_snapshot_ready():
    murphy = MurphySystem.create_test_instance()

    snapshot = murphy._build_governance_dashboard_snapshot(
        {"delivery_readiness": "ready"},
        [
            {"owner": "operations_director", "status": "ready", "description": "ops task"},
            {"owner": "quality_assurance", "status": "complete", "description": "qa task"}
        ],
        {"status": "ready", "compliance_status": "clear"},
        {"status": "clear"}
    )

    summary = snapshot["summary"]
    assert summary["ready"] == summary["total"]
    assert snapshot["status"] == "ready"


def test_governance_dashboard_snapshot_in_system_status():
    murphy = MurphySystem.create_test_instance()

    murphy.latest_activation_preview = {
        "executive_directive": {"delivery_readiness": "needs_info"},
        "operations_plan": [{"owner": "operations_director", "status": "pending"}],
        "delivery_readiness": {"status": "needs_info", "compliance_status": "clear"},
        "handoff_queue": {"status": "pending_review"}
    }

    status = murphy.get_system_status()

    governance = status["governance_dashboard"]
    assert governance["summary"]["total"] == 6
    assert governance["status"] == "needs_wiring"
    assert governance["components"]["hitl"]["normalized_status"] == "pending"
