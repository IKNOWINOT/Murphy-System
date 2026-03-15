"""
MFGC Core - Murphy-Free Generative Control AI
Complete implementation of the 7-phase control system
"""

import copy
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from pydantic import BaseModel, Field, field_validator
    _PYDANTIC_AVAILABLE = True
except ImportError:
    _PYDANTIC_AVAILABLE = False


# === TYPED STATE VECTOR (GAP-1) ===

N_BASE_DIMS: int = 6
"""Number of base state dimensions in :class:`StateVector`."""

# GAP-5 stability constants
HYSTERESIS_BAND: float = 0.05
"""If confidence is within this band of a phase threshold, hold current phase."""

MAX_PHASE_REVERSALS: int = 3
"""Maximum allowed phase reversals before forward progression is locked."""


if _PYDANTIC_AVAILABLE:
    class StateVector(BaseModel):
        """
        Typed state vector x_t for the MFGC system.

        Contains six base dimensions (each in [0.0, 1.0]) plus an optional
        dict of custom domain-specific float dimensions.

        Supports dict-like access for backward compatibility with code that
        treats x_t as a plain ``Dict[str, Any]``.
        """

        domain_knowledge_level: float = Field(default=0.0, ge=0.0, le=1.0)
        constraint_satisfaction_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
        information_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
        verification_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
        risk_exposure: float = Field(default=0.0, ge=0.0, le=1.0)
        authority_utilization: float = Field(default=0.0, ge=0.0, le=1.0)
        custom_dimensions: Dict[str, float] = Field(default_factory=dict)
        uncertainty: Dict[str, float] = Field(default_factory=dict)

        # Allow extra dict-like keys stored in extra_data for backward compat
        model_config = {"extra": "allow"}

        def get_dimensionality(self) -> int:
            """Return total number of dimensions (base + custom)."""
            return N_BASE_DIMS + len(self.custom_dimensions)

        # -------------------------------------------------------------- #
        # Dict-like interface for backward compatibility
        # -------------------------------------------------------------- #

        def get(self, key: str, default: Any = None) -> Any:
            """Dict-like get for backward compatibility."""
            base = {
                'domain_knowledge_level': self.domain_knowledge_level,
                'constraint_satisfaction_ratio': self.constraint_satisfaction_ratio,
                'information_completeness': self.information_completeness,
                'verification_coverage': self.verification_coverage,
                'risk_exposure': self.risk_exposure,
                'authority_utilization': self.authority_utilization,
            }
            if key in base:
                return base[key]
            if key in self.custom_dimensions:
                return self.custom_dimensions[key]
            # Check pydantic extra fields
            try:
                return self.__pydantic_extra__.get(key, default)
            except AttributeError:
                return default

        def __getitem__(self, key: str) -> Any:
            result = self.get(key)
            if result is None and key not in self._base_keys():
                raise KeyError(key)
            return result

        def __setitem__(self, key: str, value: Any) -> None:
            base_keys = self._base_keys()
            if key in base_keys:
                object.__setattr__(self, key, value)
            else:
                self.custom_dimensions[key] = float(value) if isinstance(value, (int, float)) else value

        def __contains__(self, key: str) -> bool:
            return self.get(key) is not None or key in self._base_keys()

        def _base_keys(self):
            return {
                'domain_knowledge_level', 'constraint_satisfaction_ratio',
                'information_completeness', 'verification_coverage',
                'risk_exposure', 'authority_utilization',
            }

        def update(self, data: Dict[str, Any]) -> None:
            """Dict-like update for backward compatibility."""
            for k, v in data.items():
                self[k] = v

        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> "StateVector":
            """Create a StateVector from a plain dict."""
            base_keys = {
                'domain_knowledge_level', 'constraint_satisfaction_ratio',
                'information_completeness', 'verification_coverage',
                'risk_exposure', 'authority_utilization',
                'custom_dimensions', 'uncertainty',
            }
            base = {k: v for k, v in data.items() if k in base_keys}
            extra = {k: v for k, v in data.items() if k not in base_keys}
            sv = cls(**base)
            if extra:
                if sv.__pydantic_extra__ is None:
                    object.__setattr__(sv, '__pydantic_extra__', {})
                sv.__pydantic_extra__.update(extra)
            return sv

else:
    # Fallback dataclass when pydantic is not available
    @dataclass
    class StateVector:  # type: ignore[no-redef]
        """Typed state vector (fallback dataclass when pydantic unavailable)."""

        domain_knowledge_level: float = 0.0
        constraint_satisfaction_ratio: float = 0.0
        information_completeness: float = 0.0
        verification_coverage: float = 0.0
        risk_exposure: float = 0.0
        authority_utilization: float = 0.0
        custom_dimensions: Dict[str, float] = field(default_factory=dict)
        uncertainty: Dict[str, float] = field(default_factory=dict)
        _extra: Dict[str, Any] = field(default_factory=dict, repr=False)

        def get_dimensionality(self) -> int:
            return N_BASE_DIMS + len(self.custom_dimensions)

        def get(self, key: str, default: Any = None) -> Any:
            base = {
                'domain_knowledge_level': self.domain_knowledge_level,
                'constraint_satisfaction_ratio': self.constraint_satisfaction_ratio,
                'information_completeness': self.information_completeness,
                'verification_coverage': self.verification_coverage,
                'risk_exposure': self.risk_exposure,
                'authority_utilization': self.authority_utilization,
            }
            if key in base:
                return base[key]
            if key in self.custom_dimensions:
                return self.custom_dimensions[key]
            return self._extra.get(key, default)

        def __getitem__(self, key: str) -> Any:
            result = self.get(key)
            if result is None:
                raise KeyError(key)
            return result

        def __setitem__(self, key: str, value: Any) -> None:
            base_keys = {
                'domain_knowledge_level', 'constraint_satisfaction_ratio',
                'information_completeness', 'verification_coverage',
                'risk_exposure', 'authority_utilization',
            }
            if key in base_keys:
                setattr(self, key, value)
            else:
                self.custom_dimensions[key] = float(value) if isinstance(value, (int, float)) else value

        def __contains__(self, key: str) -> bool:
            return self.get(key) is not None

        def update(self, data: Dict[str, Any]) -> None:
            for k, v in data.items():
                self[k] = v

        @classmethod
        def from_dict(cls, data: Dict[str, Any]) -> "StateVector":
            base_keys = {
                'domain_knowledge_level', 'constraint_satisfaction_ratio',
                'information_completeness', 'verification_coverage',
                'risk_exposure', 'authority_utilization',
                'custom_dimensions', 'uncertainty',
            }
            base = {k: v for k, v in data.items() if k in base_keys}
            extra = {k: v for k, v in data.items() if k not in base_keys}
            sv = cls(**base)
            sv._extra.update(extra)
            return sv


# === PHASE DEFINITIONS ===

class Phase(Enum):
    """7-phase execution sequence"""
    EXPAND = "expand"
    TYPE = "type"
    ENUMERATE = "enumerate"
    CONSTRAIN = "constrain"
    COLLAPSE = "collapse"
    BIND = "bind"
    EXECUTE = "execute"

    @property
    def confidence_threshold(self) -> float:
        """Minimum confidence to advance from this phase"""
        thresholds = {
            Phase.EXPAND: 0.3,
            Phase.TYPE: 0.5,
            Phase.ENUMERATE: 0.6,
            Phase.CONSTRAIN: 0.65,
            Phase.COLLAPSE: 0.7,
            Phase.BIND: 0.75,
            Phase.EXECUTE: 0.85
        }
        return thresholds[self]

    @property
    def weights(self) -> Tuple[float, float]:
        """(w_g, w_d) weights for generative vs deterministic"""
        weights_map = {
            Phase.EXPAND: (0.9, 0.1),
            Phase.TYPE: (0.8, 0.2),
            Phase.ENUMERATE: (0.7, 0.3),
            Phase.CONSTRAIN: (0.5, 0.5),
            Phase.COLLAPSE: (0.3, 0.7),
            Phase.BIND: (0.2, 0.8),
            Phase.EXECUTE: (0.1, 0.9)
        }
        return weights_map[self]


# === STATE MANAGEMENT ===

@dataclass
class MFGCSystemState:
    """Complete system state at time t"""
    # Core state — x_t is now a typed StateVector (GAP-1)
    x_t: StateVector = field(default_factory=StateVector)
    c_t: float = 0.0  # Confidence
    p_t: Phase = Phase.EXPAND  # Current phase
    a_t: float = 0.0  # Authority level
    G_t: List[str] = field(default_factory=list)  # Active gates
    M_t: float = 0.0  # Murphy index

    # Stability tracking (GAP-5)
    confidence_velocity: float = 0.0  # Rate of change of confidence
    _phase_reversal_count: int = field(default=0, repr=False)
    _forward_locked: bool = field(default=False, repr=False)

    # Execution tracking
    phase_history: List[Phase] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)
    murphy_history: List[float] = field(default_factory=list)
    gate_history: List[List[str]] = field(default_factory=list)

    # Swarm data
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    gate_proposals: List[Dict[str, Any]] = field(default_factory=list)

    # Audit trail
    events: List[Dict[str, Any]] = field(default_factory=list)

    # Feedback / learning loop (CFP-4)
    pending_feedback_signals: List[Any] = field(default_factory=list, repr=False)
    """Accumulated :class:`~feedback_integrator.FeedbackSignal` objects for
    the current execution cycle, consumed by :class:`MFGCController`."""

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Add event to audit trail"""
        self.events.append({
            'timestamp': time.time(),
            'phase': self.p_t.value,
            'confidence': self.c_t,
            'murphy_index': self.M_t,
            'type': event_type,
            'data': data
        })

    def _update_confidence_velocity(self) -> None:
        """Update confidence_velocity from history (GAP-5)."""
        if len(self.confidence_history) >= 2:
            self.confidence_velocity = (
                self.confidence_history[-1] - self.confidence_history[-2]
            )

    def is_stable(self, n: int = 3) -> bool:
        """Return True if |confidence_velocity| < 0.01 for the last *n* steps (GAP-5)."""
        if len(self.confidence_history) < n:
            return False
        recent = self.confidence_history[-n:]
        for i in range(1, len(recent)):
            if abs(recent[i] - recent[i - 1]) >= 0.01:
                return False
        return True

    def to_canonical(self):
        """Convert to a typed CanonicalStateVector for control-theoretic use.

        Returns:
            A :class:`~control_theory.canonical_state.CanonicalStateVector`
            populated from this state's scalar fields.
        """
        from control_theory.state_adapter import from_mfgc_state
        return from_mfgc_state(self)

    def advance_phase(self):
        """Move to next phase, tracking reversals for stability safeguards (GAP-5)."""
        phases = list(Phase)
        current_idx = phases.index(self.p_t)
        if current_idx < len(phases) - 1:
            old_phase = self.p_t
            self.p_t = phases[current_idx + 1]
            if old_phase != self.p_t:  # Only append if actually changed
                # Detect reversal: if last history entry is ahead of new phase
                if (self.phase_history and
                        phases.index(self.phase_history[-1]) > phases.index(self.p_t)):
                    self._phase_reversal_count += 1
                    if self._phase_reversal_count > MAX_PHASE_REVERSALS:
                        self._forward_locked = True
                self.phase_history.append(self.p_t)
            self.log_event('phase_advance', {'new_phase': self.p_t.value})


# === CONFIDENCE ENGINE ===

class ConfidenceEngine:
    """
    Continuous confidence mathematics:
    c_t = w_g(p_t) × G(x_t) + w_d(p_t) × D(x_t)
    """

    def __init__(self):
        self.base_generative = 0.5
        self.base_deterministic = 0.8

    def compute_confidence(self, state: MFGCSystemState,
                          generative_score: float,
                          deterministic_score: float) -> float:
        """
        Compute confidence using phase-locked weights.

        Incorporates hysteresis (GAP-5): if the raw confidence is within
        ``HYSTERESIS_BAND`` of the current phase threshold, the previous
        confidence value is held to prevent phase oscillation.

        Args:
            state: Current system state
            generative_score: G(x_t) - quality of generated candidates
            deterministic_score: D(x_t) - verification score

        Returns:
            Confidence value in [0, 1]
        """
        w_g, w_d = state.p_t.weights

        # Weighted combination
        confidence = w_g * generative_score + w_d * deterministic_score

        # Clamp to [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        # GAP-5: hysteresis — hold current confidence if within HYSTERESIS_BAND
        # of the phase threshold to prevent oscillation
        threshold = state.p_t.confidence_threshold
        if state.confidence_history and abs(confidence - threshold) < HYSTERESIS_BAND:
            confidence = state.confidence_history[-1]

        # Update confidence velocity (GAP-5) using the previous history only,
        # without mutating history (callers own the history.append() call).
        if state.confidence_history:
            state.confidence_velocity = confidence - state.confidence_history[-1]

        state.log_event('confidence_update', {
            'w_g': w_g,
            'w_d': w_d,
            'G_score': generative_score,
            'D_score': deterministic_score,
            'confidence': confidence
        })

        return confidence

    def evaluate_generative(self, candidates: List[Dict[str, Any]]) -> float:
        """
        Evaluate quality of generated candidates

        Metrics:
        - Diversity: How different are the candidates?
        - Coverage: Do they span the solution space?
        - Novelty: Are they creative/unexpected?
        """
        if not candidates:
            return 0.0

        # Simple heuristic: more candidates = higher score
        # In practice, would use semantic similarity, clustering, etc.
        diversity_score = min(1.0, len(candidates) / 10.0)

        # Check for variety in candidate types
        types = set(c.get('type', 'unknown') for c in candidates)
        coverage_score = min(1.0, len(types) / 5.0)

        return (diversity_score + coverage_score) / 2.0

    def evaluate_deterministic(self, state: MFGCSystemState) -> float:
        """
        Evaluate deterministic verification

        Metrics:
        - Gate coverage: Are all risks covered?
        - Constraint satisfaction: Are constraints met?
        - Specification completeness: Is solution fully specified?
        """
        # Check gate coverage
        gate_score = min(1.0, len(state.G_t) / 5.0)

        # Check Murphy index (lower is better)
        murphy_score = 1.0 - min(1.0, state.M_t / 0.3)

        # Check phase progress
        phase_score = (list(Phase).index(state.p_t) + 1) / (len(Phase) or 1)

        return (gate_score + murphy_score + phase_score) / 3.0


# === AUTHORITY CONTROLLER ===

class AuthorityController:
    """
    Authority function: a_t = Γ(c_t)
    Authority automatically revokes if confidence drops
    """

    def __init__(self):
        self.min_authority = 0.0
        self.max_authority = 1.0

    def compute_authority(self, confidence: float, phase: Phase) -> float:
        """
        Compute authority level based on confidence and phase

        Authority increases with confidence but requires higher
        confidence in later phases
        """
        # Phase-dependent threshold
        threshold = phase.confidence_threshold

        if confidence < threshold:
            # Below threshold: minimal authority
            return self.min_authority

        # Above threshold: scale authority with confidence
        # a_t = (c_t - threshold) / (1 - threshold)
        authority = (confidence - threshold) / (1.0 - threshold)

        return max(self.min_authority, min(self.max_authority, authority))

    def can_execute(self, authority: float, action: str) -> bool:
        """Check if authority level permits action"""
        # Define authority requirements for different actions
        requirements = {
            'generate': 0.0,  # Always allowed
            'filter': 0.3,
            'select': 0.5,
            'commit': 0.7,
            'deploy': 0.9
        }

        required = requirements.get(action, 0.5)
        return authority >= required


# === MURPHY INDEX MONITOR ===

class MurphyIndexMonitor:
    """
    Murphy index: M_t = Σ L_k × p_k
    Tracks accumulated risk and triggers contraction
    """

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold
        self.risks: List[Dict[str, Any]] = []

    def add_risk(self, loss: float, probability: float, description: str):
        """Add a risk to the index"""
        self.risks.append({
            'loss': loss,
            'probability': probability,
            'description': description,
            'contribution': loss * probability
        })

    def compute_index(self) -> float:
        """Compute current Murphy index"""
        if not self.risks:
            return 0.0

        return sum(r['contribution'] for r in self.risks)

    def check_threshold(self, current_index: float) -> bool:
        """Check if Murphy index exceeds threshold"""
        return current_index > self.threshold

    def get_top_risks(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N risks by contribution"""
        sorted_risks = sorted(self.risks,
                            key=lambda r: r['contribution'],
                            reverse=True)
        return sorted_risks[:n]

    def clear_risks(self):
        """Clear all risks (after mitigation)"""
        self.risks.clear()


# === GATE COMPILER ===

class GateCompiler:
    """
    Dynamic gate synthesis using Murphy inversion
    Gates are discovered, not predefined
    """

    def __init__(self):
        self.gate_templates = {
            'validation': 'Validate {aspect} before {action}',
            'constraint': 'Ensure {constraint} holds',
            'fallback': 'If {condition} fails, then {alternative}',
            'monitoring': 'Monitor {metric} and alert if {threshold}',
            'rollback': 'Enable rollback for {operation}'
        }

    def synthesize_gates(self,
                        candidates: List[Dict[str, Any]],
                        risks: List[Dict[str, Any]]) -> List[str]:
        """
        Synthesize gates from candidates and risks

        Process:
        1. Identify failure modes in candidates
        2. Invert risks into preventive gates
        3. Generate verification gates
        """
        gates = []

        # Generate gates from risks
        for risk in risks:
            gate = self._risk_to_gate(risk)
            if gate:
                gates.append(gate)

        # Generate gates from candidates
        for candidate in candidates:
            candidate_gates = self._candidate_to_gates(candidate)
            gates.extend(candidate_gates)

        # Deduplicate
        gates = list(set(gates))

        return gates

    def _risk_to_gate(self, risk: Dict[str, Any]) -> Optional[str]:
        """Convert risk to preventive gate"""
        desc = risk.get('description', '')

        # Pattern matching for common risks
        if 'vendor' in desc.lower():
            return "Validate vendor independence and avoid lock-in"
        elif 'data' in desc.lower():
            return "Ensure data validation and integrity checks"
        elif 'security' in desc.lower():
            return "Implement security review and penetration testing"
        elif 'performance' in desc.lower():
            return "Monitor performance metrics and set thresholds"
        elif 'cost' in desc.lower():
            return "Track costs and set budget alerts"

        return f"Mitigate: {desc}"

    def _candidate_to_gates(self, candidate: Dict[str, Any]) -> List[str]:
        """Generate verification gates for candidate"""
        gates = []

        # Check for required validations
        if 'requires_validation' in candidate:
            for aspect in candidate['requires_validation']:
                gates.append(f"Validate {aspect} before deployment")

        # Check for dependencies
        if 'dependencies' in candidate:
            gates.append("Verify all dependencies are available")

        # Check for constraints
        if 'constraints' in candidate:
            for constraint in candidate['constraints']:
                gates.append(f"Ensure {constraint} is satisfied")

        return gates


# === SWARM GENERATOR ===

class SwarmGenerator:
    """
    Dual-purpose swarm generation:
    1. Generate solution candidates
    2. Generate control gates
    """

    def __init__(self):
        self.generation_strategies = [
            'brainstorm',
            'systematic',
            'analogical',
            'constraint_based',
            'random_exploration'
        ]

    def generate_candidates(self,
                          task: str,
                          phase: Phase,
                          context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate solution candidates based on phase

        Each phase has different generation strategies:
        - EXPAND: Broad, creative, many options
        - TYPE: Categorize and classify
        - ENUMERATE: List specific options
        - CONSTRAIN: Apply filters and constraints
        - COLLAPSE: Synthesize best solution
        - BIND: Create detailed specification
        - EXECUTE: Generate deployment plan
        """
        candidates = []

        if phase == Phase.EXPAND:
            candidates = self._expand_candidates(task, context)
        elif phase == Phase.TYPE:
            candidates = self._type_candidates(task, context)
        elif phase == Phase.ENUMERATE:
            candidates = self._enumerate_candidates(task, context)
        elif phase == Phase.CONSTRAIN:
            candidates = self._constrain_candidates(task, context)
        elif phase == Phase.COLLAPSE:
            candidates = self._collapse_candidates(task, context)
        elif phase == Phase.BIND:
            candidates = self._bind_candidates(task, context)
        elif phase == Phase.EXECUTE:
            candidates = self._execute_candidates(task, context)

        return candidates

    def _expand_candidates(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXPAND phase: Generate broad range of approaches"""
        return [
            {'type': 'direct', 'approach': 'Direct implementation', 'score': 0.7},
            {'type': 'modular', 'approach': 'Modular architecture', 'score': 0.8},
            {'type': 'incremental', 'approach': 'Incremental development', 'score': 0.75},
            {'type': 'prototype', 'approach': 'Rapid prototyping', 'score': 0.6},
            {'type': 'research', 'approach': 'Research-first approach', 'score': 0.65}
        ]

    def _type_candidates(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """TYPE phase: Classify and categorize"""
        return [
            {'category': 'technical', 'subcategory': 'implementation'},
            {'category': 'research', 'subcategory': 'investigation'},
            {'category': 'design', 'subcategory': 'architecture'}
        ]

    def _enumerate_candidates(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ENUMERATE phase: List specific options"""
        return [
            {'option': 'Option A', 'pros': ['Fast'], 'cons': ['Limited']},
            {'option': 'Option B', 'pros': ['Flexible'], 'cons': ['Complex']},
            {'option': 'Option C', 'pros': ['Simple'], 'cons': ['Slow']}
        ]

    def _constrain_candidates(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """CONSTRAIN phase: Apply constraints"""
        return [
            {'constraint': 'budget', 'value': 'within limits'},
            {'constraint': 'time', 'value': 'meets deadline'},
            {'constraint': 'quality', 'value': 'meets standards'}
        ]

    def _collapse_candidates(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """COLLAPSE phase: Synthesize solution"""
        return [
            {'solution': 'Hybrid approach combining best elements',
             'components': ['modular', 'incremental', 'tested']}
        ]

    def _bind_candidates(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """BIND phase: Create specifications"""
        return [
            {'spec': 'Technical specification', 'completeness': 0.9},
            {'spec': 'Implementation plan', 'completeness': 0.85},
            {'spec': 'Testing strategy', 'completeness': 0.8}
        ]

    def _execute_candidates(self, task: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """EXECUTE phase: Deployment plan"""
        return [
            {'step': 'Deploy to staging', 'risk': 0.1},
            {'step': 'Run tests', 'risk': 0.05},
            {'step': 'Deploy to production', 'risk': 0.2}
        ]


# === MAIN MFGC CONTROLLER ===

class MFGCController:
    """
    Main MFGC controller implementing 7-phase execution
    """

    _DEFAULT_UNCERTAINTY: float = 0.5
    """Default per-dimension uncertainty applied when no prior data is available."""

    def __init__(self):
        self.confidence_engine = ConfidenceEngine()
        self.authority_controller = AuthorityController()
        self.murphy_monitor = MurphyIndexMonitor()
        self.gate_compiler = GateCompiler()
        self.swarm_generator = SwarmGenerator()

        # CFP-4: Closed learning loop — wired FeedbackIntegrator
        try:
            from feedback_integrator import FeedbackIntegrator
            from feedback_integrator import FeedbackSignal as _FeedbackSignal
            from state_schema import StateVariable, StateVectorSchema, TypedStateVector
            self._feedback_integrator = FeedbackIntegrator()
            self._FeedbackSignal = _FeedbackSignal
            self._StateVariable = StateVariable
            self._StateVectorSchema = StateVectorSchema
            self._TypedStateVector = TypedStateVector
            self._feedback_available = True
        except ImportError:
            self._feedback_integrator = None
            self._feedback_available = False

    def _make_uncertainty_state(self) -> Any:
        """Create a :class:`~state_schema.TypedStateVector` with base MFGC dimensions."""
        if not self._feedback_available:
            return None
        schema = self._StateVectorSchema(
            domain="mfgc",
            dimensions=[
                self._StateVariable(name=d, value=0.0, dtype="float",
                                    uncertainty=self._DEFAULT_UNCERTAINTY)
                for d in (
                    "domain_knowledge_level",
                    "constraint_satisfaction_ratio",
                    "information_completeness",
                    "verification_coverage",
                    "risk_exposure",
                    "authority_utilization",
                )
            ],
        )
        return self._TypedStateVector(schema=schema)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> MFGCSystemState:
        """
        Execute complete 7-phase MFGC cycle

        Args:
            task: Task description
            context: Optional context information

        Returns:
            Final system state with complete audit trail
        """
        # Initialize state
        state = MFGCSystemState()
        state.x_t = StateVector.from_dict({'task': task, 'context': context or {}})
        state.p_t = Phase.EXPAND
        state.phase_history.append(Phase.EXPAND)

        # CFP-4: initialise per-dimension uncertainty tracker
        uncertainty_state = self._make_uncertainty_state()

        state.log_event('execution_start', {'task': task})

        # Execute all 7 phases
        for phase in Phase:
            state.p_t = phase
            # Add to history if not already there
            if not state.phase_history or state.phase_history[-1] != phase:
                state.phase_history.append(phase)

            self._execute_phase(state)

            # Check if we can advance
            if state.c_t < phase.confidence_threshold:
                state.log_event('phase_blocked', {
                    'phase': phase.value,
                    'confidence': state.c_t,
                    'threshold': phase.confidence_threshold
                })
                # In practice, would iterate or request more information
                # For now, continue with lower confidence

            # Check Murphy index
            if self.murphy_monitor.check_threshold(state.M_t):
                state.log_event('murphy_threshold_exceeded', {
                    'murphy_index': state.M_t,
                    'threshold': self.murphy_monitor.threshold
                })
                # CFP-4: emit a feedback signal when Murphy threshold is exceeded
                # and integrate it into the uncertainty state
                if self._feedback_available and uncertainty_state is not None:
                    # Use the phase threshold as the "expected" confidence when
                    # there is no prior history entry; this ensures original ≠ corrected.
                    prev_conf = (
                        state.confidence_history[-2]
                        if len(state.confidence_history) >= 2
                        else phase.confidence_threshold
                    )
                    signal = self._FeedbackSignal(
                        signal_type="recalibration",
                        source_task_id=f"phase:{phase.value}",
                        original_confidence=prev_conf,
                        corrected_confidence=state.c_t,
                        affected_state_variables=list(uncertainty_state.keys()),
                    )
                    state.pending_feedback_signals.append(signal)
                    self._feedback_integrator.integrate(signal, uncertainty_state)

                # Synthesize emergency gates
                emergency_gates = self._synthesize_emergency_gates(state)
                state.G_t.extend(emergency_gates)

        # CFP-4: check if accumulated signals warrant recalibration
        if (self._feedback_available
                and state.pending_feedback_signals
                and self._feedback_integrator.should_trigger_recalibration(
                    state.pending_feedback_signals
                )):
            state.log_event('recalibration_triggered', {
                'signal_count': len(state.pending_feedback_signals),
            })

        state.log_event('execution_complete', {
            'final_confidence': state.c_t,
            'final_murphy_index': state.M_t,
            'total_gates': len(state.G_t)
        })

        return state

    def apply_feedback_correction(
        self,
        state: MFGCSystemState,
        original_confidence: float,
        corrected_confidence: float,
        affected_variables: Optional[List[str]] = None,
        source_task_id: str = "external",
    ) -> MFGCSystemState:
        """Apply an external feedback correction to *state*.

        Creates a :class:`~feedback_integrator.FeedbackSignal` from the supplied
        confidence pair and integrates it into *state*'s uncertainty tracker.
        This is the public hook for post-execution callers (e.g. HITL reviewers,
        automated test harnesses) to feed corrections back into the system.

        Args:
            state: The :class:`MFGCSystemState` to update.
            original_confidence: Confidence value before correction.
            corrected_confidence: Corrected/expected confidence value.
            affected_variables: State-vector dimension names to adjust.
                Defaults to all six base dimensions if not supplied.
            source_task_id: Caller identifier for the audit trail.

        Returns:
            The (mutated) *state* object for chaining.
        """
        if not self._feedback_available:
            return state

        if affected_variables is None:
            affected_variables = [
                "domain_knowledge_level",
                "constraint_satisfaction_ratio",
                "information_completeness",
                "verification_coverage",
                "risk_exposure",
                "authority_utilization",
            ]

        signal = self._FeedbackSignal(
            signal_type="correction",
            source_task_id=source_task_id,
            original_confidence=original_confidence,
            corrected_confidence=corrected_confidence,
            affected_state_variables=affected_variables,
        )
        state.pending_feedback_signals.append(signal)

        # Build a transient TypedStateVector from the current StateVector values
        uncertainty_state = self._make_uncertainty_state()
        if uncertainty_state is not None:
            for dim in affected_variables:
                raw_val = state.x_t.get(dim)
                if raw_val is not None:
                    uncertainty_state.set(dim, raw_val,
                                          uncertainty=self._DEFAULT_UNCERTAINTY)
                else:
                    # Dimension not in current StateVector; integrate with default
                    # uncertainty so the feedback signal still affects the loop.
                    uncertainty_state.set(dim, 0.0,
                                          uncertainty=self._DEFAULT_UNCERTAINTY)
            self._feedback_integrator.integrate(signal, uncertainty_state)

        state.log_event('feedback_correction_applied', {
            'original_confidence': original_confidence,
            'corrected_confidence': corrected_confidence,
            'affected_variables': affected_variables,
            'source_task_id': source_task_id,
        })
        return state

    def _execute_phase(self, state: MFGCSystemState):
        """Execute single phase"""
        phase = state.p_t

        state.log_event('phase_start', {'phase': phase.value})

        # 1. Generate candidates
        candidates = self.swarm_generator.generate_candidates(
            state.x_t['task'],
            phase,
            state.x_t.get('context', {})
        )
        state.candidates = candidates

        # 2. Evaluate generative quality
        gen_score = self.confidence_engine.evaluate_generative(candidates)

        # 3. Evaluate deterministic verification
        det_score = self.confidence_engine.evaluate_deterministic(state)

        # 4. Compute confidence
        state.c_t = self.confidence_engine.compute_confidence(
            state, gen_score, det_score
        )
        state.confidence_history.append(state.c_t)

        # 5. Compute authority
        state.a_t = self.authority_controller.compute_authority(
            state.c_t, phase
        )

        # 6. Identify risks
        self._identify_risks(state, candidates)

        # 7. Compute Murphy index
        state.M_t = self.murphy_monitor.compute_index()
        state.murphy_history.append(state.M_t)

        # 8. Synthesize gates
        new_gates = self.gate_compiler.synthesize_gates(
            candidates,
            self.murphy_monitor.get_top_risks()
        )
        state.G_t.extend(new_gates)
        state.gate_history.append(list(state.G_t))

        state.log_event('phase_complete', {
            'phase': phase.value,
            'confidence': state.c_t,
            'authority': state.a_t,
            'murphy_index': state.M_t,
            'gates_added': len(new_gates)
        })

    def _identify_risks(self, state: MFGCSystemState, candidates: List[Dict[str, Any]]):
        """Identify risks in current phase"""
        # Clear previous risks
        self.murphy_monitor.clear_risks()

        # Add phase-specific risks
        phase = state.p_t

        if phase == Phase.EXPAND:
            self.murphy_monitor.add_risk(0.3, 0.5, "Scope creep")
            self.murphy_monitor.add_risk(0.2, 0.4, "Unfocused exploration")
        elif phase == Phase.EXECUTE:
            self.murphy_monitor.add_risk(0.8, 0.3, "Deployment failure")
            self.murphy_monitor.add_risk(0.5, 0.2, "Data loss")

        # Add candidate-specific risks
        for candidate in candidates:
            if 'risk' in candidate:
                self.murphy_monitor.add_risk(
                    candidate.get('loss', 0.5),
                    candidate['risk'],
                    f"Candidate risk: {candidate.get('description', 'unknown')}"
                )

    def _synthesize_emergency_gates(self, state: MFGCSystemState) -> List[str]:
        """Synthesize emergency gates when Murphy index is high"""
        top_risks = self.murphy_monitor.get_top_risks(3)

        gates = []
        for risk in top_risks:
            gates.append(f"EMERGENCY: Mitigate {risk['description']}")

        return gates

    def get_summary(self, state: MFGCSystemState) -> Dict[str, Any]:
        """Get execution summary"""
        return {
            'task': state.x_t.get('task'),
            'phases_completed': len(state.phase_history),
            'final_confidence': state.c_t,
            'final_authority': state.a_t,
            'final_murphy_index': state.M_t,
            'total_gates': len(state.G_t),
            'confidence_trajectory': state.confidence_history,
            'murphy_trajectory': state.murphy_history,
            'gates': state.G_t,
            'events': state.events
        }


# Backward-compatible alias used by mfgc_metrics and other modules
SystemState = MFGCSystemState
