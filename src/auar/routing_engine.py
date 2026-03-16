"""
AUAR Layer 3 — Routing Decision Engine
========================================

Multi-factor routing algorithm that selects the optimal provider for a
given capability request.  Selection criteria include cost, latency,
reliability, compliance, and tenant-specific policies.

Supports A/B testing via strategy weights, circuit-breaker logic for
unhealthy providers, and deterministic fallback chains.

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .capability_graph import (
    CapabilityGraph,
    CapabilityMapping,
    CertificationLevel,
    HealthStatus,
    Provider,
)
from .signal_interpretation import IntentSignal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class RoutingStrategy(Enum):
    """Routing strategy (Enum subclass)."""
    COST_OPTIMIZED = "cost_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    RELIABILITY_FIRST = "reliability_first"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"


class CircuitState(Enum):
    """Circuit state (Enum subclass)."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderCandidate:
    """A scored candidate from the routing decision."""
    provider_id: str
    provider_name: str
    capability_mapping: CapabilityMapping
    score: float = 0.0
    reason: str = ""


@dataclass
class RoutingDecision:
    """The outcome of the routing engine for a single request."""
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    intent_signal_id: str = ""
    selected_provider: Optional[ProviderCandidate] = None
    fallback_providers: List[ProviderCandidate] = field(default_factory=list)
    strategy_used: RoutingStrategy = RoutingStrategy.RELIABILITY_FIRST
    score: float = 0.0
    latency_ms: float = 0.0
    circuit_breaker_triggered: bool = False


@dataclass
class _CircuitBreaker:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    failure_threshold: int = 5
    recovery_timeout_s: float = 30.0
    half_open_success_count: int = 0
    half_open_required_successes: int = 3
    half_open_traffic_ratio: float = 0.10


# ---------------------------------------------------------------------------
# Routing Decision Engine
# ---------------------------------------------------------------------------

class RoutingDecisionEngine:
    """Selects the best provider for a capability request.

    Scoring weights (configurable per tenant):
        reliability : 0.35
        latency     : 0.25
        cost        : 0.25
        certification: 0.15
    """

    DEFAULT_WEIGHTS = {
        "reliability": 0.35,
        "latency": 0.25,
        "cost": 0.25,
        "certification": 0.15,
    }

    def __init__(
        self,
        capability_graph: CapabilityGraph,
        strategy: RoutingStrategy = RoutingStrategy.RELIABILITY_FIRST,
        weights: Optional[Dict[str, float]] = None,
        circuit_failure_threshold: int = 5,
        circuit_recovery_s: float = 30.0,
        ml_optimizer=None,
        ml_weight: float = 0.20,
        max_latency_ms: float = 500.0,
        max_cost: float = 0.10,
        half_open_required_successes: int = 3,
        half_open_traffic_ratio: float = 0.10,
    ):
        self._graph = capability_graph
        self._strategy = strategy
        self._weights = weights or dict(self.DEFAULT_WEIGHTS)
        self._circuit_breakers: Dict[str, _CircuitBreaker] = {}
        self._cb_failure_threshold = circuit_failure_threshold
        self._cb_recovery_s = circuit_recovery_s
        self._ml_optimizer = ml_optimizer
        self._ml_weight = ml_weight
        self._max_latency_ms = max_latency_ms
        self._max_cost = max_cost
        self._half_open_required = half_open_required_successes
        self._half_open_ratio = half_open_traffic_ratio
        self._round_robin_idx: Dict[str, int] = {}
        self._tenant_configs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._stats = {"decisions": 0, "circuit_trips": 0, "fallbacks": 0, "ml_influenced": 0}

    # -- Per-tenant configuration -------------------------------------------

    def set_tenant_config(
        self,
        tenant_id: str,
        strategy: Optional[RoutingStrategy] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        """Set per-tenant routing strategy and/or weights."""
        with self._lock:
            cfg = self._tenant_configs.setdefault(tenant_id, {})
            if strategy is not None:
                cfg["strategy"] = strategy
            if weights is not None:
                cfg["weights"] = weights

    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        with self._lock:
            return dict(self._tenant_configs.get(tenant_id, {}))

    # -- Core routing -------------------------------------------------------

    def route(self, signal: IntentSignal) -> RoutingDecision:
        """Pick the best provider for *signal* and return a ``RoutingDecision``.

        If an ``ml_optimizer`` was provided at construction time, its
        recommendation is blended into the scoring as an additional factor.
        Per-tenant strategy/weight overrides are applied when the signal
        carries a ``context.tenant_id``.
        """
        start = time.monotonic()

        # Resolve per-tenant overrides
        tenant_id = signal.context.tenant_id if signal.context else ""
        strategy = self._strategy
        weights = self._weights
        with self._lock:
            tcfg = self._tenant_configs.get(tenant_id, {})
        if tcfg:
            strategy = tcfg.get("strategy", strategy)
            weights = tcfg.get("weights", weights)

        decision = RoutingDecision(intent_signal_id=signal.request_id, strategy_used=strategy)

        if not signal.parsed_intent:
            decision.latency_ms = (time.monotonic() - start) * 1000
            return decision

        candidates = self._score_candidates(signal, weights, strategy)

        # Blend ML recommendation when available
        if self._ml_optimizer and candidates and signal.parsed_intent:
            candidate_ids = [c.provider_id for c in candidates]
            ml_rec = self._ml_optimizer.recommend(
                signal.parsed_intent.capability_name, candidate_ids,
            )
            if ml_rec.recommended_provider_id:
                for c in candidates:
                    if c.provider_id == ml_rec.recommended_provider_id:
                        c.score = (1.0 - self._ml_weight) * c.score + self._ml_weight * max(0, ml_rec.confidence)
                candidates.sort(key=lambda c: c.score, reverse=True)
                with self._lock:
                    self._stats["ml_influenced"] += 1

        if not candidates:
            decision.latency_ms = (time.monotonic() - start) * 1000
            return decision

        # Select primary and fallback
        decision.selected_provider = candidates[0]
        decision.fallback_providers = candidates[1:3]
        decision.score = candidates[0].score

        # Check circuit breaker on selected provider
        if self._is_circuit_open(candidates[0].provider_id):
            decision.circuit_breaker_triggered = True
            # Promote first viable fallback
            for fb in candidates[1:]:
                if not self._is_circuit_open(fb.provider_id):
                    decision.selected_provider = fb
                    decision.score = fb.score
                    with self._lock:
                        self._stats["fallbacks"] += 1
                    break

        decision.latency_ms = (time.monotonic() - start) * 1000
        with self._lock:
            self._stats["decisions"] += 1
        return decision

    # -- Scoring ------------------------------------------------------------

    def _score_candidates(
        self,
        signal: IntentSignal,
        weights: Optional[Dict[str, float]] = None,
        strategy: Optional[RoutingStrategy] = None,
    ) -> List[ProviderCandidate]:
        w = weights or self._weights
        strat = strategy or self._strategy
        cap_name = signal.parsed_intent.capability_name  # type: ignore[union-attr]
        pairs = self._graph.providers_for_capability(cap_name)

        candidates: List[ProviderCandidate] = []
        for provider, mapping in pairs:
            if provider.health_status == HealthStatus.UNHEALTHY:
                continue
            score = self._compute_score(provider, mapping, w)
            candidates.append(ProviderCandidate(
                provider_id=provider.id,
                provider_name=provider.name,
                capability_mapping=mapping,
                score=score,
                reason=strat.value,
            ))

        # Strategy-specific ordering
        if strat == RoutingStrategy.ROUND_ROBIN and candidates:
            idx_key = cap_name
            with self._lock:
                idx = self._round_robin_idx.get(idx_key, 0)
                self._round_robin_idx[idx_key] = (idx + 1) % len(candidates)
            # rotate list
            candidates = candidates[idx:] + candidates[:idx]
        else:
            candidates.sort(key=lambda c: c.score, reverse=True)

        return candidates

    def _compute_score(
        self,
        provider: Provider,
        mapping: CapabilityMapping,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        w = weights or self._weights

        # Reliability (success rate)
        reliability = mapping.performance.success_rate  # 0-1

        # Latency (inverse, normalised using configurable ceiling)
        latency_raw = mapping.performance.avg_latency_ms
        latency = max(0.0, 1.0 - latency_raw / self._max_latency_ms)

        # Cost (inverse, normalised using configurable ceiling)
        cost_raw = mapping.cost_per_call
        cost = max(0.0, 1.0 - cost_raw / self._max_cost) if self._max_cost > 0 and cost_raw >= 0 else 1.0

        # Certification bonus
        cert_scores = {
            CertificationLevel.PRODUCTION: 1.0,
            CertificationLevel.BETA: 0.6,
            CertificationLevel.EXPERIMENTAL: 0.3,
        }
        cert = cert_scores.get(mapping.certification_level, 0.3)

        return (
            w["reliability"] * reliability
            + w["latency"] * latency
            + w["cost"] * cost
            + w["certification"] * cert
        )

    # -- Circuit breaker ----------------------------------------------------

    def _is_circuit_open(self, provider_id: str) -> bool:
        with self._lock:
            cb = self._circuit_breakers.get(provider_id)
            if not cb:
                return False
            if cb.state == CircuitState.OPEN:
                if time.monotonic() - cb.last_failure_time > cb.recovery_timeout_s:
                    cb.state = CircuitState.HALF_OPEN
                    cb.half_open_success_count = 0
                    # In HALF_OPEN: allow configurable % of traffic through
                    if random.random() < cb.half_open_traffic_ratio:
                        return False  # Allow this request
                    return True
                return True
            if cb.state == CircuitState.HALF_OPEN:
                # Allow configurable % of traffic through
                if random.random() < cb.half_open_traffic_ratio:
                    return False
                return True
        return False

    def record_failure(self, provider_id: str) -> None:
        """Record a provider failure; trip circuit breaker if threshold hit."""
        with self._lock:
            cb = self._circuit_breakers.setdefault(
                provider_id,
                _CircuitBreaker(
                    failure_threshold=self._cb_failure_threshold,
                    recovery_timeout_s=self._cb_recovery_s,
                    half_open_required_successes=self._half_open_required,
                    half_open_traffic_ratio=self._half_open_ratio,
                ),
            )
            cb.failure_count += 1
            cb.last_failure_time = time.monotonic()
            if cb.state == CircuitState.HALF_OPEN:
                # Failure in half-open → back to open
                cb.state = CircuitState.OPEN
                cb.half_open_success_count = 0
            elif cb.failure_count >= cb.failure_threshold:
                cb.state = CircuitState.OPEN
                self._stats["circuit_trips"] += 1
                logger.warning("Circuit OPEN for provider %s", provider_id)

    def record_success(self, provider_id: str) -> None:
        """Record success; require N consecutive successes in HALF_OPEN before closing."""
        with self._lock:
            cb = self._circuit_breakers.get(provider_id)
            if cb:
                if cb.state == CircuitState.HALF_OPEN:
                    cb.half_open_success_count += 1
                    if cb.half_open_success_count >= cb.half_open_required_successes:
                        cb.state = CircuitState.CLOSED
                        cb.failure_count = 0
                        cb.half_open_success_count = 0
                else:
                    cb.state = CircuitState.CLOSED
                    cb.failure_count = 0

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._stats)
