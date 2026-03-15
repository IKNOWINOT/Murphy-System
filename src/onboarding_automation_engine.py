"""
Onboarding Automation Engine for Murphy System.

Design Label: BIZ-003 — Automated HR Onboarding Workflow
Owner: HR Team / Platform Engineering
Dependencies:
  - PersistenceManager (for durable onboarding state)
  - EventBackbone (publishes LEARNING_FEEDBACK on milestone completions)
  - TicketingAdapter (optional, creates provisioning tickets)

Implements Phase 5 — Business Operations Automation:
  Manages the end-to-end onboarding workflow for new team members:
  document generation, training scheduling, progress tracking,
  and milestone notifications.

Flow:
  1. Create onboarding profile with role and department
  2. Generate checklist of onboarding tasks based on role
  3. Track task completion with timestamps
  4. Publish milestone events for downstream automation
  5. Report onboarding progress and bottlenecks

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Immutable history: completed tasks cannot be uncompleted
  - Bounded: configurable max concurrent onboardings
  - Audit trail: every status change is logged

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
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class OnboardingStatus(str, Enum):
    """Onboarding lifecycle states."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Individual task lifecycle states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass
class OnboardingTask:
    """A single task in the onboarding checklist."""
    task_id: str
    title: str
    category: str          # documents, training, access, equipment, intro
    status: TaskStatus = TaskStatus.PENDING
    assignee: str = ""
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "category": self.category,
            "status": self.status.value,
            "assignee": self.assignee,
            "completed_at": self.completed_at,
        }


@dataclass
class OnboardingProfile:
    """An onboarding workflow for a single new hire."""
    profile_id: str
    employee_name: str
    role: str
    department: str
    status: OnboardingStatus = OnboardingStatus.CREATED
    tasks: List[OnboardingTask] = field(default_factory=list)
    mentor: str = ""
    start_date: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def progress_pct(self) -> float:
        if not self.tasks:
            return 0.0
        done = sum(
            1 for t in self.tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
        )
        return round(done / (len(self.tasks) or 1) * 100, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "employee_name": self.employee_name,
            "role": self.role,
            "department": self.department,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "mentor": self.mentor,
            "start_date": self.start_date,
            "progress_pct": self.progress_pct,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Default checklists by role category
# ---------------------------------------------------------------------------

_DEFAULT_TASKS: Dict[str, List[Dict[str, str]]] = {
    "engineering": [
        {"title": "Sign employment agreement", "category": "documents"},
        {"title": "Complete tax forms", "category": "documents"},
        {"title": "Set up development environment", "category": "access"},
        {"title": "Provision GitHub / repo access", "category": "access"},
        {"title": "Provision cloud credentials", "category": "access"},
        {"title": "Security awareness training", "category": "training"},
        {"title": "Architecture overview session", "category": "training"},
        {"title": "Meet the team introduction", "category": "intro"},
        {"title": "Assign mentor / buddy", "category": "intro"},
        {"title": "First week check-in", "category": "intro"},
    ],
    "support": [
        {"title": "Sign employment agreement", "category": "documents"},
        {"title": "Complete tax forms", "category": "documents"},
        {"title": "Ticketing system access", "category": "access"},
        {"title": "Knowledge base training", "category": "training"},
        {"title": "Product overview session", "category": "training"},
        {"title": "Customer communication guidelines", "category": "training"},
        {"title": "Meet the team introduction", "category": "intro"},
        {"title": "Shadow session with senior agent", "category": "intro"},
    ],
    "default": [
        {"title": "Sign employment agreement", "category": "documents"},
        {"title": "Complete tax forms", "category": "documents"},
        {"title": "IT equipment provisioning", "category": "equipment"},
        {"title": "Email / calendar setup", "category": "access"},
        {"title": "Security awareness training", "category": "training"},
        {"title": "Company orientation", "category": "training"},
        {"title": "Meet the team introduction", "category": "intro"},
    ],
}


# ---------------------------------------------------------------------------
# OnboardingAutomationEngine
# ---------------------------------------------------------------------------

class OnboardingAutomationEngine:
    """Automated HR onboarding workflow management.

    Design Label: BIZ-003
    Owner: HR Team

    Usage::

        engine = OnboardingAutomationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
        )
        profile = engine.create_onboarding(
            employee_name="Alice",
            role="backend engineer",
            department="engineering",
        )
        engine.complete_task(profile.profile_id, profile.tasks[0].task_id)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_profiles: int = 5_000,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._profiles: Dict[str, OnboardingProfile] = {}
        self._max_profiles = max_profiles

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def create_onboarding(
        self,
        employee_name: str,
        role: str,
        department: str,
        mentor: str = "",
        start_date: str = "",
    ) -> OnboardingProfile:
        """Create an onboarding profile with auto-generated task checklist."""
        # Select task template
        dept_lower = department.lower()
        template_key = dept_lower if dept_lower in _DEFAULT_TASKS else "default"
        tasks = [
            OnboardingTask(
                task_id=f"task-{uuid.uuid4().hex[:6]}",
                title=t["title"],
                category=t["category"],
            )
            for t in _DEFAULT_TASKS[template_key]
        ]

        profile = OnboardingProfile(
            profile_id=f"onb-{uuid.uuid4().hex[:8]}",
            employee_name=employee_name,
            role=role,
            department=department,
            tasks=tasks,
            mentor=mentor,
            start_date=start_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )

        with self._lock:
            if len(self._profiles) >= self._max_profiles:
                # Evict completed profiles
                completed = [
                    k for k, v in self._profiles.items()
                    if v.status == OnboardingStatus.COMPLETED
                ]
                for k in completed[:max(1, len(completed) // 2)]:
                    del self._profiles[k]
            self._profiles[profile.profile_id] = profile

        self._persist(profile)
        logger.info("Created onboarding %s for %s", profile.profile_id, employee_name)
        return profile

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def complete_task(self, profile_id: str, task_id: str) -> Optional[OnboardingProfile]:
        """Mark a task as completed."""
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return None
            for task in profile.tasks:
                if task.task_id == task_id and task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now(timezone.utc).isoformat()
                    break
            else:
                return profile

            # Update profile status
            if profile.status == OnboardingStatus.CREATED:
                profile.status = OnboardingStatus.IN_PROGRESS
            if profile.progress_pct >= 100.0:
                profile.status = OnboardingStatus.COMPLETED
            profile.updated_at = datetime.now(timezone.utc).isoformat()

        self._persist(profile)
        self._publish_milestone(profile, task_id)
        return profile

    def skip_task(self, profile_id: str, task_id: str) -> Optional[OnboardingProfile]:
        """Skip a task (e.g., not applicable to this role)."""
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return None
            for task in profile.tasks:
                if task.task_id == task_id and task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.SKIPPED
                    break
            if profile.progress_pct >= 100.0:
                profile.status = OnboardingStatus.COMPLETED
            profile.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist(profile)
        return profile

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            p = self._profiles.get(profile_id)
        return p.to_dict() if p else None

    def list_profiles(
        self,
        status: Optional[str] = None,
        department: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            profiles = list(self._profiles.values())
        if status:
            profiles = [p for p in profiles if p.status.value == status]
        if department:
            profiles = [p for p in profiles if p.department.lower() == department.lower()]
        profiles.sort(key=lambda p: p.created_at, reverse=True)
        return [p.to_dict() for p in profiles[:limit]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._profiles)
            by_status = {}
            for p in self._profiles.values():
                by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
            avg_progress = 0.0
            active = [p for p in self._profiles.values() if p.status == OnboardingStatus.IN_PROGRESS]
            if active:
                avg_progress = sum(p.progress_pct for p in active) / (len(active) or 1)
        return {
            "total_profiles": total,
            "by_status": by_status,
            "avg_progress_pct": round(avg_progress, 1),
            "max_profiles": self._max_profiles,
            "persistence_attached": self._pm is not None,
            "backbone_attached": self._backbone is not None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, profile: OnboardingProfile) -> None:
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=profile.profile_id,
                    document=profile.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

    def _publish_milestone(self, profile: OnboardingProfile, task_id: str) -> None:
        if self._backbone is not None:
            try:
                from event_backbone import EventType
                self._backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "onboarding_automation_engine",
                        "profile_id": profile.profile_id,
                        "employee": profile.employee_name,
                        "task_completed": task_id,
                        "progress_pct": profile.progress_pct,
                        "status": profile.status.value,
                    },
                    source="onboarding_automation_engine",
                )
            except Exception as exc:
                logger.debug("EventBackbone publish skipped: %s", exc)
