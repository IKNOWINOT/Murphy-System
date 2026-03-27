"""
Luck System — High-Impact Luck Stat for MMORPG Games

Luck is a first-class stat with high implications for all in-game events.
Unlike hidden RNG, Luck is visible, exciting, and creates memorable moments.

Provides:
  - Luck score calculation and modification
  - Luck roll system for all game events
  - Luck-influenced outcomes table (critical hits, rare drops, crafting, exploration)
  - Lucky streak / unlucky streak mechanics
  - Visible luck events surfaced to players and streamers
"""

from __future__ import annotations

import logging
import math
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

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
# Enums
# ---------------------------------------------------------------------------

class LuckEventType(Enum):
    """Categories of events influenced by Luck."""

    CRITICAL_HIT = "critical_hit"
    RARE_DROP = "rare_drop"
    CRAFTING_QUALITY = "crafting_quality"
    SPELL_RESIST = "spell_resist"
    EXPLORATION_DISCOVERY = "exploration_discovery"
    NPC_INTERACTION = "npc_interaction"
    SYNERGY_TRIGGER = "synergy_trigger"
    DUNGEON_CHEST = "dungeon_chest"
    CRITICAL_FAIL = "critical_fail"


class LuckOutcome(Enum):
    """Result tier from a luck roll."""

    CATASTROPHIC = "catastrophic"   # <5  — worst-case failure
    UNLUCKY = "unlucky"             # 5–30
    NEUTRAL = "neutral"             # 31–69
    LUCKY = "lucky"                 # 70–94
    LEGENDARY = "legendary"         # 95–99
    DIVINE = "divine"               # 100 — once-in-a-lifetime moment


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class LuckRoll:
    """Result of a single luck roll."""

    roll_id: str
    character_id: str
    event_type: LuckEventType
    base_luck: int
    raw_roll: float          # 0–100
    adjusted_roll: float     # after luck stat modifier
    outcome: LuckOutcome
    streak_bonus: float      # extra modifier from current streak
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LuckProfile:
    """Per-character luck tracking."""

    character_id: str
    base_luck: int = 10          # 1–100 stat value
    current_streak: int = 0      # + = lucky streak, - = unlucky streak
    streak_peak: int = 0         # highest absolute streak
    lifetime_divine_rolls: int = 0
    lifetime_catastrophic_rolls: int = 0
    recent_rolls: List[LuckRoll] = field(default_factory=list)
    total_rolls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # Luck modifiers from items/buffs — stacks additively
    active_modifiers: Dict[str, int] = field(default_factory=dict)

    def effective_luck(self) -> int:
        """Total luck after all modifiers, capped at 100."""
        total = self.base_luck + sum(self.active_modifiers.values())
        return max(1, min(100, total))


@dataclass
class LuckEvent:
    """A notable luck moment surfaced to streaming/UI."""

    event_id: str
    character_id: str
    character_name: str
    event_type: LuckEventType
    outcome: LuckOutcome
    description: str
    timestamp: float = field(default_factory=time.time)
    is_broadcast_worthy: bool = False   # True for LEGENDARY/DIVINE/CATASTROPHIC


# ---------------------------------------------------------------------------
# Outcome configuration
# ---------------------------------------------------------------------------

# (min_adjusted_roll, outcome)
_OUTCOME_TABLE: List[Tuple[float, LuckOutcome]] = [
    (95.0, LuckOutcome.DIVINE),
    (80.0, LuckOutcome.LEGENDARY),
    (60.0, LuckOutcome.LUCKY),
    (30.0, LuckOutcome.NEUTRAL),
    (10.0, LuckOutcome.UNLUCKY),
    (0.0,  LuckOutcome.CATASTROPHIC),
]

# How much each streak level shifts the adjusted roll (linear, capped ±15)
_STREAK_PER_LEVEL = 1.5
_STREAK_CAP = 15.0

# Luck stat contribution: each point above 50 adds/subtracts from roll
_LUCK_ROLL_MODIFIER_PER_POINT = 0.3


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class LuckSystem:
    """
    Manages all luck-related calculations across MMORPG game instances.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_RECENT_ROLLS = 500
    _MAX_EVENTS = 1_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: Dict[str, LuckProfile] = {}
        self._notable_events: List[LuckEvent] = []

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------

    def get_or_create_profile(self, character_id: str, base_luck: int = 10) -> LuckProfile:
        """Return existing luck profile or create a new one."""
        with self._lock:
            if character_id not in self._profiles:
                self._profiles[character_id] = LuckProfile(
                    character_id=character_id,
                    base_luck=max(1, min(100, base_luck)),
                )
            return self._profiles[character_id]

    def set_base_luck(self, character_id: str, value: int) -> None:
        """Update base luck stat (1–100)."""
        profile = self.get_or_create_profile(character_id)
        with profile._lock:
            profile.base_luck = max(1, min(100, value))

    def add_luck_modifier(self, character_id: str, source: str, amount: int) -> None:
        """Apply a named luck modifier (from item, buff, etc.)."""
        profile = self.get_or_create_profile(character_id)
        with profile._lock:
            profile.active_modifiers[source] = amount

    def remove_luck_modifier(self, character_id: str, source: str) -> None:
        """Remove a named luck modifier."""
        profile = self.get_or_create_profile(character_id)
        with profile._lock:
            profile.active_modifiers.pop(source, None)

    # ------------------------------------------------------------------
    # Rolling
    # ------------------------------------------------------------------

    def roll(
        self,
        character_id: str,
        event_type: LuckEventType,
        context: Optional[Dict[str, Any]] = None,
    ) -> LuckRoll:
        """
        Perform a luck roll for a character on a given event type.

        The adjusted roll = raw_roll + luck_modifier + streak_bonus,
        clamped to [0, 100].
        """
        profile = self.get_or_create_profile(character_id)

        with profile._lock:
            effective = profile.effective_luck()
            raw = random.uniform(0.0, 100.0)

            # Luck modifier: each point above/below 50 shifts roll
            luck_mod = (effective - 50) * _LUCK_ROLL_MODIFIER_PER_POINT

            # Streak modifier
            streak_shift = min(
                abs(profile.current_streak) * _STREAK_PER_LEVEL, _STREAK_CAP
            )
            streak_bonus = math.copysign(streak_shift, profile.current_streak)

            adjusted = max(0.0, min(100.0, raw + luck_mod + streak_bonus))
            outcome = _determine_outcome(adjusted)

            # Update streak
            if outcome in (LuckOutcome.LUCKY, LuckOutcome.LEGENDARY, LuckOutcome.DIVINE):
                profile.current_streak = max(0, profile.current_streak) + 1
            elif outcome in (LuckOutcome.UNLUCKY, LuckOutcome.CATASTROPHIC):
                profile.current_streak = min(0, profile.current_streak) - 1
            else:
                # Neutral — decay streak toward zero
                if profile.current_streak > 0:
                    profile.current_streak -= 1
                elif profile.current_streak < 0:
                    profile.current_streak += 1

            if abs(profile.current_streak) > abs(profile.streak_peak):
                profile.streak_peak = profile.current_streak

            if outcome == LuckOutcome.DIVINE:
                profile.lifetime_divine_rolls += 1
            elif outcome == LuckOutcome.CATASTROPHIC:
                profile.lifetime_catastrophic_rolls += 1

            profile.total_rolls += 1

            roll_result = LuckRoll(
                roll_id=str(uuid.uuid4()),
                character_id=character_id,
                event_type=event_type,
                base_luck=effective,
                raw_roll=round(raw, 3),
                adjusted_roll=round(adjusted, 3),
                outcome=outcome,
                streak_bonus=round(streak_bonus, 3),
                context=context or {},
            )
            capped_append(profile.recent_rolls, roll_result, self._MAX_RECENT_ROLLS)

        self._maybe_emit_notable_event(roll_result, character_id)
        return roll_result

    # ------------------------------------------------------------------
    # Outcome helpers
    # ------------------------------------------------------------------

    def is_critical_hit(
        self, character_id: str, base_crit_chance: float = 0.05
    ) -> Tuple[bool, LuckRoll]:
        """Return (is_crit, roll) for a melee/spell critical hit check."""
        roll = self.roll(character_id, LuckEventType.CRITICAL_HIT)
        # Luck scales crit threshold linearly with luck stat
        profile = self.get_or_create_profile(character_id)
        with profile._lock:
            eff = profile.effective_luck()
        luck_boost = eff / 100.0 * 0.15  # up to +15% crit from luck
        threshold = (base_crit_chance + luck_boost) * 100
        return roll.adjusted_roll <= threshold, roll

    def rare_drop_multiplier(self, character_id: str) -> float:
        """
        Return a drop-rate multiplier based on a luck roll.

        DIVINE → 5x, LEGENDARY → 3x, LUCKY → 1.5x,
        NEUTRAL → 1x, UNLUCKY → 0.8x, CATASTROPHIC → 0.5x.
        """
        roll = self.roll(character_id, LuckEventType.RARE_DROP)
        _multipliers = {
            LuckOutcome.DIVINE: 5.0,
            LuckOutcome.LEGENDARY: 3.0,
            LuckOutcome.LUCKY: 1.5,
            LuckOutcome.NEUTRAL: 1.0,
            LuckOutcome.UNLUCKY: 0.8,
            LuckOutcome.CATASTROPHIC: 0.5,
        }
        return _multipliers[roll.outcome]

    def crafting_quality_bonus(self, character_id: str) -> int:
        """Return bonus quality levels (0–5) for a crafting attempt."""
        roll = self.roll(character_id, LuckEventType.CRAFTING_QUALITY)
        _bonuses = {
            LuckOutcome.DIVINE: 5,
            LuckOutcome.LEGENDARY: 3,
            LuckOutcome.LUCKY: 1,
            LuckOutcome.NEUTRAL: 0,
            LuckOutcome.UNLUCKY: 0,
            LuckOutcome.CATASTROPHIC: -1,  # quality reduction
        }
        return _bonuses[roll.outcome]

    def exploration_discovery_chance(self, character_id: str) -> bool:
        """Return True if a hidden area/secret is discovered."""
        roll = self.roll(character_id, LuckEventType.EXPLORATION_DISCOVERY)
        return roll.outcome in (
            LuckOutcome.LUCKY, LuckOutcome.LEGENDARY, LuckOutcome.DIVINE
        )

    # ------------------------------------------------------------------
    # Streaming / broadcast
    # ------------------------------------------------------------------

    def get_notable_events(
        self, since_timestamp: float = 0.0, broadcast_only: bool = False
    ) -> List[LuckEvent]:
        """Return notable luck events for streaming overlays."""
        with self._lock:
            events = [
                e for e in self._notable_events
                if e.timestamp >= since_timestamp
                and (not broadcast_only or e.is_broadcast_worthy)
            ]
        return events

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _maybe_emit_notable_event(
        self, roll: LuckRoll, character_id: str
    ) -> None:
        """Emit a LuckEvent for LEGENDARY/DIVINE/CATASTROPHIC rolls."""
        if roll.outcome not in (
            LuckOutcome.LEGENDARY, LuckOutcome.DIVINE, LuckOutcome.CATASTROPHIC
        ):
            return

        descriptions = {
            LuckOutcome.DIVINE: f"✨ DIVINE LUCK! A once-in-a-lifetime moment for {character_id}!",
            LuckOutcome.LEGENDARY: f"🌟 Legendary luck strikes {character_id}!",
            LuckOutcome.CATASTROPHIC: f"💀 Catastrophic luck failure for {character_id}...",
        }

        event = LuckEvent(
            event_id=str(uuid.uuid4()),
            character_id=character_id,
            character_name=character_id,
            event_type=roll.event_type,
            outcome=roll.outcome,
            description=descriptions[roll.outcome],
            is_broadcast_worthy=True,
        )
        with self._lock:
            capped_append(self._notable_events, event, self._MAX_EVENTS)
        logger.info("Luck event: %s", event.description)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _determine_outcome(adjusted_roll: float) -> LuckOutcome:
    """Map an adjusted roll (0–100) to a LuckOutcome."""
    for threshold, outcome in _OUTCOME_TABLE:
        if adjusted_roll >= threshold:
            return outcome
    return LuckOutcome.CATASTROPHIC
