"""
Typed State Vector for the MFGC Control Plane (Gap CFP-1).

Provides a Pydantic v2 ``StateVector`` model with:
- Enumerated state dimensions (confidence, phase, authority, etc.)
- Auto-computed dimensionality
- Schema versioning
- Timestamps
- ``to_vector()`` / ``diff()`` helpers
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


class StateVector(BaseModel):
    """Formal typed state vector x_t for the MFGC control plane.

    All base dimensions are floats in [0.0, 1.0] unless otherwise noted.
    """

    # ------------------------------------------------------------------ #
    # Core state dimensions
    # ------------------------------------------------------------------ #
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    phase: float = Field(default=0.0, ge=0.0, le=1.0)
    authority: float = Field(default=0.0, ge=0.0, le=1.0)
    murphy_index: float = Field(default=0.0, ge=0.0, le=1.0)
    gate_count: float = Field(default=0.0, ge=0.0)
    constraint_satisfaction: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_depth: float = Field(default=0.0, ge=0.0)
    information_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_exposure: float = Field(default=0.0, ge=0.0, le=1.0)
    verification_coverage: float = Field(default=0.0, ge=0.0, le=1.0)

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------ #
    # Extra domain dimensions
    # ------------------------------------------------------------------ #
    extra_dimensions: Dict[str, float] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    # ------------------------------------------------------------------ #
    # Base dimension names (class-level constant)
    # ------------------------------------------------------------------ #
    _BASE_DIMS: List[str] = [
        "confidence",
        "phase",
        "authority",
        "murphy_index",
        "gate_count",
        "constraint_satisfaction",
        "domain_depth",
        "information_completeness",
        "risk_exposure",
        "verification_coverage",
    ]

    @model_validator(mode="after")
    def _update_timestamp(self) -> "StateVector":
        object.__setattr__(self, "updated_at", datetime.now(timezone.utc))
        return self

    # ------------------------------------------------------------------ #
    # Public methods
    # ------------------------------------------------------------------ #

    def dimensionality(self) -> int:
        """Return total number of state dimensions (base + extra)."""
        return len(self._BASE_DIMS) + len(self.extra_dimensions)

    def to_vector(self) -> List[float]:
        """Return numerical representation of all dimensions."""
        base = [
            self.confidence,
            self.phase,
            self.authority,
            self.murphy_index,
            self.gate_count,
            self.constraint_satisfaction,
            self.domain_depth,
            self.information_completeness,
            self.risk_exposure,
            self.verification_coverage,
        ]
        extra = [self.extra_dimensions[k] for k in sorted(self.extra_dimensions)]
        return base + extra

    def to_dict(self) -> Dict[str, Any]:
        """Return dict representation (backward-compatible with x_t usage)."""
        d: Dict[str, Any] = {
            "confidence": self.confidence,
            "phase": self.phase,
            "authority": self.authority,
            "murphy_index": self.murphy_index,
            "gate_count": self.gate_count,
            "constraint_satisfaction": self.constraint_satisfaction,
            "domain_depth": self.domain_depth,
            "information_completeness": self.information_completeness,
            "risk_exposure": self.risk_exposure,
            "verification_coverage": self.verification_coverage,
        }
        d.update(self.extra_dimensions)
        return d

    def diff(self, other: "StateVector") -> Dict[str, float]:
        """Return per-dimension difference (self - other) for numeric dims."""
        self_v = self.to_dict()
        other_v = other.to_dict()
        result: Dict[str, float] = {}
        all_keys = set(self_v) | set(other_v)
        for k in all_keys:
            s = self_v.get(k, 0.0)
            o = other_v.get(k, 0.0)
            if isinstance(s, (int, float)) and isinstance(o, (int, float)):
                result[k] = float(s) - float(o)
        return result

    def with_update(self, **kwargs: Any) -> "StateVector":
        """Return a new ``StateVector`` with the given fields overridden."""
        data = self.model_dump(exclude={"created_at", "updated_at"})
        data.update(kwargs)
        data["created_at"] = self.created_at
        return StateVector(**data)


__all__ = ["StateVector"]
