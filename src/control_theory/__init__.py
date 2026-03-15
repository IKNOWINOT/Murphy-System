"""
Murphy System — Control Theory Layer.

Formal models that close the gaps identified in the structural audit.
"""

from .actor_registry import (
    Actor,
    ActorKind,
    ActorRegistry,
    AuthorityMatrix,
)
from .bayesian_engine import (
    BayesianConfidenceEngine,
    BeliefState,
    LikelihoodModel,
    Observation,
    UpdateResult,
)
from .canonical_state import CanonicalStateVector, DimensionRegistry
from .control_structure import (
    AuthorityGate,
    ControlDimension,
    StabilityMonitor,
)
from .control_structure import (
    ControlLaw as PIControlLaw,
)
from .control_structure import (
    ControlVector as PIControlVector,
)
from .control_structure import (
    StabilityResult as StructuralStabilityResult,
)
from .control_vector import (
    ControlAction,
    ControlLaw,
    ControlVector,
)
from .entropy import (
    information_gain,
    kl_divergence,
    max_entropy,
    normalize_distribution,
    shannon_entropy,
    uniform_distribution,
)
from .infinity_metric import (
    CandidateQuestion,
    EntropyTracker,
    QuestionSelector,
    UncertaintyBudget,
    compute_differential_entropy,
    compute_murphy_index_formal,
)
from .jurisdiction import (
    JURISDICTION_EU,
    JURISDICTION_GLOBAL,
    JURISDICTION_UK,
    JURISDICTION_US,
    JURISDICTION_US_CA,
    Jurisdiction,
    JurisdictionConstraint,
    JurisdictionConstraintRegistry,
)
from .llm_synthesis_validator import (
    ConflictKind,
    ConflictReport,
    GeneratedConstraint,
    GeneratedRole,
    GeneratedStateDimension,
    OutputValidator,
    RegenerationTrigger,
    ValidationResult,
    validate_output,
)
from .llm_synthesis_validator import (
    ConflictResolver as SynthesisConflictResolver,
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
from .observation_model import (
    KalmanObserver,
    ObservationChannel,
    ObservationData,
    ObservationFunction,
    ObservationNoise,
)
from .scaling_mechanism import (
    AuthorityExpander,
    ConstraintInjector,
    DimensionExpander,
    InjectedConstraint,
    RefinementLoop,
    RoleNode,
)
from .stability import (
    LyapunovFunction,
    StabilityAnalyzer,
    StabilityResult,
)
from .state_adapter import (
    from_dict,
    from_mfgc_state,
    from_rosetta_state,
    from_session,
    from_unified_system_state,
)

# New control-theory modules closing the structural audit gaps
from .state_model import (
    StateDimension,
    StateEvolution,
    StateVector,
)
from .state_transition import (
    ProcessNoise,
    StateTransitionFunction,
)

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
