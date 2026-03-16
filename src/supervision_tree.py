"""
Supervision Tree for the Murphy System.

Design Label: ARCH-013 — Erlang/OTP-Inspired Supervision Tree
Owner: Backend Team

Implements a hierarchical supervision model for Murphy's bot ecosystem,
inspired by Erlang/OTP supervision trees.  Failed components are restarted
according to the supervisor's strategy (ONE_FOR_ONE, ONE_FOR_ALL,
REST_FOR_ONE) with exponential backoff and escalation to parent supervisors.

Key concepts:
- RestartStrategy: ONE_FOR_ONE | ONE_FOR_ALL | REST_FOR_ONE
- SupervisionPolicy: configures restart limits, backoff, and escalation
- SupervisedComponent: a component with start/stop/health callables and status
- Supervisor: manages a group of components under a single policy,
  with optional parent for escalation chaining
- SupervisionTreeBuilder: fluent builder for constructing supervision trees

Thread-safe — all shared state protected by per-supervisor Locks.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RestartStrategy(Enum):
    """Restart strategy for a supervisor."""

    ONE_FOR_ONE = "one_for_one"
    """Restart only the failed component."""

    ONE_FOR_ALL = "one_for_all"
    """Restart all sibling components when one fails."""

    REST_FOR_ONE = "rest_for_one"
    """Restart the failed component and all components started after it."""


class ComponentStatus(Enum):
    """Lifecycle status of a supervised component."""

    RUNNING = "running"
    STOPPED = "stopped"
    RESTARTING = "restarting"
    FAILED = "failed"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SupervisionPolicy:
    """Configuration for a supervisor's restart behaviour."""

    strategy: RestartStrategy
    max_restarts: int = 3
    time_window_sec: float = 60.0
    backoff_base_sec: float = 1.0
    backoff_max_sec: float = 30.0
    escalate_after: int = 3


@dataclass
class SupervisedComponent:
    """A component managed by a supervisor."""

    component_id: str
    component_type: str  # "bot" | "service" | "coordinator" | "engine"
    start_fn: Callable[[], Any]
    stop_fn: Callable[[], Any]
    health_check_fn: Callable[[], bool]
    restart_count: int = 0
    last_restart_at: Optional[float] = None
    status: ComponentStatus = field(default=ComponentStatus.STOPPED)


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

class Supervisor:
    """
    Manages a group of SupervisedComponents under a single SupervisionPolicy.

    Responsibilities:
    - Start and stop components in registration order (reverse for stop)
    - Detect and handle failures using ONE_FOR_ONE, ONE_FOR_ALL, or
      REST_FOR_ONE strategies
    - Track restart counts within a rolling time window
    - Apply exponential backoff before each restart attempt
    - Escalate to a parent Supervisor when max_restarts is exceeded
    - Publish lifecycle events via EventBackbone when one is provided
    - Nest child Supervisors to form a tree

    Thread-safe via an internal Lock per Supervisor instance.
    """

    def __init__(
        self,
        supervisor_id: str,
        policy: SupervisionPolicy,
        parent: Optional["Supervisor"] = None,
        event_backbone: Any = None,
    ) -> None:
        self.supervisor_id = supervisor_id
        self.policy = policy
        self.parent = parent
        self._backbone = event_backbone

        self._components: List[SupervisedComponent] = []
        self._child_supervisors: List["Supervisor"] = []
        # Per-component restart timestamps for rolling window
        self._restart_history: Dict[str, List[float]] = {}
        # Consecutive failure counter (reset on successful restart)
        self._consecutive_failures: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._critical = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_child(self, component: SupervisedComponent) -> None:
        """Register a supervised component with this supervisor."""
        with self._lock:
            capped_append(self._components, component)
            self._restart_history.setdefault(component.component_id, [])
            self._consecutive_failures.setdefault(component.component_id, 0)

    def add_child_supervisor(self, supervisor: "Supervisor") -> None:
        """Attach a nested child supervisor, making this supervisor its parent."""
        supervisor.parent = self
        with self._lock:
            capped_append(self._child_supervisors, supervisor)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_all(self) -> None:
        """Start all registered components in registration order."""
        with self._lock:
            components = list(self._components)
        for component in components:
            self._start_component(component)
        for child_sup in self._child_supervisors:
            child_sup.start_all()

    def stop_all(self) -> None:
        """Stop all registered components in reverse registration order."""
        for child_sup in reversed(self._child_supervisors):
            child_sup.stop_all()
        with self._lock:
            components = list(reversed(self._components))
        for component in components:
            self._stop_component(component)

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def handle_failure(self, component_id: str, error: Exception) -> Dict[str, Any]:
        """
        Handle a component failure using the configured restart strategy.

        Steps:
        1. Locate the failing component
        2. Determine which components to restart per strategy
        3. Apply exponential backoff before restarting
        4. Restart each target component
        5. Track consecutive failures; escalate when threshold is reached
        6. Publish lifecycle events

        Returns a summary dict with keys: supervisor_id, strategy, restarts,
        escalated, error.
        """
        with self._lock:
            component = self._find_component(component_id)
            if component is None:
                logger.error(
                    "Supervisor %s: unknown component '%s'",
                    self.supervisor_id, component_id,
                )
                return {
                    "supervisor_id": self.supervisor_id,
                    "strategy": self.policy.strategy.value,
                    "restarts": {},
                    "escalated": True,
                    "error": str(error),
                }
            component.status = ComponentStatus.RESTARTING
            self._consecutive_failures[component_id] = (
                self._consecutive_failures.get(component_id, 0) + 1
            )
            consec = self._consecutive_failures[component_id]
            components_snapshot = list(self._components)

        # Determine targets based on strategy
        strategy = self.policy.strategy
        if strategy == RestartStrategy.ONE_FOR_ONE:
            targets = [component]
        elif strategy == RestartStrategy.ONE_FOR_ALL:
            targets = components_snapshot
        else:  # REST_FOR_ONE
            targets = self._rest_for_one_targets(component_id, components_snapshot)

        # Check restart budget (using the failing component's window)
        within_budget = self._within_restart_budget(component_id)

        restarts: Dict[str, bool] = {}
        escalated = False

        if not within_budget or consec >= self.policy.escalate_after:
            escalated = True
            with self._lock:
                component.status = ComponentStatus.ESCALATED
            self._publish_escalated(component_id, error)
            if self.parent is not None:
                logger.warning(
                    "Supervisor %s: escalating failure of '%s' to parent '%s'",
                    self.supervisor_id, component_id, self.parent.supervisor_id,
                )
                return self.parent.handle_failure(component_id, error)
            else:
                self._enter_critical(component_id, error)
                return {
                    "supervisor_id": self.supervisor_id,
                    "strategy": strategy.value,
                    "restarts": {},
                    "escalated": True,
                    "error": str(error),
                }

        # Apply exponential backoff before restarting
        backoff = self._compute_backoff(component_id)
        if backoff > 0:
            logger.debug(
                "Supervisor %s: backing off %.2fs before restarting '%s'",
                self.supervisor_id, backoff, component_id,
            )
            time.sleep(backoff)

        for target in targets:
            success = self._restart_component(target)
            restarts[target.component_id] = success

        logger.info(
            "Supervisor %s: handled failure of '%s' via %s — restarts: %s",
            self.supervisor_id, component_id, strategy.value, restarts,
        )
        return {
            "supervisor_id": self.supervisor_id,
            "strategy": strategy.value,
            "restarts": restarts,
            "escalated": escalated,
            "error": str(error),
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_tree_status(self) -> Dict[str, Any]:
        """Return a recursive health status of this supervisor and all children."""
        with self._lock:
            components_snapshot = list(self._components)
            child_sups_snapshot = list(self._child_supervisors)

        components_status = []
        for comp in components_snapshot:
            history = self._restart_history.get(comp.component_id, [])
            now = time.monotonic()
            recent = [t for t in history if now - t <= self.policy.time_window_sec]
            healthy = (
                comp.status == ComponentStatus.RUNNING
                and len(recent) < self.policy.max_restarts
            )
            components_status.append({
                "component_id": comp.component_id,
                "component_type": comp.component_type,
                "status": comp.status.value,
                "restart_count": comp.restart_count,
                "last_restart_at": comp.last_restart_at,
                "recent_restarts": len(recent),
                "healthy": healthy,
            })

        child_statuses = [cs.get_tree_status() for cs in child_sups_snapshot]

        return {
            "supervisor_id": self.supervisor_id,
            "strategy": self.policy.strategy.value,
            "critical": self._critical,
            "components": components_status,
            "child_supervisors": child_statuses,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_component(self, component_id: str) -> Optional[SupervisedComponent]:
        for comp in self._components:
            if comp.component_id == component_id:
                return comp
        return None

    def _within_restart_budget(self, component_id: str) -> bool:
        history = self._restart_history.get(component_id, [])
        now = time.monotonic()
        recent = [t for t in history if now - t <= self.policy.time_window_sec]
        return len(recent) < self.policy.max_restarts

    def _compute_backoff(self, component_id: str) -> float:
        history = self._restart_history.get(component_id, [])
        now = time.monotonic()
        recent_count = len([t for t in history if now - t <= self.policy.time_window_sec])
        if recent_count == 0:
            return 0.0
        raw = self.policy.backoff_base_sec * (2 ** (recent_count - 1))
        return min(raw, self.policy.backoff_max_sec)

    @staticmethod
    def _rest_for_one_targets(
        failed_id: str,
        components: List[SupervisedComponent],
    ) -> List[SupervisedComponent]:
        targets = []
        found = False
        for comp in components:
            if comp.component_id == failed_id:
                found = True
            if found:
                targets.append(comp)
        return targets

    def _start_component(self, component: SupervisedComponent) -> bool:
        try:
            component.start_fn()
            with self._lock:
                component.status = ComponentStatus.RUNNING
            self._publish(
                "SUPERVISOR_CHILD_STARTED",
                {"component_id": component.component_id,
                 "supervisor_id": self.supervisor_id},
            )
            logger.debug(
                "Supervisor %s: started '%s'", self.supervisor_id, component.component_id
            )
            return True
        except Exception as exc:
            logger.error(
                "Supervisor %s: failed to start '%s': %s",
                self.supervisor_id, component.component_id, exc,
            )
            with self._lock:
                component.status = ComponentStatus.FAILED
            return False

    def _stop_component(self, component: SupervisedComponent) -> bool:
        try:
            component.stop_fn()
            with self._lock:
                component.status = ComponentStatus.STOPPED
            self._publish(
                "SUPERVISOR_CHILD_STOPPED",
                {"component_id": component.component_id,
                 "supervisor_id": self.supervisor_id},
            )
            logger.debug(
                "Supervisor %s: stopped '%s'", self.supervisor_id, component.component_id
            )
            return True
        except Exception as exc:
            logger.error(
                "Supervisor %s: failed to stop '%s': %s",
                self.supervisor_id, component.component_id, exc,
            )
            return False

    def _restart_component(self, component: SupervisedComponent) -> bool:
        try:
            component.start_fn()
            now = time.monotonic()
            with self._lock:
                component.status = ComponentStatus.RUNNING
                component.restart_count += 1
                component.last_restart_at = now
                history = self._restart_history.setdefault(component.component_id, [])
                history.append(now)
                # Trim entries outside the rolling window
                self._restart_history[component.component_id] = [
                    t for t in history if now - t <= self.policy.time_window_sec
                ]
            self._publish(
                "SUPERVISOR_CHILD_RESTARTED",
                {"component_id": component.component_id,
                 "supervisor_id": self.supervisor_id,
                 "restart_count": component.restart_count},
            )
            logger.info(
                "Supervisor %s: restarted '%s' (total restarts: %d)",
                self.supervisor_id, component.component_id, component.restart_count,
            )
            return True
        except Exception as exc:
            logger.error(
                "Supervisor %s: failed to restart '%s': %s",
                self.supervisor_id, component.component_id, exc,
            )
            with self._lock:
                component.status = ComponentStatus.FAILED
            return False

    def _publish_escalated(self, component_id: str, error: Exception) -> None:
        self._publish(
            "SUPERVISOR_CHILD_ESCALATED",
            {"component_id": component_id,
             "supervisor_id": self.supervisor_id,
             "error": str(error)},
        )

    def _enter_critical(self, component_id: str, error: Exception) -> None:
        self._critical = True
        logger.critical(
            "Supervisor %s: CRITICAL — no parent to escalate '%s': %s",
            self.supervisor_id, component_id, error,
        )
        self._publish(
            "SUPERVISOR_CRITICAL",
            {"supervisor_id": self.supervisor_id,
             "component_id": component_id,
             "error": str(error)},
        )

    def _publish(self, event_type_str: str, payload: Dict[str, Any]) -> None:
        if self._backbone is None:
            return
        try:
            from event_backbone import Event, EventType  # noqa: PLC0415
            et = EventType(event_type_str.lower())
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=et,
                payload=payload,
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=f"supervisor:{self.supervisor_id}",
            )
            self._backbone.publish_event(event)
        except Exception as exc:
            logger.debug(
                "Supervisor %s: failed to publish event %s: %s",
                self.supervisor_id, event_type_str, exc,
            )


# ---------------------------------------------------------------------------
# SupervisionTreeBuilder — fluent API
# ---------------------------------------------------------------------------

class SupervisionTreeBuilder:
    """
    Fluent builder for constructing Supervisor hierarchies.

    Example::

        tree = (SupervisionTreeBuilder("root")
            .with_policy(SupervisionPolicy(
                strategy=RestartStrategy.ONE_FOR_ONE,
                max_restarts=5,
            ))
            .add_child("self_fix_loop",
                       component_type="engine",
                       start_fn=lambda: None,
                       stop_fn=lambda: None,
                       health_fn=lambda: True)
            .add_supervisor("bot_supervisor",
                            strategy=RestartStrategy.REST_FOR_ONE)
            .build())
    """

    def __init__(self, root_id: str) -> None:
        self._root_id = root_id
        self._policy: SupervisionPolicy = SupervisionPolicy(
            strategy=RestartStrategy.ONE_FOR_ONE
        )
        self._components: List[SupervisedComponent] = []
        self._child_builders: List["SupervisionTreeBuilder"] = []
        self._event_backbone: Any = None

    def with_policy(self, policy: SupervisionPolicy) -> "SupervisionTreeBuilder":
        """Set the supervision policy for this supervisor."""
        self._policy = policy
        return self

    def with_strategy(self, strategy: RestartStrategy) -> "SupervisionTreeBuilder":
        """Convenience shortcut to set only the restart strategy."""
        self._policy = SupervisionPolicy(strategy=strategy)
        return self

    def with_event_backbone(self, backbone: Any) -> "SupervisionTreeBuilder":
        """Attach an EventBackbone for event publishing."""
        self._event_backbone = backbone
        return self

    def add_child(
        self,
        component_id: str,
        start_fn: Callable[[], Any],
        stop_fn: Callable[[], Any],
        health_fn: Callable[[], bool],
        component_type: str = "service",
    ) -> "SupervisionTreeBuilder":
        """Register a supervised component with this supervisor."""
        capped_append(self._components,
            SupervisedComponent(
                component_id=component_id,
                component_type=component_type,
                start_fn=start_fn,
                stop_fn=stop_fn,
                health_check_fn=health_fn,
            )
        )
        return self

    def add_supervisor(
        self,
        supervisor_id: str,
        strategy: RestartStrategy = RestartStrategy.ONE_FOR_ONE,
        children: Optional[List[SupervisedComponent]] = None,
        policy: Optional[SupervisionPolicy] = None,
    ) -> "SupervisionTreeBuilder":
        """Add a nested child supervisor."""
        child_builder = SupervisionTreeBuilder(supervisor_id)
        if policy is not None:
            child_builder.with_policy(policy)
        else:
            child_builder.with_strategy(strategy)
        for comp in (children or []):
            child_builder._components.append(comp)
        if self._event_backbone is not None:
            child_builder._event_backbone = self._event_backbone
        capped_append(self._child_builders, child_builder)
        return self

    def build(self) -> "Supervisor":
        """Construct and return the root Supervisor with all children attached."""
        root = Supervisor(
            supervisor_id=self._root_id,
            policy=self._policy,
            event_backbone=self._event_backbone,
        )
        for comp in self._components:
            root.add_child(comp)
        for child_builder in self._child_builders:
            child_sup = child_builder.build()
            root.add_child_supervisor(child_sup)
        return root


# ---------------------------------------------------------------------------
# Backward-compatible aliases (retained for any code referencing old names)
# ---------------------------------------------------------------------------

#: Alias kept for backward compatibility
SupervisionStrategy = RestartStrategy

@dataclass
class ChildSpec:
    """Legacy dataclass retained for backward compatibility."""

    child_id: str
    start_fn: Callable[[], Any]
    restart_type: str = "permanent"
    max_restarts: int = 3
    max_restart_window_sec: float = 60.0


class SupervisorNode:
    """
    Legacy thin wrapper around Supervisor, retained for backward compatibility.

    New code should use Supervisor directly.
    """

    def __init__(
        self,
        supervisor_id: str,
        strategy: RestartStrategy,
        children: Optional[List[ChildSpec]] = None,
        parent_id: Optional[str] = None,
    ) -> None:
        self.supervisor_id = supervisor_id
        self.strategy = strategy
        self.parent_id = parent_id
        self._lock = threading.Lock()
        self._restart_history: Dict[str, List[float]] = {}

        self.children: List[ChildSpec] = []
        for spec in (children or []):
            self.add_child(spec)

    def _wrap_spec(self, spec: ChildSpec) -> SupervisedComponent:
        return SupervisedComponent(
            component_id=spec.child_id,
            component_type="service",
            start_fn=spec.start_fn,
            stop_fn=lambda: None,
            health_check_fn=lambda: True,
        )

    def _get_spec(self, child_id: str) -> Optional[ChildSpec]:
        for spec in self.children:
            if spec.child_id == child_id:
                return spec
        return None

    def _within_restart_budget(self, spec: ChildSpec) -> bool:
        history = self._restart_history.get(spec.child_id, [])
        now = time.monotonic()
        recent = [t for t in history if now - t <= spec.max_restart_window_sec]
        return len(recent) < spec.max_restarts

    def _do_restart(self, spec: ChildSpec) -> bool:
        try:
            spec.start_fn()
            now = time.monotonic()
            history = self._restart_history.setdefault(spec.child_id, [])
            history.append(now)
            self._restart_history[spec.child_id] = [
                t for t in history if now - t <= spec.max_restart_window_sec
            ]
            logger.info(
                "SupervisorNode %s: restarted child %s", self.supervisor_id, spec.child_id
            )
            return True
        except Exception as exc:
            logger.error(
                "SupervisorNode %s: failed to restart child %s: %s",
                self.supervisor_id, spec.child_id, exc,
            )
            return False

    def restart_child(self, child_id: str) -> bool:
        with self._lock:
            spec = self._get_spec(child_id)
            if spec is None:
                return False
            if not self._within_restart_budget(spec):
                raise RuntimeError(
                    f"Child '{child_id}' exceeded max_restarts={spec.max_restarts}"
                    f" within {spec.max_restart_window_sec}s"
                )
            return self._do_restart(spec)

    def restart_all(self) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        with self._lock:
            for spec in list(self.children):
                results[spec.child_id] = self._do_restart(spec)
        return results

    def add_child(self, spec: ChildSpec) -> None:
        with self._lock:
            self.children.append(spec)
            self._restart_history.setdefault(spec.child_id, [])

    def remove_child(self, child_id: str) -> None:
        with self._lock:
            self.children = [c for c in self.children if c.child_id != child_id]
            self._restart_history.pop(child_id, None)


class SupervisionTree:
    """
    Legacy root registry retained for backward compatibility.

    New code should use Supervisor / SupervisionTreeBuilder directly.
    """

    def __init__(self) -> None:
        self._supervisors: Dict[str, SupervisorNode] = {}
        self._child_to_supervisor: Dict[str, str] = {}
        self._lock = threading.Lock()

    def register_supervisor(self, node: SupervisorNode) -> None:
        with self._lock:
            self._supervisors[node.supervisor_id] = node
            for spec in node.children:
                self._child_to_supervisor[spec.child_id] = node.supervisor_id

    def handle_failure(self, failed_child_id: str, error: Exception) -> Dict[str, Any]:
        with self._lock:
            supervisor_id = self._child_to_supervisor.get(failed_child_id)
            if supervisor_id is None:
                return {
                    "supervisor_id": None,
                    "strategy": None,
                    "restarts": {},
                    "escalated": True,
                    "error": str(error),
                }
            supervisor = self._supervisors.get(supervisor_id)
            if supervisor is None:
                return {
                    "supervisor_id": supervisor_id,
                    "strategy": None,
                    "restarts": {},
                    "escalated": True,
                    "error": str(error),
                }

        strategy = supervisor.strategy
        restarts: Dict[str, bool] = {}

        try:
            if strategy == RestartStrategy.ONE_FOR_ONE:
                try:
                    restarts[failed_child_id] = supervisor.restart_child(failed_child_id)
                except RuntimeError as exc:
                    logger.error("ONE_FOR_ONE restart failed: %s", exc)
                    restarts[failed_child_id] = False
            elif strategy == RestartStrategy.ONE_FOR_ALL:
                restarts = supervisor.restart_all()
            elif strategy == RestartStrategy.REST_FOR_ONE:
                restarts = self._restart_from(supervisor, failed_child_id)
        except Exception as exc:
            logger.error("SupervisionTree.handle_failure: unexpected error: %s", exc)

        return {
            "supervisor_id": supervisor_id,
            "strategy": strategy.value,
            "restarts": restarts,
            "escalated": False,
            "error": str(error),
        }

    def get_tree_status(self) -> Dict[str, Any]:
        with self._lock:
            supervisors_snapshot = dict(self._supervisors)

        status: Dict[str, Any] = {}
        for sup_id, supervisor in supervisors_snapshot.items():
            children_status: List[Dict[str, Any]] = []
            with supervisor._lock:
                for spec in supervisor.children:
                    history = supervisor._restart_history.get(spec.child_id, [])
                    now = time.monotonic()
                    recent_restarts = [
                        t for t in history if now - t <= spec.max_restart_window_sec
                    ]
                    children_status.append({
                        "child_id": spec.child_id,
                        "restart_type": spec.restart_type,
                        "max_restarts": spec.max_restarts,
                        "recent_restarts": len(recent_restarts),
                        "healthy": len(recent_restarts) < spec.max_restarts,
                    })
            status[sup_id] = {
                "supervisor_id": sup_id,
                "strategy": supervisor.strategy.value,
                "parent_id": supervisor.parent_id,
                "children": children_status,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        return status

    @staticmethod
    def _restart_from(supervisor: SupervisorNode, failed_child_id: str) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        with supervisor._lock:
            children = list(supervisor.children)
        found = False
        for spec in children:
            if spec.child_id == failed_child_id:
                found = True
            if found:
                try:
                    results[spec.child_id] = supervisor.restart_child(spec.child_id)
                except RuntimeError as exc:
                    logger.error("REST_FOR_ONE restart failed for %s: %s", spec.child_id, exc)
                    results[spec.child_id] = False
        return results
