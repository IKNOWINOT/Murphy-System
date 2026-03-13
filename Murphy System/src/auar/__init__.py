"""
Adaptive Universal API Router (AUAR)
=====================================

Intelligent, capability-based semantic routing layer for APIs.
Internal codename: FAPI (Flexible Adaptive Provider Interface)

Accepts arbitrary API requests (REST, GraphQL, or natural language),
interprets intent using hybrid LLM + deterministic approaches, maps
requests to abstract capabilities, and routes to optimal downstream
provider APIs with automatic schema translation.

Copyright 2024 Inoni LLC – BSL-1.1
"""

__version__ = "0.1.0"
__codename__ = "FAPI"

from .capability_graph import (
    Capability,
    CapabilityGraph,
    CapabilityMapping,
    CertificationLevel,
    HealthStatus,
    PerformanceMetrics,
    Provider,
)
from .config import (
    AUARConfig,
    InterpreterConfig,
    MLConfig,
    ObservabilityConfig,
    RoutingConfig,
)
from .ml_optimization import (
    MLOptimizer,
    OptimizationResult,
    RoutingFeatures,
)
from .observability import (
    AuditEntry,
    CostAttribution,
    ObservabilityLayer,
    RequestTrace,
)
from .persistence import (
    FileStateBackend,
    InMemoryStateBackend,
    StateBackend,
)
from .pipeline import (
    AUARPipeline,
    PipelineResult,
)
from .provider_adapter import (
    AdapterConfig,
    AdapterResponse,
    AuthMethod,
    Protocol,
    ProviderAdapter,
    ProviderAdapterManager,
)
from .routing_engine import (
    ProviderCandidate,
    RoutingDecision,
    RoutingDecisionEngine,
    RoutingStrategy,
)
from .schema_translation import (
    FieldMapping,
    SchemaMapping,
    SchemaTranslator,
    TranslationResult,
)
from .signal_interpretation import (
    CapabilityIntent,
    ConfidenceScorer,
    IntentSignal,
    RequestContext,
    SignalInterpreter,
)

__all__ = [
    # Signal Interpretation
    "SignalInterpreter",
    "IntentSignal",
    "CapabilityIntent",
    "RequestContext",
    "ConfidenceScorer",
    # Capability Graph
    "CapabilityGraph",
    "Capability",
    "Provider",
    "CapabilityMapping",
    "CertificationLevel",
    "HealthStatus",
    "PerformanceMetrics",
    # Routing Engine
    "RoutingDecisionEngine",
    "RoutingDecision",
    "ProviderCandidate",
    "RoutingStrategy",
    # Schema Translation
    "SchemaTranslator",
    "SchemaMapping",
    "FieldMapping",
    "TranslationResult",
    # Provider Adapter
    "ProviderAdapterManager",
    "ProviderAdapter",
    "AdapterConfig",
    "AdapterResponse",
    "AuthMethod",
    "Protocol",
    # ML Optimization
    "MLOptimizer",
    "RoutingFeatures",
    "OptimizationResult",
    # Observability
    "ObservabilityLayer",
    "AuditEntry",
    "CostAttribution",
    "RequestTrace",
    # Pipeline
    "AUARPipeline",
    "PipelineResult",
    # Configuration
    "AUARConfig",
    "RoutingConfig",
    "MLConfig",
    "ObservabilityConfig",
    "InterpreterConfig",
    # Persistence
    "StateBackend",
    "InMemoryStateBackend",
    "FileStateBackend",
]
