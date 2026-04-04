# Copyright (c) 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Rosetta ↔ CEO Branch Integration Tests
=======================================

Tests for the five gap-closure wiring points that connect the Rosetta
state management system to the CEO Branch org-chart agent system:

  P0 — Gap 2: Load personas into Rosetta at CEO startup
  P1 — Gap 1: Give VP roles access to their Rosetta state
  P2 — Gap 3: Write RoleReports back to Rosetta
  P3 — Gap 5: Route CEO directives through Platform Manager
  P4 — Gap 4: Register heartbeat tier translators

All tests use real instances — no unittest.mock.  Follows the project
convention of zero-mock testing with monkey-patching + try/finally.

Design Label: INT-ROSETTA-CEO — Rosetta ↔ CEO Integration Tests
Owner: Platform Engineering / State Management
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import unittest
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from ceo_branch_activation import (
    CEOBranch,
    OrgChartAutomation,
    RoleReport,
    RoleStatus,
    SystemWorkflow,
    VPRole,
    WorkflowPhase,
    WorkflowTickResult,
    _ORG_CHART_DEFINITION,
)
from rosetta.rosetta_manager import RosettaManager
from rosetta.rosetta_models import (
    AgentState,
    Goal,
    GoalStatus,
    Identity,
    RosettaAgentState,
    SystemState,
    Task,
    TaskStatus,
)
from rosetta_platform_state import RosettaPlatformManager
from rosetta_stone_heartbeat import (
    OrganizationTier,
    RosettaStoneHeartbeat,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _healthy_probe() -> Dict[str, Any]:
    return {"healthy": True, "metric_a": 42}


def _degraded_probe() -> Dict[str, Any]:
    return {"healthy": False, "metric_a": 0}


def _make_rosetta_manager(tmp_dir: str) -> RosettaManager:
    """Create a RosettaManager backed by a temp directory."""
    return RosettaManager(persistence_dir=os.path.join(tmp_dir, "rosetta"))


def _make_state(agent_id: str, name: str = "", role: str = "") -> RosettaAgentState:
    """Build a minimal RosettaAgentState."""
    return RosettaAgentState(
        identity=Identity(
            agent_id=agent_id,
            name=name or agent_id,
            role=role or agent_id,
            version="1.0.0",
            organization="murphy-system",
        ),
        system_state=SystemState(status="active"),
        agent_state=AgentState(current_phase="production"),
    )


# ===========================================================================
# P0 — Gap 2: Load personas into Rosetta at CEO startup
# ===========================================================================

class TestP0PersonaLoading(unittest.TestCase):
    """P0: CEOBranch.activate() seeds Rosetta state for every VP role."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.mgr = _make_rosetta_manager(self._tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_activate_creates_rosetta_state_for_all_roles(self) -> None:
        """Every role in _ORG_CHART_DEFINITION gets a Rosetta state doc."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        result = branch.activate()
        branch.deactivate()

        self.assertTrue(result["activated"])
        self.assertEqual(result["personas_loaded"], len(_ORG_CHART_DEFINITION))

        # Verify each role has state
        all_roles = branch._org_chart.get_all_roles()
        for role in all_roles.values():
            state = self.mgr.load_state(role.agent_id)
            self.assertIsNotNone(state, f"Missing Rosetta state for {role.role_label}")
            self.assertEqual(state.identity.name, role.role_label)
            self.assertEqual(state.identity.organization, "murphy-system")

    def test_activate_is_idempotent(self) -> None:
        """Second activate does not duplicate Rosetta state documents."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        r1 = branch.activate()
        branch.deactivate()

        # Pre-existing state — reactivate
        branch2 = CEOBranch(rosetta_manager=self.mgr)
        r2 = branch2.activate()
        branch2.deactivate()

        # Same count, states not duplicated
        self.assertEqual(r1["personas_loaded"], r2["personas_loaded"])
        agents = self.mgr.list_agents()
        unique_agents = set(agents)
        self.assertEqual(len(agents), len(unique_agents))

    def test_activate_without_rosetta_manager_succeeds(self) -> None:
        """Activation works even without rosetta_manager (graceful degradation)."""
        branch = CEOBranch()
        result = branch.activate()
        branch.deactivate()

        self.assertTrue(result["activated"])
        self.assertEqual(result["personas_loaded"], 0)

    def test_persona_identity_fields_correct(self) -> None:
        """Each seeded state has correct identity fields from the org chart."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        branch.activate()
        branch.deactivate()

        ceo_role = branch._org_chart.get_role("CEO")
        self.assertIsNotNone(ceo_role)
        state = self.mgr.load_state(ceo_role.agent_id)
        self.assertIsNotNone(state)
        self.assertEqual(state.identity.role, "CEO")
        self.assertEqual(state.system_state.status, "idle")
        self.assertEqual(state.agent_state.current_phase, "onboarding")

    def test_persona_seed_count_matches_org_chart(self) -> None:
        """Exact match between org chart roles and seeded personas."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        result = branch.activate()
        branch.deactivate()

        expected = len(_ORG_CHART_DEFINITION)
        self.assertEqual(result["personas_loaded"], expected)
        self.assertEqual(len(self.mgr.list_agents()), expected)


# ===========================================================================
# P1 — Gap 1: Give VP roles access to their Rosetta state
# ===========================================================================

class TestP1VPRosettaAccess(unittest.TestCase):
    """P1: VP roles can read their own Rosetta state document."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.mgr = _make_rosetta_manager(self._tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_vp_role_has_agent_id(self) -> None:
        """VPRole derives agent_id from role_label."""
        role = VPRole(
            role_label="VP Sales",
            subsystems=["self_selling_engine"],
            responsibilities=["Revenue"],
        )
        self.assertEqual(role.agent_id, "vp_sales")

    def test_vp_role_custom_agent_id(self) -> None:
        """VPRole accepts explicit agent_id."""
        role = VPRole(
            role_label="VP Sales",
            subsystems=[],
            responsibilities=[],
            agent_id="custom-sales-agent",
        )
        self.assertEqual(role.agent_id, "custom-sales-agent")

    def test_rosetta_state_returns_none_without_manager(self) -> None:
        """No rosetta_manager → rosetta_state returns None."""
        role = VPRole(
            role_label="VP Sales",
            subsystems=[],
            responsibilities=[],
        )
        self.assertIsNone(role.rosetta_state)

    def test_rosetta_state_returns_none_when_not_seeded(self) -> None:
        """Manager present but no state saved → returns None."""
        role = VPRole(
            role_label="VP Sales",
            subsystems=[],
            responsibilities=[],
            rosetta_manager=self.mgr,
        )
        self.assertIsNone(role.rosetta_state)

    def test_rosetta_state_returns_dict_when_seeded(self) -> None:
        """After seeding state, rosetta_state returns a dict."""
        state = _make_state("vp_sales", name="VP Sales", role="VP Sales")
        self.mgr.save_state(state)

        role = VPRole(
            role_label="VP Sales",
            subsystems=[],
            responsibilities=[],
            rosetta_manager=self.mgr,
        )
        rs = role.rosetta_state
        self.assertIsNotNone(rs)
        self.assertIsInstance(rs, dict)
        self.assertEqual(rs["identity"]["agent_id"], "vp_sales")

    def test_generate_report_includes_rosetta_context(self) -> None:
        """When Rosetta state exists, generate_report includes rosetta_* metrics."""
        state = _make_state("vp_sales", name="VP Sales", role="VP Sales")
        state.agent_state.active_goals.append(
            Goal(goal_id="g1", title="Sell more", status=GoalStatus.IN_PROGRESS, priority=1)
        )
        state.agent_state.task_queue.append(
            Task(task_id="t1", goal_id="g1", title="Call prospects", status=TaskStatus.QUEUED)
        )
        self.mgr.save_state(state)

        role = VPRole(
            role_label="VP Sales",
            subsystems=["self_selling_engine"],
            responsibilities=["Revenue"],
            rosetta_manager=self.mgr,
        )
        report = role.generate_report()
        self.assertEqual(report.metrics.get("rosetta_goals"), 1)
        self.assertEqual(report.metrics.get("rosetta_tasks"), 1)
        self.assertEqual(report.metrics.get("rosetta_agent_id"), "vp_sales")

    def test_generate_report_works_without_rosetta(self) -> None:
        """Report generation still works without rosetta_manager."""
        role = VPRole(
            role_label="CTO",
            subsystems=["code_repair_engine"],
            responsibilities=["Tech"],
        )
        report = role.generate_report()
        self.assertNotIn("rosetta_goals", report.metrics)
        self.assertEqual(report.role_label, "CTO")

    def test_org_chart_passes_rosetta_to_roles(self) -> None:
        """OrgChartAutomation passes rosetta_manager to all VP roles."""
        chart = OrgChartAutomation(rosetta_manager=self.mgr)
        for role in chart.get_all_roles().values():
            self.assertIs(role._rosetta_manager, self.mgr)


# ===========================================================================
# P2 — Gap 3: Write RoleReports back to Rosetta
# ===========================================================================

class TestP2ReportWriteBack(unittest.TestCase):
    """P2: SystemWorkflow.tick() persists role reports to Rosetta."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.mgr = _make_rosetta_manager(self._tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_tick_writes_reports_to_rosetta(self) -> None:
        """After a tick, each role's Rosetta state has report data."""
        # Seed initial states
        chart = OrgChartAutomation(rosetta_manager=self.mgr)
        for role in chart.get_all_roles().values():
            state = _make_state(role.agent_id, role.role_label, role.role_label)
            self.mgr.save_state(state)

        workflow = SystemWorkflow(
            org_chart=chart,
            rosetta_manager=self.mgr,
        )
        result = workflow.tick()
        self.assertGreater(result.tick_number, 0)

        # Verify at least one role had its report written back
        roles_with_reports = 0
        for role in chart.get_all_roles().values():
            state = self.mgr.load_state(role.agent_id)
            if state is not None:
                # Report write-back stores data in automation_progress
                # and metadata.extras
                if len(state.automation_progress) > 0:
                    roles_with_reports += 1
                extras = state.metadata.extras
                if extras.get("last_report"):
                    roles_with_reports += 1
        self.assertGreater(roles_with_reports, 0)

    def test_tick_updates_system_state_status(self) -> None:
        """Report write-back updates system_state.status based on role health."""
        chart = OrgChartAutomation(
            role_probes={"CEO": _healthy_probe},
            rosetta_manager=self.mgr,
        )
        # Seed CEO state
        ceo_role = chart.get_role("CEO")
        state = _make_state(ceo_role.agent_id, "CEO", "CEO")
        self.mgr.save_state(state)

        workflow = SystemWorkflow(org_chart=chart, rosetta_manager=self.mgr)
        workflow.tick()

        # CEO should have "active" status (healthy probe)
        updated = self.mgr.load_state(ceo_role.agent_id)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.system_state.status, "active")

    def test_tick_without_rosetta_manager_is_safe(self) -> None:
        """Tick runs cleanly without rosetta_manager."""
        chart = OrgChartAutomation()
        workflow = SystemWorkflow(org_chart=chart)
        result = workflow.tick()
        self.assertGreater(result.tick_number, 0)

    def test_report_writeback_records_tick_number(self) -> None:
        """metadata.extras.last_tick is set from the tick number."""
        chart = OrgChartAutomation(rosetta_manager=self.mgr)
        for role in chart.get_all_roles().values():
            self.mgr.save_state(
                _make_state(role.agent_id, role.role_label, role.role_label)
            )
        workflow = SystemWorkflow(org_chart=chart, rosetta_manager=self.mgr)
        workflow.tick()

        # Pick any role and check metadata.extras
        some_role = list(chart.get_all_roles().values())[0]
        state = self.mgr.load_state(some_role.agent_id)
        self.assertIsNotNone(state)
        self.assertIn("last_tick", state.metadata.extras)
        self.assertEqual(state.metadata.extras["last_tick"], 1)


# ===========================================================================
# P3 — Gap 5: Route CEO directives through Platform Manager
# ===========================================================================

class TestP3DirectiveRouting(unittest.TestCase):
    """P3: CEO directives are routed through RosettaPlatformManager."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.mgr = _make_rosetta_manager(self._tmp)
        self.platform = RosettaPlatformManager(rosetta_manager=self.mgr)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_directive_updates_platform_state(self) -> None:
        """issue_directive records in platform manager."""
        branch = CEOBranch(
            rosetta_manager=self.mgr,
            platform_manager=self.platform,
        )
        branch.activate()
        results = branch.issue_directive("Focus on revenue growth")
        branch.deactivate()

        self.assertGreater(len(results), 0)
        # Platform state should reflect the directive
        plat = self.platform.get_platform()
        # Platform was updated (status should be "active")
        self.assertEqual(plat.status, "active")

    def test_directive_without_platform_manager_is_safe(self) -> None:
        """Directives work without platform_manager (graceful degradation)."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        branch.activate()
        results = branch.issue_directive("Test directive")
        branch.deactivate()

        self.assertGreater(len(results), 0)

    def test_directive_targets_subset_of_roles(self) -> None:
        """Targeted directive only hits specified roles."""
        branch = CEOBranch(
            rosetta_manager=self.mgr,
            platform_manager=self.platform,
        )
        branch.activate()
        results = branch.issue_directive("Sell harder", roles=["VP Sales"])
        branch.deactivate()

        accepted = [r for r in results if r.accepted]
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].role_label, "VP Sales")


# ===========================================================================
# P4 — Gap 4: Register heartbeat tier translators
# ===========================================================================

class TestP4HeartbeatTranslator(unittest.TestCase):
    """P4: CEO branch registers MANAGEMENT-tier heartbeat translator."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.mgr = _make_rosetta_manager(self._tmp)
        self.heartbeat = RosettaStoneHeartbeat(interval_seconds=1.0)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_activate_registers_management_translator(self) -> None:
        """After activation, MANAGEMENT tier has a registered translator."""
        branch = CEOBranch(
            rosetta_manager=self.mgr,
            heartbeat=self.heartbeat,
        )
        result = branch.activate()
        branch.deactivate()

        self.assertTrue(result["heartbeat_registered"])

        # Verify tier state shows translator registered
        tier_state = self.heartbeat.get_tier_state(OrganizationTier.MANAGEMENT)
        self.assertTrue(tier_state["translator_registered"])

    def test_heartbeat_pulse_cascades_to_vp_roles(self) -> None:
        """A pulse with directives triggers execute_directive on VP roles."""
        branch = CEOBranch(
            rosetta_manager=self.mgr,
            heartbeat=self.heartbeat,
        )
        branch.activate()

        # Emit a pulse with directives
        pulse_result = self.heartbeat.emit_pulse(
            directives={"priority": "revenue", "action": "increase outreach"},
        )
        branch.deactivate()

        self.assertTrue(pulse_result["success"])
        # Management tier should be acknowledged
        mgmt_prop = [
            p for p in pulse_result["propagation"]
            if p["tier"] == "management"
        ]
        self.assertEqual(len(mgmt_prop), 1)
        self.assertEqual(mgmt_prop[0]["status"], "acknowledged")
        # At least some VP roles received the directive
        actions = mgmt_prop[0]["ack"]["actions"]
        self.assertGreater(actions, 0)

    def test_heartbeat_pulse_without_directives_is_noop(self) -> None:
        """A pulse with empty directives is acknowledged but no actions taken."""
        branch = CEOBranch(
            rosetta_manager=self.mgr,
            heartbeat=self.heartbeat,
        )
        branch.activate()

        pulse_result = self.heartbeat.emit_pulse(directives={})
        branch.deactivate()

        mgmt_prop = [
            p for p in pulse_result["propagation"]
            if p["tier"] == "management"
        ]
        self.assertEqual(mgmt_prop[0]["ack"]["actions"], 0)

    def test_activate_without_heartbeat_is_safe(self) -> None:
        """Activation works without heartbeat (graceful degradation)."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        result = branch.activate()
        branch.deactivate()

        self.assertFalse(result["heartbeat_registered"])

    def test_ceo_role_excluded_from_pulse_directives(self) -> None:
        """CEO role does not receive its own pulse directives."""
        branch = CEOBranch(
            rosetta_manager=self.mgr,
            heartbeat=self.heartbeat,
        )
        branch.activate()

        self.heartbeat.emit_pulse(
            directives={"global": "focus on compliance"},
        )
        branch.deactivate()

        # Check CEO role directive log is empty
        ceo_role = branch._org_chart.get_role("CEO")
        self.assertIsNotNone(ceo_role)
        ceo_directives = ceo_role.get_directive_log()
        # CEO should NOT have received the heartbeat directive
        self.assertEqual(len(ceo_directives), 0)


# ===========================================================================
# End-to-end integration
# ===========================================================================

class TestEndToEndIntegration(unittest.TestCase):
    """Full lifecycle: activate → tick → directive → report → Rosetta state."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.mgr = _make_rosetta_manager(self._tmp)
        self.platform = RosettaPlatformManager(rosetta_manager=self.mgr)
        self.heartbeat = RosettaStoneHeartbeat(interval_seconds=1.0)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_full_lifecycle(self) -> None:
        """Full cycle: activate → tick → directive → verify state."""
        branch = CEOBranch(
            rosetta_manager=self.mgr,
            platform_manager=self.platform,
            heartbeat=self.heartbeat,
        )

        # 1. Activate — seeds personas + registers heartbeat
        activation = branch.activate()
        self.assertTrue(activation["activated"])
        self.assertEqual(activation["personas_loaded"], len(_ORG_CHART_DEFINITION))
        self.assertTrue(activation["heartbeat_registered"])

        # 2. Tick — collects reports, writes back to Rosetta
        tick_result = branch.run_tick()
        self.assertGreater(tick_result.tick_number, 0)
        self.assertGreater(len(tick_result.role_reports), 0)

        # 3. Issue directive — recorded in platform manager
        directive_results = branch.issue_directive("Increase revenue by 20%")
        self.assertGreater(len(directive_results), 0)

        # 4. Emit heartbeat pulse — cascades to VP roles
        pulse = self.heartbeat.emit_pulse(
            directives={"quarterly_target": "increase 20%"},
        )
        self.assertTrue(pulse["success"])

        # 5. Verify Rosetta state was updated
        vp_sales = branch._org_chart.get_role("VP Sales")
        self.assertIsNotNone(vp_sales)
        state = self.mgr.load_state(vp_sales.agent_id)
        self.assertIsNotNone(state)

        # Agent should have directive in its log
        directive_log = vp_sales.get_directive_log()
        self.assertGreater(len(directive_log), 0)

        branch.deactivate()

    def test_concurrent_ticks_with_rosetta(self) -> None:
        """Multiple threads can tick concurrently with Rosetta integration."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        branch.activate()

        errors: List[str] = []

        def tick_fn():
            try:
                branch.run_tick()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=tick_fn) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        branch.deactivate()
        self.assertEqual(len(errors), 0, f"Concurrent tick errors: {errors}")

    def test_graceful_degradation_all_off(self) -> None:
        """System operates even when all optional integrations are missing."""
        branch = CEOBranch()
        result = branch.activate()
        self.assertTrue(result["activated"])
        self.assertEqual(result["personas_loaded"], 0)
        self.assertFalse(result["heartbeat_registered"])

        tick = branch.run_tick()
        self.assertGreater(tick.tick_number, 0)

        directives = branch.issue_directive("Test")
        self.assertGreater(len(directives), 0)

        branch.deactivate()

    def test_vp_roles_see_updated_state_after_tick(self) -> None:
        """After a tick with report write-back, VP roles can see updated state."""
        branch = CEOBranch(rosetta_manager=self.mgr)
        branch.activate()
        branch.run_tick()

        # VP Sales should now have a rosetta_state with metadata.last_tick
        vp_sales = branch._org_chart.get_role("VP Sales")
        self.assertIsNotNone(vp_sales)
        rs = vp_sales.rosetta_state
        self.assertIsNotNone(rs)
        self.assertIn("metadata", rs)

        branch.deactivate()


if __name__ == "__main__":
    unittest.main()
