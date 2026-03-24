# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Wait-state handler: tracks tasks blocked on external parties (e.g. SAM.gov 10-day wait)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from .onboarding_session import OnboardingSession
from .task_catalog import TASK_CATALOG

_TASK_MAP = {t.task_id: t for t in TASK_CATALOG}


class WaitStateHandler:
    """Manages tasks that are waiting on external processes."""

    def mark_waiting(self, task_id: str, session: OnboardingSession) -> datetime:
        """Set task to waiting_on_external and return expected completion date."""
        task = _TASK_MAP.get(task_id)
        wait_days = (task.external_wait_days or 0) if task else 0
        expected = datetime.utcnow() + timedelta(days=wait_days)
        session.set_task_state(task_id, "waiting_on_external")
        session.wait_states[task_id] = expected
        return expected

    def get_waiting_tasks(self, session: OnboardingSession) -> List[Dict]:
        """Return all tasks in waiting state with days remaining."""
        now = datetime.utcnow()
        results = []
        for task_id, expected in session.wait_states.items():
            if session.get_task_state(task_id) == "waiting_on_external":
                days_remaining = max(0, (expected - now).days)
                task = _TASK_MAP.get(task_id)
                results.append({
                    "task_id": task_id,
                    "title": task.title if task else task_id,
                    "expected_completion": expected.isoformat(),
                    "days_remaining": days_remaining,
                    "overdue": now > expected,
                })
        return results

    def check_completion(self, task_id: str, session: OnboardingSession) -> bool:
        """Return True if the external wait period has elapsed."""
        expected = session.wait_states.get(task_id)
        if expected is None:
            return False
        return datetime.utcnow() >= expected

    def advance_to_unblocked(self, task_id: str, session: OnboardingSession) -> List[str]:
        """Complete wait, mark task done, return newly unblocked task IDs."""
        session.set_task_state(task_id, "completed")
        session.wait_states.pop(task_id, None)
        return self.cascade_unlock(task_id, session)

    def cascade_unlock(self, task_id: str, session: OnboardingSession) -> List[str]:
        """When a task completes, find all tasks whose dependencies are now satisfied."""
        task = _TASK_MAP.get(task_id)
        if not task:
            return []
        newly_unblocked: List[str] = []
        for blocked_id in task.blocks:
            if session.get_task_state(blocked_id) != "not_started":
                continue
            blocked_task = _TASK_MAP.get(blocked_id)
            if not blocked_task:
                continue
            if all(
                session.get_task_state(dep) == "completed"
                for dep in blocked_task.depends_on
            ):
                newly_unblocked.append(blocked_id)
        return newly_unblocked
