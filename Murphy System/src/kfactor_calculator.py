"""
K-Factor Calculator — Position Learning Rate from Knostalgia Statistics
=======================================================================
Computes the per-process learning rate (k-factor) for a shadow agent position.
Each component of the k-factor directly modulates a specific method parameter:

  recall_confidence    → QLearningAgent.lr (lower confidence = higher lr = learn faster)
  impact_weight        → RewardSignal.computed_reward (scales reward magnitude)
  variation_frequency  → ExplorationAgent.epsilon (more variation = more exploration)
  outcome_consistency  → HITLAutonomyController.confidence_threshold (consistent = lower bar)
  novelty_rate         → ExplorationStrategy selection (high novelty = Thompson sampling)

The k-factor IS the learning rate. High k = still learning. Low k = learned.
"""

import logging
import statistics
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class KFactorInput:
    """Input to the k-factor calculator. Every field triggers a method somewhere.

    recall_confidence: average confidence of knostalgia recalls for this process (0-1).
        Triggers QLearningAgent.lr.
    impact_weight: average impact weight of memories for this process (0-1).
        Triggers RewardSignal.computed_reward scaling.
    variation_frequency: ratio of deviations to total observations (0-1).
        Triggers ExplorationAgent.epsilon.
    outcome_consistency: standard deviation of outcomes normalized to 0-1, inverted
        (1.0 = perfectly consistent). Triggers HITLAutonomyController.confidence_threshold.
    novelty_rate: ratio of no-recall inputs to total inputs (0-1).
        Triggers ExplorationStrategy selection.
    """
    recall_confidence: float
    impact_weight: float
    variation_frequency: float
    outcome_consistency: float
    novelty_rate: float


@dataclass
class KFactorResult:
    """Result of the k-factor computation.

    k_factor: the composite learning rate (0-1).
    components: breakdown of each component's contribution.
    recommended_strategy: exploration strategy name.
    recommended_epsilon: direct value for ExplorationAgent.
    recommended_lr: direct value for QLearningAgent.
    """
    k_factor: float
    components: Dict[str, float]
    recommended_strategy: str
    recommended_epsilon: float
    recommended_lr: float


class KFactorCalculator:
    """Computes per-process k-factor from knostalgia memory statistics.

    Thread-safe. All alpha weights are used in compute(); no dead values.
    """

    def __init__(
        self,
        alpha_recall: float = 0.25,
        alpha_impact: float = 0.20,
        alpha_variation: float = 0.25,
        alpha_consistency: float = 0.15,
        alpha_novelty: float = 0.15,
    ) -> None:
        """Initialize with component weights.

        Each weight is used in compute(). No dead values.
        """
        self.alpha_recall = alpha_recall
        self.alpha_impact = alpha_impact
        self.alpha_variation = alpha_variation
        self.alpha_consistency = alpha_consistency
        self.alpha_novelty = alpha_novelty
        self._lock = threading.Lock()

    def compute(self, inp: KFactorInput) -> KFactorResult:
        """Compute k-factor from input metrics.

        Pure function: same inputs always produce same outputs.

        k_factor = α_recall * (1 - recall_confidence)
                 + α_impact * (1 - impact_weight)
                 + α_variation * variation_frequency
                 + α_consistency * (1 - outcome_consistency)
                 + α_novelty * novelty_rate

        Args:
            inp: KFactorInput with knostalgia statistics.

        Returns:
            KFactorResult with k_factor and all derived parameters.
        """
        with self._lock:
            c_recall = self.alpha_recall * (1.0 - inp.recall_confidence)
            c_impact = self.alpha_impact * (1.0 - inp.impact_weight)
            c_variation = self.alpha_variation * inp.variation_frequency
            c_consistency = self.alpha_consistency * (1.0 - inp.outcome_consistency)
            c_novelty = self.alpha_novelty * inp.novelty_rate

            k_factor = c_recall + c_impact + c_variation + c_consistency + c_novelty
            k_factor = max(0.0, min(1.0, k_factor))

            components = {
                "recall": c_recall,
                "impact": c_impact,
                "variation": c_variation,
                "consistency": c_consistency,
                "novelty": c_novelty,
            }

            if inp.novelty_rate > 0.6:
                recommended_strategy = "thompson_sampling"
            elif inp.novelty_rate > 0.3:
                recommended_strategy = "ucb"
            else:
                recommended_strategy = "epsilon_greedy"

            recommended_epsilon = min(
                1.0, inp.variation_frequency + inp.novelty_rate * 0.3
            )
            recommended_lr = max(0.01, min(0.5, k_factor))

            result = KFactorResult(
                k_factor=k_factor,
                components=components,
                recommended_strategy=recommended_strategy,
                recommended_epsilon=recommended_epsilon,
                recommended_lr=recommended_lr,
            )
            logger.debug(
                "KFactorCalculator.compute: k_factor=%.4f strategy=%s",
                k_factor,
                recommended_strategy,
            )
            return result

    def compute_from_memories(self, memories: List[Dict[str, Any]]) -> KFactorResult:
        """Convenience method: compute k-factor from a list of knostalgia memory dicts.

        Expected memory dict keys (all optional, defaults to 0):
          - recall_count: int (number of times recalled)
          - weight: float (impact weight 0-1)
          - outcome: float (outcome value)
          - was_variation: bool (was this a deviation?)
          - had_recall: bool (was there a recall match?)

        Args:
            memories: list of knostalgia memory dicts.

        Returns:
            KFactorResult computed from aggregated statistics.
        """
        with self._lock:
            if not memories:
                inp = KFactorInput(
                    recall_confidence=0.0,
                    impact_weight=0.0,
                    variation_frequency=0.0,
                    outcome_consistency=1.0,
                    novelty_rate=1.0,
                )
            else:
                total = len(memories)

                recall_confidences = []
                for m in memories:
                    rc = m.get("recall_confidence", None)
                    if rc is None:
                        rc_count = m.get("recall_count", 0)
                        rc = min(1.0, rc_count / 5.0) if rc_count else 0.0
                    recall_confidences.append(float(rc))

                weights = [float(m.get("weight", 0.0)) for m in memories]
                variation_count = sum(
                    1 for m in memories if m.get("was_variation", False)
                )
                no_recall_count = sum(
                    1 for m in memories if not m.get("had_recall", False)
                )
                outcomes = [
                    float(m.get("outcome", 0.0))
                    for m in memories
                    if m.get("outcome") is not None
                ]

                avg_recall = sum(recall_confidences) / total
                avg_weight = sum(weights) / total
                variation_freq = variation_count / total
                novelty = no_recall_count / total

                if len(outcomes) > 1:
                    outcome_std = statistics.pstdev(outcomes)
                    max_range = max(outcomes) - min(outcomes) if outcomes else 1.0
                    if max_range > 0:
                        consistency = max(0.0, 1.0 - (outcome_std / max_range))
                    else:
                        consistency = 1.0
                else:
                    consistency = 1.0

                inp = KFactorInput(
                    recall_confidence=avg_recall,
                    impact_weight=avg_weight,
                    variation_frequency=variation_freq,
                    outcome_consistency=consistency,
                    novelty_rate=novelty,
                )

        return self.compute(inp)
