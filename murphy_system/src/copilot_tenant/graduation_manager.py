# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Copilot Tenant — Graduation Manager (Mode Progression)

Manages task-level and system-level mode progression.  Wraps:
  - src/hitl_graduation_engine.py
  - src/graduation_controller.py
  - src/hitl_autonomy_controller.py

Rules:
  - Tasks must maintain >90% suggestion accuracy for 30 days before supervised
  - Tasks must have 0 rollbacks in supervised for 30 days before autonomous
  - Safety-critical tasks NEVER graduate past supervised
  - Emergency stop always available regardless of mode
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports
# ---------------------------------------------------------------------------

try:
    from hitl_graduation_engine import HITLGraduationEngine, GRADUATION_THRESHOLD
    _GRADUATION_ENGINE_AVAILABLE = True
except Exception:  # pragma: no cover
    HITLGraduationEngine = None  # type: ignore[assignment,misc]
    GRADUATION_THRESHOLD = 0.85  # fallback constant
    _GRADUATION_ENGINE_AVAILABLE = False

try:
    from hitl_autonomy_controller import HITLAutonomyController
    _AUTONOMY_CONTROLLER_AVAILABLE = True
except Exception:  # pragma: no cover
    HITLAutonomyController = None  # type: ignore[assignment,misc]
    _AUTONOMY_CONTROLLER_AVAILABLE = False

# Lazy import to avoid circular dependencies
_CopilotTenantMode: Any = None


def _get_mode_enum() -> Any:
    global _CopilotTenantMode
    if _CopilotTenantMode is None:
        from copilot_tenant.tenant_agent import CopilotTenantMode
        _CopilotTenantMode = CopilotTenantMode
    return _CopilotTenantMode


# ---------------------------------------------------------------------------
# GraduationManager
# ---------------------------------------------------------------------------

class GraduationManager:
    """Manages task-level and system-level mode progression for the Copilot Tenant.

    ``NEVER_GRADUATE`` tasks are locked at supervised and will never be
    promoted to autonomous.
    """

    NEVER_GRADUATE: Set[str] = {
        "finance",
        "trading",
        "social_media_posting",
        "release_deployment",
        "legal_compliance",
    }
    GRADUATION_THRESHOLD: float = 0.90
    GRADUATION_OBSERVATION_DAYS: int = 30

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._task_modes: Dict[str, str] = {}       # task_type → current mode
        self._task_metrics: Dict[str, Dict[str, Any]] = {}
        self._engine: Any  = None
        self._controller: Any = None
        self._initialize()

    def _initialize(self) -> None:
        if _GRADUATION_ENGINE_AVAILABLE:
            try:
                self._engine = HITLGraduationEngine()
            except Exception as exc:
                logger.debug("HITLGraduationEngine init failed: %s", exc)
        if _AUTONOMY_CONTROLLER_AVAILABLE:
            try:
                self._controller = HITLAutonomyController()
            except Exception as exc:
                logger.debug("HITLAutonomyController init failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_task_graduation(self, task_type: str) -> Optional[Any]:
        """Return the next CopilotTenantMode the task should be promoted to, or None.

        Returns None if the task should stay at its current mode.
        """
        CopilotTenantMode = _get_mode_enum()
        if task_type in self.NEVER_GRADUATE:
            # Safety-critical tasks cap at SUPERVISED
            with self._lock:
                current = self._task_modes.get(task_type, CopilotTenantMode.OBSERVER.value)
            if current in (CopilotTenantMode.OBSERVER.value, CopilotTenantMode.SUGGESTION.value):
                return CopilotTenantMode.SUPERVISED
            return None
        with self._lock:
            metrics = self._task_metrics.get(task_type, {})
            current = self._task_modes.get(task_type, CopilotTenantMode.OBSERVER.value)
        accuracy = metrics.get("accuracy", 0.0)
        obs_days = metrics.get("observation_days", 0)
        rollbacks = metrics.get("rollbacks", 0)
        if current == CopilotTenantMode.OBSERVER.value:
            return CopilotTenantMode.SUGGESTION
        if current == CopilotTenantMode.SUGGESTION.value:
            if accuracy >= self.GRADUATION_THRESHOLD and obs_days >= self.GRADUATION_OBSERVATION_DAYS:
                return CopilotTenantMode.SUPERVISED
        if current == CopilotTenantMode.SUPERVISED.value:
            if rollbacks == 0 and obs_days >= self.GRADUATION_OBSERVATION_DAYS:
                return CopilotTenantMode.AUTONOMOUS
        return None

    def promote_task(self, task_type: str, new_mode: Any) -> bool:
        """Promote *task_type* to *new_mode*.

        Refuses to promote safety-critical tasks beyond SUPERVISED.

        Returns True on success, False if the promotion was blocked.
        """
        CopilotTenantMode = _get_mode_enum()
        if (task_type in self.NEVER_GRADUATE
                and new_mode == CopilotTenantMode.AUTONOMOUS):
            logger.warning(
                "GraduationManager: BLOCKED promotion of %s to autonomous (safety-critical)",
                task_type,
            )
            return False
        with self._lock:
            self._task_modes[task_type] = new_mode.value if hasattr(new_mode, "value") else str(new_mode)
        logger.info("GraduationManager: promoted %s → %s", task_type, new_mode)
        return True

    def update_task_metrics(
        self,
        task_type: str,
        *,
        accuracy: Optional[float] = None,
        observation_days: Optional[int] = None,
        rollbacks: Optional[int] = None,
    ) -> None:
        """Update the graduation metrics for a task type."""
        with self._lock:
            m = self._task_metrics.setdefault(task_type, {
                "accuracy": 0.0,
                "observation_days": 0,
                "rollbacks": 0,
            })
            if accuracy is not None:
                m["accuracy"] = accuracy
            if observation_days is not None:
                m["observation_days"] = observation_days
            if rollbacks is not None:
                m["rollbacks"] = rollbacks

    def get_graduation_report(self) -> Dict[str, Any]:
        """Return a full graduation status report for all tracked tasks."""
        CopilotTenantMode = _get_mode_enum()
        with self._lock:
            tasks = {
                t: {
                    "current_mode":  self._task_modes.get(t, CopilotTenantMode.OBSERVER.value),
                    "metrics":       self._task_metrics.get(t, {}),
                    "never_graduate": t in self.NEVER_GRADUATE,
                }
                for t in set(list(self._task_modes.keys()) + list(self._task_metrics.keys()))
            }
        return {
            "generated_at":              datetime.now(timezone.utc).isoformat(),
            "graduation_threshold":      self.GRADUATION_THRESHOLD,
            "observation_days_required": self.GRADUATION_OBSERVATION_DAYS,
            "never_graduate_set":        list(self.NEVER_GRADUATE),
            "tasks":                     tasks,
        }
