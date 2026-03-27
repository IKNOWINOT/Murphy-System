# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for CopilotTenant (tenant_agent.py).

Validates:
  - Agent starts in OBSERVER mode
  - Mode transitions (observer → suggestion → supervised → autonomous)
  - Operations cycle runs correctly
  - Emergency stop halts all operations
  - Status reporting
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from copilot_tenant.tenant_agent import CopilotTenant, CopilotTenantMode


class TestCopilotTenantInit:
    def test_starts_in_observer_mode(self) -> None:
        tenant = CopilotTenant()
        assert tenant.get_mode() == CopilotTenantMode.OBSERVER

    def test_default_founder_email(self) -> None:
        tenant = CopilotTenant()
        assert tenant._founder_email == "cpost@murphy.systems"

    def test_custom_founder_email(self) -> None:
        tenant = CopilotTenant(founder_email="cpost@murphy.systems")
        assert tenant._founder_email == "cpost@murphy.systems"


class TestModeTransitions:
    def test_set_mode_suggestion(self) -> None:
        tenant = CopilotTenant()
        tenant.set_mode(CopilotTenantMode.SUGGESTION)
        assert tenant.get_mode() == CopilotTenantMode.SUGGESTION

    def test_set_mode_supervised(self) -> None:
        tenant = CopilotTenant()
        tenant.set_mode(CopilotTenantMode.SUPERVISED)
        assert tenant.get_mode() == CopilotTenantMode.SUPERVISED

    def test_set_mode_autonomous(self) -> None:
        tenant = CopilotTenant()
        tenant.set_mode(CopilotTenantMode.AUTONOMOUS)
        assert tenant.get_mode() == CopilotTenantMode.AUTONOMOUS

    def test_full_progression(self) -> None:
        tenant = CopilotTenant()
        progression = [
            CopilotTenantMode.OBSERVER,
            CopilotTenantMode.SUGGESTION,
            CopilotTenantMode.SUPERVISED,
            CopilotTenantMode.AUTONOMOUS,
        ]
        for mode in progression:
            tenant.set_mode(mode)
            assert tenant.get_mode() == mode


class TestOperationsCycle:
    def test_run_cycle_returns_dict(self) -> None:
        tenant = CopilotTenant()
        result = tenant.run_cycle()
        assert isinstance(result, dict)

    def test_run_cycle_increments_cycles_run(self) -> None:
        tenant = CopilotTenant()
        tenant.run_cycle()
        assert tenant.get_status()["cycles_run"] == 1

    def test_run_cycle_contains_expected_keys(self) -> None:
        tenant = CopilotTenant()
        result = tenant.run_cycle()
        for key in ("cycle_id", "mode", "started_at", "ended_at", "task_count"):
            assert key in result, f"Missing key: {key}"

    def test_cycle_mode_matches_tenant_mode(self) -> None:
        tenant = CopilotTenant()
        tenant.set_mode(CopilotTenantMode.SUGGESTION)
        result = tenant.run_cycle()
        assert result["mode"] == CopilotTenantMode.SUGGESTION.value


class TestEmergencyStop:
    def test_emergency_stop_blocks_execution(self) -> None:
        tenant = CopilotTenant()
        tenant.set_mode(CopilotTenantMode.AUTONOMOUS)
        tenant._gateway.emergency_stop()
        # After emergency stop, gateway should block executions
        from copilot_tenant.task_planner import PlannedTask
        task   = PlannedTask(description="do something")
        result = tenant._gateway.execute(task, CopilotTenantMode.AUTONOMOUS)
        assert result.status == "blocked"
        assert result.blocked_reason == "emergency_stop_active"

    def test_emergency_stop_resets(self) -> None:
        tenant = CopilotTenant()
        tenant._gateway.emergency_stop()
        tenant._gateway.reset_emergency_stop()
        assert not tenant._gateway._emergency_active


class TestStatus:
    def test_status_has_required_keys(self) -> None:
        tenant = CopilotTenant()
        status = tenant.get_status()
        for key in ("founder_email", "mode", "running", "cycles_run",
                    "accuracy_metrics", "corpus_size", "graduation_report"):
            assert key in status, f"Missing key: {key}"

    def test_status_not_running_before_start(self) -> None:
        tenant = CopilotTenant()
        assert tenant.get_status()["running"] is False


class TestLifecycle:
    def test_start_sets_running(self) -> None:
        tenant = CopilotTenant()
        tenant.start()
        try:
            assert tenant.get_status()["running"] is True
        finally:
            tenant.stop()

    def test_stop_clears_running(self) -> None:
        tenant = CopilotTenant()
        tenant.start()
        tenant.stop()
        assert tenant.get_status()["running"] is False

    def test_double_start_is_safe(self) -> None:
        tenant = CopilotTenant()
        tenant.start()
        try:
            tenant.start()  # should not raise
        finally:
            tenant.stop()
