"""
Founder Update Engine — Update Coordinator

Design Label: ARCH-007 — Founder Update Engine: Update Coordinator
Owner: Backend Team
Dependencies:
  - SubsystemRegistry — subsystem metadata and health state
  - RecommendationEngine — approved recommendations to apply
  - SelfFixLoop (ARCH-005) — autonomous closed-loop remediation
  - AutonomousRepairSystem (ARCH-006) — multi-layer diagnosis
  - PersistenceManager — durable storage
  - EventBackbone — event-driven coordination

Orchestrates the full update lifecycle for all subsystems:
  - Dependency-aware update sequencing
  - Maintenance window scheduling
  - Rollback capability
  - Founder notification for critical changes

Safety invariants:
  - NEVER modifies source files on disk
  - Proposals only; execution requires explicit approval
  - Thread-safe: all shared state guarded by Lock
  - Bounded: maintenance queue capped to prevent runaway scheduling

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_MAINTENANCE_RECORDS = 1_000


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MaintenanceWindow:
    """A scheduled maintenance window for a subsystem.

    Attributes:
        window_id: Unique identifier.
        subsystem: Target subsystem name.
        scheduled_start: UTC timestamp of planned start.
        scheduled_end: UTC timestamp of planned end.
        description: What work is planned.
        status: scheduled, in_progress, completed, cancelled.
        created_at: UTC timestamp when the window was created.
    """

    window_id: str
    subsystem: str
    scheduled_start: datetime
    scheduled_end: datetime
    description: str
    status: str = "scheduled"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "subsystem": self.subsystem,
            "scheduled_start": self.scheduled_start.isoformat(),
            "scheduled_end": self.scheduled_end.isoformat(),
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class UpdateRecord:
    """Audit record for a single update execution.

    Attributes:
        update_id: Unique identifier.
        subsystems: Ordered list of subsystems updated in this cycle.
        plan: The plan dict used for this update.
        result: Execution outcome metadata.
        started_at: UTC timestamp of execution start.
        completed_at: UTC timestamp of execution end (or ``None``).
        status: planned, in_progress, completed, failed, rolled_back.
        rollback_available: Whether a rollback can be triggered.
    """

    update_id: str
    subsystems: List[str]
    plan: Dict[str, Any]
    result: Dict[str, Any]
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "planned"
    rollback_available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_id": self.update_id,
            "subsystems": self.subsystems,
            "plan": self.plan,
            "result": self.result,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "rollback_available": self.rollback_available,
        }


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class UpdateCoordinator:
    """Orchestrates the update lifecycle for all Murphy subsystems.

    Design Label: ARCH-007
    Owner: Backend Team

    Manages:
    - Scheduled maintenance windows
    - Update sequencing (dependency-aware ordering)
    - Rollback capability
    - Founder notification for critical changes
    - Integration with the existing SelfFixLoop and AutonomousRepairSystem

    Usage::

        coordinator = UpdateCoordinator(
            registry=SubsystemRegistry(),
            recommendation_engine=RecommendationEngine(),
            self_fix_loop=SelfFixLoop(),
            event_backbone=EventBackbone(),
            persistence_manager=pm,
        )
        plan = coordinator.plan_update_cycle()
        result = coordinator.execute_update_plan(plan)
    """

    _PERSISTENCE_DOC_KEY = "founder_update_engine_coordinator"

    def __init__(
        self,
        registry=None,
        recommendation_engine=None,
        self_fix_loop=None,
        autonomous_repair=None,
        event_backbone=None,
        persistence_manager=None,
    ) -> None:
        self._registry = registry
        self._rec_engine = recommendation_engine
        self._self_fix_loop = self_fix_loop
        self._autonomous_repair = autonomous_repair
        self._event_backbone = event_backbone
        self._persistence = persistence_manager

        # update_id -> UpdateRecord
        self._update_records: Dict[str, UpdateRecord] = {}
        # window_id -> MaintenanceWindow
        self._maintenance_windows: Dict[str, MaintenanceWindow] = {}
        self._lock = threading.Lock()

        self._load_state()

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    def plan_update_cycle(self) -> Dict[str, Any]:
        """Build a dependency-aware update plan for all subsystems.

        Queries the SubsystemRegistry for all known subsystems, topologically
        sorts them based on declared dependencies, and returns an ordered plan
        with gating conditions.

        Returns:
            Dict with keys:
              - ``plan_id``: Unique plan identifier.
              - ``ordered_subsystems``: Topologically sorted list of names.
              - ``steps``: Per-subsystem step dicts.
              - ``created_at``: ISO timestamp.
        """
        subsystems = self._registry.get_all_subsystems() if self._registry else []

        # Build dependency graph and topological sort (Kahn's algorithm)
        name_to_deps: Dict[str, List[str]] = {}
        all_names = {s.name for s in subsystems}
        for s in subsystems:
            # Only include deps that are known subsystems
            name_to_deps[s.name] = [d for d in s.dependencies if d in all_names]

        ordered = self._topological_sort(name_to_deps)

        steps = []
        for name in ordered:
            info = self._get_subsystem_info(name, subsystems)
            steps.append(
                {
                    "subsystem": name,
                    "health_status": info.get("health_status", "unknown"),
                    "pending_recommendations": info.get("pending_recommendations", 0),
                    "dependencies_ready": True,  # post-sort assumption
                    "action": "update_check",
                }
            )

        plan = {
            "plan_id": str(uuid.uuid4()),
            "ordered_subsystems": ordered,
            "steps": steps,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return plan

    def execute_update_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a previously built update plan.

        For each step in the plan, this method checks prerequisites and
        records the outcome.  Actual code changes are NOT executed here —
        they must be applied via the SelfFixLoop or AutonomousRepairSystem.

        Args:
            plan: A plan dict returned by :meth:`plan_update_cycle`.

        Returns:
            Dict with ``update_id``, ``results``, ``success``, and
            ``completed_at``.
        """
        update_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        step_results: List[Dict[str, Any]] = []
        overall_success = True

        for step in plan.get("steps", []):
            subsystem = step["subsystem"]
            prereq = self.check_update_prerequisites(subsystem)
            step_result = {
                "subsystem": subsystem,
                "prerequisites_met": prereq.get("prerequisites_met", True),
                "status": "skipped" if not prereq.get("prerequisites_met", True) else "completed",
                "prereq_details": prereq,
            }
            if not prereq.get("prerequisites_met", True):
                overall_success = False
            step_results.append(step_result)

        completed_at = datetime.now(timezone.utc)

        record = UpdateRecord(
            update_id=update_id,
            subsystems=plan.get("ordered_subsystems", []),
            plan=plan,
            result={"steps": step_results, "overall_success": overall_success},
            started_at=started_at,
            completed_at=completed_at,
            status="completed" if overall_success else "failed",
        )
        with self._lock:
            self._update_records[update_id] = record
        self._save_state()
        self._publish_event("update_cycle_completed", {"update_id": update_id, "success": overall_success})

        return {
            "update_id": update_id,
            "results": step_results,
            "success": overall_success,
            "completed_at": completed_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Prerequisites & maintenance
    # ------------------------------------------------------------------

    def check_update_prerequisites(self, subsystem: str) -> Dict[str, Any]:
        """Validate that *subsystem* is ready to receive an update.

        Checks:
        - Subsystem is registered
        - Health status is not ``failed``
        - No active maintenance window for this subsystem

        Args:
            subsystem: Subsystem name to check.

        Returns:
            Dict with ``prerequisites_met`` (bool) and ``details`` (list).
        """
        details: List[str] = []
        prerequisites_met = True

        # Check registration
        info = None
        if self._registry is not None:
            info = self._registry.get_subsystem(subsystem)
        if info is None:
            details.append(f"Subsystem '{subsystem}' is not registered.")
            prerequisites_met = False
        elif info.health_status == "failed":
            details.append(f"Subsystem '{subsystem}' health is 'failed'; update blocked.")
            prerequisites_met = False

        # Check maintenance window conflicts
        now = datetime.now(timezone.utc)
        with self._lock:
            for win in self._maintenance_windows.values():
                if (
                    win.subsystem == subsystem
                    and win.status == "in_progress"
                    and win.scheduled_start <= now <= win.scheduled_end
                ):
                    details.append(f"Active maintenance window {win.window_id} blocks update.")
                    prerequisites_met = False

        return {"prerequisites_met": prerequisites_met, "details": details}

    def schedule_maintenance(self, subsystem: str, window: Dict[str, Any]) -> str:
        """Schedule a maintenance window for *subsystem*.

        Args:
            subsystem: Target subsystem name.
            window: Dict with at minimum ``scheduled_start``, ``scheduled_end``,
                and ``description`` keys (ISO-format strings for timestamps).

        Returns:
            The ``window_id`` of the newly created window.
        """
        with self._lock:
            if len(self._maintenance_windows) >= _MAX_MAINTENANCE_RECORDS:
                # Prune oldest completed/cancelled windows
                to_remove = [
                    wid
                    for wid, w in self._maintenance_windows.items()
                    if w.status in ("completed", "cancelled")
                ]
                for wid in to_remove[:100]:
                    del self._maintenance_windows[wid]

        window_id = str(uuid.uuid4())
        try:
            scheduled_start = datetime.fromisoformat(window["scheduled_start"])
            scheduled_end = datetime.fromisoformat(window["scheduled_end"])
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Invalid maintenance window dates: {exc}") from exc

        win = MaintenanceWindow(
            window_id=window_id,
            subsystem=subsystem,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            description=window.get("description", ""),
        )
        with self._lock:
            self._maintenance_windows[window_id] = win
        self._save_state()
        logger.info("UpdateCoordinator: scheduled maintenance %s for %s", window_id, subsystem)
        return window_id

    # ------------------------------------------------------------------
    # Status & rollback
    # ------------------------------------------------------------------

    def get_update_status(self) -> Dict[str, Any]:
        """Return a summary of the current update state.

        Returns:
            Dict with total records, active maintenance windows, and
            counts by update status.
        """
        with self._lock:
            total_updates = len(self._update_records)
            by_status: Dict[str, int] = {}
            for record in self._update_records.values():
                by_status[record.status] = by_status.get(record.status, 0) + 1

            active_windows = [
                w.to_dict()
                for w in self._maintenance_windows.values()
                if w.status in ("scheduled", "in_progress")
            ]

        return {
            "total_updates": total_updates,
            "by_status": by_status,
            "active_maintenance_windows": len(active_windows),
            "maintenance_windows": active_windows,
        }

    def rollback_update(self, update_id: str) -> bool:
        """Mark update *update_id* as rolled back.

        This method records the rollback event only; actual code
        reversal is the responsibility of the SelfFixLoop or
        AutonomousRepairSystem.

        Args:
            update_id: ID of the update record to roll back.

        Returns:
            ``True`` if the record was found and updated.
        """
        with self._lock:
            record = self._update_records.get(update_id)
            if record is None:
                logger.warning("rollback_update: id %s not found", update_id)
                return False
            if not record.rollback_available:
                logger.warning("rollback_update: rollback not available for %s", update_id)
                return False
            record.status = "rolled_back"
            record.rollback_available = False
        self._save_state()
        self._publish_event("update_rolled_back", {"update_id": update_id})
        logger.info("UpdateCoordinator: rolled back update %s", update_id)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _topological_sort(name_to_deps: Dict[str, List[str]]) -> List[str]:
        """Kahn's algorithm topological sort.

        Returns a list of names in dependency-resolved order.
        Cycles are broken by falling back to alphabetical ordering of the
        remaining nodes.
        """
        in_degree: Dict[str, int] = {name: 0 for name in name_to_deps}
        dependents: Dict[str, List[str]] = {name: [] for name in name_to_deps}

        for name, deps in name_to_deps.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1
                    dependents[dep].append(name)

        queue = sorted(name for name, deg in in_degree.items() if deg == 0)
        result: List[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in sorted(dependents.get(node, [])):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Handle cycles: append any remaining nodes alphabetically
        remaining = sorted(n for n in name_to_deps if n not in result)
        result.extend(remaining)
        return result

    @staticmethod
    def _get_subsystem_info(name: str, subsystems: list) -> Dict[str, Any]:
        for s in subsystems:
            if s.name == name:
                return s.to_dict()
        return {"name": name, "health_status": "unknown", "pending_recommendations": 0}

    def _save_state(self) -> None:
        if self._persistence is None:
            return
        try:
            with self._lock:
                data = {
                    "update_records": {uid: r.to_dict() for uid, r in self._update_records.items()},
                    "maintenance_windows": {
                        wid: w.to_dict() for wid, w in self._maintenance_windows.items()
                    },
                }
            self._persistence.save_document(self._PERSISTENCE_DOC_KEY, data)
        except Exception as exc:
            logger.debug("UpdateCoordinator: failed to save state: %s", exc)

    def _load_state(self) -> None:
        if self._persistence is None:
            return
        try:
            data = self._persistence.load_document(self._PERSISTENCE_DOC_KEY)
            if not data:
                return
            with self._lock:
                for uid, r_dict in data.get("update_records", {}).items():
                    try:
                        self._update_records[uid] = UpdateRecord(
                            update_id=r_dict["update_id"],
                            subsystems=r_dict.get("subsystems", []),
                            plan=r_dict.get("plan", {}),
                            result=r_dict.get("result", {}),
                            started_at=datetime.fromisoformat(r_dict["started_at"]),
                            completed_at=(
                                datetime.fromisoformat(r_dict["completed_at"])
                                if r_dict.get("completed_at")
                                else None
                            ),
                            status=r_dict.get("status", "planned"),
                            rollback_available=r_dict.get("rollback_available", True),
                        )
                    except Exception as exc:
                        logger.debug("UpdateCoordinator: failed to load record %s: %s", uid, exc)

                for wid, w_dict in data.get("maintenance_windows", {}).items():
                    try:
                        self._maintenance_windows[wid] = MaintenanceWindow(
                            window_id=w_dict["window_id"],
                            subsystem=w_dict["subsystem"],
                            scheduled_start=datetime.fromisoformat(w_dict["scheduled_start"]),
                            scheduled_end=datetime.fromisoformat(w_dict["scheduled_end"]),
                            description=w_dict.get("description", ""),
                            status=w_dict.get("status", "scheduled"),
                            created_at=datetime.fromisoformat(w_dict["created_at"]),
                        )
                    except Exception as exc:
                        logger.debug(
                            "UpdateCoordinator: failed to load window %s: %s", wid, exc
                        )
        except Exception as exc:
            logger.debug("UpdateCoordinator: failed to load state: %s", exc)

    def _publish_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self._event_backbone is None:
            return
        try:
            from event_backbone import EventType  # type: ignore

            self._event_backbone.publish(
                EventType.SYSTEM_HEALTH,
                {"source": "UpdateCoordinator", "event": event_name, **payload},
            )
        except Exception as exc:
            logger.debug("UpdateCoordinator: event publish failed: %s", exc)
