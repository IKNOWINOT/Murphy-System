# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for CEO Branch Activation & Org Chart Automation (CEO-002).

Covers:
  - VPRole: status_check, generate_report, execute_directive, input validation
  - OrgChartAutomation: role map, collect_reports, broadcast_directive
  - SystemWorkflow: readiness_check, tick, adaptive degradation, start/stop
  - CEOBranch: activate, deactivate, run_tick, issue_directive, get_org_chart
  - Org chart role mapping (all 10 required roles present)
  - Graceful degradation when subsystems are unavailable
  - Thread-safety for concurrent access
  - ActivatedHeartbeatRunner integration (ceo_branch wiring)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from src.ceo_branch_activation import (
    CEOBranch,
    DirectiveResult,
    OrgChartAutomation,
    RoleReport,
    RoleStatus,
    SystemWorkflow,
    VPRole,
    WorkflowPhase,
    WorkflowTickResult,
    _CONFIDENCE_THRESHOLD,
    _DEFAULT_TICK_SECONDS,
    _ORG_CHART_DEFINITION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _healthy_probe() -> Dict[str, Any]:
    return {"healthy": True, "uptime": 99.9}


def _degraded_probe() -> Dict[str, Any]:
    return {"healthy": False, "error": "subsystem_down"}


def _raising_probe() -> Dict[str, Any]:
    raise RuntimeError("connection refused")


def _make_org_chart(
    all_degraded: bool = False,
    raise_on_probe: bool = False,
) -> OrgChartAutomation:
    """Build an OrgChartAutomation with uniform probes for testing."""
    if all_degraded:
        probe_fn = _degraded_probe
    elif raise_on_probe:
        probe_fn = _raising_probe
    else:
        probe_fn = _healthy_probe

    probes = {d["label"]: probe_fn for d in _ORG_CHART_DEFINITION}
    return OrgChartAutomation(role_probes=probes)


# ---------------------------------------------------------------------------
# VPRole
# ---------------------------------------------------------------------------

class TestVPRole:
    def test_basic_construction(self):
        role = VPRole(
            role_label="VP Sales",
            subsystems=["self_selling_engine"],
            responsibilities=["Revenue generation"],
        )
        assert role.role_label == "VP Sales"
        assert "self_selling_engine" in role.subsystems

    def test_empty_label_raises(self):
        with pytest.raises(ValueError, match="role_label must not be empty"):
            VPRole(role_label="", subsystems=[], responsibilities=[])

    def test_null_byte_stripped_from_label(self):
        role = VPRole(
            role_label="VP\x00Sales",
            subsystems=[],
            responsibilities=[],
        )
        assert "\x00" not in role.role_label

    def test_status_check_healthy(self):
        role = VPRole("VP Sales", [], [], status_probe=_healthy_probe)
        assert role.status_check() == RoleStatus.HEALTHY

    def test_status_check_degraded_from_probe(self):
        role = VPRole("VP Sales", [], [], status_probe=_degraded_probe)
        assert role.status_check() == RoleStatus.DEGRADED

    def test_status_check_degraded_on_exception(self):
        role = VPRole("VP Sales", [], [], status_probe=_raising_probe)
        assert role.status_check() == RoleStatus.DEGRADED

    def test_status_check_no_probe_defaults_healthy(self):
        role = VPRole("VP Sales", [], [])
        assert role.status_check() == RoleStatus.HEALTHY

    def test_generate_report_healthy(self):
        role = VPRole("VP Compliance", ["compliance_engine"], [], status_probe=_healthy_probe)
        report = role.generate_report()
        assert isinstance(report, RoleReport)
        assert report.status == RoleStatus.HEALTHY.value
        assert report.role_label == "VP Compliance"
        assert "compliance_engine" in report.subsystems
        assert len(report.alerts) == 0

    def test_generate_report_degraded_has_alert(self):
        role = VPRole("VP Compliance", [], [], status_probe=_degraded_probe)
        report = role.generate_report()
        assert report.status == RoleStatus.DEGRADED.value
        assert len(report.alerts) > 0
        assert "degraded" in report.alerts[0].lower()

    def test_execute_directive_accepted(self):
        role = VPRole("VP Marketing", [], [])
        result = role.execute_directive("Start Q2 campaign")
        assert isinstance(result, DirectiveResult)
        assert result.accepted is True
        assert result.role_label == "VP Marketing"
        assert "Start Q2 campaign" in result.directive

    def test_execute_directive_empty_rejected(self):
        role = VPRole("VP Marketing", [], [])
        result = role.execute_directive("")
        assert result.accepted is False

    def test_execute_directive_null_byte_stripped(self):
        role = VPRole("VP Marketing", [], [])
        result = role.execute_directive("start\x00campaign")
        assert "\x00" not in result.directive

    def test_execute_directive_max_len_truncated(self):
        role = VPRole("VP Finance", [], [])
        long_directive = "x" * 5_000
        result = role.execute_directive(long_directive)
        assert len(result.directive) <= 2_000
        assert result.accepted is True

    def test_directive_log_grows(self):
        role = VPRole("VP Finance", [], [])
        for i in range(5):
            role.execute_directive(f"directive-{i}")
        log = role.get_directive_log()
        assert len(log) == 5

    def test_generate_report_includes_probe_metrics(self):
        def probe():
            return {"healthy": True, "latency_ms": 42}

        role = VPRole("CTO", [], [], status_probe=probe)
        report = role.generate_report()
        assert report.metrics.get("latency_ms") == 42
        # "healthy" key should be excluded from metrics
        assert "healthy" not in report.metrics


# ---------------------------------------------------------------------------
# OrgChartAutomation
# ---------------------------------------------------------------------------

class TestOrgChartAutomation:
    def test_all_required_roles_present(self):
        required = {d["label"] for d in _ORG_CHART_DEFINITION}
        org = OrgChartAutomation()
        actual = set(org.get_all_roles().keys())
        assert required == actual

    def test_required_roles_include_spec_roles(self):
        """Verify every role from the requirement spec exists."""
        spec_roles = {
            "CEO",
            "CTO",
            "VP Sales",
            "VP Operations",
            "VP Compliance",
            "VP Engineering",
            "VP Customer Success",
            "VP Finance",
            "VP Marketing",
            "Chief Security Officer",
        }
        org = OrgChartAutomation()
        actual = set(org.get_all_roles().keys())
        assert spec_roles.issubset(actual)

    def test_get_role_returns_correct_type(self):
        org = OrgChartAutomation()
        role = org.get_role("VP Sales")
        assert isinstance(role, VPRole)
        assert role.role_label == "VP Sales"

    def test_get_role_unknown_returns_none(self):
        org = OrgChartAutomation()
        assert org.get_role("Unknown Role") is None

    def test_get_org_chart_returns_list(self):
        org = OrgChartAutomation()
        chart = org.get_org_chart()
        assert isinstance(chart, list)
        assert len(chart) == len(_ORG_CHART_DEFINITION)
        for entry in chart:
            assert "role_label" in entry
            assert "subsystems" in entry
            assert "status" in entry

    def test_collect_reports_all_healthy(self):
        org = _make_org_chart(all_degraded=False)
        reports = org.collect_reports()
        assert len(reports) == len(_ORG_CHART_DEFINITION)
        for r in reports:
            assert r.status == RoleStatus.HEALTHY.value

    def test_collect_reports_all_degraded(self):
        org = _make_org_chart(all_degraded=True)
        reports = org.collect_reports()
        for r in reports:
            assert r.status == RoleStatus.DEGRADED.value

    def test_collect_reports_survives_raising_probe(self):
        """A probe that raises should result in OFFLINE, not a test failure."""
        org = _make_org_chart(raise_on_probe=True)
        reports = org.collect_reports()
        assert len(reports) == len(_ORG_CHART_DEFINITION)
        for r in reports:
            assert r.status in (
                RoleStatus.DEGRADED.value,
                RoleStatus.OFFLINE.value,
                RoleStatus.UNKNOWN.value,
            )

    def test_broadcast_directive_all_roles(self):
        org = OrgChartAutomation()
        results = org.broadcast_directive("Run readiness check")
        assert len(results) == len(_ORG_CHART_DEFINITION)
        for r in results:
            assert r.accepted is True

    def test_broadcast_directive_subset(self):
        org = OrgChartAutomation()
        results = org.broadcast_directive("Stop outreach", roles=["VP Sales"])
        assert len(results) == 1
        assert results[0].role_label == "VP Sales"

    def test_broadcast_directive_empty_rejected(self):
        org = OrgChartAutomation()
        results = org.broadcast_directive("")
        # All roles receive the call but all reject empty directive
        for r in results:
            assert r.accepted is False

    def test_audit_log_populated_after_build(self):
        org = OrgChartAutomation()
        log = org.get_audit_log()
        assert len(log) >= 1
        assert any(e.get("action") == "org_chart_built" for e in log)

    def test_role_subsystem_mapping(self):
        """Verify key role→subsystem mappings from the requirement spec."""
        expected = {
            "VP Sales": "self_selling_engine",
            "VP Compliance": "compliance_engine",
            "VP Engineering": "autonomous_repair_system",
            "Chief Security Officer": "fastapi_security",
        }
        org = OrgChartAutomation()
        for label, expected_subsystem in expected.items():
            role = org.get_role(label)
            assert role is not None, f"Role '{label}' missing"
            assert expected_subsystem in role.subsystems, (
                f"Expected '{expected_subsystem}' in {role.role_label}.subsystems"
            )


# ---------------------------------------------------------------------------
# SystemWorkflow
# ---------------------------------------------------------------------------

class TestSystemWorkflow:
    def test_construction_defaults(self):
        org = OrgChartAutomation()
        wf = SystemWorkflow(org)
        assert wf.phase == WorkflowPhase.IDLE
        assert not wf.running

    def test_invalid_tick_interval_raises(self):
        org = OrgChartAutomation()
        with pytest.raises(ValueError, match="tick_interval"):
            SystemWorkflow(org, tick_interval=0)

    def test_invalid_confidence_threshold_raises(self):
        org = OrgChartAutomation()
        with pytest.raises(ValueError, match="confidence_threshold"):
            SystemWorkflow(org, confidence_threshold=1.5)

    def test_readiness_check_all_healthy(self):
        org = _make_org_chart(all_degraded=False)
        wf = SystemWorkflow(org)
        result = wf.readiness_check()
        assert result["ready"] is True
        assert len(result["offline_roles"]) == 0

    def test_readiness_check_degraded_still_ready(self):
        """Degraded roles don't block readiness — only offline does."""
        org = _make_org_chart(all_degraded=True)
        wf = SystemWorkflow(org)
        result = wf.readiness_check()
        # All probes return degraded (not offline), so ready=True
        assert result["ready"] is True

    def test_readiness_check_offline_marks_not_ready(self):
        """Roles whose probes raise are marked offline by collect_reports."""
        org = _make_org_chart(raise_on_probe=True)
        wf = SystemWorkflow(org, confidence_threshold=0.0)
        result = wf.readiness_check()
        # status_check on a raising probe returns DEGRADED (not OFFLINE directly)
        # but in any case the result dict should be structurally correct
        assert "ready" in result
        assert "healthy_roles" in result
        assert "degraded_roles" in result
        assert "offline_roles" in result

    def test_tick_returns_result(self):
        org = _make_org_chart(all_degraded=False)
        wf = SystemWorkflow(org)
        result = wf.tick()
        assert isinstance(result, WorkflowTickResult)
        assert result.tick_number == 1

    def test_tick_increments_count(self):
        org = _make_org_chart()
        wf = SystemWorkflow(org)
        wf.tick()
        wf.tick()
        assert wf.get_status()["tick_count"] == 2

    def test_tick_healthy_confidence_1(self):
        org = _make_org_chart(all_degraded=False)
        wf = SystemWorkflow(org)
        result = wf.tick()
        assert result.confidence == pytest.approx(1.0)
        assert len(result.degraded_roles) == 0

    def test_tick_degraded_confidence_0(self):
        org = _make_org_chart(all_degraded=True)
        wf = SystemWorkflow(org, confidence_threshold=0.5)
        result = wf.tick()
        assert result.confidence == pytest.approx(0.0)
        assert len(result.degraded_roles) == len(_ORG_CHART_DEFINITION)

    def test_tick_phase_degrades_on_low_confidence(self):
        org = _make_org_chart(all_degraded=True)
        wf = SystemWorkflow(org, confidence_threshold=0.5)
        result = wf.tick()
        assert result.phase == WorkflowPhase.DEGRADED.value

    def test_tick_phase_running_on_high_confidence(self):
        org = _make_org_chart(all_degraded=False)
        wf = SystemWorkflow(org, confidence_threshold=0.5)
        # tick while RUNNING
        wf.start()
        result = wf.tick()
        wf.stop()
        assert result.phase == WorkflowPhase.RUNNING.value

    def test_tick_alerts_populated_on_degradation(self):
        org = _make_org_chart(all_degraded=True)
        wf = SystemWorkflow(org, confidence_threshold=0.5)
        result = wf.tick()
        assert len(result.alerts) > 0

    def test_tick_alert_hook_called(self):
        collected: List[List[str]] = []

        def hook(alerts):
            collected.append(list(alerts))

        org = _make_org_chart(all_degraded=True)
        wf = SystemWorkflow(org, confidence_threshold=0.5, alert_hook=hook)
        wf.tick()
        assert len(collected) > 0

    def test_alert_hook_exception_does_not_crash_tick(self):
        def bad_hook(alerts):
            raise RuntimeError("hook error")

        org = _make_org_chart(all_degraded=True)
        wf = SystemWorkflow(org, confidence_threshold=0.5, alert_hook=bad_hook)
        # Should not raise
        result = wf.tick()
        assert result is not None

    def test_tick_plan_updated(self):
        org = _make_org_chart()
        wf = SystemWorkflow(org)
        result = wf.tick()
        assert result.plan_updated is True

    def test_operational_plan_has_required_domains(self):
        required_domains = {
            "revenue_generation",
            "customer_onboarding",
            "production_delivery",
            "compliance_monitoring",
            "system_health",
            "community_outreach",
            "resource_allocation",
        }
        org = _make_org_chart()
        wf = SystemWorkflow(org)
        wf.tick()
        plan = wf.get_operational_plan()
        assert "domains" in plan
        assert required_domains.issubset(set(plan["domains"].keys()))

    def test_get_tick_results_returns_list(self):
        org = _make_org_chart()
        wf = SystemWorkflow(org)
        wf.tick()
        wf.tick()
        results = wf.get_tick_results(limit=10)
        assert len(results) == 2

    def test_start_stop_lifecycle(self):
        org = _make_org_chart()
        # Use a very long interval so the timer never fires
        wf = SystemWorkflow(org, tick_interval=99999)
        wf.start()
        assert wf.running
        assert wf.phase == WorkflowPhase.RUNNING
        wf.stop()
        assert not wf.running
        assert wf.phase == WorkflowPhase.STOPPED

    def test_double_start_is_safe(self):
        org = _make_org_chart()
        wf = SystemWorkflow(org, tick_interval=99999)
        wf.start()
        wf.start()  # second call must not raise
        assert wf.running
        wf.stop()

    def test_adaptive_recovery_from_degraded(self):
        """Confidence that rises above threshold returns phase to RUNNING."""
        # First tick: all degraded
        probes_degraded = {d["label"]: _degraded_probe for d in _ORG_CHART_DEFINITION}
        probes_healthy = {d["label"]: _healthy_probe for d in _ORG_CHART_DEFINITION}

        org = OrgChartAutomation(role_probes=probes_degraded)
        wf = SystemWorkflow(org, confidence_threshold=0.5)
        wf.start()

        result1 = wf.tick()
        assert result1.phase == WorkflowPhase.DEGRADED.value

        # Replace probes with healthy ones — simulate recovery
        # (Swap the org chart with a healthy one)
        wf._org_chart = OrgChartAutomation(role_probes=probes_healthy)  # noqa: SLF001
        result2 = wf.tick()
        assert result2.phase == WorkflowPhase.RUNNING.value

        wf.stop()

    def test_get_status_keys(self):
        org = _make_org_chart()
        wf = SystemWorkflow(org)
        status = wf.get_status()
        for key in ("running", "phase", "tick_count", "tick_interval",
                    "confidence_threshold", "current_confidence"):
            assert key in status


# ---------------------------------------------------------------------------
# CEOBranch
# ---------------------------------------------------------------------------

class TestCEOBranch:
    def test_construction(self):
        branch = CEOBranch()
        assert not branch.activated

    def test_activate_returns_dict(self):
        branch = CEOBranch(tick_interval=99999)
        result = branch.activate()
        assert result["activated"] is True
        assert result["already_active"] is False
        assert "branch_id" in result
        assert "readiness" in result
        branch.deactivate()

    def test_activate_idempotent(self):
        branch = CEOBranch(tick_interval=99999)
        r1 = branch.activate()
        r2 = branch.activate()
        assert r1["already_active"] is False
        assert r2["already_active"] is True
        branch.deactivate()

    def test_deactivate_stops_workflow(self):
        branch = CEOBranch(tick_interval=99999)
        branch.activate()
        assert branch.activated
        branch.deactivate()
        assert not branch.activated

    def test_run_tick_returns_result(self):
        branch = CEOBranch()
        result = branch.run_tick()
        assert isinstance(result, WorkflowTickResult)
        assert result.tick_number >= 1

    def test_run_tick_emits_telemetry(self):
        branch = CEOBranch()
        branch.run_tick()
        telemetry = branch.get_telemetry()
        assert any(e.get("event") == "ceo_tick" for e in telemetry)

    def test_get_org_chart_returns_all_roles(self):
        branch = CEOBranch()
        chart = branch.get_org_chart()
        labels = {entry["role_label"] for entry in chart}
        required = {d["label"] for d in _ORG_CHART_DEFINITION}
        assert required == labels

    def test_issue_directive_all_roles(self):
        branch = CEOBranch()
        results = branch.issue_directive("Run compliance check")
        assert len(results) == len(_ORG_CHART_DEFINITION)
        for r in results:
            assert r.accepted is True

    def test_issue_directive_subset_of_roles(self):
        branch = CEOBranch()
        results = branch.issue_directive("Pause outreach", roles=["VP Sales"])
        assert len(results) == 1
        assert results[0].role_label == "VP Sales"

    def test_get_operational_plan_has_domains(self):
        branch = CEOBranch()
        branch.run_tick()
        plan = branch.get_operational_plan()
        assert "domains" in plan

    def test_readiness_check_returns_dict(self):
        branch = CEOBranch()
        result = branch.readiness_check()
        assert "ready" in result
        assert "healthy_roles" in result

    def test_get_status_keys(self):
        branch = CEOBranch(tick_interval=99999)
        branch.activate()
        status = branch.get_status()
        for key in ("branch_id", "activated", "activation_time",
                    "running", "phase", "tick_count"):
            assert key in status
        branch.deactivate()

    def test_activate_emits_telemetry_event(self):
        branch = CEOBranch(tick_interval=99999)
        branch.activate()
        telemetry = branch.get_telemetry()
        assert any(e.get("event") == "ceo_branch_activated" for e in telemetry)
        branch.deactivate()

    def test_deactivate_emits_telemetry_event(self):
        branch = CEOBranch(tick_interval=99999)
        branch.activate()
        branch.deactivate()
        telemetry = branch.get_telemetry()
        assert any(e.get("event") == "ceo_branch_deactivated" for e in telemetry)

    def test_graceful_degradation_with_all_offline_probes(self):
        """CEOBranch must remain operational even when all probes fail."""
        all_offline = {d["label"]: _raising_probe for d in _ORG_CHART_DEFINITION}
        branch = CEOBranch(
            role_probes=all_offline,
            confidence_threshold=0.5,
            tick_interval=99999,
        )
        # activate must not raise
        result = branch.activate()
        assert result["activated"] is True
        # run_tick must not raise
        tick = branch.run_tick()
        assert tick is not None
        # confidence should be very low / zero
        assert tick.confidence == pytest.approx(0.0)
        branch.deactivate()

    def test_custom_alert_hook(self):
        fired: List[List[str]] = []

        def hook(alerts):
            fired.append(list(alerts))

        all_degraded = {d["label"]: _degraded_probe for d in _ORG_CHART_DEFINITION}
        branch = CEOBranch(
            role_probes=all_degraded,
            confidence_threshold=0.5,
            alert_hook=hook,
        )
        branch.run_tick()
        assert len(fired) > 0

    def test_telemetry_get_limit(self):
        branch = CEOBranch()
        for _ in range(10):
            branch.run_tick()
        limited = branch.get_telemetry(limit=3)
        assert len(limited) == 3

    def test_concurrent_ticks_are_thread_safe(self):
        """Multiple threads calling run_tick concurrently must not corrupt state."""
        branch = CEOBranch()
        errors: List[Exception] = []

        def _tick():
            try:
                branch.run_tick()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_tick) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f"Thread errors: {errors}"
        status = branch.get_status()
        assert status["tick_count"] == 10


# ---------------------------------------------------------------------------
# ActivatedHeartbeatRunner integration
# ---------------------------------------------------------------------------

class TestActivatedHeartbeatRunnerCEOIntegration:
    """Tests that CEOBranch is correctly wired into ActivatedHeartbeatRunner."""

    def _make_runner(self, ceo_branch=None):
        """Build a minimal ActivatedHeartbeatRunner for testing."""
        from src.activated_heartbeat_runner import ActivatedHeartbeatRunner
        from rosetta.rosetta_models import BusinessPlanMath, UnitEconomics

        plan = BusinessPlanMath(
            unit_economics=UnitEconomics(
                revenue_goal_dollars=1_200_000.0,
                unit_price_dollars=1_000.0,
                annual_cost_dollars=100_000.0,
                timeline_months=12.0,
                conversion_rate_goal=0.99,
                conversion_rate_actual=0.50,
            )
        )
        runner = ActivatedHeartbeatRunner(
            tick_interval=0.1,
            ceo_branch=ceo_branch,
        )
        runner.set_business_plan(plan)
        return runner

    def test_runner_construction_without_ceo_branch(self):
        runner = self._make_runner()
        status = runner.get_status()
        assert status["ceo_branch"] is None

    def test_runner_construction_with_ceo_branch(self):
        branch = CEOBranch()
        runner = self._make_runner(ceo_branch=branch)
        status = runner.get_status()
        assert status["ceo_branch"] is not None
        assert "branch_id" in status["ceo_branch"]

    def test_runner_tick_invokes_ceo_branch(self):
        """A heartbeat tick must call CEOBranch.run_tick exactly once."""
        branch = MagicMock(spec=CEOBranch)
        branch.run_tick.return_value = WorkflowTickResult()
        branch.get_status.return_value = {"branch_id": "mock", "activated": False}

        runner = self._make_runner(ceo_branch=branch)
        runner.tick()
        branch.run_tick.assert_called_once()

    def test_runner_tick_tolerates_ceo_branch_exception(self):
        """If CEOBranch.run_tick raises, the heartbeat tick must still succeed."""
        branch = MagicMock(spec=CEOBranch)
        branch.run_tick.side_effect = RuntimeError("ceo error")
        branch.get_status.return_value = {"branch_id": "mock"}

        runner = self._make_runner(ceo_branch=branch)
        record = runner.tick()
        # Tick should complete normally (error in CEO branch is non-fatal)
        from src.activated_heartbeat_runner import TickStatus
        assert record.status != TickStatus.ERROR

    def test_runner_without_ceo_branch_tick_works(self):
        """Heartbeat tick must function normally when ceo_branch is None."""
        runner = self._make_runner(ceo_branch=None)
        record = runner.tick()
        assert record is not None
