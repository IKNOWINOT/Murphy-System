# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Progress tracker: computes completion metrics and identifies unblocked tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .onboarding_session import OnboardingSession
from .priority_scorer import PriorityScorer
from .task_catalog import TASK_CATALOG, OnboardingTask

_TASK_MAP = {t.task_id: t for t in TASK_CATALOG}
_TOTAL = len(TASK_CATALOG)
_scorer = PriorityScorer()


@dataclass
class OnboardingProgress:
    total_tasks: int = _TOTAL
    completed: int = 0
    in_progress: int = 0
    waiting_on_external: int = 0
    blocked: int = 0
    not_started: int = 0
    completion_percentage: float = 0.0
    estimated_remaining_hours: float = 0.0
    next_recommended_tasks: List[str] = field(default_factory=list)  # top-5 task_ids
    recently_unlocked: List[str] = field(default_factory=list)
    value_captured: str = "$0"
    value_pending: str = "$0"


class ProgressTracker:
    """Computes progress metrics over an OnboardingSession."""

    def compute_progress(self, session: OnboardingSession) -> OnboardingProgress:
        completed = in_progress = waiting = blocked = not_started = 0
        remaining_minutes = 0.0

        for task in TASK_CATALOG:
            state = session.get_task_state(task.task_id)
            if state == "completed":
                completed += 1
            elif state == "in_progress":
                in_progress += 1
                remaining_minutes += task.time_estimate_minutes
            elif state == "waiting_on_external":
                waiting += 1
            elif state == "skipped":
                pass  # skipped don't count in remaining
            else:
                # not_started — check if it's actually blocked
                deps_done = all(
                    session.get_task_state(d) in ("completed", "skipped")
                    for d in task.depends_on
                )
                if not deps_done and task.depends_on:
                    blocked += 1
                else:
                    not_started += 1
                remaining_minutes += task.time_estimate_minutes

        pct = (completed / _TOTAL * 100) if _TOTAL > 0 else 0.0

        unblocked = self.get_unblocked_tasks(session)
        scored = _scorer.score_tasks(unblocked, session.session_data)
        next_5 = [t.task_id for t, _ in scored[:5]]

        prog = OnboardingProgress(
            total_tasks=_TOTAL,
            completed=completed,
            in_progress=in_progress,
            waiting_on_external=waiting,
            blocked=blocked,
            not_started=not_started,
            completion_percentage=round(pct, 2),
            estimated_remaining_hours=round(remaining_minutes / 60, 2),
            next_recommended_tasks=next_5,
            recently_unlocked=[],
            value_captured="$0",
            value_pending="$0",
        )
        return prog

    def get_unblocked_tasks(self, session: OnboardingSession) -> List[OnboardingTask]:
        """Return tasks whose dependencies are all completed/skipped and are not yet started."""
        unblocked = []
        for task in TASK_CATALOG:
            state = session.get_task_state(task.task_id)
            if state not in ("not_started", ""):
                continue
            deps_satisfied = all(
                session.get_task_state(dep) in ("completed", "skipped")
                for dep in task.depends_on
            )
            if deps_satisfied:
                unblocked.append(task)
        return unblocked

    def get_critical_path(self) -> List[str]:
        """Return the critical dependency chain for maximum grant access."""
        return ["1.02", "1.01", "1.03", "1.05", "2.01"]

    def get_parallel_groups(self) -> Dict[int, List[str]]:
        """Return tasks grouped by dependency level (0 = no deps, 1 = depends on level 0, etc.)."""
        levels: Dict[str, int] = {}

        def compute_level(task_id: str) -> int:
            if task_id in levels:
                return levels[task_id]
            task = _TASK_MAP.get(task_id)
            if not task or not task.depends_on:
                levels[task_id] = 0
                return 0
            lvl = 1 + max(compute_level(d) for d in task.depends_on)
            levels[task_id] = lvl
            return lvl

        for task in TASK_CATALOG:
            compute_level(task.task_id)

        groups: Dict[int, List[str]] = {}
        for tid, lvl in levels.items():
            groups.setdefault(lvl, []).append(tid)
        return groups
