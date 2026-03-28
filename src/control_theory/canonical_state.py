"""
Canonical State Vector for the Murphy System.

Unifies all fragmented state representations into a single typed Pydantic model
that can serve as the formal state vector X(t) for a control-theoretic formulation.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any, ClassVar, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# Ordered list of numeric dimension names — ORDER IS CANONICAL and must not change.
_DIMENSION_NAMES: List[str] = [
    "confidence",
    "authority",
    "murphy_index",
    "phase_index",
    "complexity",
    "domain_depth",
    "gate_count",
    "active_constraints",
    "artifact_count",
    "uncertainty_data",
    "uncertainty_authority",
    "uncertainty_information",
    "uncertainty_resources",
    "uncertainty_disagreement",
    "uptime_seconds",
    "active_tasks",
    "cpu_usage_percent",
    # Extended dimensions (added in v1.1.0)
    "response_latency",
    "domain_coverage",
    "constraint_violation_count",
    "delegation_depth",
    "feedback_recency",
    "observation_staleness",
    "llm_confidence_aggregate",
    "escalation_pending_count",
]


class CanonicalStateVector(BaseModel):
    """
    Canonical state vector X(t) for the Murphy System.

    Unifies scalar state dimensions from MFGCSystemState, unified_mfgc SystemState,
    system_integrator SystemState, rosetta SystemState, logging Session, and
    LivingDocument into a single versioned, serialisable model.

    Numeric dimensions (in canonical order):
        1.  confidence                  [0.0, 1.0]
        2.  authority                   [0.0, 1.0]
        3.  murphy_index                [0.0, 1.0]
        4.  phase_index                 [0, 6]
        5.  complexity                  [0.0, 1.0]
        6.  domain_depth                [0, ∞)
        7.  gate_count                  [0, ∞)
        8.  active_constraints          [0, ∞)
        9.  artifact_count              [0, ∞)
        10. uncertainty_data            [0.0, 1.0]  (UD)
        11. uncertainty_authority       [0.0, 1.0]  (UA)
        12. uncertainty_information     [0.0, 1.0] (UI)
        13. uncertainty_resources       [0.0, 1.0]  (UR)
        14. uncertainty_disagreement    [0.0, 1.0] (UG)
        15. uptime_seconds              [0.0, ∞)
        16. active_tasks                [0, ∞)
        17. cpu_usage_percent           [0.0, ∞)
        18. response_latency            [0.0, ∞)   seconds
        19. domain_coverage             [0.0, 1.0]
        20. constraint_violation_count  [0, ∞)
        21. delegation_depth            [0, ∞)
        22. feedback_recency            [0.0, ∞)   seconds since last feedback
        23. observation_staleness       [0.0, ∞)   seconds since last observation
        24. llm_confidence_aggregate    [0.0, 1.0]
        25. escalation_pending_count    [0, ∞)
    """

    # ------------------------------------------------------------------ #
    # Numeric state dimensions
    # ------------------------------------------------------------------ #
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    authority: float = Field(default=0.0, ge=0.0, le=1.0)
    murphy_index: float = Field(default=0.0, ge=0.0, le=1.0)
    phase_index: int = Field(default=0, ge=0, le=6)
    complexity: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_depth: int = Field(default=0, ge=0)
    gate_count: int = Field(default=0, ge=0)
    active_constraints: int = Field(default=0, ge=0)
    artifact_count: int = Field(default=0, ge=0)
    uncertainty_data: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_authority: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_information: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_resources: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_disagreement: float = Field(default=0.0, ge=0.0, le=1.0)
    uptime_seconds: float = Field(default=0.0, ge=0.0)
    active_tasks: int = Field(default=0, ge=0)
    cpu_usage_percent: float = Field(default=0.0, ge=0.0)
    # Extended dimensions (v1.1.0)
    response_latency: float = Field(default=0.0, ge=0.0)
    domain_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    constraint_violation_count: int = Field(default=0, ge=0)
    delegation_depth: int = Field(default=0, ge=0)
    feedback_recency: float = Field(default=0.0, ge=0.0)
    observation_staleness: float = Field(default=0.0, ge=0.0)
    llm_confidence_aggregate: float = Field(default=0.0, ge=0.0, le=1.0)
    escalation_pending_count: int = Field(default=0, ge=0)

    # ------------------------------------------------------------------ #
    # Metadata (not part of numeric vector)
    # ------------------------------------------------------------------ #
    schema_version: str = Field(default="1.0.0")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = Field(default=None)
    domain: str = Field(default="general")

    # ------------------------------------------------------------------ #
    # Validators — clamp out-of-range values instead of raising
    # ------------------------------------------------------------------ #
    # Fields that must remain within the probability simplex [0.0, 1.0].
    _PROBABILITY_FIELDS: ClassVar[tuple] = (
        "confidence",
        "authority",
        "murphy_index",
        "complexity",
        "uncertainty_data",
        "uncertainty_authority",
        "uncertainty_information",
        "uncertainty_resources",
        "uncertainty_disagreement",
        "domain_coverage",
        "llm_confidence_aggregate",
    )

    @field_validator(*_PROBABILITY_FIELDS, mode="before")
    @classmethod
    def clamp_probability(cls, v: float) -> float:
        """Clamp probability-like fields to [0.0, 1.0]."""
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, v))

    @field_validator("phase_index", mode="before")
    @classmethod
    def clamp_phase_index(cls, v: int) -> int:
        """Clamp phase_index to [0, 6]."""
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 0
        return max(0, min(6, v))

    @field_validator("domain_depth", "gate_count", "active_constraints", "artifact_count", "active_tasks",
                     "constraint_violation_count", "delegation_depth", "escalation_pending_count", mode="before")
    @classmethod
    def clamp_non_negative_int(cls, v: int) -> int:
        """Ensure non-negative integer counts."""
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 0
        return max(0, v)

    @field_validator("uptime_seconds", "cpu_usage_percent",
                     "response_latency", "feedback_recency", "observation_staleness", mode="before")
    @classmethod
    def clamp_non_negative_float(cls, v: float) -> float:
        """Ensure non-negative floats."""
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, v)

    # ------------------------------------------------------------------ #
    # Vector interface
    # ------------------------------------------------------------------ #
    @staticmethod
    def dimension_names() -> List[str]:
        """Return the ordered list of numeric dimension names."""
        return list(_DIMENSION_NAMES)

    def dimensionality(self) -> int:
        """Return the number of numeric state dimensions (25)."""
        return len(_DIMENSION_NAMES)

    def to_vector(self) -> List[float]:
        """Return the state as a flat numeric list [x₁, x₂, …, xₙ]."""
        return [
            float(self.confidence),
            float(self.authority),
            float(self.murphy_index),
            float(self.phase_index),
            float(self.complexity),
            float(self.domain_depth),
            float(self.gate_count),
            float(self.active_constraints),
            float(self.artifact_count),
            float(self.uncertainty_data),
            float(self.uncertainty_authority),
            float(self.uncertainty_information),
            float(self.uncertainty_resources),
            float(self.uncertainty_disagreement),
            float(self.uptime_seconds),
            float(self.active_tasks),
            float(self.cpu_usage_percent),
            float(self.response_latency),
            float(self.domain_coverage),
            float(self.constraint_violation_count),
            float(self.delegation_depth),
            float(self.feedback_recency),
            float(self.observation_staleness),
            float(self.llm_confidence_aggregate),
            float(self.escalation_pending_count),
        ]

    @classmethod
    def from_vector(cls, values: List[float]) -> "CanonicalStateVector":
        """
        Reconstruct a CanonicalStateVector from a flat numeric list.

        The list must contain exactly ``dimensionality()`` elements in
        canonical order.  Metadata fields are left at their defaults.
        """
        names = _DIMENSION_NAMES
        if len(values) != len(names):
            raise ValueError(
                f"Expected {len(names)} values, got {len(values)}"
            )
        data = dict(zip(names, values))
        return cls(**data)

    def norm(self) -> float:
        """Return the L2 norm of the numeric state vector."""
        return math.sqrt(sum(v * v for v in self.to_vector()))

    def state_entropy(self) -> float:
        """
        Compute Shannon entropy over the five uncertainty dimensions.

        Treats (UD, UA, UI, UR, UG) as an unnormalised weight vector,
        normalises to a probability distribution, and returns
        H = -Σ p_i log₂(p_i).  When all uncertainties are zero,
        ``normalize_distribution`` returns a uniform distribution
        (maximum ignorance) so entropy equals log₂(5) ≈ 2.32 bits.

        Returns:
            Entropy in bits (≥ 0).
        """
        from .entropy import normalize_distribution, shannon_entropy

        weights = [
            self.uncertainty_data,
            self.uncertainty_authority,
            self.uncertainty_information,
            self.uncertainty_resources,
            self.uncertainty_disagreement,
        ]
        dist = normalize_distribution(weights)
        return shannon_entropy(dist)

    # ------------------------------------------------------------------ #
    # Per-variable uncertainty (covariance diagonal)
    # ------------------------------------------------------------------ #

    def covariance_diagonal(
        self, variances: Optional[List[float]] = None
    ) -> List[float]:
        """
        Return diagonal of a covariance matrix for the state.

        If *variances* is ``None``, heuristic defaults are derived from
        the five uncertainty dimensions (UD, UA, UI, UR, UG) — each
        scaled by 0.01 so that high uncertainty ≈ high variance.
        Dimensions without an explicit uncertainty channel get a small
        default variance.
        """
        if variances is not None:
            if len(variances) != len(_DIMENSION_NAMES):
                raise ValueError(
                    f"Expected {len(_DIMENSION_NAMES)} variances, "
                    f"got {len(variances)}"
                )
            return list(variances)

        # base: small non-zero floor so the covariance matrix stays positive-definite.
        # u_scale: maps [0,1] uncertainty scores to small variance contributions.
        base = 0.001
        u_scale = 0.01
        return [
            self.uncertainty_data * u_scale + base,       # confidence
            self.uncertainty_authority * u_scale + base,   # authority
            base,                                          # murphy_index
            base,                                          # phase_index
            self.uncertainty_information * u_scale + base, # complexity
            base,                                          # domain_depth
            base,                                          # gate_count
            base,                                          # active_constraints
            base,                                          # artifact_count
            self.uncertainty_data * u_scale + base,        # uncertainty_data
            self.uncertainty_authority * u_scale + base,    # uncertainty_authority
            self.uncertainty_information * u_scale + base,  # uncertainty_information
            self.uncertainty_resources * u_scale + base,    # uncertainty_resources
            self.uncertainty_disagreement * u_scale + base, # uncertainty_disagreement
            base,                                          # uptime_seconds
            base,                                          # active_tasks
            base,                                          # cpu_usage_percent
            base,                                          # response_latency
            base,                                          # domain_coverage
            base,                                          # constraint_violation_count
            base,                                          # delegation_depth
            base,                                          # feedback_recency
            base,                                          # observation_staleness
            self.uncertainty_data * u_scale + base,        # llm_confidence_aggregate
            base,                                          # escalation_pending_count
        ]


# ------------------------------------------------------------------ #
# Schema / dimension registry
# ------------------------------------------------------------------ #

class DimensionRegistry:
    """
    Registry that tracks registered state dimensions and supports
    schema versioning when new dimensions are added.
    """

    def __init__(self) -> None:
        self._dimensions: List[str] = list(_DIMENSION_NAMES)
        self._version: int = 1

    @property
    def version(self) -> int:
        return self._version

    @property
    def names(self) -> List[str]:
        return list(self._dimensions)

    @property
    def size(self) -> int:
        """dim(x_t) as a tracked integer."""
        return len(self._dimensions)

    def register_dimension(
        self, name: str, dtype: str = "float", bounds: Optional[tuple] = None
    ) -> None:
        """
        Register a new state dimension.

        Increments the schema version.  Bounds are advisory.
        """
        if name in self._dimensions:
            raise ValueError(f"Dimension '{name}' already registered.")
        capped_append(self._dimensions, name)
        self._version += 1

    def has_dimension(self, name: str) -> bool:
        return name in self._dimensions
