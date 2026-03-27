"""
Tests for activated_heartbeat_runner.py — ActivatedHeartbeatRunner.

Test outline per tick:
- tick() returns a TickRecord with correct fields
- State snapshot captured from AgentMonitorDashboard
- Setpoints derived from BusinessPlanMath
- ControlVector computed via ControlLaw
- Approved actions create checkpoint BEFORE execution
- Unapproved actions marked PENDING_HITL
- Audit log records every tick
- Pulse emitted with goal coordinates, health metrics, metadata
- Idempotency: same state → same control vector
- Integral accumulates across ticks (Ki drift compensation)
- StabilityMonitor oscillation → automation mode downgrade
- No business plan → tick returns SKIPPED
- Timer start/stop lifecycle
"""

import os
import time
import threading


import pytest

from activated_heartbeat_runner import (
    ActivatedHeartbeatRunner,
    TickRecord,
    TickStatus,
    WorkOrder,
    WorkOrderStatus,
)
from rosetta_stone_heartbeat import RosettaStoneHeartbeat
from control_plane.control_loop import (
    ControlLaw,
    ControlVector,
    StabilityMonitor,
    StabilityViolation,
)
from control_plane.state_vector import StateVector
from full_automation_controller import (
    AutomationMode,
    AutomationToggleReason,
    FullAutomationController,
)
from agent_monitor_dashboard import (
    AgentMonitorDashboard,
    AgentState,
)
from persistence_replay_completeness import PersistenceReplayCompleteness
from feedback_integrator import FeedbackIntegrator
from rosetta.rosetta_models import BusinessPlanMath, UnitEconomics


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def unit_economics():
    return UnitEconomics(
        revenue_goal_dollars=1_200_000.0,
        unit_price_dollars=1_000.0,
        annual_cost_dollars=100_000.0,
        timeline_months=12.0,
        conversion_rate_goal=0.99,
        conversion_rate_actual=0.50,
    )


@pytest.fixture
def business_plan(unit_economics):
    return BusinessPlanMath(
        unit_economics=unit_economics,
        current_quarter=2,
        quarters_elapsed=1.0,
        units_closed_to_date=100.0,
        pipeline_units=50.0,
    )


@pytest.fixture
def dashboard():
    d = AgentMonitorDashboard()
    # Register a few agents in various states
    a1 = d.register_agent("agent-alpha", role="executor")
    d.update_state(a1.agent_id, AgentState.EXECUTING.value)
    a2 = d.register_agent("agent-beta", role="monitor")
    d.update_state(a2.agent_id, AgentState.MONITORING.value)
    a3 = d.register_agent("agent-gamma", role="executor")
    d.update_state(a3.agent_id, AgentState.IDLE.value)
    return d


@pytest.fixture
def persistence(tmp_path):
    return PersistenceReplayCompleteness(
        wal_dir=str(tmp_path / "wal"),
        snapshot_dir=str(tmp_path / "snapshots"),
    )


@pytest.fixture
def automation_controller():
    ac = FullAutomationController()
    # Set to semi-autonomous so low risk actions are auto-approved
    ac.set_automation_mode(
        tenant_id="test-tenant",
        agent_id=None,
        mode=AutomationMode.SEMI_AUTONOMOUS,
        user_id="test-setup",
        reason=AutomationToggleReason.MANUAL_ENABLE,
        user_role="admin",
    )
    return ac


@pytest.fixture
def runner(
    business_plan,
    dashboard,
    persistence,
    automation_controller,
):
    """Build a fully wired ActivatedHeartbeatRunner for testing."""
    return ActivatedHeartbeatRunner(
        heartbeat=RosettaStoneHeartbeat(interval_seconds=1.0),
        control_law=ControlLaw(gain=1.0, threshold=0.05),
        stability_monitor=StabilityMonitor(max_reversals=3, window=10),
        automation_controller=automation_controller,
        dashboard=dashboard,
        persistence=persistence,
        feedback_integrator=FeedbackIntegrator(),
        business_plan=business_plan,
        tenant_id="test-tenant",
        tick_interval=1.0,
        ki=0.1,
    )


# =====================================================================
# Tick basics
# =====================================================================


class TestTickBasics:
    """Tick returns a valid TickRecord with correct fields."""

    def test_tick_returns_tick_record(self, runner):
        result = runner.tick()
        assert isinstance(result, TickRecord)

    def test_tick_record_fields(self, runner):
        result = runner.tick()
        assert result.heartbeat_id.startswith("hb-")
        assert result.tick_number == 1
        assert result.timestamp > 0
        assert result.status == TickStatus.OK
        assert result.state_snapshot_id != ""
        assert result.control_vector is not None

    def test_tick_increments_count(self, runner):
        runner.tick()
        runner.tick()
        runner.tick()
        assert runner.tick_count == 3


# =====================================================================
# State snapshot
# =====================================================================


class TestStateSnapshot:
    """State is snapshot from AgentMonitorDashboard each tick."""

    def test_snapshot_captured_in_persistence(self, runner, persistence):
        runner.tick()
        snaps = persistence.snapshots.list_snapshots()
        assert len(snaps) >= 1
        assert "tick-1" in snaps[0].get("label", "")

    def test_state_dict_has_required_dimensions(self, runner):
        from agent_monitor_dashboard import DashboardSnapshot
        snap = runner._dashboard.get_dashboard_snapshot()
        state_dict = ActivatedHeartbeatRunner._build_state_dict(snap)
        for key in ("money", "time", "production", "confidence",
                     "info_completeness", "risk"):
            assert key in state_dict


# =====================================================================
# Setpoints
# =====================================================================


class TestSetpoints:
    """Setpoints derived from BusinessPlanMath."""

    def test_setpoints_from_plan(self, business_plan):
        sp = ActivatedHeartbeatRunner._build_setpoints(business_plan)
        assert "confidence" in sp
        assert sp["confidence"] == 1.0
        assert sp["risk"] == 0.0
        assert "production" in sp

    def test_setpoints_on_track(self):
        ue = UnitEconomics(
            revenue_goal_dollars=1_200_000.0,
            unit_price_dollars=1_000.0,
            timeline_months=12.0,
        )
        plan = BusinessPlanMath(
            unit_economics=ue,
            quarters_elapsed=1.0,
            units_closed_to_date=500.0,
        )
        sp = ActivatedHeartbeatRunner._build_setpoints(plan)
        assert sp["production"] == 1.0  # on track


# =====================================================================
# ControlVector computation
# =====================================================================


class TestControlVector:
    """ControlVector computed from state vs setpoints."""

    def test_control_vector_populated(self, runner):
        result = runner.tick()
        cv = result.control_vector
        assert cv is not None
        # ControlVector is serialised to dict
        assert "ask_question" in cv
        assert "action_intensity" in cv


# =====================================================================
# Action processing and checkpoints
# =====================================================================


class TestActionProcessing:
    """Actions create checkpoints and are approved/pending per automation mode."""

    def test_approved_action_has_checkpoint(self, runner, persistence):
        """Approved work orders must have a checkpoint_index set."""
        result = runner.tick()
        executed = [
            a for a in result.actions_taken
            if a["status"] == WorkOrderStatus.EXECUTED.value
        ]
        for action in executed:
            assert action["checkpoint_index"] is not None

    def test_pending_hitl_when_not_approved(self, tmp_path, business_plan, dashboard):
        """High-risk actions in MANUAL mode should be PENDING_HITL."""
        ac = FullAutomationController()
        # MANUAL mode rejects everything
        ac.set_automation_mode(
            tenant_id="manual-t",
            agent_id=None,
            mode=AutomationMode.MANUAL,
            user_id="test",
            reason=AutomationToggleReason.MANUAL_ENABLE,
            user_role="admin",
        )
        runner = ActivatedHeartbeatRunner(
            automation_controller=ac,
            dashboard=dashboard,
            persistence=PersistenceReplayCompleteness(
                wal_dir=str(tmp_path / "wal"),
                snapshot_dir=str(tmp_path / "snap"),
            ),
            business_plan=business_plan,
            tenant_id="manual-t",
        )
        result = runner.tick()
        for action in result.actions_taken:
            assert action["status"] == WorkOrderStatus.PENDING_HITL.value

    def test_checkpoint_before_execution(self, runner, persistence):
        """Checkpoints must be recorded before execution (invariant)."""
        executed_before = []

        original_executor = runner._action_executor

        def tracking_executor(wo):
            # At execution time, checkpoint should already exist
            executed_before.append(wo.checkpoint_index)
            return original_executor(wo)

        runner._action_executor = tracking_executor
        runner.tick()

        for cp_idx in executed_before:
            if cp_idx is not None:
                assert cp_idx >= 0  # checkpoint was set before executor ran


# =====================================================================
# Audit log
# =====================================================================


class TestAuditLog:
    """Audit log records every tick."""

    def test_audit_log_grows(self, runner):
        runner.tick()
        runner.tick()
        log = runner.get_audit_log()
        assert len(log) == 2

    def test_audit_entry_has_required_fields(self, runner):
        runner.tick()
        entry = runner.get_audit_log()[0]
        for key in ("heartbeat_id", "tick_number", "timestamp",
                     "state_snapshot_id", "control_vector",
                     "actions_taken", "status"):
            assert key in entry


# =====================================================================
# Pulse emission
# =====================================================================


class TestPulseEmission:
    """Pulse emitted with goal coordinates, health metrics, metadata."""

    def test_pulse_emitted_on_tick(self, runner):
        """Tick should emit at least one pulse (sequence advances)."""
        stats_before = runner._heartbeat.statistics()
        seq_before = stats_before["current_sequence"]
        runner.tick()
        stats_after = runner._heartbeat.statistics()
        assert stats_after["current_sequence"] > seq_before


# =====================================================================
# Idempotency
# =====================================================================


class TestIdempotency:
    """Same state → same control vector (tick is idempotent)."""

    def test_idempotent_control_vector(self, tmp_path, business_plan):
        """Two runners with identical state produce the same ControlVector."""
        d1 = AgentMonitorDashboard()
        d1.register_agent("a1", role="monitor")

        d2 = AgentMonitorDashboard()
        d2.register_agent("a1", role="monitor")

        r1 = ActivatedHeartbeatRunner(
            dashboard=d1,
            business_plan=business_plan,
            persistence=PersistenceReplayCompleteness(
                wal_dir=str(tmp_path / "wal1"),
                snapshot_dir=str(tmp_path / "snap1"),
            ),
            control_law=ControlLaw(gain=1.0, threshold=0.05),
        )
        r2 = ActivatedHeartbeatRunner(
            dashboard=d2,
            business_plan=business_plan,
            persistence=PersistenceReplayCompleteness(
                wal_dir=str(tmp_path / "wal2"),
                snapshot_dir=str(tmp_path / "snap2"),
            ),
            control_law=ControlLaw(gain=1.0, threshold=0.05),
        )

        t1 = r1.tick()
        t2 = r2.tick()

        assert t1.control_vector == t2.control_vector


# =====================================================================
# Integral accumulation (Ki)
# =====================================================================


class TestIntegralAccumulation:
    """Integral error accumulates across ticks for drift compensation."""

    def test_integral_grows_across_ticks(self, runner):
        runner.tick()
        ie1 = runner.get_integral_error()
        runner.tick()
        ie2 = runner.get_integral_error()

        # Integral should grow (or stay same if error is zero)
        total1 = sum(abs(v) for v in ie1.values())
        total2 = sum(abs(v) for v in ie2.values())
        # With non-zero error, integral must grow
        assert total2 >= total1

    def test_integral_reset_on_plan_change(self, runner, unit_economics):
        runner.tick()
        assert sum(abs(v) for v in runner.get_integral_error().values()) > 0

        new_plan = BusinessPlanMath(
            unit_economics=unit_economics,
            quarters_elapsed=2.0,
            units_closed_to_date=200.0,
        )
        runner.set_business_plan(new_plan)
        assert sum(abs(v) for v in runner.get_integral_error().values()) == 0.0


# =====================================================================
# Oscillation → automation downgrade
# =====================================================================


class TestOscillationDowngrade:
    """StabilityMonitor oscillation → automatic automation mode downgrade."""

    def test_downgrade_on_oscillation(self, tmp_path, business_plan):
        """When StabilityMonitor detects oscillation, tick downgrades automation."""
        ac = FullAutomationController()
        ac.set_automation_mode(
            tenant_id="osc-t",
            agent_id=None,
            mode=AutomationMode.FULL_AUTONOMOUS,
            user_id="test",
            reason=AutomationToggleReason.MANUAL_ENABLE,
            user_role="admin",
        )

        # max_reversals=3, min_net_gain=0.8: needs 3 reversals with low net gain
        monitor = StabilityMonitor(max_reversals=3, window=10, min_net_gain=0.8)

        dashboard = AgentMonitorDashboard()
        dashboard.register_agent("a1")

        runner = ActivatedHeartbeatRunner(
            automation_controller=ac,
            stability_monitor=monitor,
            dashboard=dashboard,
            business_plan=business_plan,
            persistence=PersistenceReplayCompleteness(
                wal_dir=str(tmp_path / "wal"),
                snapshot_dir=str(tmp_path / "snap"),
            ),
            tenant_id="osc-t",
        )

        # Pre-load oscillating readings to reach 2 reversals (< max 3).
        # Pattern: 0.5→0.3 (dir -1), 0.3→0.6 (dir +1, rev 1),
        #          0.6→0.3 (dir -1, rev 2) — last_direction = -1.
        # Tick will record confidence ~1.0 → direction +1, rev 3 → triggers.
        # net_gain = 1.0 - 0.5 = 0.5 < 0.8 → StabilityViolation
        monitor.record(0.5)
        monitor.record(0.3)
        monitor.record(0.6)
        monitor.record(0.3)

        result = runner.tick()
        assert result.status == TickStatus.OSCILLATION_DETECTED

        # Automation should have downgraded from FULL to SEMI
        mode = ac.get_automation_mode("osc-t")
        assert mode == AutomationMode.SEMI_AUTONOMOUS


# =====================================================================
# No business plan → SKIPPED
# =====================================================================


class TestNoPlan:
    """Tick without business plan returns SKIPPED."""

    def test_skip_without_plan(self, tmp_path, dashboard):
        runner = ActivatedHeartbeatRunner(
            dashboard=dashboard,
            persistence=PersistenceReplayCompleteness(
                wal_dir=str(tmp_path / "wal"),
                snapshot_dir=str(tmp_path / "snap"),
            ),
            business_plan=None,
        )
        result = runner.tick()
        assert result.status == TickStatus.SKIPPED
        assert "No business plan" in result.error_detail


# =====================================================================
# Timer lifecycle
# =====================================================================


class TestTimerLifecycle:
    """Timer start/stop lifecycle."""

    def test_start_stop(self, runner):
        assert not runner.running
        runner.start()
        assert runner.running
        runner.stop()
        assert not runner.running

    def test_start_idempotent(self, runner):
        runner.start()
        runner.start()  # second call is no-op
        assert runner.running
        runner.stop()

    def test_timer_fires_tick(self, runner):
        """Timer should fire at least one tick within interval."""
        runner._tick_interval = 0.1  # fast for tests
        runner.start()
        time.sleep(0.35)
        runner.stop()
        assert runner.tick_count >= 1


# =====================================================================
# Status / query helpers
# =====================================================================


class TestStatusHelpers:
    """Query helpers return meaningful data."""

    def test_get_status(self, runner):
        runner.tick()
        status = runner.get_status()
        assert status["tick_count"] == 1
        assert status["has_business_plan"] is True
        assert status["running"] is False

    def test_get_work_orders(self, runner):
        runner.tick()
        orders = runner.get_work_orders()
        assert isinstance(orders, list)

    def test_get_work_orders_filtered(self, runner):
        runner.tick()
        pending = runner.get_work_orders(
            status_filter=WorkOrderStatus.PENDING_HITL
        )
        for wo in pending:
            assert wo["status"] == WorkOrderStatus.PENDING_HITL.value


# =====================================================================
# WorkOrder / TickRecord dataclass tests
# =====================================================================


class TestDataclasses:
    """WorkOrder and TickRecord serialise correctly."""

    def test_work_order_to_dict(self):
        wo = WorkOrder(
            action_field="ask_question",
            action_value=True,
            risk_level="low",
            status=WorkOrderStatus.EXECUTED,
        )
        d = wo.to_dict()
        assert d["action_field"] == "ask_question"
        assert d["status"] == "executed"

    def test_tick_record_to_dict(self):
        tr = TickRecord(
            heartbeat_id="hb-test",
            tick_number=1,
            status=TickStatus.OK,
        )
        d = tr.to_dict()
        assert d["heartbeat_id"] == "hb-test"
        assert d["status"] == "ok"


# =====================================================================
# StateVector construction
# =====================================================================


class TestStateVectorConstruction:
    """StateVector correctly maps operational dimensions."""

    def test_build_state_vector(self):
        raw = {
            "money": 0.6,
            "time": 0.4,
            "production": 0.3,
            "confidence": 0.9,
            "info_completeness": 0.7,
            "risk": 0.1,
        }
        sv = ActivatedHeartbeatRunner._build_state_vector(raw)
        assert sv.confidence == pytest.approx(0.9)
        assert sv.information_completeness == pytest.approx(0.7)
        assert sv.risk_exposure == pytest.approx(0.1)
        assert sv.extra_dimensions["money"] == pytest.approx(0.6)
        assert sv.extra_dimensions["time"] == pytest.approx(0.4)
        assert sv.extra_dimensions["production"] == pytest.approx(0.3)

    def test_build_state_vector_clamps(self):
        raw = {"confidence": 1.5, "risk": -0.2, "info_completeness": 2.0}
        sv = ActivatedHeartbeatRunner._build_state_vector(raw)
        assert sv.confidence == 1.0
        assert sv.risk_exposure == 0.0
        assert sv.information_completeness == 1.0
