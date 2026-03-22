"""
HITL Task Queue — Human-in-the-loop review queue for form field validation.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

TIER_AUTO = "auto"
TIER_REVIEW = "needs_review"
TIER_BLOCKED = "blocked_human_required"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class HITLTask:
    task_id: str
    session_id: str
    application_id: str
    field_id: str
    tier: str
    value: Any
    confidence: float
    reasoning: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution: Optional[str] = None
    edited_value: Any = None


class HITLTaskQueue:
    def __init__(self) -> None:
        self._tasks: Dict[str, HITLTask] = {}

    def enqueue(
        self,
        session_id: str,
        application_id: str,
        field_id: str,
        tier: str,
        value: Any,
        confidence: float,
        reasoning: str,
    ) -> HITLTask:
        task_id = str(uuid.uuid4())
        task = HITLTask(
            task_id=task_id,
            session_id=session_id,
            application_id=application_id,
            field_id=field_id,
            tier=tier,
            value=value,
            confidence=confidence,
            reasoning=reasoning,
            created_at=_now(),
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[HITLTask]:
        return self._tasks.get(task_id)

    def get_tasks_for_application(self, application_id: str) -> List[HITLTask]:
        return [t for t in self._tasks.values() if t.application_id == application_id]

    def get_pending_review_tasks(self, application_id: str) -> List[HITLTask]:
        return [
            t for t in self._tasks.values()
            if t.application_id == application_id
            and t.tier in (TIER_REVIEW, TIER_BLOCKED)
            and t.resolution is None
        ]

    def resolve_task(
        self,
        task_id: str,
        resolver_id: str,
        resolution: str,
        edited_value: Any = None,
    ) -> Optional[HITLTask]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.resolved_at = _now()
        task.resolved_by = resolver_id
        task.resolution = resolution
        if edited_value is not None:
            task.edited_value = edited_value
        return task

    def get_queue_stats(self, application_id: str) -> Dict[str, int]:
        tasks = self.get_tasks_for_application(application_id)
        stats: Dict[str, int] = {
            TIER_AUTO: 0,
            TIER_REVIEW: 0,
            TIER_BLOCKED: 0,
            "resolved": 0,
            "pending": 0,
            "total": 0,
        }
        for task in tasks:
            stats["total"] += 1
            stats[task.tier] = stats.get(task.tier, 0) + 1
            if task.resolution is not None:
                stats["resolved"] += 1
            else:
                stats["pending"] += 1
        return stats
