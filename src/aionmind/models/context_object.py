"""
Layer 1 — ContextObject: canonical structured input for planning / orchestration.

Converts raw inputs (user query, bot outputs, memory, telemetry, workflow state)
into a single Pydantic-validated object that every downstream layer consumes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Classification of risk associated with a context."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Priority(str, Enum):
    """Priority for processing a context."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ContextObject(BaseModel):
    """Canonical structured context consumed by all AionMind layers.

    Invariants
    ----------
    * This is an **informational artifact** — it never triggers execution by itself.
    * It may be stored, enriched, and passed downstream but carries no authority
      to execute actions.
    """

    # ── identity ──────────────────────────────────────────────────
    context_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this context.",
    )
    source: str = Field(
        ...,
        description="Origin of the context (e.g. 'user_query', 'bot_output', 'telemetry').",
    )
    intent: str = Field(
        default="",
        description="Detected or declared intent of the requester.",
    )

    # ── classification ────────────────────────────────────────────
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Processing priority.",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Risk classification.",
    )

    # ── relationships ─────────────────────────────────────────────
    related_tasks: List[str] = Field(
        default_factory=list,
        description="IDs of tasks associated with this context.",
    )
    workflow_refs: List[str] = Field(
        default_factory=list,
        description="IDs of related workflow executions.",
    )
    memory_refs: List[str] = Field(
        default_factory=list,
        description="IDs of memory entries relevant to this context.",
    )

    # ── reasoning support ─────────────────────────────────────────
    constraints: List[str] = Field(
        default_factory=list,
        description="Hard constraints the system must honour.",
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="References to supporting evidence / data sources.",
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Stated assumptions that may need validation.",
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Identified risks relevant to decision-making.",
    )

    # ── payload ───────────────────────────────────────────────────
    raw_input: str = Field(
        default="",
        description="Original unprocessed input text.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional metadata.",
    )

    # ── timestamps ────────────────────────────────────────────────
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
