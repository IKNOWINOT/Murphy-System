"""
Recalibration Scheduler for Rosetta State Management.

Runs periodic recalibration cycles that analyze goals, tasks,
and automation progress for every known agent.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from .rosetta_manager import RosettaManager
from .rosetta_models import RecalibrationStatus

logger = logging.getLogger(__name__)


class RecalibrationScheduler:
    """Schedule and execute recalibration cycles for agents."""

    def __init__(
        self,
        manager: RosettaManager,
        interval_seconds: int = 604800,
    ) -> None:
        self._manager = manager
        self._interval = interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = Lock()
        self._stop_event = threading.Event()

    # ---- lifecycle ----

    def start(self) -> None:
        """Start the background recalibration loop."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop, daemon=True, name="rosetta-recalibration"
            )
            self._thread.start()
            logger.info("Recalibration scheduler started (interval=%ds)", self._interval)

    def stop(self) -> None:
        """Stop the background loop."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
        logger.info("Recalibration scheduler stopped")

    # ---- recalibration logic ----

    def run_recalibration(self, agent_id: str) -> Dict[str, Any]:
        """Run recalibration for a single agent.

        Analyses goal progress, identifies stuck tasks, and records findings.
        """
        state = self._manager.load_state(agent_id)
        if state is None:
            return {"agent_id": agent_id, "status": "not_found"}

        findings: List[str] = []

        # Analyse goals
        for goal in state.agent_state.active_goals:
            status = goal.status
            if isinstance(status, str):
                status_str = status
            else:
                status_str = status.value if hasattr(status, "value") else str(status)
            if status_str == "in_progress" and goal.progress_percent < 10:
                findings.append(f"Goal '{goal.title}' has low progress ({goal.progress_percent}%)")
            if status_str == "pending":
                findings.append(f"Goal '{goal.title}' is still pending")

        # Analyse tasks
        for task in state.agent_state.task_queue:
            task_status = task.status
            if isinstance(task_status, str):
                task_status_str = task_status
            else:
                task_status_str = task_status.value if hasattr(task_status, "value") else str(task_status)
            if task_status_str == "blocked":
                findings.append(f"Task '{task.title}' is blocked")
            if task_status_str == "failed":
                findings.append(f"Task '{task.title}' has failed")

        # Analyse automation progress
        for ap in state.automation_progress:
            if ap.total_items > 0 and ap.coverage_percent < 50:
                findings.append(
                    f"Automation category '{ap.category}' coverage is low ({ap.coverage_percent}%)"
                )

        # Update recalibration record
        state.recalibration.status = RecalibrationStatus.COMPLETED
        state.recalibration.last_run = datetime.now(timezone.utc)
        state.recalibration.next_scheduled = datetime.now(timezone.utc) + timedelta(
            seconds=self._interval
        )
        state.recalibration.cycle_count += 1
        state.recalibration.findings = findings

        self._manager.save_state(state)

        return {
            "agent_id": agent_id,
            "status": "completed",
            "cycle_count": state.recalibration.cycle_count,
            "findings": findings,
        }

    def run_all(self) -> Dict[str, Any]:
        """Run recalibration for every known agent."""
        agents = self._manager.list_agents()
        results: Dict[str, Any] = {}
        for agent_id in agents:
            results[agent_id] = self.run_recalibration(agent_id)
        return {
            "agents_processed": len(agents),
            "results": results,
        }

    def get_status(self) -> Dict[str, Any]:
        """Return scheduler status."""
        with self._lock:
            return {
                "running": self._running,
                "interval_seconds": self._interval,
            }

    # ---- internal ----

    def _loop(self) -> None:
        """Background loop that periodically calls ``run_all``."""
        while not self._stop_event.is_set():
            try:
                self.run_all()
            except Exception as exc:
                logger.debug("Suppressed exception: %s", exc)
                logger.exception("Recalibration loop error")
            self._stop_event.wait(timeout=self._interval)
