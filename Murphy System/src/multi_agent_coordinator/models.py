"""
Pydantic models for Multi-Agent Coordinator.

Design Label: MAC-002
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SubTaskStatus(str, enum.Enum):
    """Lifecycle states for a subtask."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class MergeStrategy(str, enum.Enum):
    """How to combine subtask results."""

    CONCAT = "concat"           # Concatenate all outputs
    VOTE = "vote"               # Confidence-weighted voting
    FIRST_SUCCESS = "first_success"  # Take first successful result
    PRIORITY = "priority"       # Use priority ordering
    CUSTOM = "custom"           # Caller-supplied merge function


class CoordinationStatus(str, enum.Enum):
    """Overall coordination lifecycle."""

    DECOMPOSING = "decomposing"
    DISPATCHING = "dispatching"
    EXECUTING = "executing"
    MERGING = "merging"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class SubTask(BaseModel):
    """A single unit of work dispatched to a bot/engine."""

    subtask_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    parent_task_id: str = ""
    name: str = ""
    description: str = ""
    assigned_tool_id: str = Field(
        ...,
        description="Tool ID from the UniversalToolRegistry.",
    )
    input_data: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, description="Higher = more important.")
    timeout_seconds: float = 30.0
    status: SubTaskStatus = SubTaskStatus.PENDING
    depends_on: List[str] = Field(
        default_factory=list,
        description="Subtask IDs that must complete before this one.",
    )


class SubTaskResult(BaseModel):
    """Result from executing a subtask."""

    subtask_id: str
    tool_id: str = ""
    status: SubTaskStatus = SubTaskStatus.COMPLETED
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score from the executing tool.",
    )
    execution_time_ms: float = 0.0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class ConflictResolution(BaseModel):
    """Record of how a conflict between subtask results was resolved."""

    field: str = ""
    conflicting_values: List[Any] = Field(default_factory=list)
    resolved_value: Any = None
    resolution_method: str = "confidence_weighted_vote"
    confidence: float = 0.0


class TaskDecomposition(BaseModel):
    """Phase 1 decomposition of a complex task into subtasks."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_request: str = ""
    subtasks: List[SubTask] = Field(default_factory=list)
    merge_strategy: MergeStrategy = MergeStrategy.VOTE
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CoordinationResult(BaseModel):
    """Final output from multi-agent coordination."""

    task_id: str
    status: CoordinationStatus = CoordinationStatus.COMPLETED
    subtask_results: List[SubTaskResult] = Field(default_factory=list)
    merged_output: Dict[str, Any] = Field(default_factory=dict)
    conflicts_resolved: List[ConflictResolution] = Field(default_factory=list)
    murphy_validation_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Murphy Validation formula score for merged result.",
    )
    murphy_validation_passed: bool = False
    total_execution_time_ms: float = 0.0
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
