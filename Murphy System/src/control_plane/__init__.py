"""
Control Plane Services
Adaptive, AI-heavy, probabilistic services for reasoning and planning
"""

from .execution_packet import (
    ExecutionPacket,
    Action,
    Gate,
    SafetyConstraint,
    TimeWindow,
    RollbackPlan,
    AuthorityEnvelope,
    ActionType,
    ConstraintType,
    create_simple_packet
)

from .packet_compiler import (
    PacketCompiler,
    PacketCompilationError
)

from .state_vector import StateVector

from .observation_model import (
    ObservationChannel,
    ObservationVector,
    ObservationNoise,
    ObservationMapping,
    information_gain,
)

from .control_loop import (
    ControlVector,
    ControlLaw,
    StabilityMonitor,
    StabilityViolation,
    ControlAuthorityMatrix,
)

from .formal_constraints import (
    FormalConstraint,
    MinimumConfidenceConstraint,
    MaximumRiskConstraint,
    LambdaConstraint,
    JurisdictionRegistry,
    ProbabilisticConstraintChecker,
)

from .llm_output_schemas import (
    ExpertGenerationOutput,
    GateProposalOutput,
    CandidateGenerationOutput,
    DomainAnalysisOutput,
    LLMOutputValidator,
    ConflictResolver,
    RegenerationTrigger,
)

__all__ = [
    # execution_packet
    'ExecutionPacket',
    'Action',
    'Gate',
    'SafetyConstraint',
    'TimeWindow',
    'RollbackPlan',
    'AuthorityEnvelope',
    'ActionType',
    'ConstraintType',
    'create_simple_packet',
    # packet_compiler
    'PacketCompiler',
    'PacketCompilationError',
    # state_vector
    'StateVector',
    # observation_model
    'ObservationChannel',
    'ObservationVector',
    'ObservationNoise',
    'ObservationMapping',
    'information_gain',
    # control_loop
    'ControlVector',
    'ControlLaw',
    'StabilityMonitor',
    'StabilityViolation',
    'ControlAuthorityMatrix',
    # formal_constraints
    'FormalConstraint',
    'MinimumConfidenceConstraint',
    'MaximumRiskConstraint',
    'LambdaConstraint',
    'JurisdictionRegistry',
    'ProbabilisticConstraintChecker',
    # llm_output_schemas
    'ExpertGenerationOutput',
    'GateProposalOutput',
    'CandidateGenerationOutput',
    'DomainAnalysisOutput',
    'LLMOutputValidator',
    'ConflictResolver',
    'RegenerationTrigger',
]
