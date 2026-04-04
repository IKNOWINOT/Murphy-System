# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""BAS-006 · Sequence of Operations engine.

Store, execute, and audit SOO scripts on a per-zone basis.  Each script
is a list of conditional steps that are evaluated and acted upon in order.

Thread-safe: engine state guarded by RLock; capped audit log.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
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
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SOOStep:
    """A single step in a sequence-of-operations script."""

    step_id: str = field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    description: str = ""
    condition: Callable[..., bool] = field(default_factory=lambda: (lambda ctx: True))
    action: Callable[..., Dict[str, Any]] = field(
        default_factory=lambda: (lambda ctx: {})
    )
    timeout_seconds: float = 30.0


@dataclass
class SOOScript:
    """Named, versioned sequence of operations for a zone."""

    script_id: str = field(default_factory=lambda: f"soo-{uuid.uuid4().hex[:12]}")
    name: str = ""
    zone_id: str = ""
    steps: List[SOOStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    version: int = 1


@dataclass
class SOOExecutionResult:
    """Outcome of executing an SOO script."""

    script_id: str = ""
    zone_id: str = ""
    steps_executed: int = 0
    steps_failed: int = 0
    started_at: float = 0.0
    completed_at: float = 0.0
    results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "script_id": self.script_id,
            "zone_id": self.zone_id,
            "steps_executed": self.steps_executed,
            "steps_failed": self.steps_failed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "results": list(self.results),
        }


# ---------------------------------------------------------------------------
# SOO Engine
# ---------------------------------------------------------------------------


class SOOEngine:
    """Register, execute, and audit sequence-of-operations scripts."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._scripts: Dict[str, SOOScript] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # -- Registration -------------------------------------------------------

    def register_script(self, script: SOOScript) -> None:
        with self._lock:
            self._scripts[script.script_id] = script
            logger.info("SOO registered: %s (%s)", script.name, script.script_id)

    # -- Execution ----------------------------------------------------------

    def execute_script(
        self,
        script_id: str,
        context: Dict[str, Any],
    ) -> SOOExecutionResult:
        """Run all steps of *script_id* in order, recording outcomes."""
        with self._lock:
            script = self._scripts.get(script_id)
            if script is None:
                logger.error("SOO script not found: %s", script_id)
                return SOOExecutionResult(
                    script_id=script_id,
                    started_at=time.time(),
                    completed_at=time.time(),
                    results=[{"error": "script_not_found"}],
                )

        started = time.time()
        executed = 0
        failed = 0
        step_results: List[Dict[str, Any]] = []

        for step in script.steps:
            step_record: Dict[str, Any] = {
                "step_id": step.step_id,
                "description": step.description,
            }
            try:
                cond = step.condition(context)
                step_record["condition_met"] = cond
                if cond:
                    result = step.action(context)
                    step_record["action_result"] = result
                    executed += 1
                else:
                    step_record["action_result"] = "skipped"
            except Exception as exc:
                logger.exception("SOO step %s failed", step.step_id)
                step_record["error"] = str(exc)
                failed += 1
            step_results.append(step_record)

        completed = time.time()

        execution_result = SOOExecutionResult(
            script_id=script_id,
            zone_id=script.zone_id,
            steps_executed=executed,
            steps_failed=failed,
            started_at=started,
            completed_at=completed,
            results=step_results,
        )

        with self._lock:
            capped_append(self._audit_log, {
                "ts": completed,
                "script_id": script_id,
                "zone_id": script.zone_id,
                "executed": executed,
                "failed": failed,
            })

        return execution_result

    # -- Queries ------------------------------------------------------------

    def list_scripts(self, zone_id: Optional[str] = None) -> List[SOOScript]:
        with self._lock:
            if zone_id is None:
                return list(self._scripts.values())
            return [s for s in self._scripts.values() if s.zone_id == zone_id]

    def get_audit_log(
        self,
        script_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            entries = self._audit_log
            if script_id is not None:
                entries = [e for e in entries if e.get("script_id") == script_id]
            return entries[-limit:]
