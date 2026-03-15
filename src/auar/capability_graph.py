"""
AUAR Layer 2 — Capability Graph Layer
=======================================

Maintains a semantic graph of capabilities, providers, and their
relationships for intelligent routing decisions.

Graph structure (in-memory, production would use Neo4j):
    Nodes: Capability, Provider
    Edges: SUPPORTS, SIMILAR_TO, REQUIRES, PARENT_OF

Capability taxonomy:  Domain → Category → Capability → Variant
    Example: Communication → Email → send_email → [SendGrid, Mailgun, SES]

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CertificationLevel(Enum):
    """Certification level (Enum subclass)."""
    EXPERIMENTAL = "experimental"
    BETA = "beta"
    PRODUCTION = "production"


class HealthStatus(Enum):
    """Health status (Enum subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Capability:
    """A single abstract capability in the graph."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    domain: str = ""
    category: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    semantic_tags: List[str] = field(default_factory=list)
    parent_capabilities: List[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class PerformanceMetrics:
    """Observed performance for a provider-capability pair."""
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    success_rate: float = 1.0
    throughput_rps: float = 0.0


@dataclass
class CostModel:
    """Cost structure for a provider."""
    cost_per_call: float = 0.0
    monthly_base: float = 0.0
    free_tier_calls: int = 0
    currency: str = "USD"


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for a provider."""
    requests_per_second: int = 100
    requests_per_minute: int = 6000
    burst_limit: int = 200


@dataclass
class CapabilityMapping:
    """Links a capability to a provider with metadata."""
    capability_id: str = ""
    provider_id: str = ""
    certification_level: CertificationLevel = CertificationLevel.EXPERIMENTAL
    schema_adapter: str = ""
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    cost_per_call: float = 0.0


@dataclass
class Provider:
    """A downstream API provider."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    supported_capabilities: List[CapabilityMapping] = field(default_factory=list)
    base_url: str = ""
    auth_method: str = "api_key"
    rate_limits: RateLimitConfig = field(default_factory=RateLimitConfig)
    sla_tier: str = "standard"
    cost_model: CostModel = field(default_factory=CostModel)
    health_status: HealthStatus = HealthStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Capability Graph
# ---------------------------------------------------------------------------

class CapabilityGraph:
    """In-memory capability graph with query support.

    Production deployments should back this with Neo4j; the in-memory
    implementation preserves the same API contract.
    """

    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._providers: Dict[str, Provider] = {}
        self._cap_by_name: Dict[str, str] = {}  # name → id
        self._edges_supports: Dict[str, Set[str]] = {}  # provider_id → {cap_id}
        self._edges_similar: Dict[str, Set[str]] = {}  # cap_id → {cap_id}
        self._edges_parent: Dict[str, Set[str]] = {}   # cap_id → {child_cap_id}
        self._lock = threading.Lock()

    # -- Capability management ----------------------------------------------

    def register_capability(self, cap: Capability) -> str:
        """Register a capability and return its id."""
        with self._lock:
            self._capabilities[cap.id] = cap
            self._cap_by_name[cap.name] = cap.id
            # Auto-create parent edge if parent_capabilities provided
            for parent_id in cap.parent_capabilities:
                self._edges_parent.setdefault(parent_id, set()).add(cap.id)
        logger.info("Registered capability: %s (%s)", cap.name, cap.id)
        return cap.id

    def get_capability(self, capability_id: str) -> Optional[Capability]:
        with self._lock:
            return self._capabilities.get(capability_id)

    def find_capability_by_name(self, name: str) -> Optional[Capability]:
        with self._lock:
            cap_id = self._cap_by_name.get(name)
            if cap_id:
                return self._capabilities.get(cap_id)
        return None

    def list_capabilities(self, domain: Optional[str] = None,
                          category: Optional[str] = None) -> List[Capability]:
        with self._lock:
            caps = list(self._capabilities.values())
        if domain:
            caps = [c for c in caps if c.domain == domain]
        if category:
            caps = [c for c in caps if c.category == category]
        return caps

    # -- Provider management ------------------------------------------------

    def register_provider(self, provider: Provider) -> str:
        """Register a provider and index its capability mappings."""
        with self._lock:
            self._providers[provider.id] = provider
            cap_ids: Set[str] = set()
            for mapping in provider.supported_capabilities:
                mapping.provider_id = provider.id
                cap_ids.add(mapping.capability_id)
            self._edges_supports[provider.id] = cap_ids
        logger.info("Registered provider: %s (%s)", provider.name, provider.id)
        return provider.id

    def get_provider(self, provider_id: str) -> Optional[Provider]:
        with self._lock:
            return self._providers.get(provider_id)

    def list_providers(self) -> List[Provider]:
        with self._lock:
            return list(self._providers.values())

    # -- Graph queries ------------------------------------------------------

    def providers_for_capability(self, capability_name: str) -> List[Tuple[Provider, CapabilityMapping]]:
        """Return providers that support *capability_name* with their mapping."""
        cap = self.find_capability_by_name(capability_name)
        if not cap:
            return []

        results: List[Tuple[Provider, CapabilityMapping]] = []
        with self._lock:
            for provider in self._providers.values():
                for mapping in provider.supported_capabilities:
                    if mapping.capability_id == cap.id:
                        results.append((provider, mapping))
        return results

    def similar_capabilities(self, capability_name: str) -> List[Capability]:
        """Return capabilities marked as similar."""
        cap = self.find_capability_by_name(capability_name)
        if not cap:
            return []
        with self._lock:
            similar_ids = self._edges_similar.get(cap.id, set())
            return [self._capabilities[cid] for cid in similar_ids if cid in self._capabilities]

    def add_similarity_edge(self, cap_name_a: str, cap_name_b: str) -> bool:
        """Mark two capabilities as similar to each other."""
        with self._lock:
            id_a = self._cap_by_name.get(cap_name_a)
            id_b = self._cap_by_name.get(cap_name_b)
            if not id_a or not id_b:
                return False
            self._edges_similar.setdefault(id_a, set()).add(id_b)
            self._edges_similar.setdefault(id_b, set()).add(id_a)
        return True

    def child_capabilities(self, capability_name: str) -> List[Capability]:
        """Return child capabilities of *capability_name*."""
        cap = self.find_capability_by_name(capability_name)
        if not cap:
            return []
        with self._lock:
            child_ids = self._edges_parent.get(cap.id, set())
            return [self._capabilities[cid] for cid in child_ids if cid in self._capabilities]

    # -- Health & stats -----------------------------------------------------

    def update_provider_health(self, provider_id: str, status: HealthStatus) -> bool:
        with self._lock:
            prov = self._providers.get(provider_id)
            if prov:
                prov.health_status = status
                return True
        return False

    # -- Semantic tag search ------------------------------------------------

    def search_by_tags(self, tags: List[str]) -> List[Capability]:
        """Return capabilities whose semantic_tags overlap with *tags*."""
        tag_set = set(t.lower() for t in tags)
        with self._lock:
            results = []
            for cap in self._capabilities.values():
                cap_tags = set(t.lower() for t in cap.semantic_tags)
                if cap_tags & tag_set:
                    results.append(cap)
        return results

    # -- Deregistration -----------------------------------------------------

    def deregister_provider(self, provider_id: str) -> bool:
        """Remove a provider from the graph."""
        with self._lock:
            if provider_id not in self._providers:
                return False
            del self._providers[provider_id]
            self._edges_supports.pop(provider_id, None)
        logger.info("Deregistered provider: %s", provider_id)
        return True

    def deregister_capability(self, capability_name: str) -> bool:
        """Remove a capability and its edges from the graph."""
        with self._lock:
            cap_id = self._cap_by_name.pop(capability_name, None)
            if not cap_id:
                return False
            self._capabilities.pop(cap_id, None)
            self._edges_similar.pop(cap_id, None)
            self._edges_parent.pop(cap_id, None)
            # Clean similarity back-references
            for sim_set in self._edges_similar.values():
                sim_set.discard(cap_id)
            # Clean parent back-references
            for child_set in self._edges_parent.values():
                child_set.discard(cap_id)
        logger.info("Deregistered capability: %s", capability_name)
        return True

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_capabilities": len(self._capabilities),
                "total_providers": len(self._providers),
                "total_mappings": sum(
                    len(p.supported_capabilities) for p in self._providers.values()
                ),
                "similarity_edges": sum(
                    len(v) for v in self._edges_similar.values()
                ) // 2,
            }
