"""
LLM Output Validation, Conflict Resolution, and Regeneration Triggers.

Provides:
  - LLMOutputSchema — Pydantic-based structural validation for LLM outputs.
  - ConflictResolver — explicit strategy for contradictory outputs.
  - RegenerationPolicy — trigger conditions for LLM re-generation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# LLM output schemas (Pydantic enforcement)
# ------------------------------------------------------------------ #

class LLMOutputKind(Enum):
    """Type of content the LLM can produce."""

    EXPERT_PROFILE = "expert_profile"
    GATE_PROPOSAL = "gate_proposal"
    CONSTRAINT_SET = "constraint_set"
    RECOMMENDATION = "recommendation"
    CODE_ARTIFACT = "code_artifact"
    DOCUMENT_SECTION = "document_section"


class ExpertProfileOutput(BaseModel):
    """Validated schema for a generated expert profile."""

    expert_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    capabilities: List[str] = Field(default_factory=list, min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(default="")


class GateProposalOutput(BaseModel):
    """Validated schema for a generated gate proposal."""

    gate_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    condition: str = Field(..., min_length=1)
    threshold: float = Field(..., ge=0.0, le=1.0)
    severity: str = Field(default="medium")

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"critical", "high", "medium", "low"}
        if v.lower() not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v.lower()


class RecommendationOutput(BaseModel):
    """Validated schema for a generated recommendation."""

    recommendation_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)


# Registry of output schemas by kind.
OUTPUT_SCHEMAS: Dict[LLMOutputKind, type] = {
    LLMOutputKind.EXPERT_PROFILE: ExpertProfileOutput,
    LLMOutputKind.GATE_PROPOSAL: GateProposalOutput,
    LLMOutputKind.RECOMMENDATION: RecommendationOutput,
}


def validate_llm_output(kind: LLMOutputKind, data: Dict[str, Any]) -> BaseModel:
    """
    Validate raw LLM output *data* against the registered Pydantic schema for *kind*.

    Raises ``ValidationError`` if the data does not conform.
    Returns the validated model instance.
    """
    schema_cls = OUTPUT_SCHEMAS.get(kind)
    if schema_cls is None:
        raise ValueError(f"No schema registered for {kind}")
    return schema_cls(**data)


# ------------------------------------------------------------------ #
# Conflict resolution
# ------------------------------------------------------------------ #

class ResolutionStrategy(Enum):
    """How to resolve conflicting LLM outputs."""

    PRIORITY = "priority"        # higher-confidence output wins
    HUMAN_IN_THE_LOOP = "hitl"   # escalate to human
    CONSENSUS = "consensus"      # majority vote (≥3 outputs)


@dataclass
class ConflictResult:
    """Outcome of conflict resolution."""

    winner: Optional[Dict] = None
    strategy_used: ResolutionStrategy = ResolutionStrategy.PRIORITY
    reason: str = ""
    escalated: bool = False


class ConflictResolver:
    """
    resolve_conflict(a, b) → winner  with an explicit strategy.
    """

    def __init__(self, strategy: ResolutionStrategy = ResolutionStrategy.PRIORITY):
        self.strategy = strategy

    def resolve(
        self,
        output_a: Dict[str, Any],
        output_b: Dict[str, Any],
    ) -> ConflictResult:
        if self.strategy == ResolutionStrategy.PRIORITY:
            conf_a = output_a.get("confidence", 0.0)
            conf_b = output_b.get("confidence", 0.0)
            winner = output_a if conf_a >= conf_b else output_b
            return ConflictResult(
                winner=winner,
                strategy_used=self.strategy,
                reason=f"confidence {max(conf_a, conf_b):.2f} > {min(conf_a, conf_b):.2f}",
            )
        elif self.strategy == ResolutionStrategy.HUMAN_IN_THE_LOOP:
            return ConflictResult(
                winner=None,
                strategy_used=self.strategy,
                reason="Escalated to human for resolution",
                escalated=True,
            )
        elif self.strategy == ResolutionStrategy.CONSENSUS:
            # With only 2 outputs, fall back to priority
            conf_a = output_a.get("confidence", 0.0)
            conf_b = output_b.get("confidence", 0.0)
            winner = output_a if conf_a >= conf_b else output_b
            return ConflictResult(
                winner=winner,
                strategy_used=self.strategy,
                reason="Only 2 outputs; fell back to priority",
            )
        return ConflictResult(reason="Unknown strategy")


# ------------------------------------------------------------------ #
# Regeneration triggers
# ------------------------------------------------------------------ #

@dataclass
class RegenerationPolicy:
    """
    Defines when an LLM output must be regenerated.

    Trigger conditions:
      - confidence < min_confidence
      - constraint_violated is True
      - max_retries limits re-generation attempts
    """

    min_confidence: float = 0.3
    max_retries: int = 3
    require_schema_valid: bool = True

    def should_regenerate(
        self,
        confidence: float,
        constraint_violated: bool = False,
        schema_valid: bool = True,
        attempt: int = 0,
    ) -> bool:
        """
        True if the output should be regenerated.

        Returns False if max retries have been exhausted.
        """
        if attempt >= self.max_retries:
            return False
        if confidence < self.min_confidence:
            return True
        if constraint_violated:
            return True
        if self.require_schema_valid and not schema_valid:
            return True
        return False
