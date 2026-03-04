"""
Murphy System — Control Theory Layer.

Formal models that close the gaps identified in the structural audit.
"""

from .canonical_state import CanonicalStateVector, DimensionRegistry
from .entropy import (
    information_gain,
    kl_divergence,
    normalize_distribution,
    shannon_entropy,
    uniform_distribution,
    max_entropy,
)
from .bayesian_engine import (
    BayesianConfidenceEngine,
    BeliefState,
    LikelihoodModel,
    Observation,
    UpdateResult,
)
from .state_adapter import (
    from_dict,
    from_mfgc_state,
    from_rosetta_state,
    from_session,
    from_unified_system_state,
)
from .observation_model import (
    ObservationChannel,
    ObservationData,
    ObservationFunction,
    ObservationNoise,
)
from .control_vector import (
    ControlAction,
    ControlLaw,
    ControlVector,
)
from .state_transition import (
    ProcessNoise,
    StateTransitionFunction,
)
from .stability import (
    LyapunovFunction,
    StabilityAnalyzer,
    StabilityResult,
)
from .jurisdiction import (
    Jurisdiction,
    JurisdictionConstraint,
    JurisdictionConstraintRegistry,
    JURISDICTION_EU,
    JURISDICTION_GLOBAL,
    JURISDICTION_UK,
    JURISDICTION_US,
    JURISDICTION_US_CA,
)
from .actor_registry import (
    Actor,
    ActorKind,
    ActorRegistry,
    AuthorityMatrix,
)
from .llm_validation import (
    ConflictResolver,
    ConflictResult,
    ExpertProfileOutput,
    GateProposalOutput,
    LLMOutputKind,
    RecommendationOutput,
    RegenerationPolicy,
    ResolutionStrategy,
    validate_llm_output,
)

# New control-theory modules closing the structural audit gaps
from .state_model import (
    StateDimension,
    StateVector,
    StateEvolution,
)
from .infinity_metric import (
    CandidateQuestion,
    EntropyTracker,
    QuestionSelector,
    UncertaintyBudget,
    compute_differential_entropy,
    compute_murphy_index_formal,
)
from .control_structure import (
    AuthorityGate,
    ControlDimension,
    ControlLaw as PIControlLaw,
    ControlVector as PIControlVector,
    StabilityMonitor,
    StabilityResult as StructuralStabilityResult,
)
from .scaling_mechanism import (
    AuthorityExpander,
    ConstraintInjector,
    DimensionExpander,
    InjectedConstraint,
    RefinementLoop,
    RoleNode,
)
from .llm_synthesis_validator import (
    ConflictKind,
    ConflictReport,
    ConflictResolver as SynthesisConflictResolver,
    GeneratedConstraint,
    GeneratedRole,
    GeneratedStateDimension,
    OutputValidator,
    RegenerationTrigger,
    ValidationResult,
    validate_output,
)
from .observation_model import KalmanObserver

__all__ = [
    # State model
    "CanonicalStateVector",
    "DimensionRegistry",
    # Entropy / info theory
    "shannon_entropy",
    "kl_divergence",
    "information_gain",
    "normalize_distribution",
    "uniform_distribution",
    "max_entropy",
    # Bayesian engine
    "BayesianConfidenceEngine",
    "BeliefState",
    "LikelihoodModel",
    "Observation",
    "UpdateResult",
    # Adapters
    "from_dict",
    "from_mfgc_state",
    "from_rosetta_state",
    "from_session",
    "from_unified_system_state",
    # Observation model
    "ObservationChannel",
    "ObservationData",
    "ObservationFunction",
    "ObservationNoise",
    # Control vector
    "ControlAction",
    "ControlLaw",
    "ControlVector",
    # State transition
    "ProcessNoise",
    "StateTransitionFunction",
    # Stability
    "LyapunovFunction",
    "StabilityAnalyzer",
    "StabilityResult",
    # Jurisdiction
    "Jurisdiction",
    "JurisdictionConstraint",
    "JurisdictionConstraintRegistry",
    "JURISDICTION_EU",
    "JURISDICTION_GLOBAL",
    "JURISDICTION_UK",
    "JURISDICTION_US",
    "JURISDICTION_US_CA",
    # Actor registry
    "Actor",
    "ActorKind",
    "ActorRegistry",
    "AuthorityMatrix",
    # LLM validation
    "ConflictResolver",
    "ConflictResult",
    "ExpertProfileOutput",
    "GateProposalOutput",
    "LLMOutputKind",
    "RecommendationOutput",
    "RegenerationPolicy",
    "ResolutionStrategy",
    "validate_llm_output",
    # state_model
    "StateDimension",
    "StateVector",
    "StateEvolution",
    # infinity_metric
    "CandidateQuestion",
    "EntropyTracker",
    "QuestionSelector",
    "UncertaintyBudget",
    "compute_differential_entropy",
    "compute_murphy_index_formal",
    # control_structure
    "AuthorityGate",
    "ControlDimension",
    "PIControlLaw",
    "PIControlVector",
    "StabilityMonitor",
    "StructuralStabilityResult",
    # scaling_mechanism
    "AuthorityExpander",
    "ConstraintInjector",
    "DimensionExpander",
    "InjectedConstraint",
    "RefinementLoop",
    "RoleNode",
    # llm_synthesis_validator
    "ConflictKind",
    "ConflictReport",
    "SynthesisConflictResolver",
    "GeneratedConstraint",
    "GeneratedRole",
    "GeneratedStateDimension",
    "OutputValidator",
    "RegenerationTrigger",
    "ValidationResult",
    "validate_output",
    # observation_model extension
    "KalmanObserver",
]
