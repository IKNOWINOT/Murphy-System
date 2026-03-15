"""
AUAR Layer 6 — ML Optimization Layer
======================================

Reinforcement-learning–inspired routing optimization that improves
provider selection over time.  Maintains per-capability / per-provider
feature vectors (latency, cost, success rate, user context) and uses
a UCB1-based exploration strategy with per-capability epsilon and
exponential recency decay.

The model is intentionally lightweight (no external ML framework
required) to meet the P99 < 50ms routing latency target.

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import math
import random
import threading
import time
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
    weighted_reward_sum: float = 0.0
    weight_sum: float = 0.0

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

    @property
    def weighted_avg_reward(self) -> float:
        return self.weighted_reward_sum / self.weight_sum if self.weight_sum > 0 else 0.0


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
    """UCB1-based multi-armed bandit with per-capability epsilon and recency decay.

    Reward function:
        reward = w_success * success + w_latency * (1 - latency/max_lat)
                 + w_cost * (1 - cost/max_cost)

    Exploration uses UCB1 for under-sampled providers and epsilon-greedy
    per capability.  Epsilon decays independently for each capability.
    Recent observations are weighted higher via exponential decay.
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
        recency_decay: float = 0.99,
        ucb_exploration_weight: float = 1.0,
    ):
        self._epsilon_initial = epsilon
        self._epsilon_min = epsilon_min
        self._epsilon_decay = epsilon_decay
        self._max_latency = max_latency_ms
        self._max_cost = max_cost
        self._reward_weights = reward_weights or dict(self.DEFAULT_REWARD_WEIGHTS)
        self._recency_decay = recency_decay
        self._ucb_weight = ucb_exploration_weight
        # cap_name → {provider_id → ProviderScore}
        self._scores: Dict[str, Dict[str, ProviderScore]] = {}
        # per-capability epsilon
        self._capability_epsilon: Dict[str, float] = {}
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

            # Exponential recency weighting
            ps.weighted_reward_sum = ps.weighted_reward_sum * self._recency_decay + reward
            ps.weight_sum = ps.weight_sum * self._recency_decay + 1.0

            self._observations += 1
            # Decay epsilon per capability
            cap_eps = self._capability_epsilon.get(
                features.capability_name, self._epsilon_initial,
            )
            self._capability_epsilon[features.capability_name] = max(
                self._epsilon_min, cap_eps * self._epsilon_decay,
            )
        return reward

    # -- Recommendation -----------------------------------------------------

    def recommend(
        self,
        capability_name: str,
        candidate_provider_ids: List[str],
    ) -> OptimizationResult:
        """Return the recommended provider for *capability_name*.

        Uses UCB1 for under-sampled providers and epsilon-greedy with
        per-capability epsilon for general exploration.
        """
        if not candidate_provider_ids:
            return OptimizationResult(reason="no candidates")

        with self._lock:
            cap_eps = self._capability_epsilon.get(
                capability_name, self._epsilon_initial,
            )
            cap_scores = self._scores.get(capability_name, {})

            # Check for under-sampled providers (UCB1 exploration)
            total_calls_all = sum(
                cap_scores.get(pid, ProviderScore()).total_calls
                for pid in candidate_provider_ids
            )

            if total_calls_all > 0:
                # UCB1 scoring
                best_id = candidate_provider_ids[0]
                best_ucb = -math.inf
                for pid in candidate_provider_ids:
                    ps = cap_scores.get(pid)
                    if not ps or ps.total_calls == 0:
                        # Never tried — explore immediately
                        return OptimizationResult(
                            recommended_provider_id=pid,
                            confidence=0.0,
                            exploration=True,
                            reason="UCB1: untried provider",
                        )
                    avg = ps.weighted_avg_reward
                    exploration_term = self._ucb_weight * math.sqrt(
                        math.log(total_calls_all) / ps.total_calls
                    )
                    ucb = avg + exploration_term
                    if ucb > best_ucb:
                        best_ucb = ucb
                        best_id = pid

                # Epsilon-greedy on top of UCB1
                if random.random() < cap_eps:
                    chosen = random.choice(candidate_provider_ids)
                    return OptimizationResult(
                        recommended_provider_id=chosen,
                        confidence=0.0,
                        exploration=True,
                        reason="epsilon-greedy exploration",
                    )

                confidence = max(0.0, min(1.0, best_ucb))
                return OptimizationResult(
                    recommended_provider_id=best_id,
                    confidence=confidence,
                    exploration=False,
                    reason="UCB1 exploitation",
                )
            else:
                # No data at all — pure exploration
                chosen = random.choice(candidate_provider_ids)
                return OptimizationResult(
                    recommended_provider_id=chosen,
                    confidence=0.0,
                    exploration=True,
                    reason="cold start exploration",
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
                    "weighted_avg_reward": ps.weighted_avg_reward,
                }
                for pid, ps in cap_scores.items()
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_observations": self._observations,
                "epsilon": self._capability_epsilon.copy(),
                "epsilon_initial": self._epsilon_initial,
                "capabilities_tracked": len(self._scores),
            }
