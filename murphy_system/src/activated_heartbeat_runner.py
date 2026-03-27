"""
Activated Heartbeat Runner — Murphy System

Turns the passive Rosetta Stone heartbeat into an operational control loop
by wiring together:

- rosetta_stone_heartbeat → pulse emission, ack tracking
- control_plane.control_loop → ControlLaw (proportional), ControlVector, StabilityMonitor
- control_plane.state_vector → StateVector
- control_theory.control_structure → PI ControlLaw (Kp + Ki integral accumulation)
- full_automation_controller → AutomationMode, should_auto_approve()
- agent_monitor_dashboard → AgentState, AgentMonitorDashboard, DashboardSnapshot
- persistence_replay_completeness → PersistenceReplayCompleteness, PointInTimeRecovery
- feedback_integrator → FeedbackSignal, FeedbackIntegrator
- rosetta.rosetta_models → BusinessPlanMath, UnitEconomics

Each tick:
1. Snapshot current state from all registered agents
2. Read goal graph setpoints from BusinessPlanMath
3. Build a StateVector from agent/business state
4. Compute ControlVector via ControlLaw
5. Evaluate actions through FullAutomationController
6. Record tick in audit log
7. Emit pulse via heartbeat with directives

Invariants:
- Tick is idempotent (same state → same control vector)
- Conversation endpoints are never blocked by tick processing
- Every action creates a checkpoint BEFORE execution
- Integral term (Ki) accumulates across ticks for chronic-drift compensation
- StabilityMonitor oscillation → automatic automation mode downgrade

Owner: INONI LLC / Corey Post
Contact: corey.gfc@gmail.com
Repository: https://github.com/IKNOWINOT/Murphy-System
"""

from __future__ import annotations

import copy
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_monitor_dashboard import (
    AgentMonitorDashboard,
    AgentState,
    DashboardSnapshot,
)
from ceo_branch_activation import CEOBranch
from control_plane.control_loop import (
    ControlLaw as ProportionalControlLaw,
)
from control_plane.control_loop import (
    ControlVector,
    StabilityMonitor,
    StabilityViolation,
)
from control_plane.state_vector import StateVector
from feedback_integrator import FeedbackIntegrator, FeedbackSignal
from full_automation_controller import (
    AutomationMode,
    AutomationToggleReason,
    FullAutomationController,
)
from persistence_replay_completeness import PersistenceReplayCompleteness
from rosetta.rosetta_models import BusinessPlanMath, UnitEconomics
from rosetta_stone_heartbeat import RosettaStoneHeartbeat

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# Supporting types
# ────────────────────────────────────────────────────────────────────


class WorkOrderStatus(str, Enum):
    """Status of a generated work order."""
    APPROVED = "approved"
    PENDING_HITL = "pending_hitl"
    EXECUTED = "executed"
    REJECTED = "rejected"


class TickStatus(str, Enum):
    """Outcome status of a single tick."""
    OK = "ok"
    OSCILLATION_DETECTED = "oscillation_detected"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class WorkOrder:
    """A single action prescribed by the control loop."""
    work_order_id: str = field(default_factory=lambda: f"wo-{uuid.uuid4().hex[:12]}")
    action_field: str = ""
    action_value: Any = None
    risk_level: str = "low"
    status: WorkOrderStatus = WorkOrderStatus.PENDING_HITL
    checkpoint_index: Optional[int] = None
    approval_reason: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "action_field": self.action_field,
            "action_value": self.action_value,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "checkpoint_index": self.checkpoint_index,
            "approval_reason": self.approval_reason,
            "created_at": self.created_at,
        }


@dataclass
class TickRecord:
    """Immutable audit record for a single tick."""
    heartbeat_id: str = ""
    tick_number: int = 0
    timestamp: float = field(default_factory=time.time)
    state_snapshot_id: str = ""
    control_vector: Optional[Dict[str, Any]] = None
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    status: TickStatus = TickStatus.OK
    error_detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heartbeat_id": self.heartbeat_id,
            "tick_number": self.tick_number,
            "timestamp": self.timestamp,
            "state_snapshot_id": self.state_snapshot_id,
            "control_vector": self.control_vector,
            "actions_taken": self.actions_taken,
            "status": self.status.value,
            "error_detail": self.error_detail,
        }


# ────────────────────────────────────────────────────────────────────
# Pulse schema additions
# ────────────────────────────────────────────────────────────────────
#
# The pulse emitted at the end of each tick carries extra fields:
#
#   directives:
#     goal_coordinates:
#       units_per_month: float       — target pace from BusinessPlanMath
#       prospect_reach_needed: float — required prospect reach
#       units_remaining: float       — units still needed
#       months_remaining: float      — months left in plan
#       on_track: bool               — pace vs plan check
#     control_actions:               — list of action names activated
#     automation_mode: str           — current automation mode
#
#   health_metrics:
#     confidence_avg: float          — average agent confidence
#     info_completeness_avg: float   — average information completeness
#     risk_max: float                — highest active risk
#     agent_count: int               — total monitored agents
#     agents_executing: int          — agents in EXECUTING state
#     agents_in_error: int           — agents in ERROR state
#     stability_reversals: int       — oscillation reversal count
#
#   metadata:
#     tick_number: int               — monotonic tick counter
#     tick_status: str               — TickStatus value
#     integral_error_sum: float      — current integral accumulator magnitude
#     work_orders_created: int       — work orders generated this tick
#     work_orders_auto_approved: int — auto-approved count
#     work_orders_pending_hitl: int  — pending human review count
# ────────────────────────────────────────────────────────────────────


# Mapping from ControlVector boolean fields to action_type strings for
# the FullAutomationController.
_CV_ACTION_FIELDS: List[str] = [
    "ask_question",
    "generate_candidates",
    "evaluate_gate",
    "advance_phase",
    "request_human_intervention",
    "execute_action",
]

# Default risk mapping: more impactful actions carry higher risk labels.
_ACTION_RISK: Dict[str, str] = {
    "ask_question": "minimal",
    "generate_candidates": "low",
    "evaluate_gate": "medium",
    "advance_phase": "high",
    "request_human_intervention": "low",
    "execute_action": "high",
}


class ActivatedHeartbeatRunner:
    """Operational control loop built on the Rosetta Stone heartbeat.

    Runs on a configurable timer (default 5 s).  Each tick:
    1. Snapshots agent state from :class:`AgentMonitorDashboard`.
    2. Reads goal setpoints from :class:`BusinessPlanMath`.
    3. Builds a :class:`StateVector` from operational dimensions.
    4. Computes a :class:`ControlVector` via :class:`ControlLaw` with
       PI integral accumulation for chronic-drift compensation.
    5. For each activated action, checks
       :meth:`FullAutomationController.should_auto_approve`; approved
       actions create a checkpoint then execute, others pend for HITL.
    6. Records the tick in an immutable audit log.
    7. Emits a heartbeat pulse carrying goal coordinates and health
       metrics as directives.

    Thread-safety: all mutable state is protected by a reentrant lock.
    Tick processing never blocks callers of non-tick methods.
    """

    # ────────────────────────────────────────────────────────────────
    # Construction
    # ────────────────────────────────────────────────────────────────

    def __init__(
        self,
        heartbeat: Optional[RosettaStoneHeartbeat] = None,
        control_law: Optional[ProportionalControlLaw] = None,
        stability_monitor: Optional[StabilityMonitor] = None,
        automation_controller: Optional[FullAutomationController] = None,
        dashboard: Optional[AgentMonitorDashboard] = None,
        persistence: Optional[PersistenceReplayCompleteness] = None,
        feedback_integrator: Optional[FeedbackIntegrator] = None,
        business_plan: Optional[BusinessPlanMath] = None,
        tenant_id: str = "default",
        tick_interval: float = 5.0,
        ki: float = 0.1,
        action_executor: Optional[Callable[[WorkOrder], bool]] = None,
        ceo_branch: Optional[CEOBranch] = None,
    ) -> None:
        """Initialise the activated heartbeat runner.

        Args:
            heartbeat: Rosetta Stone heartbeat engine. Created if *None*.
            control_law: Proportional control law. Created with default
                gain if *None*.
            stability_monitor: Oscillation detector. Created if *None*.
            automation_controller: Full-automation controller. Created
                if *None*.
            dashboard: Agent monitor dashboard. Created if *None*.
            persistence: Persistence / recovery facade. Created if *None*.
            feedback_integrator: Feedback signal integrator. Created if
                *None*.
            business_plan: Business plan mathematics (setpoints). May be
                set later via :meth:`set_business_plan`.
            tenant_id: Tenant identifier for automation decisions.
            tick_interval: Seconds between ticks (default 5).
            ki: Integral gain for PI accumulation across ticks.
            action_executor: Optional callback ``(WorkOrder) -> bool``
                invoked when an approved action is executed.  Default
                is a no-op that always returns *True*.
        """
        self._lock = threading.RLock()

        # ── wired modules ──
        self._heartbeat = heartbeat or RosettaStoneHeartbeat(
            interval_seconds=tick_interval,
        )
        self._control_law = control_law or ProportionalControlLaw()
        self._stability_monitor = stability_monitor or StabilityMonitor()
        self._automation_controller = (
            automation_controller or FullAutomationController()
        )
        self._dashboard = dashboard or AgentMonitorDashboard()
        self._persistence = persistence or PersistenceReplayCompleteness()
        self._feedback_integrator = (
            feedback_integrator or FeedbackIntegrator()
        )
        self._business_plan: Optional[BusinessPlanMath] = business_plan

        # ── configuration ──
        self._tenant_id = tenant_id
        self._tick_interval = tick_interval
        self._ki = ki
        self._action_executor: Callable[[WorkOrder], bool] = (
            action_executor or (lambda _wo: True)
        )

        # ── integral accumulator (persists across ticks) ──
        self._integral_error: Dict[str, float] = {}

        # ── tick state ──
        self._tick_count: int = 0
        self._running: bool = False
        self._timer: Optional[threading.Timer] = None

        # ── audit log (bounded) ──
        self._audit_log: List[TickRecord] = []
        self._max_audit: int = 500

        # ── work orders ──
        self._work_orders: List[WorkOrder] = []

        # ── CEO branch (optional extension) ──
        self._ceo_branch: Optional[CEOBranch] = ceo_branch

        logger.info(
            "ActivatedHeartbeatRunner initialised (interval=%.1fs, ki=%.3f)",
            tick_interval,
            ki,
        )

    # ────────────────────────────────────────────────────────────────
    # Business plan management
    # ────────────────────────────────────────────────────────────────

    def set_business_plan(self, plan: BusinessPlanMath) -> None:
        """Replace the current business plan (setpoints).

        Resets the integral accumulator because setpoints changed.
        """
        with self._lock:
            self._business_plan = plan
            self._integral_error.clear()
            logger.info("Business plan updated — integral reset")

    def get_business_plan(self) -> Optional[BusinessPlanMath]:
        """Return the currently configured business plan."""
        with self._lock:
            return self._business_plan

    # ────────────────────────────────────────────────────────────────
    # Timer lifecycle
    # ────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the periodic tick timer."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._schedule_next()
            logger.info("Heartbeat runner started")

    def stop(self) -> None:
        """Stop the periodic tick timer."""
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            logger.info("Heartbeat runner stopped")

    @property
    def running(self) -> bool:
        """Whether the runner is currently active."""
        return self._running

    def _schedule_next(self) -> None:
        """Schedule the next tick on a daemon thread."""
        if not self._running:
            return
        self._timer = threading.Timer(self._tick_interval, self._run_tick)
        self._timer.daemon = True
        self._timer.start()

    def _run_tick(self) -> None:
        """Internal timer callback — runs tick and reschedules."""
        try:
            self.tick()
        except Exception as exc:
            logger.exception("Tick failed: %s", exc)
        finally:
            with self._lock:
                if self._running:
                    self._schedule_next()

    # ────────────────────────────────────────────────────────────────
    # Core tick
    # ────────────────────────────────────────────────────────────────

    def tick(self) -> TickRecord:
        """Execute a single control-loop tick.

        This method is **idempotent**: given identical agent states and
        business plan, it produces the same :class:`ControlVector`.

        Returns:
            A :class:`TickRecord` capturing the full audit trail of this
            tick.

        The method is safe to call from any thread; all mutable state
        is guarded by ``self._lock``.
        """
        with self._lock:
            self._tick_count += 1
            tick_num = self._tick_count
            heartbeat_id = f"hb-{uuid.uuid4().hex[:12]}"
            ts = time.time()

            # ── guard: no business plan → skip ──
            if self._business_plan is None:
                record = TickRecord(
                    heartbeat_id=heartbeat_id,
                    tick_number=tick_num,
                    timestamp=ts,
                    status=TickStatus.SKIPPED,
                    error_detail="No business plan configured",
                )
                self._append_audit(record)
                return record

            try:
                # 1. Snapshot current state from agents
                snapshot = self._dashboard.get_dashboard_snapshot()
                state_dict = self._build_state_dict(snapshot)

                # Persist snapshot
                snap_result = self._persistence.snapshot_and_record(
                    state_dict,
                    label=f"tick-{tick_num}",
                )
                snap_id = snap_result.get("snapshot_id", "")

                # 2. Read goal setpoints from BusinessPlanMath
                setpoints = self._build_setpoints(self._business_plan)

                # 3. Build StateVector
                state_vec = self._build_state_vector(state_dict)
                target_vec = self._build_state_vector(setpoints)

                # 4. Compute control vector with PI integral accumulation
                control_vec = self._compute_pi_control(state_vec, target_vec)

                # Record confidence for stability monitoring
                oscillation_detected = False
                try:
                    self._stability_monitor.record(state_vec.confidence)
                except StabilityViolation:
                    oscillation_detected = True
                    logger.warning(
                        "Tick %d: oscillation detected — downgrading automation",
                        tick_num,
                    )
                    self._downgrade_automation()

                # 5. Process actions from ControlVector
                work_orders = self._process_control_actions(
                    control_vec,
                    state_dict,
                    snap_id,
                )

                # 6. Build audit record
                status = (
                    TickStatus.OSCILLATION_DETECTED
                    if oscillation_detected
                    else TickStatus.OK
                )
                record = TickRecord(
                    heartbeat_id=heartbeat_id,
                    tick_number=tick_num,
                    timestamp=ts,
                    state_snapshot_id=snap_id,
                    control_vector=control_vec.model_dump(),
                    actions_taken=[wo.to_dict() for wo in work_orders],
                    status=status,
                )
                self._append_audit(record)

                # 7. Emit pulse with directives carrying goal coordinates
                self._emit_pulse(
                    tick_num=tick_num,
                    status=status,
                    control_vec=control_vec,
                    state_dict=state_dict,
                    work_orders=work_orders,
                )

                # 8. CEO branch tick (if configured) — runs autonomously
                #    alongside the control loop without blocking the audit.
                if self._ceo_branch is not None:
                    try:
                        self._ceo_branch.run_tick()
                    except Exception as _ceo_exc:  # noqa: BLE001
                        logger.warning(
                            "CEOBranch tick error (non-fatal): %s",
                            str(_ceo_exc)[:200],
                        )

                return record

            except Exception as exc:
                logger.exception("Tick %d error", tick_num)
                record = TickRecord(
                    heartbeat_id=heartbeat_id,
                    tick_number=tick_num,
                    timestamp=ts,
                    status=TickStatus.ERROR,
                    error_detail=str(exc),
                )
                self._append_audit(record)
                return record

    # ────────────────────────────────────────────────────────────────
    # State building helpers
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_state_dict(snapshot: DashboardSnapshot) -> Dict[str, Any]:
        """Build a raw state dict from the dashboard snapshot.

        Dimensions:
          money   — placeholder (0.5) until real budget integration
          time    — placeholder (0.5) until real deadline integration
          production — fraction of agents in EXECUTING state
          confidence — average confidence proxy (1 - error_fraction)
          info_completeness — fraction of agents in MONITORING or above
          risk    — alert density as proxy for highest active risk
        """
        total = max(snapshot.total_agents, 1)
        by_state = snapshot.agents_by_state

        executing = by_state.get(AgentState.EXECUTING.value, 0)
        monitoring = by_state.get(AgentState.MONITORING.value, 0)
        error_count = by_state.get(AgentState.ERROR.value, 0)
        alerting = by_state.get(AgentState.ALERTING.value, 0)
        idle = by_state.get(AgentState.IDLE.value, 0)

        # production: fraction executing vs total
        production = min(1.0, executing / total)
        # confidence proxy: 1 - error fraction
        confidence = max(0.0, min(1.0, 1.0 - (error_count / total)))
        # info completeness: fraction that are monitoring or executing
        active_count = monitoring + executing + alerting
        info_completeness = min(1.0, active_count / total)
        # risk proxy: alert density
        risk = min(1.0, (alerting + error_count) / total)

        return {
            "money": 0.5,
            "time": 0.5,
            "production": production,
            "confidence": confidence,
            "info_completeness": info_completeness,
            "risk": risk,
            "agent_count": total,
            "agents_executing": executing,
            "agents_in_error": error_count,
            "agents_alerting": alerting,
        }

    @staticmethod
    def _build_setpoints(plan: BusinessPlanMath) -> Dict[str, Any]:
        """Derive normalised setpoints from BusinessPlanMath.

        Maps business targets into the same dimension space as the
        state vector so the control law can compute meaningful error.
        """
        ue = plan.unit_economics

        # production target: pace ratio (actual vs needed).
        # 1.0 means on track, <1.0 means behind.
        pace_target = 1.0 if plan.on_track else min(
            1.0, plan.required_pace_remaining / max(ue.units_per_month, 1e-9)
        )

        return {
            "money": 0.5,       # budget neutral target
            "time": 0.5,        # on-schedule target
            "production": min(1.0, pace_target),
            "confidence": 1.0,  # full confidence desired
            "info_completeness": 1.0,  # full information desired
            "risk": 0.0,        # zero risk desired
        }

    @staticmethod
    def _build_state_vector(raw: Dict[str, Any]) -> StateVector:
        """Convert a raw dict into a :class:`StateVector`.

        Maps operational dimensions into the formal state vector's base
        dimensions and extra dimensions.
        """
        return StateVector(
            confidence=max(0.0, min(1.0, raw.get("confidence", 0.0))),
            information_completeness=max(
                0.0, min(1.0, raw.get("info_completeness", 0.0))
            ),
            risk_exposure=max(0.0, min(1.0, raw.get("risk", 0.0))),
            extra_dimensions={
                "money": float(raw.get("money", 0.0)),
                "time": float(raw.get("time", 0.0)),
                "production": float(raw.get("production", 0.0)),
            },
        )

    # ────────────────────────────────────────────────────────────────
    # PI control computation
    # ────────────────────────────────────────────────────────────────

    def _compute_pi_control(
        self,
        state: StateVector,
        target: StateVector,
    ) -> ControlVector:
        """Compute :class:`ControlVector` with PI integral accumulation.

        The proportional term comes from
        :meth:`ProportionalControlLaw.compute_control`.  The integral
        term accumulates per-dimension error across ticks, compensating
        for chronic drift that proportional-only control cannot
        eliminate.

        The integral error is stored in ``self._integral_error`` and
        persists across ticks (invariant: Ki accumulates).
        """
        # Proportional component via existing ControlLaw
        cv = self._control_law.compute_control(state, target)

        # Compute raw error for integral accumulation
        error = target.diff(state)
        for dim, err_val in error.items():
            prev = self._integral_error.get(dim, 0.0)
            self._integral_error[dim] = prev + err_val

        # Use integral to potentially activate additional actions
        # that pure proportional control would miss (chronic drift).
        integral_magnitude = sum(
            abs(v) for v in self._integral_error.values()
        )

        # If integral error is large, intensify action outputs
        if integral_magnitude > 0.5:
            ki_boost = min(1.0, self._ki * integral_magnitude)
            cv = ControlVector(
                ask_question=cv.ask_question,
                generate_candidates=cv.generate_candidates,
                evaluate_gate=cv.evaluate_gate,
                advance_phase=cv.advance_phase,
                request_human_intervention=cv.request_human_intervention,
                execute_action=cv.execute_action,
                question_weight=min(1.0, cv.question_weight + ki_boost * 0.5),
                action_intensity=min(1.0, cv.action_intensity + ki_boost * 0.5),
            )

        return cv

    # ────────────────────────────────────────────────────────────────
    # Action processing
    # ────────────────────────────────────────────────────────────────

    def _process_control_actions(
        self,
        cv: ControlVector,
        state_dict: Dict[str, Any],
        snap_id: str,
    ) -> List[WorkOrder]:
        """Convert activated :class:`ControlVector` actions into work orders.

        For each activated boolean field:
        a. Check ``FullAutomationController.should_auto_approve``
        b. If approved: checkpoint → execute → mark EXECUTED
        c. If not approved: mark PENDING_HITL
        """
        work_orders: List[WorkOrder] = []

        for action_field in _CV_ACTION_FIELDS:
            if not getattr(cv, action_field, False):
                continue

            risk_label = _ACTION_RISK.get(action_field, "low")
            context = {
                "state_snapshot_id": snap_id,
                "action_field": action_field,
                "risk_level": risk_label,
            }

            approved, reason = self._automation_controller.should_auto_approve(
                tenant_id=self._tenant_id,
                agent_id=None,
                action_type=action_field,
                context=context,
            )

            wo = WorkOrder(
                action_field=action_field,
                action_value=getattr(cv, action_field),
                risk_level=risk_label,
                approval_reason=reason,
            )

            if approved:
                # Checkpoint BEFORE execution (invariant)
                cp = self._persistence.recovery.record_state(
                    {"action": action_field, "snapshot_id": snap_id},
                    label=f"pre-exec-{action_field}",
                )
                wo.checkpoint_index = cp["index"]
                # Execute
                success = self._action_executor(wo)
                wo.status = (
                    WorkOrderStatus.EXECUTED if success
                    else WorkOrderStatus.REJECTED
                )
            else:
                wo.status = WorkOrderStatus.PENDING_HITL

            work_orders.append(wo)
            capped_append(self._work_orders, wo)

        return work_orders

    # ────────────────────────────────────────────────────────────────
    # Automation downgrade on oscillation
    # ────────────────────────────────────────────────────────────────

    def _downgrade_automation(self) -> None:
        """Downgrade automation mode when StabilityMonitor detects oscillation."""
        current = self._automation_controller.get_automation_mode(
            self._tenant_id, None,
        )
        if current == AutomationMode.FULL_AUTONOMOUS:
            self._automation_controller.set_automation_mode(
                tenant_id=self._tenant_id,
                agent_id=None,
                mode=AutomationMode.SEMI_AUTONOMOUS,
                user_id="heartbeat_runner",
                reason=AutomationToggleReason.RISK_THRESHOLD_EXCEEDED,
                user_role="admin",
            )
            logger.info("Automation downgraded FULL → SEMI due to oscillation")
        elif current == AutomationMode.SEMI_AUTONOMOUS:
            self._automation_controller.set_automation_mode(
                tenant_id=self._tenant_id,
                agent_id=None,
                mode=AutomationMode.MANUAL,
                user_id="heartbeat_runner",
                reason=AutomationToggleReason.RISK_THRESHOLD_EXCEEDED,
                user_role="admin",
            )
            logger.info("Automation downgraded SEMI → MANUAL due to oscillation")

    # ────────────────────────────────────────────────────────────────
    # Pulse emission
    # ────────────────────────────────────────────────────────────────

    def _emit_pulse(
        self,
        tick_num: int,
        status: TickStatus,
        control_vec: ControlVector,
        state_dict: Dict[str, Any],
        work_orders: List[WorkOrder],
    ) -> Dict[str, Any]:
        """Emit a heartbeat pulse with enriched directives.

        Pulse schema additions documented at the top of this module.
        """
        plan = self._business_plan
        ue = plan.unit_economics if plan else None

        auto_approved = sum(
            1 for wo in work_orders
            if wo.status == WorkOrderStatus.EXECUTED
        )
        pending_hitl = sum(
            1 for wo in work_orders
            if wo.status == WorkOrderStatus.PENDING_HITL
        )
        activated_actions = [
            f for f in _CV_ACTION_FIELDS if getattr(control_vec, f, False)
        ]

        current_mode = self._automation_controller.get_automation_mode(
            self._tenant_id, None,
        )

        integral_sum = sum(abs(v) for v in self._integral_error.values())

        directives = {
            "goal_coordinates": {
                "units_per_month": ue.units_per_month if ue else 0.0,
                "prospect_reach_needed": (
                    ue.prospect_reach_needed_per_month if ue else 0.0
                ),
                "units_remaining": plan.units_remaining if plan else 0.0,
                "months_remaining": plan.months_remaining if plan else 0.0,
                "on_track": plan.on_track if plan else False,
            },
            "control_actions": activated_actions,
            "automation_mode": (
                current_mode.value if current_mode else "unknown"
            ),
        }

        health_metrics = {
            "confidence_avg": state_dict.get("confidence", 0.0),
            "info_completeness_avg": state_dict.get("info_completeness", 0.0),
            "risk_max": state_dict.get("risk", 0.0),
            "agent_count": state_dict.get("agent_count", 0),
            "agents_executing": state_dict.get("agents_executing", 0),
            "agents_in_error": state_dict.get("agents_in_error", 0),
            "stability_reversals": self._stability_monitor.reversal_count,
        }

        metadata = {
            "tick_number": tick_num,
            "tick_status": status.value,
            "integral_error_sum": integral_sum,
            "work_orders_created": len(work_orders),
            "work_orders_auto_approved": auto_approved,
            "work_orders_pending_hitl": pending_hitl,
        }

        return self._heartbeat.emit_pulse(
            directives=directives,
            health_metrics=health_metrics,
            metadata=metadata,
        )

    # ────────────────────────────────────────────────────────────────
    # Audit / query helpers
    # ────────────────────────────────────────────────────────────────

    def _append_audit(self, record: TickRecord) -> None:
        """Append a tick record to the bounded audit log."""
        self._audit_log.append(record)
        if len(self._audit_log) > self._max_audit:
            self._audit_log = self._audit_log[-self._max_audit:]

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent *limit* tick records."""
        with self._lock:
            return [r.to_dict() for r in self._audit_log[-limit:]]

    def get_work_orders(
        self,
        status_filter: Optional[WorkOrderStatus] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return work orders, optionally filtered by status."""
        with self._lock:
            orders = self._work_orders
            if status_filter is not None:
                orders = [wo for wo in orders if wo.status == status_filter]
            return [wo.to_dict() for wo in orders[-limit:]]

    def get_integral_error(self) -> Dict[str, float]:
        """Return a copy of the current integral error accumulator."""
        with self._lock:
            return dict(self._integral_error)

    @property
    def tick_count(self) -> int:
        """Number of ticks executed so far."""
        return self._tick_count

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of the runner's current state."""
        with self._lock:
            ceo_status = (
                self._ceo_branch.get_status()
                if self._ceo_branch is not None
                else None
            )
            return {
                "running": self._running,
                "tick_count": self._tick_count,
                "tick_interval": self._tick_interval,
                "tenant_id": self._tenant_id,
                "has_business_plan": self._business_plan is not None,
                "integral_error_magnitude": sum(
                    abs(v) for v in self._integral_error.values()
                ),
                "audit_log_size": len(self._audit_log),
                "work_orders_total": len(self._work_orders),
                "ki": self._ki,
                "ceo_branch": ceo_status,
            }


__all__ = [
    "ActivatedHeartbeatRunner",
    "WorkOrder",
    "WorkOrderStatus",
    "TickRecord",
    "TickStatus",
]
