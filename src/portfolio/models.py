"""
Portfolio – Data Models
========================

Core data structures for the Project Portfolio Management system
(Phase 4 of management systems parity).

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations
import logging

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

class DependencyType(Enum):
    """Standard project dependency types."""
    FINISH_TO_START = "fs"    # predecessor must finish before successor starts
    START_TO_START = "ss"     # predecessor must start before successor starts
    FINISH_TO_FINISH = "ff"   # predecessor must finish before successor finishes
    START_TO_FINISH = "sf"    # predecessor must start before successor finishes


class MilestoneStatus(Enum):
    """Milestone completion state."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

@dataclass
class GanttBar:
    """A single bar on the Gantt chart representing an item's time span."""
    item_id: str = ""
    item_name: str = ""
    board_id: str = ""
    group_id: str = ""
    start_date: str = ""
    end_date: str = ""
    progress: float = 0.0
    assignee_ids: List[str] = field(default_factory=list)
    is_critical: bool = False

    def duration_days(self) -> int:
        """Calculate duration in days (0 if dates invalid)."""
        try:
            start = datetime.fromisoformat(self.start_date)
            end = datetime.fromisoformat(self.end_date)
            return max(0, (end - start).days)
        except (ValueError, TypeError):
            return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "board_id": self.board_id,
            "group_id": self.group_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "progress": self.progress,
            "duration_days": self.duration_days(),
            "assignee_ids": self.assignee_ids,
            "is_critical": self.is_critical,
        }


@dataclass
class Dependency:
    """A dependency between two items."""
    id: str = field(default_factory=_new_id)
    predecessor_id: str = ""
    successor_id: str = ""
    dependency_type: DependencyType = DependencyType.FINISH_TO_START
    lag_days: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "predecessor_id": self.predecessor_id,
            "successor_id": self.successor_id,
            "dependency_type": self.dependency_type.value,
            "lag_days": self.lag_days,
        }


@dataclass
class Milestone:
    """A project milestone with a target date."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    board_id: str = ""
    target_date: str = ""
    status: MilestoneStatus = MilestoneStatus.PENDING
    linked_item_ids: List[str] = field(default_factory=list)
    owner_id: str = ""
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "board_id": self.board_id,
            "target_date": self.target_date,
            "status": self.status.value,
            "linked_item_ids": self.linked_item_ids,
            "owner_id": self.owner_id,
            "created_at": self.created_at,
        }


@dataclass
class Baseline:
    """A snapshot of planned schedule at a point in time."""
    id: str = field(default_factory=_new_id)
    name: str = ""
    board_id: str = ""
    snapshot_date: str = field(default_factory=_now)
    bars: List[GanttBar] = field(default_factory=list)
    created_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "board_id": self.board_id,
            "snapshot_date": self.snapshot_date,
            "bars": [b.to_dict() for b in self.bars],
            "created_by": self.created_by,
        }


@dataclass
class PortfolioProject:
    """A project within a portfolio for cross-board overview."""
    board_id: str = ""
    name: str = ""
    owner_id: str = ""
    status: str = ""
    start_date: str = ""
    end_date: str = ""
    progress: float = 0.0
    health: str = "on_track"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "board_id": self.board_id,
            "name": self.name,
            "owner_id": self.owner_id,
            "status": self.status,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "progress": self.progress,
            "health": self.health,
        }
