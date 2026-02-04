"""
Murphy System - Stability-Based Attention and Role-Governed Cognition
Complete Implementation of the Attention Subsystem

Scope:
- Govern internal attention formation before proposal generation
- Ensure internal representations remain mutually consistent
- Make internal focus explicitly time-dependent and traceable
- Align attention with responsibility, authority, and execution constraints
- Prevent unstable, infeasible, or unauthorized proposals from forming

Authoritative Specification:
Based on Murphy System Stability-Based Attention and Role-Governed Cognition
Technical Specification (Plain-Text Math)
"""

from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import uuid
import math
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============================================================================
# CORE TYPES AND ENUMS
# ============================================================================

class AttentionStatus(Enum):
    """Status of attention formation process"""
    SUCCESS = "success"
    REFUSED = "refused"
    ERROR = "error"
    TIMEOUT = "timeout"


class SubsystemType(Enum):
    """Types of internal predictive subsystems"""
    PERCEPTION = "perception"
    MEMORY = "memory"
    PLANNING = "planning"
    CONTROL = "control"
    SAFETY_POLICY = "safety_policy"


class CognitiveRole(Enum):
    """Cognitive roles for attention governance"""
    EXECUTOR = "executor"
    SUPERVISOR = "supervisor"
    GOVERNOR = "governor"
    AUDITOR = "auditor"


class AttentionFailureReason(Enum):
    """Reasons for attention refusal"""
    AGREEMENT_DECAY = "agreement_decay"
    RAPID_SWITCHING = "rapid_switching"
    LOSS_OF_FEASIBILITY = "loss_of_feasibility"
    AUTHORITY_CONFLICT = "authority_conflict"
    UNCONTROLLED_ABSTRACTION = "uncontrolled_abstraction"
    INSUFFICIENT_AGREEMENT = "insufficient_agreement"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Hypothesis:
    """Hypothesis from a subsystem about which representation should be active"""
    subsystem_type: SubsystemType
    vector: List[float]
    confidence: float
    timestamp: datetime
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            'subsystem_type': self.subsystem_type.value,
            'vector': self.vector,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'weight': self.weight
        }
    
    def get_weight(self) -> float:
        """Get the weight of this hypothesis"""
        return self.weight


@dataclass
class InternalRepresentation:
    """Internal representation candidate for attention"""
    id: str
    vector: List[float]
    abstraction_level: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'vector': self.vector,
            'abstraction_level': self.abstraction_level,
            'metadata': self.metadata
        }


@dataclass
class AttentionLogEntry:
    """Immutable log entry for attention updates"""
    timestamp: datetime
    role: CognitiveRole
    chosen_representation: Optional[InternalRepresentation]
    candidate_representations: List[InternalRepresentation]
    subsystem_scores: Dict[SubsystemType, float]
    temporal_scores: List[float]
    decision_reason: str
    status: AttentionStatus
    failure_reason: Optional[AttentionFailureReason] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for auditing"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'role': self.role.value,
            'chosen_representation': self.chosen_representation.to_dict() if self.chosen_representation else None,
            'candidate_representations': [r.to_dict() for r in self.candidate_representations],
            'subsystem_scores': {k.value: v for k, v in self.subsystem_scores.items()},
            'temporal_scores': self.temporal_scores,
            'decision_reason': self.decision_reason,
            'status': self.status.value,
            'failure_reason': self.failure_reason.value if self.failure_reason else None
        }


@dataclass
class SubsystemScore:
    """Score contribution from a specific subsystem"""
    subsystem_type: SubsystemType
    score: float
    agreement: float
    weight: float


# ============================================================================
# ABSTRACT SUBSYSTEM INTERFACE
# ============================================================================

class PredictiveSubsystem(ABC):
    """
    Abstract base class for internal predictive subsystems.
    Each subsystem produces a hypothesis about which internal representation should be active.
    """
    
    def __init__(self, subsystem_type: SubsystemType, weight: float = 1.0):
        """
        Initialize subsystem
        
        Args:
            subsystem_type: Type of this subsystem
            weight: Weight of this subsystem's influence (default: 1.0)
        """
        self.subsystem_type = subsystem_type
        self.weight = weight
    
    @abstractmethod
    def predict(self, state: Dict[str, Any], memory: Dict[str, Any], goal: Dict[str, Any]) -> Hypothesis:
        """
        Returns a hypothesis vector in the shared latent space
        
        Args:
            state: Current system state
            memory: Available memory
            goal: Current goal
            
        Returns:
            Hypothesis vector with confidence
        """
        raise NotImplementedError("Subsystems must implement predict() method")
    
    def get_weight(self) -> float:
        """Get the weight of this subsystem"""
        return self.weight
    
    def set_weight(self, weight: float) -> None:
        """Set the weight of this subsystem"""
        self.weight = weight


# ============================================================================
# CONCRETE SUBSYSTEM IMPLEMENTATIONS
# ============================================================================

class PerceptionSubsystem(PredictiveSubsystem):
    """
    Perception subsystem: continuity and observability of state
    Focuses on what is directly observable and maintains continuity
    """
    
    def __init__(self, weight: float = 1.0):
        """
        Initialize perception subsystem
        
        Args:
            weight: Weight of this subsystem's influence
        """
        super().__init__(SubsystemType.PERCEPTION, weight)
    
    def predict(self, state: Dict[str, Any], memory: Dict[str, Any], goal: Dict[str, Any]) -> Hypothesis:
        """
        Generate hypothesis based on perceptual continuity and observability
        """
        # Extract observable features from state
        observable_features = self._extract_observable_features(state)
        
        # Generate hypothesis vector
        hypothesis_vector = self._generate_hypothesis_vector(observable_features)
        
        # Confidence based on observability
        confidence = min(1.0, len(observable_features) / 10.0)
        
        return Hypothesis(
            subsystem_type=SubsystemType.PERCEPTION,
            vector=hypothesis_vector,
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def _extract_observable_features(self, state: Dict[str, Any]) -> List[float]:
        """Extract observable features from state"""
        # Simple implementation: flatten state values
        features = []
        for value in state.values():
            if isinstance(value, (int, float)):
                features.append(float(value))
            elif isinstance(value, str):
                features.append(float(len(value)))
            elif isinstance(value, list):
                features.append(float(len(value)))
            elif isinstance(value, dict):
                features.append(float(len(value)))
        
        # Pad or truncate to standard length
        return features[:100] + [0.0] * max(0, 100 - len(features))
    
    def _generate_hypothesis_vector(self, features: List[float]) -> List[float]:
        """Generate hypothesis vector from features"""
        # Normalize features
        if not features:
            return [0.0] * 100
        
        max_val = max(abs(f) for f in features) if features else 1.0
        if max_val > 0:
            normalized = [f / max_val for f in features]
        else:
            normalized = features
        
        return normalized[:100] + [0.0] * max(0, 100 - len(normalized))


class MemorySubsystem(PredictiveSubsystem):
    """
    Memory subsystem: historical relevance and precedent
    Focuses on what has worked or failed in the past
    """
    
    def __init__(self, weight: float = 1.0, memory_decay: float = 0.95):
        """
        Initialize memory subsystem
        
        Args:
            weight: Weight of this subsystem
            memory_decay: Decay factor for memory relevance
        """
        super().__init__(SubsystemType.MEMORY, weight)
        self.memory_decay = memory_decay
    
    def predict(self, state: Dict[str, Any], memory: Dict[str, Any], goal: Dict[str, Any]) -> Hypothesis:
        """
        Generate hypothesis based on historical relevance
        """
        # Extract relevant memories
        relevant_memories = self._retrieve_relevant_memories(state, memory)
        
        # Generate hypothesis from memory patterns
        hypothesis_vector = self._generate_memory_hypothesis(relevant_memories)
        
        # Confidence based on relevance and recency
        confidence = min(1.0, len(relevant_memories) / 5.0)
        
        return Hypothesis(
            subsystem_type=SubsystemType.MEMORY,
            vector=hypothesis_vector,
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def _retrieve_relevant_memories(self, state: Dict[str, Any], memory: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve memories relevant to current state"""
        relevant = []
        
        # Simple relevance matching based on state keys
        state_keys = set(state.keys())
        for mem_id, mem_data in memory.items():
            mem_keys = set(mem_data.keys()) if isinstance(mem_data, dict) else set()
            overlap = len(state_keys & mem_keys)
            if overlap > 0:
                relevant.append({'id': mem_id, 'data': mem_data, 'relevance': overlap})
        
        # Sort by relevance
        relevant.sort(key=lambda x: x['relevance'], reverse=True)
        return relevant[:10]
    
    def _generate_memory_hypothesis(self, memories: List[Dict[str, Any]]) -> List[float]:
        """Generate hypothesis vector from relevant memories"""
        if not memories:
            return [0.0] * 100
        
        # Aggregate memory features
        vector = [0.0] * 100
        for mem in memories:
            relevance = mem.get('relevance', 1.0)
            mem_data = mem.get('data', {})
            
            # Simple feature extraction
            for i, (key, value) in enumerate(mem_data.items()):
                if isinstance(value, (int, float)):
                    idx = i % 100
                    vector[idx] += value * relevance * self.memory_decay
        
        # Normalize
        max_val = max(abs(v) for v in vector) if vector else 1.0
        if max_val > 0:
            vector = [v / max_val for v in vector]
        
        return vector


class PlanningSubsystem(PredictiveSubsystem):
    """
    Planning subsystem: projection of future states
    Focuses on what leads to goal achievement
    """
    
    def __init__(self, weight: float = 1.0):
        """
        Initialize planning subsystem
        
        Args:
            weight: Weight of this subsystem's influence
        """
        super().__init__(SubsystemType.PLANNING, weight)
    
    def predict(self, state: Dict[str, Any], memory: Dict[str, Any], goal: Dict[str, Any]) -> Hypothesis:
        """
        Generate hypothesis based on projected future states
        """
        # Simulate projection into future
        projected_states = self._project_future_states(state, goal, steps=5)
        
        # Generate hypothesis from projections
        hypothesis_vector = self._generate_projection_hypothesis(projected_states, goal)
        
        # Confidence based on projection consistency
        consistency_score = self._measure_projection_consistency(projected_states)
        confidence = min(1.0, consistency_score)
        
        return Hypothesis(
            subsystem_type=SubsystemType.PLANNING,
            vector=hypothesis_vector,
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def _project_future_states(self, state: Dict[str, Any], goal: Dict[str, Any], steps: int = 5) -> List[Dict[str, Any]]:
        """Project future states"""
        projections = []
        current_state = state.copy()
        
        for _ in range(steps):
            # Simple projection: move toward goal
            projected = {}
            for key, goal_value in goal.items():
                if key in current_state:
                    current_value = current_state[key]
                    if isinstance(current_value, (int, float)) and isinstance(goal_value, (int, float)):
                        # Move 20% toward goal
                        projected[key] = current_value + 0.2 * (goal_value - current_value)
                    else:
                        projected[key] = current_value
                else:
                    projected[key] = goal_value
            projections.append(projected)
            current_state = projected
        
        return projections
    
    def _generate_projection_hypothesis(self, projections: List[Dict[str, Any]], goal: Dict[str, Any]) -> List[float]:
        """Generate hypothesis from projections"""
        if not projections:
            return [0.0] * 100
        
        # Extract features from projections
        vector = [0.0] * 100
        
        for proj in projections:
            for i, (key, value) in enumerate(proj.items()):
                if isinstance(value, (int, float)):
                    idx = i % 100
                    vector[idx] += value / len(projections)
        
        # Normalize
        max_val = max(abs(v) for v in vector) if vector else 1.0
        if max_val > 0:
            vector = [v / max_val for v in vector]
        
        return vector
    
    def _measure_projection_consistency(self, projections: List[Dict[str, Any]]) -> float:
        """Measure how consistent projections are"""
        if len(projections) < 2:
            return 1.0
        
        # Calculate variance in projections
        total_variance = 0.0
        count = 0
        
        for i in range(len(projections) - 1):
            proj1 = projections[i]
            proj2 = projections[i + 1]
            
            for key in proj1.keys():
                if key in proj2:
                    diff = abs(proj1[key] - proj2[key])
                    if isinstance(diff, (int, float)):
                        total_variance += diff
                        count += 1
        
        if count == 0:
            return 1.0
        
        avg_variance = total_variance / count
        # Lower variance = higher consistency
        consistency = max(0.0, 1.0 - avg_variance / 10.0)
        return consistency


class ControlSubsystem(PredictiveSubsystem):
    """
    Control subsystem: physical or logical feasibility
    Focuses on what is actually achievable
    """
    
    def __init__(self, weight: float = 1.0):
        """
        Initialize control subsystem
        
        Args:
            weight: Weight of this subsystem's influence
        """
        super().__init__(SubsystemType.CONTROL, weight)
    
    def predict(self, state: Dict[str, Any], memory: Dict[str, Any], goal: Dict[str, Any]) -> Hypothesis:
        """
        Generate hypothesis based on feasibility constraints
        """
        # Assess feasibility
        feasibility_score = self._assess_feasibility(state, goal)
        
        # Generate hypothesis based on feasible actions
        hypothesis_vector = self._generate_feasibility_hypothesis(state, goal, feasibility_score)
        
        # Confidence based on feasibility
        confidence = feasibility_score
        
        return Hypothesis(
            subsystem_type=SubsystemType.CONTROL,
            vector=hypothesis_vector,
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def _assess_feasibility(self, state: Dict[str, Any], goal: Dict[str, Any]) -> float:
        """Assess feasibility of achieving goal from current state"""
        # Simple feasibility check: goal must be within reasonable bounds
        feasibility = 1.0
        
        for key, goal_value in goal.items():
            if key in state:
                state_value = state[key]
                if isinstance(state_value, (int, float)) and isinstance(goal_value, (int, float)):
                    # Check if goal is within reasonable range
                    if abs(goal_value) > 1000000:  # Unrealistic value
                        feasibility *= 0.5
                    if abs(goal_value - state_value) > 1000:  # Too large jump
                        feasibility *= 0.7
        
        return feasibility
    
    def _generate_feasibility_hypothesis(self, state: Dict[str, Any], goal: Dict[str, Any], feasibility: float) -> List[float]:
        """Generate hypothesis based on feasibility"""
        # Generate vector that encodes feasibility constraints
        vector = [feasibility] * 100
        
        # Add state features
        for i, (key, value) in enumerate(state.items()):
            if isinstance(value, (int, float)):
                idx = i % 100
                vector[idx] = (vector[idx] + value) / 2.0
        
        # Normalize
        max_val = max(abs(v) for v in vector) if vector else 1.0
        if max_val > 0:
            vector = [v / max_val for v in vector]
        
        return vector


class SafetyPolicySubsystem(PredictiveSubsystem):
    """
    Safety/Policy subsystem: authority and constraint boundaries
    Focuses on what is allowed and safe
    """
    
    def __init__(self, weight: float = 1.0, policy_constraints: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize safety/policy subsystem
        
        Args:
            weight: Weight of this subsystem
            policy_constraints: List of policy constraints
        """
        super().__init__(SubsystemType.SAFETY_POLICY, weight)
        self.policy_constraints = policy_constraints or []
    
    def predict(self, state: Dict[str, Any], memory: Dict[str, Any], goal: Dict[str, Any]) -> Hypothesis:
        """
        Generate hypothesis based on policy constraints
        """
        # Check policy compliance
        compliance_score = self._check_policy_compliance(state, goal)
        
        # Generate hypothesis based on safe actions
        hypothesis_vector = self._generate_policy_hypothesis(state, goal, compliance_score)
        
        # Confidence based on compliance
        confidence = compliance_score
        
        return Hypothesis(
            subsystem_type=SubsystemType.SAFETY_POLICY,
            vector=hypothesis_vector,
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def _check_policy_compliance(self, state: Dict[str, Any], goal: Dict[str, Any]) -> float:
        """Check if goal complies with policy constraints"""
        compliance = 1.0
        
        for constraint in self.policy_constraints:
            constraint_type = constraint.get('type')
            if constraint_type == 'max_value':
                for key, max_val in constraint.get('limits', {}).items():
                    if key in goal and isinstance(goal[key], (int, float)):
                        if goal[key] > max_val:
                            compliance *= 0.5
            elif constraint_type == 'forbidden_keys':
                forbidden_keys = constraint.get('keys', [])
                for key in forbidden_keys:
                    if key in goal:
                        compliance *= 0.3
        
        return compliance
    
    def _generate_policy_hypothesis(self, state: Dict[str, Any], goal: Dict[str, Any], compliance: float) -> List[float]:
        """Generate hypothesis based on policy constraints"""
        # Generate vector that encodes policy constraints
        vector = [compliance] * 100
        
        # Encode forbidden zones as negative values
        for constraint in self.policy_constraints:
            if constraint.get('type') == 'forbidden_keys':
                forbidden_keys = constraint.get('keys', [])
                for i, key in enumerate(forbidden_keys):
                    idx = i % 100
                    vector[idx] = -0.5  # Mark forbidden
        
        # Normalize
        max_val = max(abs(v) for v in vector) if vector else 1.0
        if max_val > 0:
            vector = [v / max_val for v in vector]
        
        return vector


# ============================================================================
# AGREEMENT FUNCTION
# ============================================================================

def agreement(hypothesis: Hypothesis, candidate: InternalRepresentation, 
              abstraction_tolerance: int = 2) -> float:
    """
    Compute agreement between a subsystem hypothesis and a candidate representation.
    
    Agreement is:
    - Continuous
    - Bounded between 0 and 1
    - Allows partial matches
    - Considers abstraction level tolerance
    
    Args:
        hypothesis: Hypothesis from a subsystem
        candidate: Candidate internal representation
        abstraction_tolerance: Maximum allowed abstraction level difference
    
    Returns:
        Agreement score between 0 and 1
    """
    # Check abstraction level compatibility
    abstraction_diff = abs(hypothesis.vector[-1] - candidate.abstraction_level) if hypothesis.vector else 0
    if abstraction_diff > abstraction_tolerance:
        return 0.0
    
    # Compute cosine similarity
    hypothesis_vec = hypothesis.vector[:min(len(hypothesis.vector), len(candidate.vector))]
    candidate_vec = candidate.vector[:len(hypothesis_vec)]
    
    if not hypothesis_vec or not candidate_vec:
        return 0.0
    
    # Dot product
    dot_product = sum(h * c for h, c in zip(hypothesis_vec, candidate_vec))
    
    # Magnitudes
    hypothesis_mag = math.sqrt(sum(h * h for h in hypothesis_vec))
    candidate_mag = math.sqrt(sum(c * c for c in candidate_vec))
    
    if hypothesis_mag == 0 or candidate_mag == 0:
        return 0.0
    
    # Cosine similarity
    similarity = dot_product / (hypothesis_mag * candidate_mag)
    
    # Scale to [0, 1] range (cosine is [-1, 1])
    similarity = (similarity + 1) / 2
    
    return similarity


# ============================================================================
# TEMPORAL ATTENTION MECHANISM
# ============================================================================

class StabilityAttention:
    """
    Stability-based attention mechanism.
    Favors representations that remain useful across subsystems and across time.
    Prevents rapid oscillation and enforces continuity.
    """
    
    def __init__(self, window_size: int = 10, agreement_threshold: float = 0.3):
        """
        Initialize stability attention
        
        Args:
            window_size: Size of temporal history window
            agreement_threshold: Minimum agreement threshold for selection
        """
        self.window_size = window_size
        self.agreement_threshold = agreement_threshold
        self.history: List[InternalRepresentation] = []
        self.history_scores: List[float] = []
    
    def update(self, candidates: List[InternalRepresentation], 
               hypotheses: List[Hypothesis]) -> Tuple[Optional[InternalRepresentation], Dict[str, Any]]:
        """
        Update attention and select best candidate.
        
        Args:
            candidates: List of candidate representations
            hypotheses: List of hypotheses from subsystems
            
        Returns:
            Tuple of (chosen representation, diagnostic info)
        """
        if not candidates:
            return None, {'reason': 'No candidates available'}
        
        scores = []
        diagnostics = []
        
        # Score each candidate
        for candidate in candidates:
            score = 0.0
            subsystem_scores = {}
            temporal_score = 0.0
            
            # Compute agreement with each subsystem hypothesis
            for hypothesis in hypotheses:
                ag = agreement(hypothesis, candidate)
                weighted_agreement = ag * hypothesis.confidence * hypothesis.get_weight()
                subsystem_scores[hypothesis.subsystem_type] = weighted_agreement
                score += weighted_agreement
            
            # Add temporal persistence weight
            for past in self.history[-self.window_size:]:
                temporal_ag = agreement(
                    Hypothesis(SubsystemType.MEMORY, past.vector, 1.0, datetime.now()),
                    candidate
                )
                temporal_score += temporal_ag
            
            score += temporal_score
            
            scores.append(score)
            
            diagnostics.append({
                'candidate_id': candidate.id,
                'total_score': score,
                'subsystem_scores': subsystem_scores,
                'temporal_score': temporal_score
            })
        
        # Check if any candidate meets threshold
        max_score = max(scores) if scores else 0
        
        if max_score < self.agreement_threshold:
            # Attention failure - no candidate meets threshold
            return None, {
                'reason': 'No candidate meets agreement threshold',
                'max_score': max_score,
                'threshold': self.agreement_threshold,
                'diagnostics': diagnostics
            }
        
        # Select candidate with highest score
        best_index = scores.index(max_score)
        chosen = candidates[best_index]
        
        # Update history
        self.history.append(chosen)
        self.history_scores.append(max_score)
        
        # Trim history to window size
        if len(self.history) > self.window_size:
            self.history.pop(0)
            self.history_scores.pop(0)
        
        return chosen, {
            'reason': 'Candidate selected successfully',
            'diagnostics': diagnostics,
            'chosen_index': best_index
        }
    
    def get_history(self) -> List[InternalRepresentation]:
        """Get attention history"""
        return self.history.copy()
    
    def clear_history(self) -> None:
        """Clear attention history"""
        self.history.clear()
        self.history_scores.clear()


# ============================================================================
# COGNITIVE ROLES
# ============================================================================

@dataclass
class RoleConfiguration:
    """Configuration for a cognitive role"""
    role: CognitiveRole
    subsystem_types: List[SubsystemType]
    subsystem_weights: Dict[SubsystemType, float]
    persistence_threshold: float
    abstraction_limits: Dict[SubsystemType, int]


class CognitiveRoleManager:
    """
    Manages cognitive roles for attention governance.
    Roles define which subsystems participate and how strongly they influence agreement.
    """
    
    def __init__(self):
        """Initialize role manager with default roles"""
        self.roles: Dict[CognitiveRole, RoleConfiguration] = {}
        self._initialize_default_roles()
    
    def _initialize_default_roles(self) -> None:
        """Initialize default cognitive roles"""
        
        # Executor role: perception and control dominate
        self.roles[CognitiveRole.EXECUTOR] = RoleConfiguration(
            role=CognitiveRole.EXECUTOR,
            subsystem_types=[SubsystemType.PERCEPTION, SubsystemType.CONTROL],
            subsystem_weights={
                SubsystemType.PERCEPTION: 1.5,
                SubsystemType.CONTROL: 1.5,
                SubsystemType.MEMORY: 0.5,
                SubsystemType.PLANNING: 0.5,
                SubsystemType.SAFETY_POLICY: 1.0
            },
            persistence_threshold=0.7,
            abstraction_limits={
                SubsystemType.PERCEPTION: 1,
                SubsystemType.CONTROL: 0,  # Concrete level required
                SubsystemType.MEMORY: 2,
                SubsystemType.PLANNING: 3,
                SubsystemType.SAFETY_POLICY: 2
            }
        )
        
        # Supervisor role: memory and planning dominate
        self.roles[CognitiveRole.SUPERVISOR] = RoleConfiguration(
            role=CognitiveRole.SUPERVISOR,
            subsystem_types=[SubsystemType.MEMORY, SubsystemType.PLANNING],
            subsystem_weights={
                SubsystemType.PERCEPTION: 0.8,
                SubsystemType.CONTROL: 0.8,
                SubsystemType.MEMORY: 1.5,
                SubsystemType.PLANNING: 1.5,
                SubsystemType.SAFETY_POLICY: 1.0
            },
            persistence_threshold=0.6,
            abstraction_limits={
                SubsystemType.PERCEPTION: 1,
                SubsystemType.CONTROL: 1,
                SubsystemType.MEMORY: 2,
                SubsystemType.PLANNING: 3,
                SubsystemType.SAFETY_POLICY: 2
            }
        )
        
        # Governor role: policy and risk dominate
        self.roles[CognitiveRole.GOVERNOR] = RoleConfiguration(
            role=CognitiveRole.GOVERNOR,
            subsystem_types=[SubsystemType.SAFETY_POLICY, SubsystemType.PLANNING],
            subsystem_weights={
                SubsystemType.PERCEPTION: 0.5,
                SubsystemType.CONTROL: 0.5,
                SubsystemType.MEMORY: 1.0,
                SubsystemType.PLANNING: 1.2,
                SubsystemType.SAFETY_POLICY: 2.0
            },
            persistence_threshold=0.8,
            abstraction_limits={
                SubsystemType.PERCEPTION: 1,
                SubsystemType.CONTROL: 1,
                SubsystemType.MEMORY: 2,
                SubsystemType.PLANNING: 2,
                SubsystemType.SAFETY_POLICY: 1
            }
        )
        
        # Auditor role: memory and consistency dominate
        self.roles[CognitiveRole.AUDITOR] = RoleConfiguration(
            role=CognitiveRole.AUDITOR,
            subsystem_types=[SubsystemType.MEMORY, SubsystemType.SAFETY_POLICY],
            subsystem_weights={
                SubsystemType.PERCEPTION: 0.5,
                SubsystemType.CONTROL: 0.5,
                SubsystemType.MEMORY: 1.8,
                SubsystemType.PLANNING: 0.8,
                SubsystemType.SAFETY_POLICY: 1.5
            },
            persistence_threshold=0.9,
            abstraction_limits={
                SubsystemType.PERCEPTION: 1,
                SubsystemType.CONTROL: 1,
                SubsystemType.MEMORY: 2,
                SubsystemType.PLANNING: 2,
                SubsystemType.SAFETY_POLICY: 1
            }
        )
    
    def get_role_configuration(self, role: CognitiveRole) -> Optional[RoleConfiguration]:
        """Get configuration for a role"""
        return self.roles.get(role)
    
    def apply_role_weights(self, subsystems: List[PredictiveSubsystem], 
                          role: CognitiveRole) -> List[PredictiveSubsystem]:
        """
        Apply role-specific weights to subsystems
        
        Args:
            subsystems: List of subsystems
            role: Cognitive role to apply
            
        Returns:
            Subsystems with updated weights
        """
        role_config = self.get_role_configuration(role)
        if not role_config:
            return subsystems
        
        for subsystem in subsystems:
            if subsystem.subsystem_type in role_config.subsystem_weights:
                weight = role_config.subsystem_weights[subsystem.subsystem_type]
                subsystem.set_weight(weight)
        
        return subsystems


# ============================================================================
# ATTENTION FAILURE DETECTION
# ============================================================================

class AttentionFailureDetector:
    """
    Detects attention failure conditions.
    """
    
    def __init__(self):
        """Initialize failure detector"""
        self.switching_history: List[str] = []
        self.agreement_history: List[float] = []
        self.max_history_size = 20
    
    def detect_failures(self, current_attention: Optional[InternalRepresentation],
                       diagnostics: Dict[str, Any]) -> List[AttentionFailureReason]:
        """
        Detect attention failure conditions
        
        Args:
            current_attention: Current chosen representation
            diagnostics: Diagnostic information from attention update
            
        Returns:
            List of detected failure reasons
        """
        failures = []
        
        # Check for agreement decay
        if self._detect_agreement_decay(diagnostics):
            failures.append(AttentionFailureReason.AGREEMENT_DECAY)
        
        # Check for rapid switching
        if current_attention and self._detect_rapid_switching(current_attention):
            failures.append(AttentionFailureReason.RAPID_SWITCHING)
        
        # Check for insufficient agreement
        if diagnostics.get('max_score', 0) < 0.1:
            failures.append(AttentionFailureReason.INSUFFICIENT_AGREEMENT)
        
        return failures
    
    def _detect_agreement_decay(self, diagnostics: Dict[str, Any]) -> bool:
        """Detect agreement decay across subsystems"""
        # Simple check: if max score is below threshold and trending down
        current_score = diagnostics.get('max_score', 0)
        if current_score < 0.2:
            self.agreement_history.append(current_score)
            if len(self.agreement_history) > self.max_history_size:
                self.agreement_history.pop(0)
            
            # Check if trend is downward
            if len(self.agreement_history) >= 5:
                recent_avg = sum(self.agreement_history[-5:]) / 5
                older_avg = sum(self.agreement_history[-10:-5]) / 5 if len(self.agreement_history) >= 10 else recent_avg
                if recent_avg < older_avg * 0.8:
                    return True
        
        return False
    
    def _detect_rapid_switching(self, current_attention: InternalRepresentation) -> bool:
        """Detect rapid switching between candidates"""
        self.switching_history.append(current_attention.id)
        
        if len(self.switching_history) > self.max_history_size:
            self.switching_history.pop(0)
        
        # Check if we've switched too many times recently
        if len(self.switching_history) >= 10:
            unique_recent = len(set(self.switching_history[-10:]))
            if unique_recent >= 6:  # 6+ different representations in last 10 steps
                return True
        
        return False
    
    def reset(self) -> None:
        """Reset failure detection history"""
        self.switching_history.clear()
        self.agreement_history.clear()


# ============================================================================
# CHRONOLOGICAL ATTENTION LOGGING
# ============================================================================

class AttentionLogger:
    """
    Immutable, ordered, auditable attention event logging.
    """
    
    def __init__(self):
        """Initialize attention logger"""
        self.log: List[AttentionLogEntry] = []
    
    def log_attention_event(self, entry: AttentionLogEntry) -> None:
        """
        Log an attention event
        
        Args:
            entry: Attention log entry to record
        """
        self.log.append(entry)
    
    def get_recent_events(self, count: int = 100) -> List[AttentionLogEntry]:
        """Get recent attention events"""
        return self.log[-count:] if len(self.log) >= count else self.log.copy()
    
    def get_events_by_role(self, role: CognitiveRole) -> List[AttentionLogEntry]:
        """Get events for a specific role"""
        return [e for e in self.log if e.role == role]
    
    def get_events_by_status(self, status: AttentionStatus) -> List[AttentionLogEntry]:
        """Get events with a specific status"""
        return [e for e in self.log if e.status == status]
    
    def clear_log(self) -> None:
        """Clear the attention log"""
        self.log.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about attention events"""
        if not self.log:
            return {'total_events': 0}
        
        total = len(self.log)
        successful = len([e for e in self.log if e.status == AttentionStatus.SUCCESS])
        refused = len([e for e in self.log if e.status == AttentionStatus.REFUSED])
        
        role_counts = {}
        for role in CognitiveRole:
            role_counts[role.value] = len([e for e in self.log if e.role == role])
        
        return {
            'total_events': total,
            'successful': successful,
            'refused': refused,
            'success_rate': successful / total if total > 0 else 0,
            'role_distribution': role_counts
        }


# ============================================================================
# MAIN ATTENTION SYSTEM
# ============================================================================

class StabilityBasedAttentionSystem:
    """
    Main attention system implementing stability-based attention and role-governed cognition.
    
    This system:
    - Governs internal attention formation before proposal generation
    - Ensures internal representations remain mutually consistent
    - Makes internal focus explicitly time-dependent and traceable
    - Aligns attention with responsibility, authority, and execution constraints
    - Prevents unstable, infeasible, or unauthorized proposals from forming
    """
    
    def __init__(self, window_size: int = 10, agreement_threshold: float = 0.3):
        """
        Initialize the attention system
        
        Args:
            window_size: Size of temporal history window
            agreement_threshold: Minimum agreement threshold for selection
        """
        # Initialize subsystems
        self.subsystems: Dict[SubsystemType, PredictiveSubsystem] = {}
        self._initialize_subsystems()
        
        # Initialize attention mechanism
        self.attention = StabilityAttention(
            window_size=window_size,
            agreement_threshold=agreement_threshold
        )
        
        # Initialize role manager
        self.role_manager = CognitiveRoleManager()
        
        # Initialize failure detector
        self.failure_detector = AttentionFailureDetector()
        
        # Initialize logger
        self.logger = AttentionLogger()
        
        # Current role
        self.current_role = CognitiveRole.SUPERVISOR
        
        logger.info("Stability-Based Attention System initialized")
    
    def _initialize_subsystems(self) -> None:
        """Initialize all predictive subsystems"""
        self.subsystems[SubsystemType.PERCEPTION] = PerceptionSubsystem(weight=1.0)
        self.subsystems[SubsystemType.MEMORY] = MemorySubsystem(weight=1.0, memory_decay=0.95)
        self.subsystems[SubsystemType.PLANNING] = PlanningSubsystem(weight=1.0)
        self.subsystems[SubsystemType.CONTROL] = ControlSubsystem(weight=1.0)
        self.subsystems[SubsystemType.SAFETY_POLICY] = SafetyPolicySubsystem(weight=1.0)
    
    def set_role(self, role: CognitiveRole) -> None:
        """
        Set the current cognitive role
        
        Args:
            role: Cognitive role to activate
        """
        self.current_role = role
        logger.info(f"Cognitive role set to: {role.value}")
    
    def form_attention(self, state: Dict[str, Any], memory: Dict[str, Any], 
                      goal: Dict[str, Any], candidates: List[InternalRepresentation]) -> Tuple[Optional[InternalRepresentation], AttentionLogEntry]:
        """
        Form attention for the current state, memory, and goal.
        
        This is the main entry point for the attention system.
        
        Args:
            state: Current system state
            memory: Available memory
            goal: Current goal
            candidates: List of candidate representations
            
        Returns:
            Tuple of (chosen representation, log entry)
        """
        # Apply role weights to subsystems
        subsystems = list(self.subsystems.values())
        weighted_subsystems = self.role_manager.apply_role_weights(subsystems, self.current_role)
        
        # Generate hypotheses from subsystems
        hypotheses = []
        for subsystem in weighted_subsystems:
            try:
                hypothesis = subsystem.predict(state, memory, goal)
                hypotheses.append(hypothesis)
            except Exception as e:
                logger.error(f"Error generating hypothesis from {subsystem.subsystem_type}: {e}")
        
        # Update attention mechanism
        chosen_representation, diagnostics = self.attention.update(candidates, hypotheses)
        
        # Check for failures
        failures = []
        if chosen_representation is None:
            failures = self.failure_detector.detect_failures(chosen_representation, diagnostics)
        else:
            failures = self.failure_detector.detect_failures(chosen_representation, diagnostics)
        
        # Create log entry
        if chosen_representation is None:
            status = AttentionStatus.REFUSED
            failure_reason = failures[0] if failures else AttentionFailureReason.INSUFFICIENT_AGREEMENT
            decision_reason = f"Attention refused: {failure_reason.value}"
        else:
            status = AttentionStatus.SUCCESS
            failure_reason = None
            decision_reason = diagnostics.get('reason', 'Success')
        
        # Extract subsystem scores for logging
        subsystem_scores = {}
        if 'diagnostics' in diagnostics and diagnostics['diagnostics']:
            best_diag = diagnostics['diagnostics'][diagnostics.get('chosen_index', 0)]
            subsystem_scores = {
                SubsystemType(st): score
                for st, score in best_diag.get('subsystem_scores', {}).items()
                if isinstance(st, str)
            }
        
        # Calculate temporal scores
        temporal_scores = []
        if 'diagnostics' in diagnostics and diagnostics['diagnostics']:
            for diag in diagnostics['diagnostics']:
                temporal_scores.append(diag.get('temporal_score', 0.0))
        
        # Create log entry
        log_entry = AttentionLogEntry(
            timestamp=datetime.now(),
            role=self.current_role,
            chosen_representation=chosen_representation,
            candidate_representations=candidates,
            subsystem_scores=subsystem_scores,
            temporal_scores=temporal_scores,
            decision_reason=decision_reason,
            status=status,
            failure_reason=failure_reason
        )
        
        # Log the event
        self.logger.log_attention_event(log_entry)
        
        logger.info(f"Attention formation: {status.value} - {decision_reason}")
        
        return chosen_representation, log_entry
    
    def get_attention_history(self) -> List[InternalRepresentation]:
        """Get attention history"""
        return self.attention.get_history()
    
    def get_attention_log(self, count: int = 100) -> List[AttentionLogEntry]:
        """Get attention log entries"""
        return self.logger.get_recent_events(count)
    
    def get_attention_statistics(self) -> Dict[str, Any]:
        """Get attention statistics"""
        return self.logger.get_statistics()
    
    def reset(self) -> None:
        """Reset the attention system"""
        self.attention.clear_history()
        self.failure_detector.reset()
        logger.info("Attention system reset")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_candidate_representations(state: Dict[str, Any], memory: Dict[str, Any], 
                                    goal: Dict[str, Any], count: int = 10) -> List[InternalRepresentation]:
    """
    Create candidate internal representations from state, memory, and goal.
    
    Args:
        state: Current system state
        memory: Available memory
        goal: Current goal
        count: Number of candidates to create
        
    Returns:
        List of candidate representations
    """
    candidates = []
    
    for i in range(count):
        # Mix state and goal features
        features = []
        for key, value in state.items():
            if isinstance(value, (int, float)):
                features.append(float(value))
        
        for key, value in goal.items():
            if isinstance(value, (int, float)):
                features.append(float(value))
        
        # Pad to standard length
        features = features[:100] + [0.0] * max(0, 100 - len(features))
        
        # Vary abstraction level
        abstraction_level = i % 5
        
        candidate = InternalRepresentation(
            id=str(uuid.uuid4()),
            vector=features,
            abstraction_level=abstraction_level,
            metadata={
                'source': 'generated',
                'index': i
            }
        )
        candidates.append(candidate)
    
    return candidates


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Core types
    'AttentionStatus',
    'SubsystemType',
    'CognitiveRole',
    'AttentionFailureReason',
    
    # Data structures
    'Hypothesis',
    'InternalRepresentation',
    'AttentionLogEntry',
    'SubsystemScore',
    'RoleConfiguration',
    
    # Subsystems
    'PredictiveSubsystem',
    'PerceptionSubsystem',
    'MemorySubsystem',
    'PlanningSubsystem',
    'ControlSubsystem',
    'SafetyPolicySubsystem',
    
    # Attention mechanism
    'agreement',
    'StabilityAttention',
    
    # Role management
    'CognitiveRoleManager',
    
    # Failure detection
    'AttentionFailureDetector',
    
    # Logging
    'AttentionLogger',
    
    # Main system
    'StabilityBasedAttentionSystem',
    
    # Utilities
    'create_candidate_representations'
]


if __name__ == '__main__':
    # Example usage
    print("Murphy System - Stability-Based Attention and Role-Governed Cognition")
    print("=" * 70)
    
    # Create attention system
    attention_system = StabilityBasedAttentionSystem()
    
    # Create sample state, memory, goal
    state = {
        'cpu_usage': 45.0,
        'memory_usage': 60.0,
        'active_tasks': 5,
        'system_load': 2.3
    }
    
    memory = {
        'previous_state': state.copy(),
        'performance_history': [45, 50, 48, 52, 47]
    }
    
    goal = {
        'cpu_usage': 40.0,
        'memory_usage': 50.0,
        'system_load': 2.0
    }
    
    # Create candidate representations
    candidates = create_candidate_representations(state, memory, goal, count=5)
    
    # Form attention
    chosen, log_entry = attention_system.form_attention(state, memory, goal, candidates)
    
    # Print results
    print(f"\nAttention Status: {log_entry.status.value}")
    print(f"Decision Reason: {log_entry.decision_reason}")
    
    if chosen:
        print(f"\nChosen Representation:")
        print(f"  ID: {chosen.id}")
        print(f"  Abstraction Level: {chosen.abstraction_level}")
        print(f"  Vector Length: {len(chosen.vector)}")
    else:
        print("\nNo representation met attention criteria")
    
    # Print statistics
    stats = attention_system.get_attention_statistics()
    print(f"\nAttention Statistics:")
    print(f"  Total Events: {stats['total_events']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Refused: {stats['refused']}")
    print(f"  Success Rate: {stats['success_rate']:.2%}")