"""
Supervisor System Data Schemas

Core data models for the Supervisor Feedback Loops & Assumption Correction system.

CRITICAL SAFETY CONSTRAINTS:
1. validated_by_self MUST be False (enforced in __post_init__)
2. requires_external_validation MUST be True (enforced in __post_init__)
3. ValidationEvidence MUST be external (enforced in __post_init__)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class AssumptionStatus(Enum):
    """Status of an assumption."""
    ACTIVE = "active"
    STALE = "stale"
    INVALIDATED = "invalidated"
    VALIDATED = "validated"
    UNDER_REVIEW = "under_review"


class FeedbackType(Enum):
    """Type of supervisor feedback."""
    APPROVE = "approve"
    DENY = "deny"
    MODIFY = "modify"
    INVALIDATE = "invalidate"
    VALIDATE = "validate"
    REQUEST_EVIDENCE = "request_evidence"


class InvalidationSource(Enum):
    """Source of invalidation signal."""
    TELEMETRY = "telemetry"
    SUPERVISOR = "supervisor"
    DETERMINISTIC = "deterministic"
    TIMEOUT = "timeout"


class CorrectionActionType(Enum):
    """Type of correction action."""
    DROP_CONFIDENCE = "drop_confidence"
    DECAY_AUTHORITY = "decay_authority"
    FREEZE_EXECUTION = "freeze_execution"
    DOWNGRADE_PHASE = "downgrade_phase"
    TRIGGER_REEXPANSION = "trigger_reexpansion"


@dataclass
class InvalidationSignal:
    """Signal indicating an assumption may be invalid."""
    signal_id: str
    assumption_id: str
    source: InvalidationSource
    reason: str
    confidence: float  # Confidence that assumption is invalid
    severity: str  # "low", "medium", "high", "critical"
    timestamp: datetime
    evidence: Optional[str] = None


@dataclass
class ValidationEvidence:
    """Evidence for validating an assumption."""
    evidence_id: str
    assumption_id: str
    evidence_type: str  # "deterministic", "api", "supervisor", "telemetry"
    description: str
    confidence: float
    source: str
    timestamp: datetime
    is_external: bool  # MUST be True for validation

    def __post_init__(self):
        """Enforce that validation evidence must be external."""
        if not self.is_external:
            raise ValueError(
                "ValidationEvidence must be external (is_external=True). "
                "Self-generated evidence cannot validate assumptions."
            )


@dataclass
class AssumptionArtifact:
    """
    An assumption that must be validated externally.

    CRITICAL SAFETY CONSTRAINTS:
    - validated_by_self MUST be False
    - requires_external_validation MUST be True
    """
    assumption_id: str
    description: str
    source_artifact_id: str  # Hypothesis or packet that made this assumption

    # Confidence impact
    confidence_if_true: float
    confidence_if_false: float

    # Status
    status: AssumptionStatus
    created_at: datetime
    next_review_date: datetime

    # CRITICAL: Self-validation prevention
    validated_by_self: bool  # MUST be False
    requires_external_validation: bool  # MUST be True

    # Evidence
    validation_evidence: List[ValidationEvidence] = field(default_factory=list)
    invalidation_signals: List[InvalidationSignal] = field(default_factory=list)

    # Metadata
    owner_role: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Enforce safety constraints."""
        if self.validated_by_self:
            raise ValueError(
                "AssumptionArtifact cannot have validated_by_self=True. "
                "Assumptions must be validated externally."
            )
        if not self.requires_external_validation:
            raise ValueError(
                "AssumptionArtifact must have requires_external_validation=True. "
                "All assumptions require external validation."
            )


@dataclass
class SupervisorFeedbackArtifact:
    """Feedback from a human supervisor."""
    feedback_id: str
    assumption_id: str
    feedback_type: FeedbackType
    supervisor_id: str
    supervisor_role: str
    timestamp: datetime

    # Content
    rationale: str
    corrections: Optional[str] = None
    required_evidence: Optional[List[str]] = None

    # Impact
    confidence_adjustment: Optional[float] = None
    authority_adjustment: Optional[str] = None


@dataclass
class CorrectionAction:
    """Action taken to correct based on invalidation."""
    action_id: str
    assumption_id: str
    action_type: CorrectionActionType
    triggered_by: str  # Signal ID or feedback ID
    timestamp: datetime

    # Details
    rationale: str
    confidence_before: Optional[float] = None
    confidence_after: Optional[float] = None
    authority_before: Optional[str] = None
    authority_after: Optional[str] = None

    # Execution impact
    execution_frozen: bool = False
    affected_artifacts: List[str] = field(default_factory=list)


@dataclass
class AssumptionBinding:
    """Binding between assumption and artifact (hypothesis or execution packet)."""
    assumption_id: str
    hypothesis_id: Optional[str]
    execution_packet_id: Optional[str]
    is_critical: bool  # If True, invalidation blocks execution
    bound_at: datetime


@dataclass
class ConfidenceTrend:
    """Tracks confidence over time to detect degradation."""
    artifact_id: str
    timestamps: List[datetime] = field(default_factory=list)
    confidence_values: List[float] = field(default_factory=list)

    def add_measurement(self, timestamp: datetime, confidence: float):
        """Add a confidence measurement."""
        self.timestamps.append(timestamp)
        self.confidence_values.append(confidence)

    def is_decreasing(self, window_size: int = 5) -> bool:
        """Check if confidence is decreasing over recent window."""
        if len(self.confidence_values) < window_size:
            return False

        recent = self.confidence_values[-window_size:]
        for i in range(1, len(recent)):
            if recent[i] > recent[i-1]:
                return False
        return True

    def is_volatile(self, threshold: float = 0.2) -> bool:
        """Check if confidence is volatile (high variance)."""
        if len(self.confidence_values) < 3:
            return False

        recent = self.confidence_values[-5:]
        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / (len(recent) or 1)
        return variance > threshold


@dataclass
class MurphyIndexTrend:
    """Tracks Murphy index (risk) over time to detect increasing risk."""
    artifact_id: str
    timestamps: List[datetime] = field(default_factory=list)
    murphy_values: List[float] = field(default_factory=list)

    def add_measurement(self, timestamp: datetime, murphy_index: float):
        """Add a Murphy index measurement."""
        self.timestamps.append(timestamp)
        self.murphy_values.append(murphy_index)

    def is_increasing(self, window_size: int = 5) -> bool:
        """Check if Murphy index is increasing over recent window."""
        if len(self.murphy_values) < window_size:
            return False

        recent = self.murphy_values[-window_size:]
        for i in range(1, len(recent)):
            if recent[i] < recent[i-1]:
                return False
        return True

    def exceeds_threshold(self, threshold: float = 0.7) -> bool:
        """Check if Murphy index exceeds threshold."""
        if not self.murphy_values:
            return False
        return self.murphy_values[-1] > threshold
