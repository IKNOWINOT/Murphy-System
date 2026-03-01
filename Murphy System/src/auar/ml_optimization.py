"""
AUAR Layer 6 — ML Optimization Layer
======================================

Reinforcement-learning–inspired routing optimization that improves
provider selection over time.  Maintains per-capability / per-provider
feature vectors (latency, cost, success rate, user context) and uses
an epsilon-greedy exploration strategy for gradual rollout.

The model is intentionally lightweight (no external ML framework
required) to meet the P99 < 50ms routing latency target.

Copyright 2024 Inoni LLC – Apache License 2.0
"""

import logging
import math
import random
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RoutingFeatures:
    """Feature vector for a single routing observation."""
    capability_name: str = ""
    provider_id: str = ""
    latency_ms: float = 0.0
    cost: float = 0.0
    success: bool = True
    user_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class ProviderScore:
    """Running statistics for a provider on a given capability."""
    provider_id: str = ""
    total_calls: int = 0
    successes: int = 0
    total_latency_ms: float = 0.0
    total_cost: float = 0.0
    reward_sum: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.total_calls if self.total_calls else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_calls if self.total_calls else 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.total_calls if self.total_calls else 0.0

    @property
    def avg_reward(self) -> float:
        return self.reward_sum / self.total_calls if self.total_calls else 0.0


@dataclass
class OptimizationResult:
    """Recommendation from the ML layer."""
    recommended_provider_id: str = ""
    confidence: float = 0.0
    exploration: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# ML Optimizer
# ---------------------------------------------------------------------------

class MLOptimizer:
    """Epsilon-greedy multi-armed bandit for routing optimization.

    Reward function:
        reward = w_success * success + w_latency * (1 - latency/max_lat)
                 + w_cost * (1 - cost/max_cost)

    Exploration decays over time: epsilon = max(epsilon_min, epsilon * decay)
    """

    DEFAULT_REWARD_WEIGHTS = {
        "success": 0.50,
        "latency": 0.30,
        "cost": 0.20,
    }

    def __init__(
        self,
        epsilon: float = 0.15,
        epsilon_min: float = 0.01,
        epsilon_decay: float = 0.995,
        max_latency_ms: float = 500.0,
        max_cost: float = 0.10,
        reward_weights: Optional[Dict[str, float]] = None,
    ):
        self._epsilon = epsilon
        self._epsilon_min = epsilon_min
        self._epsilon_decay = epsilon_decay
        self._max_latency = max_latency_ms
        self._max_cost = max_cost
        self._reward_weights = reward_weights or dict(self.DEFAULT_REWARD_WEIGHTS)
        # cap_name → {provider_id → ProviderScore}
        self._scores: Dict[str, Dict[str, ProviderScore]] = {}
        self._lock = threading.Lock()
        self._observations = 0

    # -- Observation recording ----------------------------------------------

    def record(self, features: RoutingFeatures) -> float:
        """Record an observation and return the computed reward."""
        reward = self._compute_reward(features)
        with self._lock:
            cap_scores = self._scores.setdefault(features.capability_name, {})
            ps = cap_scores.setdefault(
                features.provider_id,
                ProviderScore(provider_id=features.provider_id),
            )
            ps.total_calls += 1
            if features.success:
                ps.successes += 1
            ps.total_latency_ms += features.latency_ms
            ps.total_cost += features.cost
            ps.reward_sum += reward
            self._observations += 1
            # Decay epsilon
            self._epsilon = max(self._epsilon_min, self._epsilon * self._epsilon_decay)
        return reward

    # -- Recommendation -----------------------------------------------------

    def recommend(
        self,
        capability_name: str,
        candidate_provider_ids: List[str],
    ) -> OptimizationResult:
        """Return the recommended provider for *capability_name*."""
        if not candidate_provider_ids:
            return OptimizationResult(reason="no candidates")

        # Exploration
        if random.random() < self._epsilon:
            chosen = random.choice(candidate_provider_ids)
            return OptimizationResult(
                recommended_provider_id=chosen,
                confidence=0.0,
                exploration=True,
                reason="epsilon-greedy exploration",
            )

        # Exploitation: pick highest average reward
        best_id = candidate_provider_ids[0]
        best_reward = -math.inf
        with self._lock:
            cap_scores = self._scores.get(capability_name, {})
            for pid in candidate_provider_ids:
                ps = cap_scores.get(pid)
                if ps and ps.avg_reward > best_reward:
                    best_reward = ps.avg_reward
                    best_id = pid

        confidence = max(0.0, min(1.0, best_reward)) if best_reward > -math.inf else 0.0
        return OptimizationResult(
            recommended_provider_id=best_id,
            confidence=confidence,
            exploration=False,
            reason="highest avg reward",
        )

    # -- Reward computation -------------------------------------------------

    def _compute_reward(self, f: RoutingFeatures) -> float:
        w = self._reward_weights
        r_success = 1.0 if f.success else 0.0
        r_latency = max(0.0, 1.0 - f.latency_ms / self._max_latency)
        r_cost = max(0.0, 1.0 - f.cost / self._max_cost) if self._max_cost > 0 else 1.0
        return (
            w["success"] * r_success
            + w["latency"] * r_latency
            + w["cost"] * r_cost
        )

    # -- Stats & inspection -------------------------------------------------

    def get_provider_stats(
        self, capability_name: str
    ) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            cap_scores = self._scores.get(capability_name, {})
            return {
                pid: {
                    "total_calls": ps.total_calls,
                    "success_rate": ps.success_rate,
                    "avg_latency_ms": ps.avg_latency_ms,
                    "avg_cost": ps.avg_cost,
                    "avg_reward": ps.avg_reward,
                }
                for pid, ps in cap_scores.items()
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_observations": self._observations,
                "epsilon": self._epsilon,
                "capabilities_tracked": len(self._scores),
            }
