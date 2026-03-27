"""
Correction Data Model
Defines the structure for capturing and storing human corrections.
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CorrectionType(str, Enum):
    """Types of corrections."""
    OUTPUT_MODIFICATION = "output_modification"
    PARAMETER_ADJUSTMENT = "parameter_adjustment"
    LOGIC_CORRECTION = "logic_correction"
    VALIDATION_OVERRIDE = "validation_override"
    ASSUMPTION_CORRECTION = "assumption_correction"
    RISK_ASSESSMENT = "risk_assessment"
    RESOURCE_ALLOCATION = "resource_allocation"
    WORKFLOW_CHANGE = "workflow_change"


class CorrectionSeverity(str, Enum):
    """Severity of the correction."""
    CRITICAL = "critical"  # System would have failed
    HIGH = "high"  # Significant error
    MEDIUM = "medium"  # Noticeable issue
    LOW = "low"  # Minor improvement
    COSMETIC = "cosmetic"  # Style/formatting only


class CorrectionSource(str, Enum):
    """Source of the correction."""
    HUMAN_EXPERT = "human_expert"
    AUTOMATED_VALIDATION = "automated_validation"
    PEER_REVIEW = "peer_review"
    SYSTEM_FEEDBACK = "system_feedback"
    USER_REPORT = "user_report"


class CorrectionStatus(str, Enum):
    """Status of a correction."""
    PENDING = "pending"
    VALIDATED = "validated"
    APPLIED = "applied"
    REJECTED = "rejected"
    UNDER_REVIEW = "under_review"


class CorrectionContext(BaseModel):
    """Context in which the correction was made."""
    task_id: str
    phase: str
    operation: str
    domain: Optional[str] = None
    environment: str = "production"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OriginalValue(BaseModel):
    """Original value before correction."""
    value: Any
    type: str
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    source: Optional[str] = None


class CorrectedValue(BaseModel):
    """Corrected value after human intervention."""
    value: Any
    type: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str
    source: CorrectionSource
    validator_id: Optional[str] = None


class CorrectionDiff(BaseModel):
    """Difference between original and corrected values."""
    field_name: str
    original: OriginalValue
    corrected: CorrectedValue
    change_type: str  # "modified", "added", "removed"
    impact_score: float = Field(ge=0.0, le=1.0)
    description: str


class CorrectionMetrics(BaseModel):
    """Metrics associated with a correction."""
    time_to_correct_seconds: float
    correction_complexity: str  # "simple", "moderate", "complex"
    affected_components: List[str] = Field(default_factory=list)
    downstream_impacts: int = 0
    confidence_improvement: float = 0.0
    risk_reduction: float = 0.0


class LearningSignal(BaseModel):
    """Learning signal extracted from correction."""
    pattern_type: str
    pattern_description: str
    applicable_contexts: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    frequency: int = 1
    examples: List[str] = Field(default_factory=list)


class Correction(BaseModel):
    """
    Complete correction record.
    Captures all information about a human correction to system output.
    """
    # Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correction_type: CorrectionType
    severity: CorrectionSeverity
    status: CorrectionStatus = CorrectionStatus.PENDING

    # Context
    context: CorrectionContext

    # Changes
    diffs: List[CorrectionDiff]

    # Explanation
    explanation: str
    reasoning: str
    alternative_approaches: List[str] = Field(default_factory=list)

    # Metrics
    metrics: CorrectionMetrics

    # Learning
    learning_signals: List[LearningSignal] = Field(default_factory=list)

    # Validation
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None
    validation_notes: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    applied_at: Optional[datetime] = None

    # Metadata
    tags: List[str] = Field(default_factory=list)
    related_corrections: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def calculate_impact_score(self) -> float:
        """Calculate overall impact score of the correction."""
        if not self.diffs:
            return 0.0

        # Weighted average of diff impact scores
        total_impact = sum(diff.impact_score for diff in self.diffs)
        avg_impact = total_impact / (len(self.diffs) or 1)

        # Adjust by severity
        severity_weights = {
            CorrectionSeverity.CRITICAL: 1.0,
            CorrectionSeverity.HIGH: 0.8,
            CorrectionSeverity.MEDIUM: 0.6,
            CorrectionSeverity.LOW: 0.4,
            CorrectionSeverity.COSMETIC: 0.2
        }

        severity_weight = severity_weights.get(self.severity, 0.5)
        return avg_impact * severity_weight

    def get_affected_fields(self) -> List[str]:
        """Get list of fields that were corrected."""
        return [diff.field_name for diff in self.diffs]

    def is_validated(self) -> bool:
        """Check if correction has been validated."""
        return self.status == CorrectionStatus.VALIDATED

    def is_applied(self) -> bool:
        """Check if correction has been applied."""
        return self.status == CorrectionStatus.APPLIED


class CorrectionBatch(BaseModel):
    """
    Batch of related corrections.
    Used for bulk operations and pattern analysis.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    corrections: List[str]  # Correction IDs
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CorrectionTemplate(BaseModel):
    """
    Template for common correction patterns.
    Speeds up correction entry for recurring issues.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    correction_type: CorrectionType
    default_severity: CorrectionSeverity

    # Template fields
    field_templates: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_template: str
    tags: List[str] = Field(default_factory=list)

    # Usage stats
    usage_count: int = 0
    last_used: Optional[datetime] = None

    def apply_template(self, context: CorrectionContext, values: Dict[str, Any]) -> Correction:
        """Apply template to create a new correction."""
        diffs = []

        for field_template in self.field_templates:
            field_name = field_template["field_name"]
            if field_name in values:
                diff = CorrectionDiff(
                    field_name=field_name,
                    original=OriginalValue(
                        value=values.get(f"{field_name}_original"),
                        type=field_template.get("type", "string")
                    ),
                    corrected=CorrectedValue(
                        value=values[field_name],
                        type=field_template.get("type", "string"),
                        reasoning=self.reasoning_template,
                        source=CorrectionSource.HUMAN_EXPERT
                    ),
                    change_type="modified",
                    impact_score=field_template.get("impact_score", 0.5),
                    description=field_template.get("description", "")
                )
                diffs.append(diff)

        correction = Correction(
            correction_type=self.correction_type,
            severity=self.default_severity,
            context=context,
            diffs=diffs,
            explanation=self.description,
            reasoning=self.reasoning_template,
            metrics=CorrectionMetrics(
                time_to_correct_seconds=0,
                correction_complexity="simple"
            ),
            tags=self.tags
        )

        # Update usage stats
        self.usage_count += 1
        self.last_used = datetime.now(timezone.utc)

        return correction


class CorrectionStatistics(BaseModel):
    """Statistics about corrections."""
    total_corrections: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    average_impact_score: float = 0.0
    average_time_to_correct: float = 0.0
    most_corrected_fields: List[Tuple[str, int]] = Field(default_factory=list)
    correction_rate: float = 0.0  # Corrections per task
    validation_rate: float = 0.0  # Validated / Total
    application_rate: float = 0.0  # Applied / Validated


class CorrectionQuery(BaseModel):
    """Query for searching corrections."""
    correction_type: Optional[CorrectionType] = None
    severity: Optional[CorrectionSeverity] = None
    status: Optional[CorrectionStatus] = None
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    min_impact_score: Optional[float] = None
    limit: int = 100
    offset: int = 0


class CorrectionSummary(BaseModel):
    """Summary of a correction for display."""
    id: str
    correction_type: CorrectionType
    severity: CorrectionSeverity
    status: CorrectionStatus
    fields_corrected: List[str]
    impact_score: float
    created_at: datetime
    explanation: str
    tags: List[str]


# ============================================================================
# CORRECTION RELATIONSHIPS
# ============================================================================

class CorrectionRelationship(BaseModel):
    """Relationship between corrections."""
    source_correction_id: str
    target_correction_id: str
    relationship_type: str  # "duplicate", "related", "supersedes", "conflicts"
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CorrectionCluster(BaseModel):
    """Cluster of similar corrections."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    correction_ids: List[str]
    common_pattern: str
    frequency: int
    average_impact: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = Field(default_factory=list)


# ============================================================================
# CORRECTION EVENTS
# ============================================================================

class CorrectionEvent(BaseModel):
    """Event in the correction lifecycle."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correction_id: str
    event_type: str  # "created", "validated", "applied", "rejected", "modified"
    actor_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_simple_correction(
    task_id: str,
    field_name: str,
    original_value: Any,
    corrected_value: Any,
    reasoning: str,
    correction_type: CorrectionType = CorrectionType.OUTPUT_MODIFICATION,
    severity: CorrectionSeverity = CorrectionSeverity.MEDIUM
) -> Correction:
    """
    Helper function to create a simple correction quickly.

    Args:
        task_id: ID of the task being corrected
        field_name: Name of the field being corrected
        original_value: Original value
        corrected_value: Corrected value
        reasoning: Explanation for the correction
        correction_type: Type of correction
        severity: Severity level

    Returns:
        Correction object
    """
    context = CorrectionContext(
        task_id=task_id,
        phase="execution",
        operation="output_generation"
    )

    diff = CorrectionDiff(
        field_name=field_name,
        original=OriginalValue(
            value=original_value,
            type=type(original_value).__name__
        ),
        corrected=CorrectedValue(
            value=corrected_value,
            type=type(corrected_value).__name__,
            reasoning=reasoning,
            source=CorrectionSource.HUMAN_EXPERT
        ),
        change_type="modified",
        impact_score=0.5,
        description=f"Corrected {field_name}"
    )

    return Correction(
        correction_type=correction_type,
        severity=severity,
        context=context,
        diffs=[diff],
        explanation=reasoning,
        reasoning=reasoning,
        metrics=CorrectionMetrics(
            time_to_correct_seconds=0,
            correction_complexity="simple"
        )
    )


def merge_corrections(corrections: List[Correction]) -> Correction:
    """
    Merge multiple corrections into a single correction.

    Args:
        corrections: List of corrections to merge

    Returns:
        Merged correction
    """
    if not corrections:
        raise ValueError("Cannot merge empty list of corrections")

    if len(corrections) == 1:
        return corrections[0]

    # Use first correction as base
    base = corrections[0]

    # Merge diffs
    all_diffs = []
    for correction in corrections:
        all_diffs.extend(correction.diffs)

    # Merge learning signals
    all_signals = []
    for correction in corrections:
        all_signals.extend(correction.learning_signals)

    # Merge tags
    all_tags = list(set(tag for correction in corrections for tag in correction.tags))

    # Create merged correction
    merged = Correction(
        correction_type=base.correction_type,
        severity=max(c.severity for c in corrections),
        context=base.context,
        diffs=all_diffs,
        explanation=f"Merged correction from {len(corrections)} corrections",
        reasoning="; ".join(c.reasoning for c in corrections),
        metrics=CorrectionMetrics(
            time_to_correct_seconds=sum(c.metrics.time_to_correct_seconds for c in corrections),
            correction_complexity="complex"
        ),
        learning_signals=all_signals,
        tags=all_tags,
        related_corrections=[c.id for c in corrections]
    )

    return merged
