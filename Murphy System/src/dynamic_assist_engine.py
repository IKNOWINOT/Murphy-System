"""
Dynamic Assist Engine — Knostalgia-Driven Assistance Mode
=========================================================
Replaces static autonomy tiers (shadow/suggest/copilot/autonomous) with
a continuous function where the agent's assistance behavior is computed
per-interaction from knostalgia metrics.

Every output is a parameter that triggers a method call somewhere in the
system. No labels. No dead constants.

Integrates with:
  - KnostalgiaEngine for memory statistics
  - HITLAutonomyController for autonomy evaluation
  - ExplorationAgent for exploration/exploitation balance
  - QLearningAgent for learning rate adjustment
"""

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DynamicAssistInput:
    """Input to the dynamic assist engine. Every field triggers a method somewhere.

    recall_confidence: from knostalgia recall (0.0-1.0).
        Triggers HITLAutonomyController.evaluate_autonomy confidence parameter.
    impact_weight: from knostalgia memory weight (0.0-1.0).
        Triggers RewardSignal.computed_reward scaling.
    k_factor: from KFactorCalculator (0.0-1.0).
        Triggers QLearningAgent learning_rate.
    risk_level: from governance boundary (0.0-1.0).
        Triggers HITLAutonomyController.evaluate_autonomy risk_level parameter.
    variation_frequency: how often the person deviates from observed pattern (0.0-1.0).
        Triggers ExplorationAgent.epsilon.
    novelty_rate: how often genuinely new situations arise (0.0-1.0).
        Triggers ExplorationStrategy selection.
    """
    recall_confidence: float
    impact_weight: float
    k_factor: float
    risk_level: float
    variation_frequency: float
    novelty_rate: float


@dataclass
class DynamicAssistOutput:
    """Output of the dynamic assist engine. Every field triggers a method call.

    observe_only: if True, agent only watches, no suggestions.
        Triggers ExplorationAgent.select_action with epsilon=1.0 (pure exploration).
    may_suggest: if True, agent may surface knostalgia recall prompts.
        Triggers _build_reflection_reply inclusion of recall prompts.
    may_execute: if True, agent may execute actions after HITL confirmation.
        Triggers HITLAutonomyController.evaluate_autonomy call.
    requires_approval: if True, every action needs HITL approval.
        Triggers HITL gate in firing pipeline.
    computed_epsilon: direct epsilon value for ExplorationAgent.
        Triggers ExplorationAgent constructor/setter.
    computed_learning_rate: direct lr value for QLearningAgent.
        Triggers QLearningAgent constructor/setter.
    computed_confidence_threshold: direct confidence threshold for HITLAutonomyController.
        Triggers AutonomyPolicy.confidence_threshold.
    """
    observe_only: bool
    may_suggest: bool
    may_execute: bool
    requires_approval: bool
    computed_epsilon: float
    computed_learning_rate: float
    computed_confidence_threshold: float


class DynamicAssistEngine:
    """Computes per-interaction assistance behavior from knostalgia metrics.

    Pure function engine: no configuration, no state. All behavior is computed
    from inputs. Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def evaluate(self, inp: DynamicAssistInput) -> DynamicAssistOutput:
        """Evaluate the dynamic assist mode for a single interaction.

        Pure function: same inputs always produce same outputs.

        Args:
            inp: DynamicAssistInput with knostalgia and governance metrics.

        Returns:
            DynamicAssistOutput with all method trigger parameters computed.
        """
        with self._lock:
            k_factor = inp.k_factor
            recall_confidence = inp.recall_confidence
            novelty_rate = inp.novelty_rate
            risk_level = inp.risk_level
            variation_frequency = inp.variation_frequency

            observe_only = (k_factor > 0.85) or (
                recall_confidence < 0.2 and novelty_rate > 0.7
            )

            may_suggest = (recall_confidence > 0.4) and (not observe_only)

            may_execute = (
                recall_confidence > 0.7
                and k_factor < 0.4
                and risk_level < 0.5
            )

            requires_approval = (
                risk_level > 0.3
                or k_factor > 0.5
                or (not may_execute)
            )

            computed_epsilon = min(1.0, variation_frequency + (novelty_rate * 0.3))
            computed_learning_rate = max(0.01, min(0.5, k_factor))
            computed_confidence_threshold = max(
                0.5, min(0.99, 1.0 - (recall_confidence * 0.4))
            )

            result = DynamicAssistOutput(
                observe_only=observe_only,
                may_suggest=may_suggest,
                may_execute=may_execute,
                requires_approval=requires_approval,
                computed_epsilon=computed_epsilon,
                computed_learning_rate=computed_learning_rate,
                computed_confidence_threshold=computed_confidence_threshold,
            )
            logger.debug(
                "DynamicAssistEngine.evaluate: k_factor=%.3f recall=%.3f "
                "observe_only=%s may_suggest=%s may_execute=%s",
                k_factor,
                recall_confidence,
                result.observe_only,
                result.may_suggest,
                result.may_execute,
            )
            return result
