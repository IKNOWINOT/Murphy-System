"""
Shadow-Knostalgia Bridge — Training as Memory Creation
======================================================
Bridges the ShadowLearningAgent observation system with the KnostalgiaEngine
memory system, ensuring:

1. Every shadow observation becomes a knostalgia memory
   (content=what happened, weight=pending until outcome measured)
2. Shadow Q&A uses knostalgia recall prompts
   ("When you do X, do you mean like...?")
3. Measured outcomes become impact weights via score_impact()
4. Impact weights feed into ExplorationLoop as rewards
5. K-factors computed from accumulated memories modulate all RL parameters

The bridge makes training and memory creation the same operation.
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from knostalgia_engine import KnostalgiaEngine
except ImportError:
    KnostalgiaEngine = None  # type: ignore[assignment,misc]

from dynamic_assist_engine import DynamicAssistEngine, DynamicAssistInput, DynamicAssistOutput
from kfactor_calculator import KFactorCalculator, KFactorResult

logger = logging.getLogger(__name__)


@dataclass
class ObservationMemory:
    """A single shadow observation with its linked knostalgia memory state."""
    observation_id: str
    shadow_agent_id: str
    process_name: str
    action_observed: str
    variation_from_norm: bool
    memory_id: Optional[str] = None
    outcome_measured: bool = False
    efficiency_delta: float = 0.0
    profit_delta: float = 0.0


class ShadowKnostalgiaBridge:
    """Bridges shadow agent observations with knostalgia memory.

    Training and memory creation are the same operation.
    Thread-safe via threading.Lock.
    """

    def __init__(
        self,
        knostalgia_engine: Any = None,
        kfactor_calculator: Optional[KFactorCalculator] = None,
        dynamic_assist_engine: Optional[DynamicAssistEngine] = None,
    ) -> None:
        """Initialize with the three new engines.

        Args:
            knostalgia_engine: KnostalgiaEngine instance (or None for graceful degradation).
            kfactor_calculator: KFactorCalculator instance (creates default if None).
            dynamic_assist_engine: DynamicAssistEngine instance (creates default if None).
        """
        self._knostalgia_engine = knostalgia_engine
        self._kfactor_calculator = kfactor_calculator or KFactorCalculator()
        self._dynamic_assist_engine = dynamic_assist_engine or DynamicAssistEngine()
        self._observations: Dict[str, ObservationMemory] = {}
        self._memories_by_agent_process: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Observation recording
    # ------------------------------------------------------------------

    def record_observation(
        self,
        shadow_agent_id: str,
        process_name: str,
        action_observed: str,
        variation_from_norm: bool,
    ) -> ObservationMemory:
        """Record a shadow observation and create a knostalgia memory.

        The observation is stored with a pending weight (0.0) until the
        outcome is measured via record_outcome().

        Args:
            shadow_agent_id: ID of the shadow agent making the observation.
            process_name: name of the process being observed.
            action_observed: description of what the person did.
            variation_from_norm: whether the action deviated from expected pattern.

        Returns:
            ObservationMemory with observation_id and pending memory_id.
        """
        observation_id = uuid.uuid4().hex[:16]
        memory_id: Optional[str] = None

        # Create knostalgia memory with pending weight
        if self._knostalgia_engine is not None:
            try:
                content = f"[{process_name}] {action_observed}"
                memory_id = self._knostalgia_engine.store(
                    content=content,
                    weight=0.0,  # pending until outcome measured
                    metadata={
                        "shadow_agent_id": shadow_agent_id,
                        "process_name": process_name,
                        "variation_from_norm": variation_from_norm,
                        "observation_id": observation_id,
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Could not store knostalgia memory for observation %s: %s",
                    observation_id,
                    exc,
                )
        else:
            # Graceful degradation: generate a synthetic memory_id
            memory_id = f"mem-{observation_id}"

        obs = ObservationMemory(
            observation_id=observation_id,
            shadow_agent_id=shadow_agent_id,
            process_name=process_name,
            action_observed=action_observed,
            variation_from_norm=variation_from_norm,
            memory_id=memory_id,
            outcome_measured=False,
            efficiency_delta=0.0,
            profit_delta=0.0,
        )

        with self._lock:
            self._observations[observation_id] = obs
            key = f"{shadow_agent_id}:{process_name}"
            if key not in self._memories_by_agent_process:
                self._memories_by_agent_process[key] = []
            self._memories_by_agent_process[key].append({
                "observation_id": observation_id,
                "memory_id": memory_id,
                "was_variation": variation_from_norm,
                "had_recall": False,  # updated when recall fires
                "weight": 0.0,
                "outcome": None,
            })

        logger.debug(
            "record_observation: agent=%s process=%s obs_id=%s memory_id=%s",
            shadow_agent_id,
            process_name,
            observation_id,
            memory_id,
        )
        return obs

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self, observation_id: str, efficiency_delta: float, profit_delta: float
    ) -> float:
        """Record the measured outcome for an observation.

        Calls knostalgia_engine.score_impact() to update the memory weight.
        Returns the computed reward for the RL loop.

        Args:
            observation_id: ID from record_observation.
            efficiency_delta: measured efficiency impact.
            profit_delta: measured profit impact.

        Returns:
            Computed reward value for the RL ExplorationLoop.
        """
        with self._lock:
            obs = self._observations.get(observation_id)
            if obs is None:
                logger.warning(
                    "record_outcome: unknown observation_id=%s", observation_id
                )
                return 0.0

            obs.efficiency_delta = efficiency_delta
            obs.profit_delta = profit_delta
            obs.outcome_measured = True

            # Compute reward: normalized combination of efficiency and profit deltas
            reward = max(0.0, min(1.0, (efficiency_delta + profit_delta) / 2.0))

            # Update knostalgia memory weight via score_impact if available
            if self._knostalgia_engine is not None and obs.memory_id is not None:
                try:
                    self._knostalgia_engine.score_impact(
                        memory_id=obs.memory_id,
                        efficiency_delta=efficiency_delta,
                        profit_delta=profit_delta,
                    )
                except Exception as exc:
                    logger.warning(
                        "score_impact failed for memory %s: %s", obs.memory_id, exc
                    )

            # Update local memory record
            key = f"{obs.shadow_agent_id}:{obs.process_name}"
            for mem_record in self._memories_by_agent_process.get(key, []):
                if mem_record["observation_id"] == observation_id:
                    mem_record["weight"] = reward
                    mem_record["outcome"] = (efficiency_delta + profit_delta) / 2.0
                    break

        logger.debug(
            "record_outcome: obs_id=%s efficiency=%.3f profit=%.3f reward=%.3f",
            observation_id,
            efficiency_delta,
            profit_delta,
            reward,
        )
        return reward

    # ------------------------------------------------------------------
    # Process question generation
    # ------------------------------------------------------------------

    def generate_process_question(
        self, shadow_agent_id: str, process_name: str
    ) -> Optional[str]:
        """Generate a recall-based question for the shadow agent.

        Uses knostalgia recall to generate: "When you do [process], do you mean like [recalled pattern]?"

        Args:
            shadow_agent_id: ID of the shadow agent.
            process_name: name of the process to ask about.

        Returns:
            A question string, or None if no recall is available.
        """
        if self._knostalgia_engine is None:
            return f"When you do {process_name}, can you describe what that looks like?"

        try:
            recall_result = self._knostalgia_engine.recall(
                query=process_name,
                context={"shadow_agent_id": shadow_agent_id},
            )
            recalled_content = None
            if recall_result and hasattr(recall_result, "content"):
                recalled_content = recall_result.content
            elif isinstance(recall_result, dict) and recall_result.get("content"):
                recalled_content = recall_result["content"]
            elif isinstance(recall_result, str) and recall_result:
                recalled_content = recall_result

            if recalled_content:
                return f"When you do {process_name}, do you mean like: {recalled_content}?"
        except Exception as exc:
            logger.warning(
                "generate_process_question recall failed for %s: %s", process_name, exc
            )

        return f"When you do {process_name}, can you describe what that looks like?"

    # ------------------------------------------------------------------
    # Question answer handling
    # ------------------------------------------------------------------

    def on_question_answered(
        self, observation_id: str, answer_text: str, confirmed: bool
    ) -> None:
        """Handle the person's answer to a process question.

        If confirmed: calls on_recall_confirmed() on the knostalgia engine.
        If rejected: calls on_recall_rejected() on the knostalgia engine.
        Creates a new memory from the answer.

        Args:
            observation_id: ID of the originating observation.
            answer_text: the person's answer text.
            confirmed: True if they confirmed the recalled pattern.
        """
        with self._lock:
            obs = self._observations.get(observation_id)

        if obs is None:
            logger.warning(
                "on_question_answered: unknown observation_id=%s", observation_id
            )
            return

        if self._knostalgia_engine is not None and obs.memory_id is not None:
            try:
                if confirmed:
                    self._knostalgia_engine.on_recall_confirmed(obs.memory_id)
                else:
                    self._knostalgia_engine.on_recall_rejected(obs.memory_id)
            except Exception as exc:
                logger.warning(
                    "on_question_answered knostalgia callback failed: %s", exc
                )

        # Create a new memory from the answer
        self.record_observation(
            shadow_agent_id=obs.shadow_agent_id,
            process_name=obs.process_name,
            action_observed=f"[answer] {answer_text}",
            variation_from_norm=not confirmed,
        )

        # Mark had_recall in the memory record
        with self._lock:
            key = f"{obs.shadow_agent_id}:{obs.process_name}"
            for mem_record in self._memories_by_agent_process.get(key, []):
                if mem_record["observation_id"] == observation_id:
                    mem_record["had_recall"] = True
                    break

        logger.debug(
            "on_question_answered: obs_id=%s confirmed=%s answer=%s",
            observation_id,
            confirmed,
            answer_text[:50] if answer_text else "",
        )

    # ------------------------------------------------------------------
    # K-factor computation
    # ------------------------------------------------------------------

    def compute_process_k_factor(
        self, shadow_agent_id: str, process_name: str
    ) -> KFactorResult:
        """Compute the k-factor for a specific shadow agent + process pair.

        Aggregates all knostalgia memories and calls kfactor_calculator.compute_from_memories().

        Args:
            shadow_agent_id: ID of the shadow agent.
            process_name: name of the process.

        Returns:
            KFactorResult with k_factor and derived parameters.
        """
        with self._lock:
            key = f"{shadow_agent_id}:{process_name}"
            memories = list(self._memories_by_agent_process.get(key, []))

        return self._kfactor_calculator.compute_from_memories(memories)

    # ------------------------------------------------------------------
    # Dynamic assist mode
    # ------------------------------------------------------------------

    def compute_assist_mode(
        self, shadow_agent_id: str, process_name: str, risk_level: float
    ) -> DynamicAssistOutput:
        """Compute the dynamic assist mode for a shadow agent + process pair.

        Uses knostalgia stats → k_factor → dynamic_assist_engine.evaluate().

        Args:
            shadow_agent_id: ID of the shadow agent.
            process_name: name of the process.
            risk_level: governance risk level (0.0-1.0).

        Returns:
            DynamicAssistOutput with all method trigger parameters computed.
        """
        k_result = self.compute_process_k_factor(shadow_agent_id, process_name)

        with self._lock:
            key = f"{shadow_agent_id}:{process_name}"
            memories = list(self._memories_by_agent_process.get(key, []))

        # Compute recall confidence and impact weight from memories
        if memories:
            weights = [m.get("weight", 0.0) for m in memories]
            had_recall = [m.get("had_recall", False) for m in memories]
            variation = [m.get("was_variation", False) for m in memories]

            recall_confidence = sum(1 for r in had_recall if r) / (len(memories) or 1)
            impact_weight = sum(weights) / (len(memories) or 1)
            variation_frequency = sum(1 for v in variation if v) / (len(memories) or 1)
            no_recall_count = sum(1 for r in had_recall if not r)
            novelty_rate = no_recall_count / (len(memories) or 1)
        else:
            recall_confidence = 0.0
            impact_weight = 0.0
            variation_frequency = 0.5
            novelty_rate = 1.0

        inp = DynamicAssistInput(
            recall_confidence=recall_confidence,
            impact_weight=impact_weight,
            k_factor=k_result.k_factor,
            risk_level=risk_level,
            variation_frequency=variation_frequency,
            novelty_rate=novelty_rate,
        )
        return self._dynamic_assist_engine.evaluate(inp)

    # ------------------------------------------------------------------
    # RL reward retrieval
    # ------------------------------------------------------------------

    def get_reward_for_rl(self, observation_id: str) -> float:
        """Return the knostalgia impact weight as the reward for the ExplorationLoop.

        This IS where training and memory become the same thing.

        Args:
            observation_id: ID from record_observation.

        Returns:
            Impact weight (reward) for the RL system.
        """
        with self._lock:
            obs = self._observations.get(observation_id)
            if obs is None:
                return 0.0

            key = f"{obs.shadow_agent_id}:{obs.process_name}"
            for mem_record in self._memories_by_agent_process.get(key, []):
                if mem_record["observation_id"] == observation_id:
                    return float(mem_record.get("weight", 0.0))

        return 0.0
