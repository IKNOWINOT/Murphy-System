"""
Pydantic models for the Feature Flag system.

Design Label: FF-002
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FlagType(str, enum.Enum):
    """Type of feature flag."""

    BOOLEAN = "boolean"         # Simple on/off
    PERCENTAGE = "percentage"   # Gradual rollout by percentage
    MRR_GATED = "mrr_gated"    # Unlocks at MRR threshold
    TENANT_LIST = "tenant_list"  # Explicit tenant allowlist


class FlagStatus(str, enum.Enum):
    """Feature flag lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class RolloutConfig(BaseModel):
    """Configuration for gradual rollout."""

    percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of tenants that see this feature (0-100).",
    )
    mrr_threshold_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="MRR threshold in USD to unlock this feature.",
    )
    allowed_tenants: List[str] = Field(
        default_factory=list,
        description="Explicit tenant IDs allowed (for TENANT_LIST type).",
    )
    blocked_tenants: List[str] = Field(
        default_factory=list,
        description="Tenant IDs explicitly blocked.",
    )


class TenantOverride(BaseModel):
    """Per-tenant flag override."""

    tenant_id: str
    enabled: bool
    reason: str = ""
    set_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class FeatureFlag(BaseModel):
    """Complete feature flag definition."""

    flag_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Unique flag identifier (e.g. 'mcp_plugin_enabled').",
    )
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    flag_type: FlagType = FlagType.BOOLEAN
    status: FlagStatus = FlagStatus.DRAFT

    # Default state
    default_enabled: bool = False

    # Rollout
    rollout: RolloutConfig = Field(default_factory=RolloutConfig)

    # Per-tenant overrides
    tenant_overrides: Dict[str, TenantOverride] = Field(default_factory=dict)

    # Metadata
    owner: str = "platform"
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FlagEvaluation(BaseModel):
    """Result of evaluating a feature flag for a specific tenant."""

    flag_id: str
    tenant_id: str
    enabled: bool
    reason: str = ""
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
