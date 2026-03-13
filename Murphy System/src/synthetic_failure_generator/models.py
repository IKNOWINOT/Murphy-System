"""
Synthetic Failure Generator - Core Data Models
===============================================

Data structures for failure cases, scenarios, and training outputs.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures that can be generated"""
    # Semantic failures
    UNIT_MISMATCH = "unit_mismatch"
    AMBIGUOUS_LABEL = "ambiguous_label"
    MISSING_CONSTRAINT = "missing_constraint"
    CONFLICTING_GOAL = "conflicting_goal"

    # Control plane failures
    DELAYED_VERIFICATION = "delayed_verification"
    SKIPPED_GATE = "skipped_gate"
    FALSE_CONFIDENCE = "false_confidence"
    MISSING_ROLLBACK = "missing_rollback"

    # Interface failures
    STALE_DATA = "stale_data"
    ACTUATOR_DRIFT = "actuator_drift"
    INTERMITTENT_CONNECTIVITY = "intermittent_connectivity"
    PARTIAL_WRITE = "partial_write"

    # Organizational failures
    AUTHORITY_OVERRIDE = "authority_override"
    IGNORED_WARNING = "ignored_warning"
    MISALIGNED_INCENTIVE = "misaligned_incentive"
    SCHEDULE_PRESSURE = "schedule_pressure"


class SeverityLevel(Enum):
    """Severity levels for failures"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FailureCase:
    """
    A single synthetic failure case

    Contains:
    - Root cause identification
    - Violated assumptions
    - Missed gates
    - Recommended gates
    - Confidence drift profile
    """
    failure_id: str
    failure_type: FailureType
    severity: SeverityLevel
    root_cause: str
    violated_assumptions: List[str]
    missed_gates: List[str]
    recommended_gates: List[Dict[str, Any]]
    confidence_drift_profile: 'ConfidenceProfile'
    expected_loss: float
    murphy_probability: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'failure_id': self.failure_id,
            'failure_type': self.failure_type.value,
            'severity': self.severity.value,
            'root_cause': self.root_cause,
            'violated_assumptions': self.violated_assumptions,
            'missed_gates': self.missed_gates,
            'recommended_gates': self.recommended_gates,
            'confidence_drift_profile': self.confidence_drift_profile.to_dict(),
            'expected_loss': self.expected_loss,
            'murphy_probability': self.murphy_probability,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class FailureManifold:
    """
    A manifold of related failures

    Represents a family of failures with similar characteristics
    """
    manifold_id: str
    base_failure_type: FailureType
    perturbation_space: Dict[str, List[Any]]
    failure_cases: List[FailureCase] = field(default_factory=list)

    def add_failure_case(self, case: FailureCase):
        """Add failure case to manifold"""
        self.failure_cases.append(case)

    def get_severity_distribution(self) -> Dict[str, int]:
        """Get distribution of severity levels"""
        distribution = {level.value: 0 for level in SeverityLevel}
        for case in self.failure_cases:
            distribution[case.severity.value] += 1
        return distribution

    def to_dict(self) -> Dict[str, Any]:
        return {
            'manifold_id': self.manifold_id,
            'base_failure_type': self.base_failure_type.value,
            'perturbation_space': self.perturbation_space,
            'failure_cases': [case.to_dict() for case in self.failure_cases],
            'severity_distribution': self.get_severity_distribution()
        }


@dataclass
class BaseScenario:
    """
    Base scenario for failure generation

    Defines the initial state before perturbations
    """
    scenario_id: str
    scenario_name: str
    artifact_graph: Dict[str, Any]
    interface_definitions: Dict[str, Any]
    gate_library: List[Dict[str, Any]]
    initial_confidence: float
    initial_risk: float
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scenario_id': self.scenario_id,
            'scenario_name': self.scenario_name,
            'artifact_graph': self.artifact_graph,
            'interface_definitions': self.interface_definitions,
            'gate_library': self.gate_library,
            'initial_confidence': self.initial_confidence,
            'initial_risk': self.initial_risk,
            'context': self.context
        }


@dataclass
class PerturbationOperator:
    """
    Operator that perturbs a base scenario to create failures

    Applies transformations to introduce specific failure modes
    """
    operator_id: str
    operator_name: str
    failure_type: FailureType
    perturbation_function: str  # Name of function to apply
    parameters: Dict[str, Any]
    expected_impact: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'operator_id': self.operator_id,
            'operator_name': self.operator_name,
            'failure_type': self.failure_type.value,
            'perturbation_function': self.perturbation_function,
            'parameters': self.parameters,
            'expected_impact': self.expected_impact
        }


@dataclass
class ConfidenceProfile:
    """
    Profile of confidence changes over time

    Tracks how confidence drifts during failure scenarios
    """
    initial_confidence: float
    confidence_trajectory: List[float]
    instability_scores: List[float]  # H(x) over time
    grounding_scores: List[float]    # D(x) over time
    final_confidence: float
    drift_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'initial_confidence': self.initial_confidence,
            'confidence_trajectory': self.confidence_trajectory,
            'instability_scores': self.instability_scores,
            'grounding_scores': self.grounding_scores,
            'final_confidence': self.final_confidence,
            'drift_rate': self.drift_rate
        }


@dataclass
class TrainingArtifact:
    """
    Training artifact for model learning

    Contains labeled data for training confidence models and gate policies
    """
    artifact_id: str
    artifact_type: str  # 'confidence_training', 'gate_policy', 'reward_signal'
    input_features: Dict[str, Any]
    target_labels: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'artifact_id': self.artifact_id,
            'artifact_type': self.artifact_type,
            'input_features': self.input_features,
            'target_labels': self.target_labels,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class SimulationResult:
    """
    Result of simulating a failure scenario

    Contains execution outcomes and telemetry
    """
    simulation_id: str
    scenario_id: str
    failure_case: FailureCase
    execution_steps: List[Dict[str, Any]]
    telemetry_outcome: 'TelemetryOutcome'
    gates_triggered: List[str]
    gates_missed: List[str]
    final_risk: float
    final_confidence: float
    execution_halted: bool
    halt_reason: Optional[str]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'simulation_id': self.simulation_id,
            'scenario_id': self.scenario_id,
            'failure_case': self.failure_case.to_dict(),
            'execution_steps': self.execution_steps,
            'telemetry_outcome': self.telemetry_outcome.to_dict(),
            'gates_triggered': self.gates_triggered,
            'gates_missed': self.gates_missed,
            'final_risk': self.final_risk,
            'final_confidence': self.final_confidence,
            'execution_halted': self.execution_halted,
            'halt_reason': self.halt_reason,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TelemetryOutcome:
    """
    Telemetry outcome from simulation

    Captures all observable metrics during failure simulation
    """
    risk_trajectory: List[float]
    confidence_trajectory: List[float]
    murphy_index_trajectory: List[float]
    authority_level_trajectory: List[str]
    events: List[Dict[str, Any]]
    total_loss: float
    detection_latency: float  # Time to detect failure

    def to_dict(self) -> Dict[str, Any]:
        return {
            'risk_trajectory': self.risk_trajectory,
            'confidence_trajectory': self.confidence_trajectory,
            'murphy_index_trajectory': self.murphy_index_trajectory,
            'authority_level_trajectory': self.authority_level_trajectory,
            'events': self.events,
            'total_loss': self.total_loss,
            'detection_latency': self.detection_latency
        }


@dataclass
class HistoricalDisaster:
    """
    Historical disaster for replay

    Real-world disasters to learn from
    """
    disaster_id: str
    disaster_name: str
    date: str
    domain: str  # 'aviation', 'finance', 'medical', etc.
    root_causes: List[str]
    failure_chain: List[str]
    casualties: Optional[int]
    financial_loss: Optional[float]
    lessons_learned: List[str]
    preventable_by_gates: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'disaster_id': self.disaster_id,
            'disaster_name': self.disaster_name,
            'date': self.date,
            'domain': self.domain,
            'root_causes': self.root_causes,
            'failure_chain': self.failure_chain,
            'casualties': self.casualties,
            'financial_loss': self.financial_loss,
            'lessons_learned': self.lessons_learned,
            'preventable_by_gates': self.preventable_by_gates
        }


@dataclass
class RewardSignal:
    """
    Reward signal for gate policy learning

    Reward function: R = -Σ(L_k × p_k) - latency_penalty - false_positive_penalty
    """
    scenario_id: str
    expected_loss: float
    latency_penalty: float
    false_positive_penalty: float
    total_reward: float
    gate_configuration: List[str]
    detection_time: float
    false_positives: int

    def calculate_reward(self) -> float:
        """Calculate total reward"""
        self.total_reward = -(
            self.expected_loss +
            self.latency_penalty +
            self.false_positive_penalty
        )
        return self.total_reward

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scenario_id': self.scenario_id,
            'expected_loss': self.expected_loss,
            'latency_penalty': self.latency_penalty,
            'false_positive_penalty': self.false_positive_penalty,
            'total_reward': self.total_reward,
            'gate_configuration': self.gate_configuration,
            'detection_time': self.detection_time,
            'false_positives': self.false_positives
        }
