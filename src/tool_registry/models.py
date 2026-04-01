"""
Pydantic models for the Universal Tool Registry.

Design Label: TR-002
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PermissionLevel(str, enum.Enum):
    """Maps to HITL confidence gates.

    UNRESTRICTED  – auto-execute, no human check
    LOW           – abbreviated gate evaluation
    MEDIUM        – full gate evaluation
    HIGH          – full gate + HITL approval required
    CRITICAL      – always requires explicit human sign-off
    """

    UNRESTRICTED = "unrestricted"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CostTier(str, enum.Enum):
    """Coarse cost classification for budget planning."""

    FREE = "free"
    CHEAP = "cheap"       # < $0.01 per invocation
    MODERATE = "moderate"  # $0.01 – $0.10
    EXPENSIVE = "expensive"  # $0.10 – $1.00
    PREMIUM = "premium"    # > $1.00


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ToolInputSchema(BaseModel):
    """Describes expected inputs for a tool invocation."""

    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-Schema-style field definitions for tool inputs.",
    )
    required: List[str] = Field(
        default_factory=list,
        description="List of required field names.",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the input contract.",
    )


class ToolOutputSchema(BaseModel):
    """Describes the shape of tool output."""

    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-Schema-style field definitions for tool outputs.",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the output contract.",
    )


class CostEstimate(BaseModel):
    """Per-invocation cost estimate for budget tracking."""

    tier: CostTier = CostTier.FREE
    estimated_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated cost in USD per invocation.",
    )
    token_estimate: int = Field(
        default=0,
        ge=0,
        description="Estimated LLM tokens consumed per invocation.",
    )
    notes: str = ""


class ToolDefinition(BaseModel):
    """Complete self-describing tool registration record.

    Every bot, engine, or integration registers one of these.
    """

    tool_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Unique identifier (e.g. 'bot.triage', 'engine.trading').",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Human-readable name.",
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="What this tool does.",
    )
    version: str = Field(
        default="1.0.0",
        description="Semantic version of the tool.",
    )

    # Schema
    input_schema: ToolInputSchema = Field(default_factory=ToolInputSchema)
    output_schema: ToolOutputSchema = Field(default_factory=ToolOutputSchema)

    # Permission / cost
    permission_level: PermissionLevel = PermissionLevel.MEDIUM
    cost_estimate: CostEstimate = Field(default_factory=CostEstimate)

    # Discovery metadata for AionMind
    provider: str = Field(
        default="unknown",
        description="Subsystem that owns this tool (bot, engine, integration).",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Free-form tags for capability matching.",
    )
    category: str = Field(
        default="general",
        description="Broad functional category.",
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether HITL approval is mandatory before execution.",
    )
    max_concurrency: int = Field(
        default=1,
        ge=1,
        description="Maximum parallel invocations allowed.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Maximum execution time in seconds.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible key-value metadata.",
    )

    # Timestamps
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tool_id": "bot.triage",
                "name": "Triage Bot",
                "description": "Routes incoming requests to the correct handler.",
                "permission_level": "low",
                "cost_estimate": {"tier": "free", "estimated_usd": 0.0},
                "provider": "bot",
                "tags": ["routing", "triage"],
            }
        }


class ToolExecutionResult(BaseModel):
    """Structured result from a tool invocation."""

    tool_id: str
    success: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
