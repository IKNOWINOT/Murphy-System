"""
Time Tracking – Data Models
=============================

Core data structures for the Time Tracking & Reporting system
(Phase 6 of management systems parity).

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


class EntryStatus(Enum):
    """Time entry status."""
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"       # alias for completed; ready to submit
    SUBMITTED = "submitted"   # awaiting approval
    APPROVED = "approved"     # approved by a manager
    REJECTED = "rejected"     # rejected with reason


class SheetStatus(Enum):
    """Timesheet approval status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class TimeEntry:
    """A single time tracking entry."""
    id: str = field(default_factory=_new_id)
    user_id: str = ""
    board_id: str = ""
    item_id: str = ""
    note: str = ""
    status: EntryStatus = EntryStatus.COMPLETED
    started_at: str = field(default_factory=_now)
    ended_at: str = ""
    duration_seconds: int = 0
    billable: bool = True
    tags: List[str] = field(default_factory=list)
    # Approval fields
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "board_id": self.board_id,
            "item_id": self.item_id,
            "note": self.note,
            "status": self.status.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "billable": self.billable,
            "tags": self.tags,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class TimeSheet:
    """A weekly/periodic timesheet for approval."""
    id: str = field(default_factory=_new_id)
    user_id: str = ""
    period_start: str = ""
    period_end: str = ""
    status: SheetStatus = SheetStatus.DRAFT
    entry_ids: List[str] = field(default_factory=list)
    total_seconds: int = 0
    submitted_at: str = ""
    approved_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "status": self.status.value,
            "entry_ids": self.entry_ids,
            "total_seconds": self.total_seconds,
            "submitted_at": self.submitted_at,
            "approved_by": self.approved_by,
        }
