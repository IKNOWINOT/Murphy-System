"""
Pulse controller for real-time autonomous robot coordination.

The PulseController is the Murphy robotics "nervous system" coordinator. It
runs robot control as a deterministic phase clock instead of allowing an agent
or LLM to issue actuator commands directly. Each pulse advances one phase:

* SCAN       -- refresh sensor/world state, like eyes and proprioception.
* FLOW       -- update working memory and route observations to agent logic.
* CONSTRAINT -- apply safety gates before any physical actuation.
* ACTION     -- dispatch only commands that survived the constraint phase.

This pattern is intentionally small and dependency-free so it can run in tests,
simulation, or on constrained robot hardware. Integrations with ROS, PiCar-X,
SLAM, learned policies, telemetry, and fleet tools can be attached through
callbacks and adapters without changing the core timing model.
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Event, Lock, Thread
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Protocol

from robotics.actuator_engine import ActuatorEngine
from robotics.robot_registry import RobotRegistry
from robotics.robotics_models import ActuatorCommand, ActuatorResult, RobotStatus, SensorReading
from robotics.sensor_engine import SensorEngine


class PulsePhase(str, Enum):
    """Controller phases mapped to the user's jump-rope clock metaphor."""

    ACTION = "action"          # 12 o'clock: perform approved work.
    FLOW = "flow"              # 3 o'clock: route information through memory/agents.
    SCAN = "scan"              # 6 o'clock: refresh perception/world state.
    CONSTRAINT = "constraint"  # 9 o'clock: safety and policy gate.


class CommandStatus(str, Enum):
    """Lifecycle state of a queued robot command."""

    QUEUED = "queued"
    APPROVED = "approved"
    BLOCKED = "blocked"
    EXECUTED = "executed"
    FAILED = "failed"


@dataclass
class PulseConfig:
    """Runtime configuration for the pulse loop."""

    tick_hz: float = 4.0
    stale_sensor_seconds: float = 2.0
    max_commands_per_action_phase: int = 1
    max_history: int = 500
    auto_connect: bool = True
    require_fresh_scan_before_action: bool = True

    def __post_init__(self) -> None:
        if self.tick_hz <= 0:
            raise ValueError("tick_hz must be greater than zero")
        if self.stale_sensor_seconds <= 0:
            raise ValueError("stale_sensor_seconds must be greater than zero")
        if self.max_commands_per_action_phase <= 0:
            raise ValueError("max_commands_per_action_phase must be greater than zero")
        if self.max_history <= 0:
            raise ValueError("max_history must be greater than zero")


@dataclass
class PulseContext:
    """Shared state passed through phase hooks and safety checks."""

    tick: int = 0
    phase: PulsePhase = PulsePhase.SCAN
    robot_ids: List[str] = field(default_factory=list)
    sensor_cache: Dict[str, SensorReading] = field(default_factory=dict)
    memory: Dict[str, Any] = field(default_factory=dict)
    last_scan_monotonic: float = 0.0
    last_action_monotonic: float = 0.0
    emergency_stop: bool = False
    diagnostics: List[str] = field(default_factory=list)


@dataclass
class QueuedCommand:
    """A command submitted by an AI agent, planner, or external service."""

    command: ActuatorCommand
    command_id: str = ""
    source: str = "agent"
    priority: int = 50
    status: CommandStatus = CommandStatus.QUEUED
    reason: str = ""
    submitted_at: float = 0.0
    approved_at: Optional[float] = None
    executed_at: Optional[float] = None
    result: Optional[ActuatorResult] = None

    def __post_init__(self) -> None:
        if not self.command_id:
            self.command_id = f"cmd_{uuid.uuid4().hex[:8]}"
        if self.submitted_at == 0.0:
            self.submitted_at = time.monotonic()


@dataclass
class PulseReport:
    """Observable report emitted after each controller phase."""

    tick: int
    phase: PulsePhase
    queued_commands: int
    approved_commands: int
    executed_commands: int
    blocked_commands: int
    emergency_stop: bool
    diagnostics: List[str] = field(default_factory=list)


class SafetyRule(Protocol):
    """Callable safety rule. Return a block reason, or None to allow."""

    def __call__(self, queued: QueuedCommand, context: PulseContext) -> Optional[str]: ...


PhaseHook = Callable[[PulseContext], None]


class PulseController:
    """Deterministic pulse-loop coordinator for autonomous robot control.

    The controller deliberately separates cognition from actuation. Agents can
    observe context through FLOW hooks and submit command intents through
    :meth:`submit_command`, but the controller only executes commands during the
    ACTION phase after the CONSTRAINT phase has approved them.
    """

    _PHASE_RING = (
        PulsePhase.SCAN,
        PulsePhase.FLOW,
        PulsePhase.CONSTRAINT,
        PulsePhase.ACTION,
    )

    def __init__(
        self,
        registry: RobotRegistry,
        sensor_engine: Optional[SensorEngine] = None,
        actuator_engine: Optional[ActuatorEngine] = None,
        config: Optional[PulseConfig] = None,
    ) -> None:
        self.registry = registry
        self.sensor_engine = sensor_engine or SensorEngine(registry)
        self.actuator_engine = actuator_engine or ActuatorEngine(registry)
        self.config = config or PulseConfig()
        self.context = PulseContext()
        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._pending: Deque[QueuedCommand] = deque()
        self._approved: Deque[QueuedCommand] = deque()
        self._history: Deque[QueuedCommand] = deque(maxlen=self.config.max_history)
        self._reports: Deque[PulseReport] = deque(maxlen=self.config.max_history)
        self._hooks: Dict[PulsePhase, List[PhaseHook]] = {phase: [] for phase in PulsePhase}
        self._safety_rules: List[SafetyRule] = [self._default_safety_rule]

    # ------------------------------------------------------------------
    # Public command, hook, and safety APIs
    # ------------------------------------------------------------------

    def submit_command(
        self,
        command: ActuatorCommand,
        *,
        source: str = "agent",
        priority: int = 50,
    ) -> str:
        """Queue a command intent for later constraint-gated execution."""
        queued = QueuedCommand(command=command, source=source, priority=priority)
        with self._lock:
            self._pending.append(queued)
            self._pending = deque(sorted(self._pending, key=lambda item: item.priority))
        return queued.command_id

    def add_phase_hook(self, phase: PulsePhase, hook: PhaseHook) -> None:
        """Run *hook* whenever *phase* is processed."""
        with self._lock:
            self._hooks[phase].append(hook)

    def add_safety_rule(self, rule: SafetyRule) -> None:
        """Add a custom safety/constraint rule.

        Rules are evaluated during CONSTRAINT. A rule blocks a command by
        returning a human-readable reason; returning None approves evaluation to
        continue to the next rule.
        """
        with self._lock:
            self._safety_rules.append(rule)

    def set_memory(self, key: str, value: Any) -> None:
        """Store controller-level working memory used by agents and rules."""
        with self._lock:
            self.context.memory[key] = value

    def request_emergency_stop(self, reason: str = "Emergency stop requested") -> Dict[str, bool]:
        """Immediately stop all known clients and block future actions."""
        with self._lock:
            self.context.emergency_stop = True
            self.context.diagnostics.append(reason)
            self._block_all_pending_locked(reason)
        return self.registry.emergency_stop_all()

    def clear_emergency_stop(self) -> None:
        """Clear the software emergency-stop latch after human/operator review."""
        with self._lock:
            self.context.emergency_stop = False
            self.context.diagnostics.append("Emergency stop cleared")

    # ------------------------------------------------------------------
    # Pulse execution APIs
    # ------------------------------------------------------------------

    def step(self, phase: Optional[PulsePhase] = None) -> PulseReport:
        """Run one pulse phase and return an observable report."""
        with self._lock:
            selected_phase = phase or self._PHASE_RING[self.context.tick % len(self._PHASE_RING)]
            self.context.phase = selected_phase
            self.context.tick += 1

        if selected_phase == PulsePhase.SCAN:
            self._scan_phase()
        elif selected_phase == PulsePhase.FLOW:
            self._flow_phase()
        elif selected_phase == PulsePhase.CONSTRAINT:
            self._constraint_phase()
        elif selected_phase == PulsePhase.ACTION:
            self._action_phase()

        return self._build_report(selected_phase)

    def run_forever(self) -> None:
        """Run the pulse loop until :meth:`stop` is called."""
        self._stop_event.clear()
        interval = 1.0 / self.config.tick_hz
        while not self._stop_event.is_set():
            started = time.monotonic()
            self.step()
            elapsed = time.monotonic() - started
            self._stop_event.wait(max(0.0, interval - elapsed))

    def start_background(self) -> None:
        """Start the pulse loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(target=self.run_forever, name="robot-pulse-controller", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop a background loop if one is running."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Introspection APIs
    # ------------------------------------------------------------------

    def get_context_snapshot(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of current controller state."""
        with self._lock:
            return {
                "tick": self.context.tick,
                "phase": self.context.phase.value,
                "robot_ids": list(self.context.robot_ids),
                "sensor_cache_keys": list(self.context.sensor_cache.keys()),
                "memory": dict(self.context.memory),
                "last_scan_monotonic": self.context.last_scan_monotonic,
                "last_action_monotonic": self.context.last_action_monotonic,
                "emergency_stop": self.context.emergency_stop,
                "diagnostics": list(self.context.diagnostics[-20:]),
                "pending_commands": len(self._pending),
                "approved_commands": len(self._approved),
                "history_count": len(self._history),
            }

    def get_command_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent queued command states as dictionaries."""
        with self._lock:
            items = list(self._history)[-limit:]
        return [self._command_to_dict(item) for item in items]

    def get_reports(self, limit: int = 100) -> List[PulseReport]:
        """Return recent pulse reports."""
        with self._lock:
            return list(self._reports)[-limit:]

    # ------------------------------------------------------------------
    # Phase internals
    # ------------------------------------------------------------------

    def _scan_phase(self) -> None:
        readings: Dict[str, SensorReading] = {}
        diagnostics: List[str] = []
        robots = self.registry.list_robots()
        for robot in robots:
            if self.config.auto_connect:
                client = self.registry.get_client(robot.robot_id)
                if client and client.status == RobotStatus.DISCONNECTED:
                    try:
                        client.connect()
                    except Exception as exc:  # pragma: no cover - defensive hardware boundary
                        diagnostics.append(f"connect failed for {robot.robot_id}: {exc}")
            try:
                for reading in self.sensor_engine.read_all_sensors(robot.robot_id):
                    readings[f"{reading.robot_id}:{reading.sensor_id}"] = reading
            except Exception as exc:
                diagnostics.append(f"scan failed for {robot.robot_id}: {exc}")

        with self._lock:
            self.context.robot_ids = [robot.robot_id for robot in robots]
            self.context.sensor_cache.update(readings)
            self.context.last_scan_monotonic = time.monotonic()
            self.context.diagnostics.extend(diagnostics)
        self._run_hooks(PulsePhase.SCAN)

    def _flow_phase(self) -> None:
        with self._lock:
            self.context.memory["pending_commands"] = len(self._pending)
            self.context.memory["approved_commands"] = len(self._approved)
            self.context.memory["known_sensor_count"] = len(self.context.sensor_cache)
            self.context.memory["known_robot_count"] = len(self.context.robot_ids)
        self._run_hooks(PulsePhase.FLOW)

    def _constraint_phase(self) -> None:
        with self._lock:
            pending = list(self._pending)
            self._pending.clear()
            rules = list(self._safety_rules)

        for queued in pending:
            block_reason = self._evaluate_rules(queued, rules)
            with self._lock:
                if block_reason:
                    queued.status = CommandStatus.BLOCKED
                    queued.reason = block_reason
                    self._history.append(queued)
                    self.context.diagnostics.append(f"blocked {queued.command_id}: {block_reason}")
                else:
                    queued.status = CommandStatus.APPROVED
                    queued.reason = "approved"
                    queued.approved_at = time.monotonic()
                    self._approved.append(queued)
        self._run_hooks(PulsePhase.CONSTRAINT)

    def _action_phase(self) -> None:
        executed = 0
        while executed < self.config.max_commands_per_action_phase:
            with self._lock:
                if not self._approved:
                    break
                queued = self._approved.popleft()
            try:
                queued.result = self.actuator_engine.execute(queued.command)
                queued.status = CommandStatus.EXECUTED if queued.result.success else CommandStatus.FAILED
                queued.executed_at = time.monotonic()
                queued.reason = queued.result.message or queued.status.value
            except Exception as exc:
                queued.status = CommandStatus.FAILED
                queued.reason = str(exc)
            with self._lock:
                self._history.append(queued)
                self.context.last_action_monotonic = time.monotonic()
            executed += 1
        self._run_hooks(PulsePhase.ACTION)

    # ------------------------------------------------------------------
    # Safety and helper internals
    # ------------------------------------------------------------------

    def _default_safety_rule(self, queued: QueuedCommand, context: PulseContext) -> Optional[str]:
        if context.emergency_stop:
            return "software emergency stop is active"
        if queued.command.robot_id not in context.robot_ids:
            return f"unknown or unscanned robot: {queued.command.robot_id}"
        if self.config.require_fresh_scan_before_action:
            age = time.monotonic() - context.last_scan_monotonic if context.last_scan_monotonic else float("inf")
            if age > self.config.stale_sensor_seconds:
                return f"sensor scan is stale: {age:.3f}s old"
        client = self.registry.get_client(queued.command.robot_id)
        if client is None:
            return f"no protocol client for robot: {queued.command.robot_id}"
        if client.status in {RobotStatus.DISCONNECTED, RobotStatus.ERROR, RobotStatus.EMERGENCY_STOP}:
            return f"robot status blocks action: {client.status.value}"
        if queued.command.timeout_seconds <= 0:
            return "command timeout must be positive"
        return None

    def _evaluate_rules(self, queued: QueuedCommand, rules: Iterable[SafetyRule]) -> Optional[str]:
        with self._lock:
            snapshot = PulseContext(
                tick=self.context.tick,
                phase=self.context.phase,
                robot_ids=list(self.context.robot_ids),
                sensor_cache=dict(self.context.sensor_cache),
                memory=dict(self.context.memory),
                last_scan_monotonic=self.context.last_scan_monotonic,
                last_action_monotonic=self.context.last_action_monotonic,
                emergency_stop=self.context.emergency_stop,
                diagnostics=list(self.context.diagnostics),
            )
        for rule in rules:
            reason = rule(queued, snapshot)
            if reason:
                return reason
        return None

    def _run_hooks(self, phase: PulsePhase) -> None:
        with self._lock:
            hooks = list(self._hooks[phase])
        for hook in hooks:
            try:
                hook(self.context)
            except Exception as exc:  # pragma: no cover - defensive callback boundary
                with self._lock:
                    self.context.diagnostics.append(f"{phase.value} hook failed: {exc}")

    def _build_report(self, phase: PulsePhase) -> PulseReport:
        with self._lock:
            history = list(self._history)
            report = PulseReport(
                tick=self.context.tick,
                phase=phase,
                queued_commands=len(self._pending),
                approved_commands=len(self._approved),
                executed_commands=sum(1 for item in history if item.status == CommandStatus.EXECUTED),
                blocked_commands=sum(1 for item in history if item.status == CommandStatus.BLOCKED),
                emergency_stop=self.context.emergency_stop,
                diagnostics=list(self.context.diagnostics[-20:]),
            )
            self._reports.append(report)
            return report

    def _block_all_pending_locked(self, reason: str) -> None:
        for queue in (self._pending, self._approved):
            while queue:
                queued = queue.popleft()
                queued.status = CommandStatus.BLOCKED
                queued.reason = reason
                self._history.append(queued)

    @staticmethod
    def _command_to_dict(item: QueuedCommand) -> Dict[str, Any]:
        return {
            "command_id": item.command_id,
            "source": item.source,
            "priority": item.priority,
            "status": item.status.value,
            "reason": item.reason,
            "robot_id": item.command.robot_id,
            "actuator_id": item.command.actuator_id,
            "command_type": item.command.command_type,
            "parameters": dict(item.command.parameters),
            "submitted_at": item.submitted_at,
            "approved_at": item.approved_at,
            "executed_at": item.executed_at,
            "result": item.result.model_dump() if item.result is not None else None,
        }
