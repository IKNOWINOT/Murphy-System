"""
Adaptive Universal API Router (AUAR)
=====================================

Intelligent, capability-based semantic routing layer for APIs.
Internal codename: FAPI (Flexible Adaptive Provider Interface)

Accepts arbitrary API requests (REST, GraphQL, or natural language),
interprets intent using hybrid LLM + deterministic approaches, maps
requests to abstract capabilities, and routes to optimal downstream
provider APIs with automatic schema translation.

Copyright 2024 Inoni LLC – Apache License 2.0
"""

__version__ = "0.1.0"
__codename__ = "FAPI"

from .signal_interpretation import (
    SignalInterpreter,
    IntentSignal,
    CapabilityIntent,
    RequestContext,
    ConfidenceScorer,
)
from .capability_graph import (
    CapabilityGraph,
    Capability,
    Provider,
    CapabilityMapping,
    CertificationLevel,
)
from .routing_engine import (
    RoutingDecisionEngine,
    RoutingDecision,
    ProviderCandidate,
    RoutingStrategy,
)
from .schema_translation import (
    SchemaTranslator,
    SchemaMapping,
    TranslationResult,
)
from .provider_adapter import (
    ProviderAdapterManager,
    ProviderAdapter,
    AdapterConfig,
    AuthMethod,
)
from .ml_optimization import (
    MLOptimizer,
    RoutingFeatures,
    OptimizationResult,
)
from .observability import (
    ObservabilityLayer,
    AuditEntry,
    CostAttribution,
    RequestTrace,
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
    # Routing Engine
    "RoutingDecisionEngine",
    "RoutingDecision",
    "ProviderCandidate",
    "RoutingStrategy",
    # Schema Translation
    "SchemaTranslator",
    "SchemaMapping",
    "TranslationResult",
    # Provider Adapter
    "ProviderAdapterManager",
    "ProviderAdapter",
    "AdapterConfig",
    "AuthMethod",
    # ML Optimization
    "MLOptimizer",
    "RoutingFeatures",
    "OptimizationResult",
    # Observability
    "ObservabilityLayer",
    "AuditEntry",
    "CostAttribution",
    "RequestTrace",
]
