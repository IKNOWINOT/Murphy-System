"""
Execution Context

Maintains state and context throughout task execution.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

import logging

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
    started_at: datetime = field(default_factory=datetime.now)
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
                self.confidence_history.append({
                    'phase': phase,
                    'confidence': phase_result['confidence'],
                    'timestamp': datetime.now().isoformat()
                })

            # Update risk
            if 'risk_score' in phase_result:
                self.risk_score = phase_result['risk_score']
                self.risk_history.append({
                    'phase': phase,
                    'risk_score': phase_result['risk_score'],
                    'timestamp': datetime.now().isoformat()
                })

            # Add to audit trail
            self.audit_trail.append({
                'event': 'phase_completed',
                'phase': phase,
                'timestamp': datetime.now().isoformat(),
                'confidence': self.confidence,
                'risk_score': self.risk_score
            })

    def add_assumption(self, assumption: str):
        """Add an assumption"""
        if assumption not in self.assumptions:
            self.assumptions.append(assumption)
            self.audit_trail.append({
                'event': 'assumption_added',
                'assumption': assumption,
                'timestamp': datetime.now().isoformat()
            })

    def invalidate_assumption(self, assumption: str, reason: str):
        """Invalidate an assumption"""
        if assumption in self.assumptions and assumption not in self.invalidated_assumptions:
            self.invalidated_assumptions.append(assumption)
            self.audit_trail.append({
                'event': 'assumption_invalidated',
                'assumption': assumption,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            })

    def add_human_intervention(self, intervention_type: str, details: Dict[str, Any]):
        """Record human intervention"""
        intervention = {
            'type': intervention_type,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.human_interventions.append(intervention)
        self.audit_trail.append({
            'event': 'human_intervention',
            'intervention': intervention,
            'timestamp': datetime.now().isoformat()
        })

    def log_event(self, event_type: str, details: Dict[str, Any]):
        """Log an event to audit trail"""
        self.audit_trail.append({
            'event': event_type,
            'details': details,
            'timestamp': datetime.now().isoformat()
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
