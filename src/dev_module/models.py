"""
Dev Module – Data Models
=========================

Core data structures for the Dev Module (Phase 9 of management systems parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_UTC = timezone.utc


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(tz=_UTC).isoformat()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SprintStatus(Enum):
    """Sprint lifecycle status."""
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BugSeverity(Enum):
    """Bug severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BugPriority(Enum):
    """Bug priority levels."""
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class BugStatus(Enum):
    """Bug tracking status."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    WONT_FIX = "wont_fix"


class ReleaseStatus(Enum):
    """Release lifecycle status."""
    DRAFT = "draft"
    STAGING = "staging"
    RELEASED = "released"
    ROLLED_BACK = "rolled_back"


class RoadmapItemStatus(Enum):
    """Product roadmap item status."""
    PROPOSED = "proposed"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SprintItem:
    """An item within a sprint (story / task)."""
    id: str = field(default_factory=_new_id)
    item_id: str = ""
    story_points: int = 0
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "story_points": self.story_points,
            "completed": self.completed,
        }


@dataclass
class Sprint:
    """A development sprint with velocity tracking."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    board_id: str = ""
    status: SprintStatus = SprintStatus.PLANNING
    start_date: str = ""
    end_date: str = ""
    goal: str = ""
    items: List[SprintItem] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    @property
    def total_points(self) -> int:
        return sum(i.story_points for i in self.items)

    @property
    def completed_points(self) -> int:
        return sum(i.story_points for i in self.items if i.completed)

    @property
    def velocity(self) -> int:
        if self.status == SprintStatus.COMPLETED:
            return self.completed_points
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "board_id": self.board_id,
            "status": self.status.value,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "goal": self.goal,
            "items": [i.to_dict() for i in self.items],
            "total_points": self.total_points,
            "completed_points": self.completed_points,
            "velocity": self.velocity,
            "created_at": self.created_at,
        }


@dataclass
class Bug:
    """A tracked software bug."""
    id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    board_id: str = ""
    severity: BugSeverity = BugSeverity.MEDIUM
    priority: BugPriority = BugPriority.P2
    status: BugStatus = BugStatus.OPEN
    assignee_id: str = ""
    reporter_id: str = ""
    sprint_id: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    resolved_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "board_id": self.board_id,
            "severity": self.severity.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "assignee_id": self.assignee_id,
            "reporter_id": self.reporter_id,
            "sprint_id": self.sprint_id,
            "tags": self.tags,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


@dataclass
class ReleaseChecklist:
    """A single checklist item for a release."""
    id: str = field(default_factory=_new_id)
    label: str = ""
    checked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "label": self.label, "checked": self.checked}


@dataclass
class Release:
    """A software release."""
    id: str = field(default_factory=_new_id)
    version: str = ""
    name: str = ""
    status: ReleaseStatus = ReleaseStatus.DRAFT
    sprint_ids: List[str] = field(default_factory=list)
    checklist: List[ReleaseChecklist] = field(default_factory=list)
    release_notes: str = ""
    released_at: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "status": self.status.value,
            "sprint_ids": self.sprint_ids,
            "checklist": [c.to_dict() for c in self.checklist],
            "release_notes": self.release_notes,
            "released_at": self.released_at,
            "created_at": self.created_at,
        }


@dataclass
class GitActivity:
    """A read-only git activity entry."""
    id: str = field(default_factory=_new_id)
    board_id: str = ""
    event_type: str = ""  # commit, pr_opened, pr_merged, branch_created
    author: str = ""
    message: str = ""
    ref: str = ""
    url: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "board_id": self.board_id,
            "event_type": self.event_type,
            "author": self.author,
            "message": self.message,
            "ref": self.ref,
            "url": self.url,
            "created_at": self.created_at,
        }


@dataclass
class RoadmapItem:
    """A product roadmap timeline item."""
    id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    status: RoadmapItemStatus = RoadmapItemStatus.PROPOSED
    quarter: str = ""
    owner_id: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "quarter": self.quarter,
            "owner_id": self.owner_id,
            "tags": self.tags,
            "created_at": self.created_at,
        }
