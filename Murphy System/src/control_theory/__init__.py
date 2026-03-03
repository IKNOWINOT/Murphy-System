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
]