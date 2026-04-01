"""
Pydantic models for the Skill System.

Design Label: SK-002
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillAccess(str, enum.Enum):
    """Visibility / sharing level for a skill."""

    PRIVATE = "private"       # Only the creating tenant
    TENANT = "tenant"         # All users within the tenant
    COMMUNITY = "community"   # Shared across tenants


class SkillStepStatus(str, enum.Enum):
    """Status of a skill step execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SkillStep(BaseModel):
    """A single step in a skill workflow (one node in the DAG)."""

    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    tool_id: Optional[str] = Field(
        default=None,
        description="Tool from UniversalToolRegistry to execute.",
    )
    sub_skill_id: Optional[str] = Field(
        default=None,
        description="Nested skill to compose (mutually exclusive with tool_id).",
    )
    input_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Map parent context keys → step input keys.",
    )
    output_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Map step output keys → parent context keys.",
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="Step IDs that must complete before this one.",
    )
    timeout_seconds: float = 60.0
    retry_count: int = 0
    condition: Optional[str] = Field(
        default=None,
        description="Optional condition expression (e.g. 'context.approval == true').",
    )


class SkillComposition(BaseModel):
    """Defines the DAG of steps for a composed skill."""

    steps: List[SkillStep] = Field(default_factory=list)
    entry_points: List[str] = Field(
        default_factory=list,
        description="Step IDs with no dependencies (DAG roots).",
    )


class SkillMetadata(BaseModel):
    """Discovery metadata for a skill."""

    tags: List[str] = Field(default_factory=list)
    category: str = "general"
    estimated_duration_seconds: float = 60.0
    estimated_cost_usd: float = 0.0
    example_input: Dict[str, Any] = Field(default_factory=dict)
    example_output: Dict[str, Any] = Field(default_factory=dict)


class SkillSpec(BaseModel):
    """Complete specification for a registered skill."""

    skill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    version: str = "1.0.0"
    owner_tenant: str = "system"
    access: SkillAccess = SkillAccess.PRIVATE

    # Composition DAG
    composition: SkillComposition = Field(default_factory=SkillComposition)

    # Discovery
    metadata: SkillMetadata = Field(default_factory=SkillMetadata)

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # Usage tracking
    execution_count: int = 0
    success_count: int = 0


class SkillExecutionRecord(BaseModel):
    """Record of a skill execution."""

    skill_id: str
    tenant_id: str = ""
    status: SkillStepStatus = SkillStepStatus.COMPLETED
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    step_results: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
