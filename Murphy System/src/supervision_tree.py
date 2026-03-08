"""
Supervision Tree for the Murphy System.

Design Label: ARCH-013 — Erlang/OTP-Inspired Supervision Tree
Owner: Backend Team

Implements a hierarchical supervision model for Murphy's bot ecosystem,
inspired by Erlang/OTP supervision trees.  Failed children are restarted
according to the supervisor's strategy (ONE_FOR_ONE, ONE_FOR_ALL,
REST_FOR_ONE).

Key concepts:
- ChildSpec: declares how a child process/callable should be started and
  restarted.
- SupervisorNode: manages a group of children under a single strategy.
- SupervisionTree: the root registry that maps failures to supervisors and
  executes the appropriate restart strategy.

Thread-safe — all shared state protected by a Lock.

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
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and data models
# ---------------------------------------------------------------------------

class SupervisionStrategy(Enum):
    """Restart strategy for a supervisor node."""

    ONE_FOR_ONE = "one_for_one"
    """Restart only the failed child."""

    ONE_FOR_ALL = "one_for_all"
    """Restart all children when one fails."""

    REST_FOR_ONE = "rest_for_one"
    """Restart the failed child and all children started after it."""


@dataclass
class ChildSpec:
    """Specification for a supervised child process/callable."""

    child_id: str
    start_fn: Callable[[], Any]
    restart_type: str = "permanent"  # "permanent" | "transient" | "temporary"
    max_restarts: int = 3
    max_restart_window_sec: float = 60.0


@dataclass
class SupervisorNode:
    """
    Manages a group of children under a single supervision strategy.

    Thread-safe via an internal lock.
    """

    supervisor_id: str
    strategy: SupervisionStrategy
    children: List[ChildSpec] = field(default_factory=list)
    parent_id: Optional[str] = None

    def __post_init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        # Restart history: child_id → list of restart timestamps
        self._restart_history: Dict[str, List[float]] = {}

    def restart_child(self, child_id: str) -> bool:
        """
        Restart a single child by its ID.

        Returns True if the child was restarted successfully.
        Raises RuntimeError if the child has exceeded its restart budget.
        """
        with self._lock:
            spec = self._get_spec(child_id)
            if spec is None:
                logger.warning(
                    "SupervisorNode %s: child %s not found", self.supervisor_id, child_id
                )
                return False

            if not self._within_restart_budget(spec):
                logger.error(
                    "SupervisorNode %s: child %s exceeded max_restarts (%d)",
                    self.supervisor_id,
                    child_id,
                    spec.max_restarts,
                )
                raise RuntimeError(
                    f"Child '{child_id}' exceeded max_restarts={spec.max_restarts}"
                    f" within {spec.max_restart_window_sec}s"
                )

            return self._do_restart(spec)

    def restart_all(self) -> Dict[str, bool]:
        """Restart every child managed by this supervisor."""
        results: Dict[str, bool] = {}
        with self._lock:
            for spec in list(self.children):
                results[spec.child_id] = self._do_restart(spec)
        return results

    def add_child(self, spec: ChildSpec) -> None:
        """Register a new child with this supervisor."""
        with self._lock:
            self.children.append(spec)
            self._restart_history.setdefault(spec.child_id, [])

    def remove_child(self, child_id: str) -> None:
        """Remove a child from this supervisor."""
        with self._lock:
            self.children = [c for c in self.children if c.child_id != child_id]
            self._restart_history.pop(child_id, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_spec(self, child_id: str) -> Optional[ChildSpec]:
        for spec in self.children:
            if spec.child_id == child_id:
                return spec
        return None

    def _within_restart_budget(self, spec: ChildSpec) -> bool:
        """Check whether restarting spec would exceed its budget."""
        history = self._restart_history.get(spec.child_id, [])
        now = time.monotonic()
        recent = [t for t in history if now - t <= spec.max_restart_window_sec]
        return len(recent) < spec.max_restarts

    def _do_restart(self, spec: ChildSpec) -> bool:
        """Actually invoke start_fn and record the attempt."""
        try:
            spec.start_fn()
            history = self._restart_history.setdefault(spec.child_id, [])
            history.append(time.monotonic())
            # Trim old entries
            now = time.monotonic()
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
                self.supervisor_id,
                spec.child_id,
                exc,
            )
            return False


# ---------------------------------------------------------------------------
# SupervisionTree
# ---------------------------------------------------------------------------

class SupervisionTree:
    """
    Root registry for all supervisor nodes.

    Maps children to their supervisors and applies the correct restart
    strategy when a failure is reported.

    Thread-safe — all shared state protected by a Lock.
    """

    def __init__(self) -> None:
        self._supervisors: Dict[str, SupervisorNode] = {}
        self._child_to_supervisor: Dict[str, str] = {}  # child_id → supervisor_id
        self._lock = threading.Lock()

    def register_supervisor(self, node: SupervisorNode) -> None:
        """Register a supervisor node and index all of its children."""
        with self._lock:
            self._supervisors[node.supervisor_id] = node
            for spec in node.children:
                self._child_to_supervisor[spec.child_id] = node.supervisor_id

    def handle_failure(
        self, failed_child_id: str, error: Exception
    ) -> Dict[str, Any]:
        """
        Look up the supervisor for the failed child and apply its restart strategy.

        Returns a dict with:
        - supervisor_id: which supervisor handled the failure
        - strategy: the strategy applied
        - restarts: Dict[child_id, bool] of restart outcomes
        - escalated: True if the failure was escalated (no supervisor found)
        """
        with self._lock:
            supervisor_id = self._child_to_supervisor.get(failed_child_id)
            if supervisor_id is None:
                logger.error(
                    "SupervisionTree: no supervisor for child '%s'", failed_child_id
                )
                return {
                    "supervisor_id": None,
                    "strategy": None,
                    "restarts": {},
                    "escalated": True,
                    "error": str(error),
                }

            supervisor = self._supervisors.get(supervisor_id)
            if supervisor is None:
                logger.error(
                    "SupervisionTree: supervisor '%s' not found", supervisor_id
                )
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
            if strategy == SupervisionStrategy.ONE_FOR_ONE:
                try:
                    restarts[failed_child_id] = supervisor.restart_child(failed_child_id)
                except RuntimeError as exc:
                    logger.error("ONE_FOR_ONE restart failed: %s", exc)
                    restarts[failed_child_id] = False

            elif strategy == SupervisionStrategy.ONE_FOR_ALL:
                restarts = supervisor.restart_all()

            elif strategy == SupervisionStrategy.REST_FOR_ONE:
                restarts = self._restart_from(supervisor, failed_child_id)

        except Exception as exc:
            logger.error(
                "SupervisionTree.handle_failure: unexpected error: %s", exc
            )

        logger.info(
            "SupervisionTree: handled failure of '%s' via %s — restarts: %s",
            failed_child_id,
            strategy.value,
            restarts,
        )

        return {
            "supervisor_id": supervisor_id,
            "strategy": strategy.value,
            "restarts": restarts,
            "escalated": False,
            "error": str(error),
        }

    def get_tree_status(self) -> Dict[str, Any]:
        """Return a hierarchical health report of all supervisors and children."""
        with self._lock:
            supervisors_snapshot = dict(self._supervisors)

        status: Dict[str, Any] = {}
        for sup_id, supervisor in supervisors_snapshot.items():
            children_status: List[Dict[str, Any]] = []
            with supervisor._lock:
                for spec in supervisor.children:
                    history = supervisor._restart_history.get(spec.child_id, [])
                    now = time.monotonic()
                    recent_restarts = [t for t in history if now - t <= spec.max_restart_window_sec]
                    children_status.append(
                        {
                            "child_id": spec.child_id,
                            "restart_type": spec.restart_type,
                            "max_restarts": spec.max_restarts,
                            "recent_restarts": len(recent_restarts),
                            "healthy": len(recent_restarts) < spec.max_restarts,
                        }
                    )
            status[sup_id] = {
                "supervisor_id": sup_id,
                "strategy": supervisor.strategy.value,
                "parent_id": supervisor.parent_id,
                "children": children_status,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        return status

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _restart_from(
        supervisor: SupervisorNode, failed_child_id: str
    ) -> Dict[str, bool]:
        """
        REST_FOR_ONE: restart the failed child and all children registered after it.
        """
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
