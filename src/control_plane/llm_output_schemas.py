"""
LLM Output Schemas and Validation for the MFGC Control Plane (Gap CFP-5).

Defines Pydantic models for each LLM call type and utilities for
validating, conflict-resolving, and regenerating LLM outputs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# LLM Output Schema Models
# ------------------------------------------------------------------ #


class ExpertGenerationOutput(BaseModel):
    """Schema for expert-profile generation LLM calls."""

    expert_name: str
    domain: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    suggested_gates: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class GateProposalOutput(BaseModel):
    """Schema for gate-proposal LLM calls."""

    gate_id: str
    gate_name: str
    gate_type: str
    severity: str = "medium"
    evaluation_criteria: List[str] = Field(default_factory=list)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("severity", mode="before")
    @classmethod
    def _validate_severity(cls, v: str) -> str:
        allowed = {"low", "medium", "high", "critical"}
        if str(v).lower() not in allowed:
            raise ValueError(f"severity must be one of {allowed}, got {v!r}")
        return str(v).lower()

    model_config = {"extra": "ignore"}


class CandidateGenerationOutput(BaseModel):
    """Schema for candidate-solution generation LLM calls."""

    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    domain: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class DomainAnalysisOutput(BaseModel):
    """Schema for domain-analysis LLM calls."""

    domain: str
    complexity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    key_entities: List[str] = Field(default_factory=list)
    recommended_phases: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


# ------------------------------------------------------------------ #
# LLM Output Validator
# ------------------------------------------------------------------ #


class LLMOutputValidator:
    """Validate raw LLM output dicts against expected Pydantic schemas."""

    def validate(
        self,
        raw_output: Dict[str, Any],
        expected_schema: Type[BaseModel],
    ) -> Tuple[bool, Optional[BaseModel], List[str]]:
        """Validate *raw_output* against *expected_schema*.

        Returns:
            (is_valid, parsed_model_or_None, list_of_error_messages)
        """
        try:
            model = expected_schema.model_validate(raw_output)
            return True, model, []
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            errors = self._extract_errors(exc)
            return False, None, errors

    @staticmethod
    def _extract_errors(exc: Exception) -> List[str]:
        try:
            # pydantic v2 ValidationError has .errors()
            return [f"{e['loc']}: {e['msg']}" for e in exc.errors()]  # type: ignore[attr-defined]
        except AttributeError:
            return [str(exc)]


# ------------------------------------------------------------------ #
# Conflict Resolver
# ------------------------------------------------------------------ #


class ConflictResolver:
    """Resolve contradictory LLM outputs.

    Strategy: majority-vote on boolean fields, average on numeric fields,
    keep the first non-empty string/list.
    """

    def resolve(self, outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge *outputs* into a single reconciled dict.

        Args:
            outputs: List of raw LLM output dicts for the same call type.

        Returns:
            A merged dict suitable for passing to a Pydantic model.
        """
        if not outputs:
            return {}
        if len(outputs) == 1:
            return dict(outputs[0])

        merged: Dict[str, Any] = {}
        all_keys = set().union(*(o.keys() for o in outputs))

        for key in all_keys:
            values = [o[key] for o in outputs if key in o]
            merged[key] = self._merge_values(values)

        return merged

    @staticmethod
    def _merge_values(values: List[Any]) -> Any:
        if not values:
            return None
        # Numeric: average
        if all(isinstance(v, (int, float)) for v in values):
            return sum(values) / len(values)
        # Bool: majority vote
        if all(isinstance(v, bool) for v in values):
            return sum(values) > len(values) / 2
        # List: union
        if all(isinstance(v, list) for v in values):
            seen = []
            for lst in values:
                for item in lst:
                    if item not in seen:
                        seen.append(item)
            return seen
        # String: first non-empty
        for v in values:
            if v:
                return v
        return values[0]


# ------------------------------------------------------------------ #
# Regeneration Trigger
# ------------------------------------------------------------------ #


class RegenerationTrigger:
    """Detect when LLM output quality is below threshold and trigger re-query.

    Tracks how many regeneration attempts have been made and stops when
    *max_retries* is reached.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.4,
        max_retries: int = 3,
    ) -> None:
        self._threshold = confidence_threshold
        self._max_retries = max_retries
        self._retry_counts: Dict[str, int] = {}

    def should_regenerate(
        self,
        output: Dict[str, Any],
        is_valid: bool,
        call_id: str = "default",
    ) -> bool:
        """Return True when the output should be regenerated.

        Triggers when:
        1. ``is_valid`` is False (schema validation failed), OR
        2. ``output["confidence"]`` is below threshold.

        Will NOT trigger if *call_id* has already exceeded *max_retries*.
        """
        count = self._retry_counts.get(call_id, 0)
        if count >= self._max_retries:
            return False

        if not is_valid:
            self._retry_counts[call_id] = count + 1
            return True

        confidence = output.get("confidence", 1.0)
        if isinstance(confidence, (int, float)) and confidence < self._threshold:
            self._retry_counts[call_id] = count + 1
            return True

        return False

    def reset(self, call_id: str = "default") -> None:
        """Reset retry counter for *call_id*."""
        self._retry_counts.pop(call_id, None)

    def retry_count(self, call_id: str = "default") -> int:
        """Return current retry count for *call_id*."""
        return self._retry_counts.get(call_id, 0)


__all__ = [
    "ExpertGenerationOutput",
    "GateProposalOutput",
    "CandidateGenerationOutput",
    "DomainAnalysisOutput",
    "LLMOutputValidator",
    "ConflictResolver",
    "RegenerationTrigger",
]
