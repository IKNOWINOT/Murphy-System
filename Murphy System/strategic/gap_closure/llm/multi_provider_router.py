# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
multi_provider_router.py — Murphy System LLM Multi-Provider Router
Routes requests to 12+ LLM providers using 6 configurable strategies.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RoutingStrategy(Enum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    MOST_RELIABLE = "most_reliable"
    CAPABILITY_MATCH = "capability_match"
    ROUND_ROBIN = "round_robin"
    CONFIDENCE_WEIGHTED = "confidence_weighted"


class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Provider:
    name: str
    endpoint: str
    model: str
    cost_per_1k_tokens: float          # USD per 1,000 tokens (combined in+out)
    latency_ms: float                  # typical latency in milliseconds
    reliability_score: float           # 0.0 – 1.0
    capabilities: List[str]            # e.g. ["chat", "code", "vision", "function_calling"]
    context_window: int = 8192         # tokens
    provider_id: Optional[str] = None  # vendor ID / deployment name
    status: ProviderStatus = ProviderStatus.HEALTHY
    requests_routed: int = 0
    cumulative_latency_ms: float = 0.0
    errors: int = 0

    def __post_init__(self) -> None:
        if not self.provider_id:
            self.provider_id = self.name.lower().replace(" ", "_").replace("/", "_")

    @property
    def avg_latency_ms(self) -> float:
        if self.requests_routed == 0:
            return self.latency_ms
        return round(self.cumulative_latency_ms / self.requests_routed, 1)

    @property
    def error_rate(self) -> float:
        if self.requests_routed == 0:
            return 0.0
        return round(self.errors / self.requests_routed, 4)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "endpoint": self.endpoint,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "latency_ms": self.latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "reliability_score": self.reliability_score,
            "capabilities": self.capabilities,
            "context_window": self.context_window,
            "status": self.status.value,
            "requests_routed": self.requests_routed,
            "error_rate": self.error_rate,
        }


@dataclass
class RoutingDecision:
    provider: Provider
    strategy: RoutingStrategy
    score: float
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider.name,
            "model": self.provider.model,
            "strategy": self.strategy.value,
            "score": self.score,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class BenchmarkResult:
    provider_name: str
    latency_ms: float
    success: bool
    tokens_per_second: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "provider": self.provider_name,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "tokens_per_second": self.tokens_per_second,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# MultiProviderRouter
# ---------------------------------------------------------------------------

class MultiProviderRouter:
    """
    Routes LLM requests to the optimal provider based on the chosen strategy.

    Usage:
        router = MultiProviderRouter()
        decision = router.route(
            prompt="Summarize this contract.",
            strategy=RoutingStrategy.CHEAPEST,
            required_capabilities=["chat"],
        )
        print(decision.provider.name, decision.reason)
    """

    def __init__(self) -> None:
        self._providers: Dict[str, Provider] = {}
        self._round_robin_index: int = 0
        self._routing_history: List[RoutingDecision] = []

    # ── Provider management ──────────────────────────────────────────────────

    def add_provider(self, provider: Provider) -> None:
        self._providers[provider.provider_id] = provider  # type: ignore[index]

    def remove_provider(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            del self._providers[provider_id]
            return True
        return False

    def get_provider(self, provider_id: str) -> Optional[Provider]:
        return self._providers.get(provider_id)

    def list_providers(self, status: Optional[ProviderStatus] = None) -> List[Provider]:
        providers = list(self._providers.values())
        if status:
            providers = [p for p in providers if p.status == status]
        return providers

    # ── Routing ──────────────────────────────────────────────────────────────

    def route(
        self,
        prompt: str = "",
        strategy: RoutingStrategy = RoutingStrategy.MOST_RELIABLE,
        required_capabilities: Optional[List[str]] = None,
        max_cost_per_1k: Optional[float] = None,
        confidence_hint: float = 0.9,
    ) -> Optional[RoutingDecision]:
        candidates = [
            p for p in self._providers.values()
            if p.status == ProviderStatus.HEALTHY
        ]

        if required_capabilities:
            candidates = [
                p for p in candidates
                if all(cap in p.capabilities for cap in required_capabilities)
            ]

        if max_cost_per_1k is not None:
            candidates = [p for p in candidates if p.cost_per_1k_tokens <= max_cost_per_1k]

        if not candidates:
            return None

        if strategy == RoutingStrategy.CHEAPEST:
            winner = min(candidates, key=lambda p: p.cost_per_1k_tokens)
            score = 1.0 / (winner.cost_per_1k_tokens + 0.001)
            reason = f"Lowest cost: ${winner.cost_per_1k_tokens}/1K tokens"

        elif strategy == RoutingStrategy.FASTEST:
            winner = min(candidates, key=lambda p: p.avg_latency_ms)
            score = 1.0 / (winner.avg_latency_ms + 1)
            reason = f"Lowest latency: {winner.avg_latency_ms}ms"

        elif strategy == RoutingStrategy.MOST_RELIABLE:
            winner = max(candidates, key=lambda p: p.reliability_score)
            score = winner.reliability_score
            reason = f"Highest reliability: {winner.reliability_score}"

        elif strategy == RoutingStrategy.CAPABILITY_MATCH:
            caps = required_capabilities or []
            winner = max(candidates, key=lambda p: len(set(p.capabilities) & set(caps)))
            matched = len(set(winner.capabilities) & set(caps))
            score = matched / max(len(caps), 1)
            reason = f"Best capability match: {matched}/{len(caps)} capabilities"

        elif strategy == RoutingStrategy.ROUND_ROBIN:
            idx = self._round_robin_index % len(candidates)
            self._round_robin_index += 1
            winner = candidates[idx]
            score = 1.0
            reason = f"Round-robin index {idx}"

        elif strategy == RoutingStrategy.CONFIDENCE_WEIGHTED:
            # High-confidence tasks → cheapest; low-confidence → most reliable
            if confidence_hint >= 0.9:
                winner = min(candidates, key=lambda p: p.cost_per_1k_tokens)
                reason = f"High confidence ({confidence_hint}) → cheapest: ${winner.cost_per_1k_tokens}/1K"
            else:
                winner = max(candidates, key=lambda p: p.reliability_score)
                reason = f"Low confidence ({confidence_hint}) → most reliable: {winner.reliability_score}"
            score = confidence_hint

        else:
            winner = candidates[0]
            score = 1.0
            reason = "Default selection"

        decision = RoutingDecision(provider=winner, strategy=strategy,
                                   score=round(score, 4), reason=reason)
        self._routing_history.append(decision)
        winner.requests_routed += 1
        return decision

    # ── Benchmarking ─────────────────────────────────────────────────────────

    def benchmark(self, test_prompt: str = "Say hello.") -> List[BenchmarkResult]:
        """Simulate benchmarking all healthy providers."""
        results: List[BenchmarkResult] = []
        for provider in self.list_providers(ProviderStatus.HEALTHY):
            # Simulate with jitter ±10%
            jitter = random.uniform(0.9, 1.1)
            latency = round(provider.latency_ms * jitter, 1)
            tps = round(random.uniform(30, 150), 1)
            results.append(BenchmarkResult(
                provider_name=provider.name,
                latency_ms=latency,
                success=True,
                tokens_per_second=tps,
            ))
            provider.cumulative_latency_ms += latency
            provider.requests_routed += 1
        results.sort(key=lambda r: r.latency_ms)
        return results

    def get_routing_table(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._providers.values()]

    def routing_history(self, last_n: int = 20) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._routing_history[-last_n:]]


# ---------------------------------------------------------------------------
# Pre-registered providers
# ---------------------------------------------------------------------------

def build_default_router() -> MultiProviderRouter:
    router = MultiProviderRouter()
    providers = [
        Provider(
            name="GPT-4o",
            endpoint="https://api.openai.com/v1/chat/completions",
            model="gpt-4o",
            cost_per_1k_tokens=0.005,
            latency_ms=800,
            reliability_score=0.995,
            capabilities=["chat", "code", "vision", "function_calling", "json_mode"],
            context_window=128000,
        ),
        Provider(
            name="GPT-4-Turbo",
            endpoint="https://api.openai.com/v1/chat/completions",
            model="gpt-4-turbo",
            cost_per_1k_tokens=0.010,
            latency_ms=1200,
            reliability_score=0.993,
            capabilities=["chat", "code", "vision", "function_calling"],
            context_window=128000,
        ),
        Provider(
            name="Claude 3 Opus",
            endpoint="https://api.anthropic.com/v1/messages",
            model="claude-3-opus-20240229",
            cost_per_1k_tokens=0.015,
            latency_ms=2000,
            reliability_score=0.992,
            capabilities=["chat", "code", "vision", "long_context", "analysis"],
            context_window=200000,
        ),
        Provider(
            name="Claude 3.5 Sonnet",
            endpoint="https://api.anthropic.com/v1/messages",
            model="claude-3-5-sonnet-20241022",
            cost_per_1k_tokens=0.003,
            latency_ms=700,
            reliability_score=0.994,
            capabilities=["chat", "code", "vision", "function_calling", "long_context"],
            context_window=200000,
        ),
        Provider(
            name="Gemini 1.5 Pro",
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro",
            model="gemini-1.5-pro-latest",
            cost_per_1k_tokens=0.0035,
            latency_ms=900,
            reliability_score=0.990,
            capabilities=["chat", "code", "vision", "long_context", "multimodal"],
            context_window=1000000,
        ),
        Provider(
            name="Gemini Flash",
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash",
            model="gemini-1.5-flash-latest",
            cost_per_1k_tokens=0.00035,
            latency_ms=300,
            reliability_score=0.988,
            capabilities=["chat", "code", "vision", "fast"],
            context_window=1000000,
        ),
        Provider(
            name="DeepInfra Mixtral",
            endpoint="https://api.deepinfra.com/v1/openai/chat/completions",
            model="meta-llama/Meta-Llama-3.1-70B-Instruct",
            cost_per_1k_tokens=0.00027,
            latency_ms=150,
            reliability_score=0.985,
            capabilities=["chat", "code", "fast", "function_calling"],
            context_window=32768,
        ),
        Provider(
            name="DeepInfra LLaMA3",
            endpoint="https://api.deepinfra.com/v1/openai/chat/completions",
            model="meta-llama/Meta-Llama-3.1-70B-Instruct",
            cost_per_1k_tokens=0.00059,
            latency_ms=180,
            reliability_score=0.983,
            capabilities=["chat", "code", "fast"],
            context_window=8192,
        ),
        Provider(
            name="Mistral Large",
            endpoint="https://api.mistral.ai/v1/chat/completions",
            model="mistral-large-latest",
            cost_per_1k_tokens=0.008,
            latency_ms=600,
            reliability_score=0.989,
            capabilities=["chat", "code", "function_calling", "multilingual"],
            context_window=32000,
        ),
        Provider(
            name="Cohere Command R+",
            endpoint="https://api.cohere.ai/v1/chat",
            model="command-r-plus",
            cost_per_1k_tokens=0.003,
            latency_ms=500,
            reliability_score=0.987,
            capabilities=["chat", "rag", "search", "multilingual", "enterprise"],
            context_window=128000,
        ),
        Provider(
            name="Perplexity Online",
            endpoint="https://api.perplexity.ai/chat/completions",
            model="llama-3-sonar-large-32k-online",
            cost_per_1k_tokens=0.001,
            latency_ms=1500,
            reliability_score=0.981,
            capabilities=["chat", "search", "realtime", "citations"],
            context_window=32768,
        ),
        Provider(
            name="Local Ollama",
            endpoint="http://localhost:11434/api/chat",
            model="llama3:8b",
            cost_per_1k_tokens=0.0,
            latency_ms=400,
            reliability_score=0.970,
            capabilities=["chat", "code", "offline", "private"],
            context_window=8192,
        ),
    ]
    for p in providers:
        router.add_provider(p)
    return router


# Module-level singleton
default_router: MultiProviderRouter = build_default_router()


if __name__ == "__main__":
    import json as _json

    router = build_default_router()
    print("Murphy System LLM Multi-Provider Router")
    print(f"Providers loaded: {len(router.list_providers())}")
    print()

    for strategy in RoutingStrategy:
        decision = router.route(
            prompt="Summarize this document.",
            strategy=strategy,
            required_capabilities=["chat"],
        )
        if decision:
            print(f"  [{strategy.value:>20}] → {decision.provider.name:<25} ({decision.reason})")

    print()
    print("Benchmark results (top 5 by latency):")
    results = router.benchmark()
    for r in results[:5]:
        print(f"  {r.provider_name:<25} {r.latency_ms:>7.1f}ms  {r.tokens_per_second:>5.1f} tok/s")
