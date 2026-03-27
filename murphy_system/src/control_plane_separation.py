"""
Control Plane Separation for Murphy System Runtime

This module implements planning-plane / execution-plane separation,
providing clear boundaries between reasoning and enforcement:
- Planning plane: reasoning, decomposition, gate synthesis, compliance proposal generation
- Execution plane: policy enforcement, permission validation, budget enforcement,
  escalation routing, audit logging
- Runtime mode switching (strict, balanced, dynamic)
- Handler registration for each plane
- Task routing through the appropriate plane based on mode and type
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class PlaneType(str, Enum):
    """Identifies which control plane a handler or task belongs to."""
    PLANNING = "planning"
    EXECUTION = "execution"


class RuntimeMode(str, Enum):
    """Runtime mode governing how tasks are routed between planes."""
    STRICT = "strict"
    BALANCED = "balanced"
    DYNAMIC = "dynamic"


PLANNING_TASK_TYPES = frozenset([
    "reasoning",
    "decomposition",
    "gate_synthesis",
    "compliance_proposal",
])


@dataclass
class PlaneHandler:
    """A registered handler for a specific control plane."""
    handler_id: str
    plane: PlaneType
    name: str
    capabilities: List[str]
    registered_at: datetime


@dataclass
class PlaneRoutingResult:
    """The outcome of routing a single task to a control plane."""
    task_id: str
    routed_to: PlaneType
    mode: RuntimeMode
    handler_id: str
    reason: str
    timestamp: datetime


class ControlPlaneSeparation:
    """Separates planning from execution with configurable routing modes.

    Manages handler registration, task routing, and provides auditable
    routing history for all decisions made by the control plane.
    """

    def __init__(self, mode: RuntimeMode = RuntimeMode.BALANCED) -> None:
        self._lock = threading.Lock()
        self._mode: RuntimeMode = mode
        self._handlers: Dict[str, PlaneHandler] = {}
        self._routing_history: List[PlaneRoutingResult] = []

        # Pre-register default handlers
        self.register_handler(
            PlaneType.PLANNING,
            "default_planning_handler",
            ["reasoning", "decomposition", "gate_synthesis", "compliance_proposal"],
        )
        self.register_handler(
            PlaneType.EXECUTION,
            "default_execution_handler",
            ["policy_enforcement", "permission_validation", "budget_enforcement", "audit_logging"],
        )

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def set_mode(self, mode: RuntimeMode) -> None:
        """Switch the runtime routing mode."""
        with self._lock:
            self._mode = mode
        logger.info("Runtime mode set to %s", mode.value)

    def get_mode(self) -> RuntimeMode:
        """Return the current runtime routing mode."""
        with self._lock:
            return self._mode

    # ------------------------------------------------------------------
    # Handler registration
    # ------------------------------------------------------------------

    def register_handler(self, plane: PlaneType, name: str, capabilities: List[str]) -> str:
        """Register a handler for the given plane and return its handler_id."""
        handler_id = f"{plane.value}-{uuid.uuid4().hex[:8]}"
        handler = PlaneHandler(
            handler_id=handler_id,
            plane=plane,
            name=name,
            capabilities=list(capabilities),
            registered_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._handlers[handler_id] = handler
        logger.info("Registered handler %s (%s) on %s plane", handler_id, name, plane.value)
        return handler_id

    # ------------------------------------------------------------------
    # Task routing
    # ------------------------------------------------------------------

    def route_task(self, task_id: str, task_type: str, context: Optional[Dict] = None) -> PlaneRoutingResult:
        """Route a task to the appropriate plane based on mode and type."""
        context = context or {}

        with self._lock:
            mode = self._mode
            handlers = dict(self._handlers)

        target_plane, reason = self._resolve_plane(mode, task_type, context)
        handler_id, final_plane, final_reason = self._select_handler(
            target_plane, handlers, reason,
        )

        result = PlaneRoutingResult(
            task_id=task_id,
            routed_to=final_plane,
            mode=mode,
            handler_id=handler_id,
            reason=final_reason,
            timestamp=datetime.now(timezone.utc),
        )

        with self._lock:
            capped_append(self._routing_history, result)

        logger.info(
            "Routed task %s to %s plane (mode=%s, reason=%s)",
            task_id, final_plane.value, mode.value, final_reason,
        )
        return result

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_handlers(self, plane: Optional[PlaneType] = None) -> List[PlaneHandler]:
        """Return registered handlers, optionally filtered by plane."""
        with self._lock:
            all_handlers = list(self._handlers.values())
        if plane is not None:
            return [h for h in all_handlers if h.plane == plane]
        return all_handlers

    def get_routing_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent routing results as dictionaries."""
        with self._lock:
            recent = list(self._routing_history[-limit:])
        return [
            {
                "task_id": r.task_id,
                "routed_to": r.routed_to.value,
                "mode": r.mode.value,
                "handler_id": r.handler_id,
                "reason": r.reason,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in recent
        ]

    def get_status(self) -> Dict[str, Any]:
        """Return current control-plane status."""
        with self._lock:
            mode = self._mode
            total_handlers = len(self._handlers)
            planning_count = sum(1 for h in self._handlers.values() if h.plane == PlaneType.PLANNING)
            execution_count = sum(1 for h in self._handlers.values() if h.plane == PlaneType.EXECUTION)
            total_routed = len(self._routing_history)

        return {
            "mode": mode.value,
            "total_handlers": total_handlers,
            "planning_handlers": planning_count,
            "execution_handlers": execution_count,
            "total_routed_tasks": total_routed,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_plane(mode: RuntimeMode, task_type: str, context: Dict) -> tuple:
        """Determine the target plane and reason based on mode rules."""
        if mode == RuntimeMode.STRICT:
            if context.get("approved") is True:
                return PlaneType.EXECUTION, "strict_approved"
            return PlaneType.PLANNING, "strict_requires_approval"

        if mode == RuntimeMode.BALANCED:
            if task_type in PLANNING_TASK_TYPES:
                return PlaneType.PLANNING, "balanced_planning_type"
            return PlaneType.EXECUTION, "balanced_execution_type"

        # DYNAMIC
        confidence = context.get("confidence", 0.0)
        if isinstance(confidence, (int, float)) and confidence >= 0.95:
            return PlaneType.EXECUTION, "dynamic_high_confidence"
        return PlaneType.PLANNING, "dynamic_low_confidence"

    @staticmethod
    def _select_handler(
        target_plane: PlaneType,
        handlers: Dict[str, PlaneHandler],
        reason: str,
    ) -> tuple:
        """Pick a handler on *target_plane*; fall back to the other plane if none exists."""
        candidates = [h for h in handlers.values() if h.plane == target_plane]
        if candidates:
            chosen = candidates[0]
            return chosen.handler_id, target_plane, reason

        # Fallback to opposite plane
        other_plane = (
            PlaneType.EXECUTION if target_plane == PlaneType.PLANNING else PlaneType.PLANNING
        )
        fallback_candidates = [h for h in handlers.values() if h.plane == other_plane]
        if fallback_candidates:
            chosen = fallback_candidates[0]
            return chosen.handler_id, other_plane, "fallback"

        # No handlers at all
        return "none", target_plane, "no_handlers"
