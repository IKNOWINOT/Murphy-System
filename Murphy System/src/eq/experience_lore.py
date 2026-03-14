"""
Experience-Based Lore Engine — Action Logging, Recall, and Collective Propagation

Implements the experience-based lore system described in §10 and §11.3 of
the Experimental EverQuest Modification Plan.

Provides:
  - Action screenshot capture → memory processing → delete cycle
  - Interaction-triggered recall (history surfaces when re-encountering entities)
  - Collective lore propagation (agents share knowledge through social communication)
  - Lore fidelity degradation (information distorts with each retelling)
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIDELITY_MAX = 1.0
FIDELITY_MIN = 0.5  # Floor — information never degrades below 50% accuracy
FIDELITY_DECAY_PER_RETELLING = 0.05  # 5% fidelity loss per retelling
FIRST_HAND_FIDELITY = 1.0  # First-hand memories are always 100% accurate


# ---------------------------------------------------------------------------
# Experience Record
# ---------------------------------------------------------------------------

@dataclass
class ExperienceRecord:
    """A single experience captured from an agent's gameplay."""

    experience_id: str
    agent_id: str
    experience_type: str  # "combat", "trade", "conversation", "discovery", "death"
    zone: str = ""
    involved_entities: List[str] = field(default_factory=list)
    description: str = ""
    fidelity: float = FIRST_HAND_FIDELITY  # Accuracy of the memory
    timestamp: float = field(default_factory=time.time)
    source_agent_id: str = ""  # Empty = first-hand; set = received from another agent
    retelling_count: int = 0  # How many times this has been retold


# ---------------------------------------------------------------------------
# Recall Trigger
# ---------------------------------------------------------------------------

@dataclass
class RecallTrigger:
    """A trigger that surfaces memories when re-encountering known entities."""

    entity_id: str
    recalled_experiences: List[ExperienceRecord] = field(default_factory=list)
    trigger_timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Lore Propagation Result
# ---------------------------------------------------------------------------

@dataclass
class LorePropagationResult:
    """Result of propagating lore from one agent to another."""

    source_agent_id: str
    target_agent_id: str
    experiences_shared: int
    fidelity_after: float


# ---------------------------------------------------------------------------
# Experience Lore Engine
# ---------------------------------------------------------------------------

class ExperienceLoreEngine:
    """Manages the experience-based lore cycle for all agents.

    The cycle:
      1. **Capture**: Agent performs action → experience recorded
      2. **Process**: Experience stored in agent's memory archive
      3. **Recall**: On re-encountering entity → relevant experiences surface
      4. **Propagate**: Agent shares knowledge with others (faction/social)
      5. **Degrade**: Each retelling loses fidelity toward the 50% floor
    """

    def __init__(self) -> None:
        # agent_id → list of experiences
        self._experiences: Dict[str, List[ExperienceRecord]] = {}
        self._propagation_log: List[LorePropagationResult] = []
        self._experience_counter: int = 0

    # --- Capture (Step 1) ---

    def capture_experience(
        self,
        agent_id: str,
        experience_type: str,
        zone: str = "",
        involved_entities: Optional[List[str]] = None,
        description: str = "",
    ) -> ExperienceRecord:
        """Record a new first-hand experience for an agent."""
        self._experience_counter += 1
        record = ExperienceRecord(
            experience_id=f"exp_{self._experience_counter}",
            agent_id=agent_id,
            experience_type=experience_type,
            zone=zone,
            involved_entities=involved_entities or [],
            description=description,
            fidelity=FIRST_HAND_FIDELITY,
            source_agent_id="",  # First-hand
        )
        self._experiences.setdefault(agent_id, []).append(record)
        return record

    # --- Recall (Step 3) ---

    def recall_by_entity(self, agent_id: str, entity_id: str) -> RecallTrigger:
        """Retrieve all experiences involving a specific entity.

        This is the interaction-triggered recall: when an agent
        re-encounters an entity, all relevant memories surface.
        """
        agent_experiences = self._experiences.get(agent_id, [])
        relevant = [
            exp for exp in agent_experiences
            if entity_id in exp.involved_entities
        ]
        return RecallTrigger(
            entity_id=entity_id,
            recalled_experiences=relevant,
        )

    def recall_by_zone(self, agent_id: str, zone: str) -> List[ExperienceRecord]:
        """Retrieve all experiences that occurred in a specific zone."""
        return [
            exp for exp in self._experiences.get(agent_id, [])
            if exp.zone == zone
        ]

    def recall_by_type(self, agent_id: str, exp_type: str) -> List[ExperienceRecord]:
        """Retrieve all experiences of a specific type."""
        return [
            exp for exp in self._experiences.get(agent_id, [])
            if exp.experience_type == exp_type
        ]

    # --- Propagation (Step 4) ---

    def propagate_lore(
        self,
        source_agent_id: str,
        target_agent_id: str,
        experience_types: Optional[Set[str]] = None,
    ) -> LorePropagationResult:
        """Share lore from source agent to target agent.

        Each shared experience loses fidelity in the retelling.
        Target receives copies with degraded fidelity.
        """
        source_experiences = self._experiences.get(source_agent_id, [])

        # Filter by type if specified
        to_share = source_experiences
        if experience_types:
            to_share = [e for e in to_share if e.experience_type in experience_types]

        shared_count = 0
        min_fidelity = FIDELITY_MAX

        for exp in to_share:
            # Degrade fidelity for the retelling
            new_fidelity = max(
                FIDELITY_MIN,
                exp.fidelity - FIDELITY_DECAY_PER_RETELLING,
            )

            # Create a copy for the target
            self._experience_counter += 1
            retold = ExperienceRecord(
                experience_id=f"exp_{self._experience_counter}",
                agent_id=target_agent_id,
                experience_type=exp.experience_type,
                zone=exp.zone,
                involved_entities=list(exp.involved_entities),
                description=exp.description,
                fidelity=new_fidelity,
                source_agent_id=source_agent_id,
                retelling_count=exp.retelling_count + 1,
            )
            self._experiences.setdefault(target_agent_id, []).append(retold)
            shared_count += 1
            min_fidelity = min(min_fidelity, new_fidelity)

        result = LorePropagationResult(
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            experiences_shared=shared_count,
            fidelity_after=min_fidelity if shared_count > 0 else FIDELITY_MAX,
        )
        capped_append(self._propagation_log, result)
        return result

    # --- Queries ---

    def get_agent_experience_count(self, agent_id: str) -> int:
        return len(self._experiences.get(agent_id, []))

    def get_first_hand_experiences(self, agent_id: str) -> List[ExperienceRecord]:
        """Return only first-hand (not retold) experiences."""
        return [
            exp for exp in self._experiences.get(agent_id, [])
            if not exp.source_agent_id
        ]

    def get_retold_experiences(self, agent_id: str) -> List[ExperienceRecord]:
        """Return only retold (received from others) experiences."""
        return [
            exp for exp in self._experiences.get(agent_id, [])
            if exp.source_agent_id
        ]

    @property
    def total_experience_count(self) -> int:
        return sum(len(exps) for exps in self._experiences.values())

    @property
    def propagation_count(self) -> int:
        return len(self._propagation_log)
