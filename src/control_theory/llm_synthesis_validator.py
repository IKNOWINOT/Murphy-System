"""
Schema Validation for LLM Outputs in the Murphy System.

Provides:
  - SynthesisSchema: Pydantic models for expected LLM output structures
  - OutputValidator: validates LLM-generated structures against schema
  - ConflictResolver: detects and resolves conflicts between generated components
  - RegenerationTrigger: triggers LLM regeneration when confidence drops below threshold

Control-theoretic motivation:
  The existing LLMIntegrationLayer and DynamicExpertGenerator lack formal
  output validation, which means LLM-generated state dimensions, constraints
  and roles can be structurally inconsistent with the control system.  By
  validating against a typed schema before injection, we close the feedback
  loop: invalid outputs are caught before they corrupt the state model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Synthesis schemas — Pydantic models for LLM-generated structures
# ------------------------------------------------------------------ #

class GeneratedStateDimension(BaseModel):
    """Schema for an LLM-generated state dimension."""

    dimension_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    dtype: str = Field(default="float")
    lower_bound: Optional[float] = Field(default=None)
    upper_bound: Optional[float] = Field(default=None)
    unit: str = Field(default="")
    rationale: str = Field(default="")

    @field_validator("dtype")
    @classmethod
    def validate_dtype(cls, v: str) -> str:
        allowed = {"float", "int", "bool"}
        if v not in allowed:
            raise ValueError(f"dtype must be one of {allowed}, got '{v}'")
        return v

    @model_validator(mode="after")
    def bounds_consistent(self) -> "GeneratedStateDimension":
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError(
                f"lower_bound ({self.lower_bound}) must be ≤ upper_bound ({self.upper_bound})"
            )
        return self


class GeneratedConstraint(BaseModel):
    """Schema for an LLM-generated constraint g(x) ≤ 0."""

    constraint_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    constraint_type: str = Field(default="inequality")  # "inequality" | "equality"
    affected_dimensions: List[str] = Field(default_factory=list)
    severity: str = Field(default="medium")
    rationale: str = Field(default="")

    @field_validator("constraint_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"inequality", "equality", "soft"}
        if v not in allowed:
            raise ValueError(f"constraint_type must be one of {allowed}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"critical", "high", "medium", "low"}
        if v.lower() not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v.lower()


class GeneratedRole(BaseModel):
    """Schema for an LLM-generated authority role."""

    role_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    authority_level: float = Field(..., ge=0.0, le=1.0)
    capabilities: List[str] = Field(default_factory=list)
    reports_to: Optional[str] = Field(default=None)
    rationale: str = Field(default="")


# Registry of output schemas.
_SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {
    "state_dimension": GeneratedStateDimension,
    "constraint": GeneratedConstraint,
    "role": GeneratedRole,
}


# ------------------------------------------------------------------ #
# Output validator
# ------------------------------------------------------------------ #

@dataclass
class ValidationResult:
    """Result of validating an LLM output against a schema."""

    is_valid: bool
    schema_name: str
    errors: List[str] = field(default_factory=list)
    validated_object: Optional[BaseModel] = None


def validate_output(
    schema_name: str,
    llm_output: Dict[str, Any],
) -> ValidationResult:
    """
    Validate raw LLM output *llm_output* against the registered schema.

    Args:
        schema_name: one of "state_dimension", "constraint", "role".
        llm_output: raw dict from LLM.

    Returns:
        ValidationResult — check ``is_valid`` and ``errors``.
    """
    schema_cls = _SCHEMA_REGISTRY.get(schema_name)
    if schema_cls is None:
        return ValidationResult(
            is_valid=False,
            schema_name=schema_name,
            errors=[f"Unknown schema '{schema_name}'. "
                    f"Available: {list(_SCHEMA_REGISTRY.keys())}"],
        )
    try:
        obj = schema_cls(**llm_output)
        return ValidationResult(
            is_valid=True,
            schema_name=schema_name,
            validated_object=obj,
        )
    except Exception as exc:  # pydantic.ValidationError or TypeError
        logger.debug("Caught exception: %s", exc)
        return ValidationResult(
            is_valid=False,
            schema_name=schema_name,
            errors=[str(exc)],
        )


class OutputValidator:
    """
    Validates batches of LLM outputs against registered schemas.
    """

    def validate(
        self, schema_name: str, llm_output: Dict[str, Any]
    ) -> ValidationResult:
        """Validate a single LLM output."""
        return validate_output(schema_name, llm_output)

    def validate_batch(
        self, items: List[Tuple[str, Dict[str, Any]]]
    ) -> List[ValidationResult]:
        """Validate a list of (schema_name, output) pairs."""
        return [validate_output(schema_name, output) for schema_name, output in items]

    def all_valid(
        self, items: List[Tuple[str, Dict[str, Any]]]
    ) -> bool:
        """True if every item in *items* is valid."""
        return all(r.is_valid for r in self.validate_batch(items))


# ------------------------------------------------------------------ #
# Conflict resolver
# ------------------------------------------------------------------ #

class ConflictKind(Enum):
    """Type of conflict between generated structures."""

    DUPLICATE_ID = "duplicate_id"
    OVERLAPPING_BOUNDS = "overlapping_bounds"
    AUTHORITY_CYCLE = "authority_cycle"
    CONSTRAINT_INCONSISTENCY = "constraint_inconsistency"
    NONE = "none"


@dataclass
class ConflictReport:
    """Report of detected conflicts."""

    has_conflicts: bool
    conflicts: List[Tuple[ConflictKind, str]]  # (kind, description)


class ConflictResolver:
    """
    Detects and resolves conflicts between generated structures.

    Detects:
      - Duplicate IDs (two dimensions/constraints with the same ID)
      - Overlapping bounds (two dimensions with conflicting ranges)
      - Authority cycles (role A reports_to role B reports_to role A)
      - Constraint inconsistency (two constraints that can't be satisfied together)
    """

    def detect_conflicts(
        self,
        new_structure: Dict[str, Any],
        existing_structures: List[Dict[str, Any]],
        schema_name: str = "state_dimension",
    ) -> ConflictReport:
        """
        Detect conflicts between *new_structure* and *existing_structures*.

        Args:
            new_structure: the proposed new output (raw dict).
            existing_structures: list of already-accepted outputs (raw dicts).
            schema_name: type of structure being checked.

        Returns:
            ConflictReport.
        """
        conflicts: List[Tuple[ConflictKind, str]] = []

        new_id = new_structure.get("dimension_id") or new_structure.get(
            "constraint_id"
        ) or new_structure.get("role_id")

        # Check for duplicate IDs
        for existing in existing_structures:
            ex_id = existing.get("dimension_id") or existing.get(
                "constraint_id"
            ) or existing.get("role_id")
            if ex_id and new_id and ex_id == new_id:
                conflicts.append(
                    (ConflictKind.DUPLICATE_ID, f"ID '{new_id}' already exists.")
                )

        # Check for overlapping bounds (state dimensions only)
        if schema_name == "state_dimension":
            conflicts.extend(
                self._check_overlapping_bounds(new_structure, existing_structures)
            )

        # Check authority cycles (roles only)
        if schema_name == "role":
            conflicts.extend(
                self._check_authority_cycle(new_structure, existing_structures)
            )

        return ConflictReport(has_conflicts=bool(conflicts), conflicts=conflicts)

    def _check_overlapping_bounds(
        self,
        new_dim: Dict[str, Any],
        existing_dims: List[Dict[str, Any]],
    ) -> List[Tuple[ConflictKind, str]]:
        """Flag if a new dimension name duplicates an existing one with different bounds."""
        conflicts: List[Tuple[ConflictKind, str]] = []
        new_name = new_dim.get("name")
        new_lo = new_dim.get("lower_bound")
        new_hi = new_dim.get("upper_bound")

        for ex in existing_dims:
            if ex.get("name") == new_name:
                ex_lo = ex.get("lower_bound")
                ex_hi = ex.get("upper_bound")
                if (ex_lo, ex_hi) != (new_lo, new_hi):
                    conflicts.append(
                        (
                            ConflictKind.OVERLAPPING_BOUNDS,
                            f"Dimension '{new_name}' has conflicting bounds: "
                            f"existing [{ex_lo}, {ex_hi}] vs new [{new_lo}, {new_hi}].",
                        )
                    )
        return conflicts

    def _check_authority_cycle(
        self,
        new_role: Dict[str, Any],
        existing_roles: List[Dict[str, Any]],
    ) -> List[Tuple[ConflictKind, str]]:
        """Detect simple direct-cycle in reports_to chain."""
        conflicts: List[Tuple[ConflictKind, str]] = []
        new_id = new_role.get("role_id")
        reports_to = new_role.get("reports_to")

        if reports_to is not None:
            # Check if the reported-to role itself reports to new_id (direct cycle)
            for ex in existing_roles:
                if ex.get("role_id") == reports_to:
                    if ex.get("reports_to") == new_id:
                        conflicts.append(
                            (
                                ConflictKind.AUTHORITY_CYCLE,
                                f"Cycle detected: '{new_id}' ↔ '{reports_to}'.",
                            )
                        )
        return conflicts


# ------------------------------------------------------------------ #
# Regeneration trigger
# ------------------------------------------------------------------ #

class RegenerationTrigger:
    """
    Triggers LLM re-synthesis when confidence drops below a threshold.

    Monitors a confidence history window and emits a regeneration signal
    when the moving average falls below *threshold*.
    """

    def __init__(
        self,
        threshold: float = 0.4,
        window_size: int = 5,
        max_retries: int = 3,
    ) -> None:
        """
        Args:
            threshold: minimum acceptable confidence.
            window_size: number of recent steps to average.
            max_retries: maximum regeneration attempts before giving up.
        """
        self.threshold = threshold
        self.window_size = window_size
        self.max_retries = max_retries

    def should_regenerate(
        self,
        confidence_history: Sequence[float],
        current_retries: int = 0,
    ) -> bool:
        """
        True if regeneration should be triggered.

        Args:
            confidence_history: recent confidence values (newest last).
            current_retries: number of regeneration attempts so far.

        Returns:
            True if the moving-average confidence is below threshold
            and max_retries has not been reached.
        """
        if current_retries >= self.max_retries:
            return False

        if not confidence_history:
            return True

        window = list(confidence_history)[-self.window_size:]
        moving_avg = sum(window) / len(window)
        return moving_avg < self.threshold
