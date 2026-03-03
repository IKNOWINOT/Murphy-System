"""Task lifecycle models using Pydantic."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Enumeration of task states."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class TaskLifecycle(BaseModel):
    """Represents lifecycle metadata for a task."""

    task_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: TaskState = TaskState.CREATED
    metadata: Optional[Dict] = None

    def transition(self, new_state: TaskState) -> None:
        """Update the task state and timestamp."""
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)
