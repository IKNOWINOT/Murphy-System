"""
Execution Context

Maintains state and context throughout task execution.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """
    Execution context that maintains state throughout task execution

    This context is passed through all phases and accumulates:
    - Phase outputs
    - Assumptions
    - Validation results
    - Human interventions
    - Audit trail
    """

    # Task information
    task_id: str
    task: Any
    execution_mode: str = "supervised"
    confidence_threshold: float = 0.7

    # Current state
    current_phase: Optional[str] = None
    phase_completed: bool = False

    # Accumulated outputs
    phase_outputs: Dict[str, Any] = field(default_factory=dict)
    final_output: Optional[Dict[str, Any]] = None

    # Confidence tracking
    confidence: float = 0.0
    confidence_history: List[Dict[str, float]] = field(default_factory=list)

    # Risk tracking
    risk_score: float = 0.0
    risk_history: List[Dict[str, float]] = field(default_factory=list)

    # Assumptions
    assumptions: List[str] = field(default_factory=list)
    invalidated_assumptions: List[str] = field(default_factory=list)

    # Human interaction
    human_approved: bool = False
    human_interventions: List[Dict[str, Any]] = field(default_factory=list)

    # Audit trail
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update(self, phase_result: Dict[str, Any]):
        """Update context with phase result"""
        phase = phase_result.get('phase')

        if phase:
            self.phase_outputs[phase] = phase_result.get('output', {})
            self.current_phase = phase
            self.phase_completed = True

            # Update confidence
            if 'confidence' in phase_result:
                self.confidence = phase_result['confidence']
                capped_append(self.confidence_history, {
                    'phase': phase,
                    'confidence': phase_result['confidence'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

            # Update risk
            if 'risk_score' in phase_result:
                self.risk_score = phase_result['risk_score']
                capped_append(self.risk_history, {
                    'phase': phase,
                    'risk_score': phase_result['risk_score'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

            # Add to audit trail
            capped_append(self.audit_trail, {
                'event': 'phase_completed',
                'phase': phase,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'confidence': self.confidence,
                'risk_score': self.risk_score
            })

    def add_assumption(self, assumption: str):
        """Add an assumption"""
        if assumption not in self.assumptions:
            self.assumptions.append(assumption)
            capped_append(self.audit_trail, {
                'event': 'assumption_added',
                'assumption': assumption,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

    def invalidate_assumption(self, assumption: str, reason: str):
        """Invalidate an assumption"""
        if assumption in self.assumptions and assumption not in self.invalidated_assumptions:
            self.invalidated_assumptions.append(assumption)
            capped_append(self.audit_trail, {
                'event': 'assumption_invalidated',
                'assumption': assumption,
                'reason': reason,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

    def add_human_intervention(self, intervention_type: str, details: Dict[str, Any]):
        """Record human intervention"""
        intervention = {
            'type': intervention_type,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.human_interventions.append(intervention)
        capped_append(self.audit_trail, {
            'event': 'human_intervention',
            'intervention': intervention,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log an event to audit trail"""
        capped_append(self.audit_trail, {
            'event': event_type,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    def get_phase_output(self, phase: str) -> Optional[Dict[str, Any]]:
        """Get output from a specific phase"""
        return self.phase_outputs.get(phase)

    def has_invalidated_assumptions(self) -> bool:
        """Check if any assumptions have been invalidated"""
        return len(self.invalidated_assumptions) > 0

    def get_confidence_trend(self) -> str:
        """Get confidence trend (improving/stable/declining)"""
        if len(self.confidence_history) < 2:
            return "stable"

        recent = [h['confidence'] for h in self.confidence_history[-3:]]

        if all(recent[i] < recent[i+1] for i in range(len(recent)-1)):
            return "improving"
        elif all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
            return "declining"
        else:
            return "stable"

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary"""
        return {
            'task_id': self.task_id,
            'execution_mode': self.execution_mode,
            'confidence_threshold': self.confidence_threshold,
            'current_phase': self.current_phase,
            'confidence': self.confidence,
            'risk_score': self.risk_score,
            'assumptions': self.assumptions,
            'invalidated_assumptions': self.invalidated_assumptions,
            'human_interventions': self.human_interventions,
            'audit_trail': self.audit_trail,
            'started_at': self.started_at.isoformat()
        }
