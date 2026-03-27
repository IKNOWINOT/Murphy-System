"""
Permutation Policy Registry for Murphy System

Stores learned sequence families and their promotion status. This is the central
registry for permutation-discovered orderings that have been validated through
exploratory runs and promoted to procedural execution.

Implements Mode A → Mode B transition from the Permutation Calibration spec:
- Experimental: Newly discovered pattern, lightly supported
- Probationary: Shows repeated promise, not enough validation
- Promoted: Allowed to drive procedural routing in Mode B
- Deprecated: Demoted because drift or fragility appeared

Reference: Permutation Calibration Application Spec Section 7 & 5.2
Owner: INONI LLC / Corey Post
"""

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class SequenceStatus(str, Enum):
    """Lifecycle status for a learned sequence family."""
    EXPERIMENTAL = "experimental"
    PROBATIONARY = "probationary"
    PROMOTED = "promoted"
    DEPRECATED = "deprecated"


class SequenceType(str, Enum):
    """Type of sequence being tracked."""
    CONNECTOR_ORDER = "connector_order"       # Order of connector queries
    EVIDENCE_ORDER = "evidence_order"         # Order of evidence collection
    ESCALATION_ORDER = "escalation_order"     # Order of escalation steps
    API_RESPONSE_ORDER = "api_response_order" # Order of API responses
    FEEDBACK_ORDER = "feedback_order"         # Order of human feedback
    TELEMETRY_ORDER = "telemetry_order"       # Order of telemetry data
    TRIAGE_ORDER = "triage_order"             # Order of triage steps
    ROUTING_ORDER = "routing_order"           # Order of routing decisions


@dataclass
class SequenceEvaluation:
    """Result of evaluating a sequence ordering."""
    evaluation_id: str
    sequence_id: str
    outcome_quality: float          # 0.0-1.0 overall quality score
    calibration_quality: float      # 0.0-1.0 confidence calibration
    stability_score: float          # 0.0-1.0 stability across variations
    latency_ms: float               # Execution latency
    cost: float                     # Execution cost
    hitl_efficiency: float          # 0.0-1.0 HITL efficiency
    governance_fit: float           # 0.0-1.0 governance compliance
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SequenceFamily:
    """A learned sequence family representing an ordering pattern.
    
    This represents the core learnable unit - a sequence of operations
    that Murphy has discovered through exploratory permutation and
    validated as producing better outcomes than alternatives.
    """
    sequence_id: str
    name: str
    sequence_type: SequenceType
    domain: str                               # Domain/task family this applies to
    ordering: List[str]                       # The ordered sequence of steps/operations
    status: SequenceStatus = SequenceStatus.EXPERIMENTAL
    
    # Evaluation metrics
    success_count: int = 0
    failure_count: int = 0
    total_evaluations: int = 0
    avg_outcome_quality: float = 0.0
    avg_calibration_quality: float = 0.0
    avg_stability_score: float = 0.0
    confidence_score: float = 0.5
    
    # Promotion tracking
    promoted_at: Optional[str] = None
    deprecated_at: Optional[str] = None
    deprecation_reason: Optional[str] = None
    
    # Gate tracking
    requires_gate_approval: bool = True
    gate_approved: bool = False
    gate_approver: Optional[str] = None
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_used_at: Optional[str] = None
    last_evaluated_at: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class PromotionCriteria:
    """Criteria for promoting a sequence from one status to another."""
    min_evaluations: int = 10
    min_success_rate: float = 0.75
    min_stability_score: float = 0.7
    min_calibration_quality: float = 0.65
    max_fragility: float = 0.3
    require_gate_approval: bool = True
    require_explanation: bool = True


# Default promotion criteria by status transition
DEFAULT_PROMOTION_CRITERIA = {
    (SequenceStatus.EXPERIMENTAL, SequenceStatus.PROBATIONARY): PromotionCriteria(
        min_evaluations=5,
        min_success_rate=0.6,
        min_stability_score=0.5,
        min_calibration_quality=0.5,
        max_fragility=0.5,
        require_gate_approval=False,
        require_explanation=False,
    ),
    (SequenceStatus.PROBATIONARY, SequenceStatus.PROMOTED): PromotionCriteria(
        min_evaluations=10,
        min_success_rate=0.75,
        min_stability_score=0.7,
        min_calibration_quality=0.65,
        max_fragility=0.3,
        require_gate_approval=True,
        require_explanation=True,
    ),
}


class PermutationPolicyRegistry:
    """Central registry for learned sequence families.
    
    Manages the lifecycle of permutation-discovered orderings from
    experimental discovery through promotion to procedural execution.
    
    Implements the promote model from spec Section 5.2:
    - Experimental → Probationary → Promoted → (optionally) Deprecated
    """
    
    _MAX_SEQUENCES = 10_000
    _MAX_EVALUATIONS = 50_000
    _MAX_HISTORY = 10_000
    
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sequences: Dict[str, SequenceFamily] = {}
        self._evaluations: Dict[str, List[SequenceEvaluation]] = defaultdict(list)
        self._domain_index: Dict[str, List[str]] = defaultdict(list)
        self._type_index: Dict[SequenceType, List[str]] = defaultdict(list)
        self._status_index: Dict[SequenceStatus, List[str]] = defaultdict(list)
        self._history: List[Dict[str, Any]] = []
        self._promotion_criteria: Dict[Tuple[SequenceStatus, SequenceStatus], PromotionCriteria] = dict(DEFAULT_PROMOTION_CRITERIA)
        logger.info("PermutationPolicyRegistry initialized")
    
    # ------------------------------------------------------------------
    # Sequence Registration
    # ------------------------------------------------------------------
    
    def register_sequence(
        self,
        name: str,
        sequence_type: SequenceType,
        domain: str,
        ordering: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a new experimental sequence family.
        
        Args:
            name: Human-readable name for the sequence
            sequence_type: Type of sequence being registered
            domain: Domain/task family this applies to
            ordering: The ordered list of steps/operations
            metadata: Optional additional metadata
            
        Returns:
            sequence_id: Unique identifier for the registered sequence
        """
        sequence_id = f"seq-{uuid.uuid4().hex[:12]}"
        sequence = SequenceFamily(
            sequence_id=sequence_id,
            name=name,
            sequence_type=sequence_type,
            domain=domain,
            ordering=list(ordering),
            metadata=metadata or {},
        )
        
        with self._lock:
            if len(self._sequences) >= self._MAX_SEQUENCES:
                # Evict oldest deprecated sequences first
                deprecated = [s for s in self._sequences.values() 
                             if s.status == SequenceStatus.DEPRECATED]
                if deprecated:
                    deprecated.sort(key=lambda s: s.deprecated_at or s.created_at)
                    to_remove = deprecated[:len(deprecated)//2]
                    for s in to_remove:
                        self._remove_sequence_locked(s.sequence_id)
                        
            self._sequences[sequence_id] = sequence
            self._domain_index[domain].append(sequence_id)
            self._type_index[sequence_type].append(sequence_id)
            self._status_index[SequenceStatus.EXPERIMENTAL].append(sequence_id)
            
            self._record_event_locked("sequence_registered", sequence_id, {
                "name": name,
                "sequence_type": sequence_type.value,
                "domain": domain,
                "ordering": ordering,
            })
            
        logger.info("Registered sequence %s (%s) for domain '%s'", sequence_id, name, domain)
        return sequence_id
    
    def _remove_sequence_locked(self, sequence_id: str) -> None:
        """Remove a sequence from all indices (must hold lock)."""
        seq = self._sequences.pop(sequence_id, None)
        if seq:
            if sequence_id in self._domain_index[seq.domain]:
                self._domain_index[seq.domain].remove(sequence_id)
            if sequence_id in self._type_index[seq.sequence_type]:
                self._type_index[seq.sequence_type].remove(sequence_id)
            if sequence_id in self._status_index[seq.status]:
                self._status_index[seq.status].remove(sequence_id)
            self._evaluations.pop(sequence_id, None)
    
    # ------------------------------------------------------------------
    # Evaluation Recording
    # ------------------------------------------------------------------
    
    def record_evaluation(
        self,
        sequence_id: str,
        outcome_quality: float,
        calibration_quality: float,
        stability_score: float,
        latency_ms: float = 0.0,
        cost: float = 0.0,
        hitl_efficiency: float = 1.0,
        governance_fit: float = 1.0,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record an evaluation result for a sequence.
        
        This updates the sequence's metrics and potentially triggers
        automatic promotion if criteria are met.
        
        Returns:
            Status dict with evaluation result and any promotion triggered
        """
        evaluation = SequenceEvaluation(
            evaluation_id=f"eval-{uuid.uuid4().hex[:12]}",
            sequence_id=sequence_id,
            outcome_quality=_clamp(outcome_quality),
            calibration_quality=_clamp(calibration_quality),
            stability_score=_clamp(stability_score),
            latency_ms=max(0.0, latency_ms),
            cost=max(0.0, cost),
            hitl_efficiency=_clamp(hitl_efficiency),
            governance_fit=_clamp(governance_fit),
            metadata=metadata or {},
        )
        
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"status": "error", "reason": "sequence_not_found", "sequence_id": sequence_id}
            
            # Record evaluation
            evals = self._evaluations[sequence_id]
            if len(evals) >= self._MAX_EVALUATIONS // len(self._sequences) if self._sequences else 100:
                evals.pop(0)
            evals.append(evaluation)
            
            # Update sequence metrics
            seq.total_evaluations += 1
            if success:
                seq.success_count += 1
            else:
                seq.failure_count += 1
            
            # Update running averages
            n = seq.total_evaluations
            seq.avg_outcome_quality = ((seq.avg_outcome_quality * (n - 1)) + outcome_quality) / n
            seq.avg_calibration_quality = ((seq.avg_calibration_quality * (n - 1)) + calibration_quality) / n
            seq.avg_stability_score = ((seq.avg_stability_score * (n - 1)) + stability_score) / n
            
            # Update confidence score (Bayesian-style update)
            success_rate = seq.success_count / max(1, seq.total_evaluations)
            seq.confidence_score = _clamp(
                seq.confidence_score * 0.9 + (success_rate * seq.avg_stability_score) * 0.1
            )
            
            seq.last_evaluated_at = evaluation.timestamp
            
            self._record_event_locked("evaluation_recorded", sequence_id, {
                "evaluation_id": evaluation.evaluation_id,
                "success": success,
                "outcome_quality": outcome_quality,
            })
            
            # Check for automatic promotion
            promotion_result = self._check_auto_promotion_locked(seq)
            
        return {
            "status": "ok",
            "evaluation_id": evaluation.evaluation_id,
            "sequence_id": sequence_id,
            "total_evaluations": seq.total_evaluations,
            "confidence_score": round(seq.confidence_score, 4),
            "promotion_result": promotion_result,
        }
    
    def _check_auto_promotion_locked(self, seq: SequenceFamily) -> Optional[Dict[str, Any]]:
        """Check if a sequence qualifies for automatic promotion."""
        if seq.status == SequenceStatus.PROMOTED:
            return None
        if seq.status == SequenceStatus.DEPRECATED:
            return None
            
        # Determine target status
        if seq.status == SequenceStatus.EXPERIMENTAL:
            target = SequenceStatus.PROBATIONARY
        elif seq.status == SequenceStatus.PROBATIONARY:
            target = SequenceStatus.PROMOTED
        else:
            return None
        
        criteria = self._promotion_criteria.get((seq.status, target))
        if criteria is None:
            return None
            
        # Check criteria
        success_rate = seq.success_count / max(1, seq.total_evaluations)
        fragility = 1.0 - seq.avg_stability_score
        
        if seq.total_evaluations < criteria.min_evaluations:
            return None
        if success_rate < criteria.min_success_rate:
            return None
        if seq.avg_stability_score < criteria.min_stability_score:
            return None
        if seq.avg_calibration_quality < criteria.min_calibration_quality:
            return None
        if fragility > criteria.max_fragility:
            return None
        if criteria.require_gate_approval and not seq.gate_approved:
            return {"status": "pending_gate_approval", "target": target.value}
            
        # Auto-promote
        return self._promote_locked(seq, target)
    
    # ------------------------------------------------------------------
    # Promotion / Demotion
    # ------------------------------------------------------------------
    
    def promote_sequence(
        self,
        sequence_id: str,
        target_status: SequenceStatus,
        approver: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Manually promote a sequence to a new status.
        
        Args:
            sequence_id: ID of the sequence to promote
            target_status: Target status to promote to
            approver: Optional approver identity for gate approval
            reason: Optional reason for promotion
            
        Returns:
            Status dict with promotion result
        """
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"status": "error", "reason": "sequence_not_found", "sequence_id": sequence_id}
            
            if approver:
                seq.gate_approved = True
                seq.gate_approver = approver
                
            return self._promote_locked(seq, target_status, reason)
    
    def _promote_locked(
        self, 
        seq: SequenceFamily, 
        target: SequenceStatus,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Internal promotion logic (must hold lock)."""
        old_status = seq.status
        
        # Update status indices
        if seq.sequence_id in self._status_index[old_status]:
            self._status_index[old_status].remove(seq.sequence_id)
        self._status_index[target].append(seq.sequence_id)
        
        seq.status = target
        now = datetime.now(timezone.utc).isoformat()
        
        if target == SequenceStatus.PROMOTED:
            seq.promoted_at = now
        elif target == SequenceStatus.DEPRECATED:
            seq.deprecated_at = now
            seq.deprecation_reason = reason
            
        self._record_event_locked("sequence_promoted", seq.sequence_id, {
            "old_status": old_status.value,
            "new_status": target.value,
            "reason": reason,
        })
        
        logger.info("Promoted sequence %s from %s to %s", seq.sequence_id, old_status.value, target.value)
        
        return {
            "status": "promoted",
            "sequence_id": seq.sequence_id,
            "old_status": old_status.value,
            "new_status": target.value,
            "promoted_at": now,
        }
    
    def deprecate_sequence(
        self,
        sequence_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Deprecate a sequence that has become unreliable.
        
        This implements the reversion rule from spec Section 5.3:
        - Success rate dropped
        - Confidence drifted down
        - Connector timing changed
        - Human overrides rose
        - Policy became brittle
        """
        return self.promote_sequence(
            sequence_id,
            SequenceStatus.DEPRECATED,
            reason=reason,
        )
    
    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------
    
    def get_sequence(self, sequence_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific sequence."""
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return None
            return self._sequence_to_dict(seq)
    
    def _sequence_to_dict(self, seq: SequenceFamily) -> Dict[str, Any]:
        """Convert sequence to dict representation."""
        success_rate = seq.success_count / max(1, seq.total_evaluations)
        return {
            "sequence_id": seq.sequence_id,
            "name": seq.name,
            "sequence_type": seq.sequence_type.value,
            "domain": seq.domain,
            "ordering": seq.ordering,
            "status": seq.status.value,
            "success_count": seq.success_count,
            "failure_count": seq.failure_count,
            "total_evaluations": seq.total_evaluations,
            "success_rate": round(success_rate, 4),
            "avg_outcome_quality": round(seq.avg_outcome_quality, 4),
            "avg_calibration_quality": round(seq.avg_calibration_quality, 4),
            "avg_stability_score": round(seq.avg_stability_score, 4),
            "confidence_score": round(seq.confidence_score, 4),
            "fragility": round(1.0 - seq.avg_stability_score, 4),
            "gate_approved": seq.gate_approved,
            "gate_approver": seq.gate_approver,
            "created_at": seq.created_at,
            "promoted_at": seq.promoted_at,
            "deprecated_at": seq.deprecated_at,
            "deprecation_reason": seq.deprecation_reason,
            "last_used_at": seq.last_used_at,
            "last_evaluated_at": seq.last_evaluated_at,
            "metadata": seq.metadata,
        }
    
    def find_sequences(
        self,
        domain: Optional[str] = None,
        sequence_type: Optional[SequenceType] = None,
        status: Optional[SequenceStatus] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Find sequences matching the given criteria."""
        with self._lock:
            candidates = list(self._sequences.values())
            
            if domain is not None:
                candidates = [s for s in candidates if s.domain == domain]
            if sequence_type is not None:
                candidates = [s for s in candidates if s.sequence_type == sequence_type]
            if status is not None:
                candidates = [s for s in candidates if s.status == status]
            if min_confidence > 0.0:
                candidates = [s for s in candidates if s.confidence_score >= min_confidence]
            
            # Sort by confidence score descending
            candidates.sort(key=lambda s: s.confidence_score, reverse=True)
            
            return [self._sequence_to_dict(s) for s in candidates]
    
    def get_promoted_sequences(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all promoted sequences, optionally filtered by domain.
        
        These are the sequences available for Mode B procedural execution.
        """
        return self.find_sequences(domain=domain, status=SequenceStatus.PROMOTED)
    
    def get_best_sequence_for_domain(
        self,
        domain: str,
        sequence_type: Optional[SequenceType] = None,
        require_promoted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get the best (highest confidence) sequence for a domain.
        
        Args:
            domain: Domain to find sequence for
            sequence_type: Optional type filter
            require_promoted: If True, only return promoted sequences
            
        Returns:
            Best matching sequence or None
        """
        status = SequenceStatus.PROMOTED if require_promoted else None
        sequences = self.find_sequences(
            domain=domain,
            sequence_type=sequence_type,
            status=status,
        )
        return sequences[0] if sequences else None
    
    # ------------------------------------------------------------------
    # Usage Tracking
    # ------------------------------------------------------------------
    
    def record_usage(self, sequence_id: str) -> Dict[str, Any]:
        """Record that a sequence was used in execution."""
        with self._lock:
            seq = self._sequences.get(sequence_id)
            if seq is None:
                return {"status": "error", "reason": "sequence_not_found"}
            seq.last_used_at = datetime.now(timezone.utc).isoformat()
            return {"status": "ok", "sequence_id": sequence_id, "last_used_at": seq.last_used_at}
    
    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall registry statistics."""
        with self._lock:
            total = len(self._sequences)
            by_status = {s.value: len(self._status_index[s]) for s in SequenceStatus}
            by_type = {t.value: len(self._type_index[t]) for t in SequenceType}
            
            promoted = [s for s in self._sequences.values() if s.status == SequenceStatus.PROMOTED]
            avg_promoted_confidence = (
                sum(s.confidence_score for s in promoted) / len(promoted) 
                if promoted else 0.0
            )
            
            total_evaluations = sum(len(e) for e in self._evaluations.values())
            
            return {
                "status": "ok",
                "total_sequences": total,
                "by_status": by_status,
                "by_type": by_type,
                "total_evaluations": total_evaluations,
                "promoted_count": by_status.get("promoted", 0),
                "avg_promoted_confidence": round(avg_promoted_confidence, 4),
                "domains": list(self._domain_index.keys()),
                "history_events": len(self._history),
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get registry operational status."""
        stats = self.get_statistics()
        return {
            "engine": "PermutationPolicyRegistry",
            "operational": True,
            **stats,
        }
    
    # ------------------------------------------------------------------
    # History / Audit
    # ------------------------------------------------------------------
    
    def _record_event_locked(
        self, 
        event_type: str, 
        sequence_id: str, 
        details: Dict[str, Any]
    ) -> None:
        """Record an event in history (must hold lock)."""
        event = {
            "event_id": uuid.uuid4().hex[:12],
            "event_type": event_type,
            "sequence_id": sequence_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }
        capped_append(self._history, event, self._MAX_HISTORY)
    
    def get_history(
        self,
        sequence_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get event history, optionally filtered."""
        with self._lock:
            events = list(self._history)
            
        if sequence_id:
            events = [e for e in events if e.get("sequence_id") == sequence_id]
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
            
        return list(reversed(events[-limit:]))
    
    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    
    def clear(self) -> None:
        """Clear all registry state."""
        with self._lock:
            self._sequences.clear()
            self._evaluations.clear()
            self._domain_index.clear()
            self._type_index.clear()
            self._status_index.clear()
            self._history.clear()
        logger.info("PermutationPolicyRegistry cleared")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value between lo and hi."""
    return max(lo, min(hi, value))
