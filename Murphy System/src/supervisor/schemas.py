"""
Core data models for Supervisor Feedback Loops & Assumption Correction

CRITICAL SAFETY CONSTRAINTS:
- Assumptions MUST be declared for all plans/hypotheses
- Invalidation MUST trigger confidence/authority decay
- Self-validation is PROHIBITED
- Restoration requires external evidence
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json


class AssumptionStatus(Enum):
    """Status of an assumption"""
    ACTIVE = "active"              # Currently valid
    STALE = "stale"               # Needs review (past review_interval)
    INVALIDATED = "invalidated"   # Proven false by telemetry/feedback
    VALIDATED = "validated"       # Confirmed by external evidence
    UNDER_REVIEW = "under_review" # Being reviewed by supervisor


class FeedbackType(Enum):
    """Type of supervisor feedback"""
    APPROVE = "approve"           # Approve plan/execution
    DENY = "deny"                 # Deny plan/execution
    MODIFY = "modify"             # Request modifications
    INVALIDATE = "invalidate"     # Invalidate assumption
    VALIDATE = "validate"         # Validate assumption
    REQUEST_EVIDENCE = "request_evidence"  # Request more evidence


class InvalidationSource(Enum):
    """Source of assumption invalidation"""
    TELEMETRY = "telemetry"       # Telemetry data contradicts assumption
    SUPERVISOR = "supervisor"     # Supervisor feedback invalidates
    DETERMINISTIC = "deterministic"  # Deterministic verification fails
    TIMEOUT = "timeout"           # Assumption expired (stale)


@dataclass
class InvalidationSignal:
    """
    Signal indicating an assumption may be invalid
    """
    signal_id: str
    assumption_id: str
    source: InvalidationSource
    timestamp: datetime
    
    # Evidence of invalidation
    evidence: Dict[str, any]
    confidence: float  # Confidence that assumption is invalid (0-1)
    
    # Metadata
    detected_by: str  # System/component that detected invalidation
    severity: Literal["low", "medium", "high", "critical"]
    
    def __post_init__(self):
        """Validate signal"""
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")


@dataclass
class AssumptionArtifact:
    """
    An assumption that must be declared for plans/hypotheses
    
    CRITICAL: All plans and hypotheses MUST declare assumptions.
    Assumptions can be invalidated by telemetry or supervisor feedback.
    """
    assumption_id: str
    statement: str  # Clear statement of the assumption
    
    # Evidence supporting the assumption
    evidence_refs: List[str]  # References to evidence artifacts
    
    # Confidence (initially null for System A hypotheses)
    confidence_support: Optional[float] = None  # 0-1, null if not yet evaluated
    
    # Invalidation tracking
    invalidation_signals: List[InvalidationSignal] = field(default_factory=list)
    
    # Ownership
    owner_role: str  # Human/team responsible for this assumption
    
    # Review schedule
    review_interval_days: int = 30  # How often to review
    last_reviewed: Optional[datetime] = None
    next_review: Optional[datetime] = None
    
    # Status
    status: AssumptionStatus = AssumptionStatus.ACTIVE
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"  # Who created this assumption
    
    # Integrity
    integrity_hash: Optional[str] = None
    
    # CRITICAL: Self-validation prevention
    validated_by_self: bool = False  # MUST be False
    requires_external_validation: bool = True  # MUST be True for restoration
    
    def __post_init__(self):
        """Enforce safety constraints"""
        # CRITICAL: Cannot be validated by self
        if self.validated_by_self:
            raise ValueError("AssumptionArtifact.validated_by_self MUST be False")
        
        # CRITICAL: Must require external validation
        if not self.requires_external_validation:
            raise ValueError("AssumptionArtifact.requires_external_validation MUST be True")
        
        # Set next review date
        if self.next_review is None and self.last_reviewed:
            self.next_review = self.last_reviewed + timedelta(days=self.review_interval_days)
        elif self.next_review is None:
            self.next_review = self.created_at + timedelta(days=self.review_interval_days)
        
        # Compute integrity hash
        if self.integrity_hash is None:
            self.integrity_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of assumption"""
        data = {
            "assumption_id": self.assumption_id,
            "statement": self.statement,
            "evidence_refs": sorted(self.evidence_refs),
            "owner_role": self.owner_role,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def is_stale(self) -> bool:
        """Check if assumption is stale (needs review)"""
        if self.next_review is None:
            return False
        return datetime.utcnow() >= self.next_review
    
    def is_valid(self) -> bool:
        """Check if assumption is currently valid"""
        return self.status == AssumptionStatus.ACTIVE and not self.is_stale()
    
    def add_invalidation_signal(self, signal: InvalidationSignal):
        """Add invalidation signal"""
        self.invalidation_signals.append(signal)
        
        # If high confidence invalidation, mark as invalidated
        if signal.confidence >= 0.8 and signal.severity in ["high", "critical"]:
            self.status = AssumptionStatus.INVALIDATED


@dataclass
class SupervisorFeedbackArtifact:
    """
    Feedback from human supervisor
    
    Supervisors can:
    - Approve/deny plans and executions
    - Invalidate assumptions
    - Request modifications
    - Provide corrections
    - Request additional evidence
    """
    feedback_id: str
    feedback_type: FeedbackType
    
    # Target (what is being reviewed)
    target_type: Literal["hypothesis", "execution_packet", "assumption", "plan"]
    target_id: str
    
    # Feedback content
    rationale: str  # Why this feedback was given
    corrections: List[str] = field(default_factory=list)  # Requested corrections
    required_evidence: List[str] = field(default_factory=list)  # Evidence needed
    
    # Supervisor info
    supervisor_id: str
    supervisor_role: str
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Integrity
    integrity_hash: Optional[str] = None
    
    def __post_init__(self):
        """Compute integrity hash"""
        if self.integrity_hash is None:
            self.integrity_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of feedback"""
        data = {
            "feedback_id": self.feedback_id,
            "feedback_type": self.feedback_type.value,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "rationale": self.rationale,
            "supervisor_id": self.supervisor_id,
            "timestamp": self.timestamp.isoformat(),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class CorrectionAction:
    """
    Action to take when assumption is invalidated
    
    Correction actions:
    - Drop confidence
    - Decay authority
    - Freeze execution
    - Trigger re-expansion
    """
    action_id: str
    assumption_id: str
    
    # Actions to take
    drop_confidence_to: Optional[float] = None  # New confidence level
    decay_authority_to: Optional[str] = None    # New authority level
    freeze_execution: bool = False              # Freeze current execution
    downgrade_phase: bool = False               # Downgrade execution phase
    trigger_reexpansion: bool = False           # Trigger hypothesis re-expansion
    
    # Rationale
    reason: str
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    executed: bool = False
    executed_at: Optional[datetime] = None


@dataclass
class AssumptionBinding:
    """
    Binding between assumption and hypothesis/execution packet
    
    CRITICAL: Execution cannot proceed if critical assumptions are invalid.
    """
    binding_id: str
    assumption_id: str
    
    # What this assumption is bound to
    bound_to_type: Literal["hypothesis", "execution_packet", "plan"]
    bound_to_id: str
    
    # Criticality
    is_critical: bool  # If true, invalidation blocks execution
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConfidenceTrend:
    """
    Tracks confidence trend over time
    
    Used to detect confidence decay and trigger corrections.
    """
    artifact_id: str
    artifact_type: str
    
    # Confidence history
    confidence_history: List[Dict[str, any]] = field(default_factory=list)
    
    # Current state
    current_confidence: float = 1.0
    trend: Literal["stable", "increasing", "decreasing", "volatile"] = "stable"
    
    # Thresholds
    decay_threshold: float = 0.7  # Below this triggers correction
    volatility_threshold: float = 0.2  # Variance above this is volatile
    
    def add_confidence_point(self, confidence: float, reason: str):
        """Add confidence measurement"""
        self.confidence_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'confidence': confidence,
            'reason': reason
        })
        
        self.current_confidence = confidence
        self._update_trend()
    
    def _update_trend(self):
        """Update trend based on recent history"""
        if len(self.confidence_history) < 2:
            self.trend = "stable"
            return
        
        # Get last 5 points
        recent = self.confidence_history[-5:]
        values = [p['confidence'] for p in recent]
        
        # Calculate trend
        if len(values) >= 2:
            first_half = sum(values[:len(values)//2]) / (len(values)//2)
            second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
            
            diff = second_half - first_half
            
            if abs(diff) < 0.05:
                self.trend = "stable"
            elif diff > 0.05:
                self.trend = "increasing"
            else:
                self.trend = "decreasing"
        
        # Check volatility
        if len(values) >= 3:
            variance = sum((v - self.current_confidence) ** 2 for v in values) / len(values)
            if variance > self.volatility_threshold:
                self.trend = "volatile"
    
    def should_trigger_correction(self) -> bool:
        """Check if correction should be triggered"""
        return (
            self.current_confidence < self.decay_threshold or
            self.trend == "decreasing" or
            self.trend == "volatile"
        )


@dataclass
class MurphyIndexTrend:
    """
    Tracks Murphy index trend over time
    
    Rising Murphy index indicates increasing risk.
    """
    artifact_id: str
    artifact_type: str
    
    # Murphy index history
    murphy_history: List[Dict[str, any]] = field(default_factory=list)
    
    # Current state
    current_murphy: float = 0.0
    trend: Literal["stable", "increasing", "decreasing"] = "stable"
    
    # Thresholds
    danger_threshold: float = 0.7  # Above this triggers intervention
    
    def add_murphy_point(self, murphy_index: float, reason: str):
        """Add Murphy index measurement"""
        self.murphy_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'murphy_index': murphy_index,
            'reason': reason
        })
        
        self.current_murphy = murphy_index
        self._update_trend()
    
    def _update_trend(self):
        """Update trend based on recent history"""
        if len(self.murphy_history) < 2:
            self.trend = "stable"
            return
        
        # Get last 5 points
        recent = self.murphy_history[-5:]
        values = [p['murphy_index'] for p in recent]
        
        # Calculate trend
        if len(values) >= 2:
            first_half = sum(values[:len(values)//2]) / (len(values)//2)
            second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
            
            diff = second_half - first_half
            
            if abs(diff) < 0.05:
                self.trend = "stable"
            elif diff > 0.05:
                self.trend = "increasing"
            else:
                self.trend = "decreasing"
    
    def should_trigger_intervention(self) -> bool:
        """Check if intervention should be triggered"""
        return (
            self.current_murphy > self.danger_threshold or
            self.trend == "increasing"
        )


@dataclass
class ValidationEvidence:
    """
    Evidence for validating or invalidating an assumption
    
    CRITICAL: Evidence must be external (not self-generated).
    """
    evidence_id: str
    assumption_id: str
    
    # Evidence content
    evidence_type: Literal["telemetry", "deterministic", "human", "external_api"]
    evidence_data: Dict[str, any]
    
    # Validation result
    supports_assumption: bool  # True if evidence supports, False if contradicts
    confidence: float  # Confidence in this evidence (0-1)
    
    # Source
    source: str  # Where this evidence came from
    is_external: bool  # MUST be True for validation
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Validate evidence"""
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        
        # For validation, evidence must be external
        if self.supports_assumption and not self.is_external:
            raise ValueError("Validation evidence must be external")