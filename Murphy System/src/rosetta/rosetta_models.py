"""
Pydantic models for the Rosetta State Management System.

Defines the full agent state schema used by Murphy System agents,
including identity, system health, goals, tasks, automation progress,
recalibration tracking, archival, improvement proposals, and workflow patterns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

import logging

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class GoalStatus(str, Enum):
    """Goal status (str subclass)."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"


class TaskStatus(str, Enum):
    """Task status (str subclass)."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class RecalibrationStatus(str, Enum):
    """Recalibration status (str subclass)."""
    IDLE = "idle"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Sub-models ====================

class Identity(BaseModel):
    """Agent identity information."""
    agent_id: str
    name: str
    role: str = ""
    version: str = "1.0.0"
    organization: str = ""


class SystemState(BaseModel):
    """System health snapshot."""
    model_config = ConfigDict(use_enum_values=True)

    status: str = "idle"  # idle, active, paused, error
    uptime_seconds: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    active_tasks: int = 0
    last_heartbeat: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class Goal(BaseModel):
    """An agent goal."""
    model_config = ConfigDict(use_enum_values=True)

    goal_id: str
    title: str
    description: str = ""
    status: GoalStatus = GoalStatus.PENDING
    priority: int = Field(default=3, ge=1, le=5)
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dependencies: List[str] = Field(default_factory=list)


class Task(BaseModel):
    """An agent task linked to a goal."""
    model_config = ConfigDict(use_enum_values=True)

    task_id: str
    goal_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


class AgentState(BaseModel):
    """Aggregated agent operational state."""
    current_phase: str = "idle"
    active_goals: List[Goal] = Field(default_factory=list)
    task_queue: List[Task] = Field(default_factory=list)


class AutomationProgress(BaseModel):
    """Progress tracking for an automation category."""
    category: str
    total_items: int = 0
    completed_items: int = 0
    coverage_percent: float = 0.0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Recalibration(BaseModel):
    """Recalibration cycle tracking."""
    model_config = ConfigDict(use_enum_values=True)

    status: RecalibrationStatus = RecalibrationStatus.IDLE
    last_run: Optional[datetime] = None
    next_scheduled: Optional[datetime] = None
    cycle_count: int = 0
    findings: List[str] = Field(default_factory=list)


class ArchiveEntry(BaseModel):
    """A single archived item."""
    entry_id: str
    archived_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    category: str = "manual"
    data: Dict[str, Any] = Field(default_factory=dict)


class ArchiveLog(BaseModel):
    """Collection of archived entries."""
    entries: List[ArchiveEntry] = Field(default_factory=list)
    total_archived: int = 0


class ImprovementProposal(BaseModel):
    """A proposed improvement for the system."""
    proposal_id: str
    title: str
    description: str = ""
    priority: int = Field(default=3, ge=1, le=5)
    status: str = "proposed"
    estimated_effort_hours: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    category: str = "general"


class WorkflowPattern(BaseModel):
    """A reusable workflow pattern."""
    pattern_id: str
    name: str
    steps: List[str] = Field(default_factory=list)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    avg_duration_seconds: float = 0.0
    usage_count: int = 0


class Metadata(BaseModel):
    """Document metadata."""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    schema_version: str = "1.0"


# ==================== Main Model ====================

class RosettaAgentState(BaseModel):
    """
    Complete Rosetta agent state document.

    Combines identity, system health, operational state, automation tracking,
    recalibration, archival, improvement proposals, and workflow patterns.
    """
    model_config = ConfigDict(use_enum_values=True)

    identity: Identity
    system_state: SystemState = Field(default_factory=SystemState)
    agent_state: AgentState = Field(default_factory=AgentState)
    automation_progress: List[AutomationProgress] = Field(default_factory=list)
    recalibration: Recalibration = Field(default_factory=Recalibration)
    archive_log: ArchiveLog = Field(default_factory=ArchiveLog)
    improvement_proposals: List[ImprovementProposal] = Field(default_factory=list)
    workflow_patterns: List[WorkflowPattern] = Field(default_factory=list)
    metadata: Metadata = Field(default_factory=Metadata)
