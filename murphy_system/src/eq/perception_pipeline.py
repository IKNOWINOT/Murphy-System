"""
Perception Pipeline — Screen-Scan → Inference → Action → Mind-Write Cycle

Implements the rapid perception-inference-action pipeline described in §6.1
and §11.3 of the Experimental EverQuest Modification Plan.

The pipeline operates on a ~250ms cycle:
  1. **Scan**: Read game state (nearby entities, buffs, HP/mana, zone, combat)
  2. **Infer**: Evaluate state against soul document and trigger templates
  3. **Decide**: Select the highest-priority action from macro-trigger engine
  4. **Write**: Write the decision back to the agent's mind (soul short-term memory)

This module provides the pipeline framework; the actual game-state reading
is delegated to the EQEmu game connector.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .macro_trigger_engine import MacroTriggerEngine, TriggerResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline Stage
# ---------------------------------------------------------------------------

class PipelineStage(Enum):
    """Pipeline stage (Enum subclass)."""
    SCAN = "scan"
    INFER = "infer"
    DECIDE = "decide"
    WRITE = "write"


# ---------------------------------------------------------------------------
# Game State Snapshot
# ---------------------------------------------------------------------------

@dataclass
class GameStateSnapshot:
    """A point-in-time capture of the agent's game environment."""

    agent_id: str
    timestamp: float = field(default_factory=time.time)

    # Character state
    hp_percent: float = 100.0
    mana_percent: float = 100.0
    combat_state: str = "idle"
    current_zone: str = ""
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})

    # Target
    has_target: bool = False
    target_id: str = ""
    target_name: str = ""
    target_level: int = 0
    target_hp_percent: float = 100.0

    # Group
    group_size: int = 0
    group_healer_alive: bool = True
    lowest_group_hp_percent: float = 100.0
    group_missing_buffs: int = 0

    # Nearby entities
    nearby_entities: List[Dict[str, Any]] = field(default_factory=list)

    # Active buffs
    active_buffs: List[str] = field(default_factory=list)

    # Levitation state (important for Tower of the Unmaker)
    has_levitation: bool = False

    def to_trigger_state(self) -> Dict[str, Any]:
        """Convert snapshot to the flat dict expected by MacroTriggerEngine."""
        return {
            "hp_percent": self.hp_percent,
            "mana_percent": self.mana_percent,
            "combat_state": self.combat_state,
            "has_target": self.has_target,
            "target_level": self.target_level,
            "group_healer_alive": self.group_healer_alive,
            "lowest_group_hp_percent": self.lowest_group_hp_percent,
            "group_missing_buffs": self.group_missing_buffs,
            "has_levitation": self.has_levitation,
        }


# ---------------------------------------------------------------------------
# Pipeline Decision
# ---------------------------------------------------------------------------

@dataclass
class PipelineDecision:
    """The output of a single pipeline cycle."""

    agent_id: str
    trigger_result: Optional[TriggerResult] = None
    stage_reached: PipelineStage = PipelineStage.SCAN
    cycle_time_ms: float = 0.0
    snapshot: Optional[GameStateSnapshot] = None


# ---------------------------------------------------------------------------
# Perception Pipeline
# ---------------------------------------------------------------------------

class PerceptionPipeline:
    """Rapid perception-inference-action-write cycle for a single agent.

    Each cycle reads the game state, evaluates triggers, selects an action,
    and writes the decision to the agent's soul short-term memory.
    """

    TARGET_CYCLE_MS = 250.0  # Target cycle time in milliseconds

    def __init__(
        self,
        agent_id: str,
        trigger_engine: MacroTriggerEngine,
        state_reader: Optional[Callable[[], GameStateSnapshot]] = None,
        mind_writer: Optional[Callable[[str, PipelineDecision], None]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.trigger_engine = trigger_engine
        self._state_reader = state_reader
        self._mind_writer = mind_writer
        self._cycle_count: int = 0
        self._last_decision: Optional[PipelineDecision] = None

    # --- Single cycle ---

    def run_cycle(self, snapshot: Optional[GameStateSnapshot] = None) -> PipelineDecision:
        """Execute one scan→infer→decide→write cycle.

        If no snapshot is provided, the pipeline uses the registered
        state_reader callback.  If neither is available, returns an
        empty decision.
        """
        start = time.time()
        self._cycle_count += 1

        # Stage 1: SCAN
        if snapshot is None and self._state_reader:
            snapshot = self._state_reader()
        if snapshot is None:
            return PipelineDecision(
                agent_id=self.agent_id,
                stage_reached=PipelineStage.SCAN,
            )

        # Stage 2: INFER — convert snapshot to trigger state
        trigger_state = snapshot.to_trigger_state()

        # Stage 3: DECIDE — evaluate triggers
        trigger_result = self.trigger_engine.evaluate(trigger_state)

        # Stage 4: WRITE — write decision to mind
        decision = PipelineDecision(
            agent_id=self.agent_id,
            trigger_result=trigger_result,
            stage_reached=PipelineStage.WRITE,
            cycle_time_ms=(time.time() - start) * 1000,
            snapshot=snapshot,
        )

        if self._mind_writer:
            self._mind_writer(self.agent_id, decision)

        self._last_decision = decision
        return decision

    # --- Queries ---

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_decision(self) -> Optional[PipelineDecision]:
        return self._last_decision
