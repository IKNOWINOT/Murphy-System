"""
Structured task record used by the scheduler and lifecycle agents.
Supports priority, feedback, recursion, entropy, and tracking.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, timezone
import uuid


@dataclass
class TaskRecord:
    """Represents a queued or running task in HiveMind."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    bot: str = ""  # Bot responsible for execution
    source: Optional[str] = None  # Who/what created it
    resources: Optional[str] = None
    status: str = "pending"  # pending, running, complete, failed

    # Scheduling & Optimization
    priority: int = 5  # 1 (highest) to 10 (lowest)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    estimated_runtime: Optional[float] = None  # seconds
    stage: Optional[int] = None  # 30, 60, 90, 100%

    # Feedback & Learning
    feedback_score: Optional[float] = None  # -1 to 1 or 0.0–1.0
    feedback_comments: Optional[List[str]] = field(default_factory=list)

    # Recursive Stability
    recursion_depth: int = 0
    max_recursion_depth: int = 5
    entropy: Optional[float] = None  # Optional tracking of randomness/unpredictability

    # Debugging / Routing
    tags: List[str] = field(default_factory=list)
    reason_for_creation: Optional[str] = None

    def update_status(self, new_status: str):
        self.status = new_status
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def add_feedback(self, score: float, comment: Optional[str] = None):
        self.feedback_score = score
        if comment:
            self.feedback_comments.append(comment)
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def bump_priority(self):
        if self.priority > 1:
            self.priority -= 1
        self.last_updated = datetime.now(timezone.utc).isoformat()