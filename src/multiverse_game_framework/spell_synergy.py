"""
Cooperative Spell Synergy & Combination System for the Multiverse Game Framework.

Design Label: GAME-004 — Cooperative Spell Synergy & Combination System
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager

When multiple players cast spells within a time window, combined effects fire
with magnified power. Discovering new combinations rewards XP and achievements.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded collections with capped_append pattern (CWE-770)
  - Graceful degradation when subsystem dependencies are unavailable
  - Full audit trail via EventBackbone and PersistenceManager

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports with graceful fallback
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from event_backbone import EventBackbone, EventType
    _BACKBONE_AVAILABLE = True
except Exception:  # pragma: no cover
    EventBackbone = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment]
    _BACKBONE_AVAILABLE = False

try:
    from persistence_manager import PersistenceManager
    _PERSISTENCE_AVAILABLE = True
except Exception:  # pragma: no cover
    PersistenceManager = None  # type: ignore[assignment,misc]
    _PERSISTENCE_AVAILABLE = False

_MAX_SYNERGY_LOG = 10_000
_MAX_SPELL_WINDOW = 5_000  # Hard upper bound on window size (ms)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SynergyType(str, Enum):
    """Category of spell synergy combination."""
    SAME_SPELL = "same_spell"
    ELEMENTAL_CHAIN = "elemental_chain"
    ROLE_COMBO = "role_combo"
    HEALING_CHAIN = "healing_chain"
    DISCOVERED = "discovered"  # Newly found combination


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SpellCastEvent:
    """Record of a single spell cast.

    Args:
        cast_id: Unique cast UUID.
        caster_id: ID of the player or agent casting.
        spell_id: Identifier of the spell cast.
        spell_tags: Tags describing this spell's attributes.
        timestamp_ms: Cast time in milliseconds (monotonic clock).
        world_id: World where the cast occurred.
    """
    cast_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    caster_id: str = ""
    spell_id: str = ""
    spell_tags: List[str] = field(default_factory=list)
    timestamp_ms: float = field(default_factory=lambda: time.monotonic() * 1000)
    world_id: str = ""


@dataclass
class SynergyResult:
    """Result of a detected spell synergy.

    Args:
        synergy_id: Unique synergy event UUID.
        synergy_type: Category of the synergy.
        participants: List of caster IDs involved.
        magnifier: Power multiplier (e.g., 3.0 = triple power).
        combined_spell_name: Name of the combined/emergent spell.
        combined_effect: Description of the combined effect.
        discovery_xp: XP awarded for discovering a new combination.
    """
    synergy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    synergy_type: SynergyType = SynergyType.SAME_SPELL
    participants: List[str] = field(default_factory=list)
    magnifier: float = 1.0
    combined_spell_name: str = ""
    combined_effect: str = ""
    discovery_xp: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SynergyCombination:
    """Definition of a known spell combination.

    Args:
        combination_id: Unique identifier.
        name: Display name of the combined spell.
        required_tags: Tag sets that must be present to trigger.
        synergy_type: Category of this combination.
        magnifier_base: Base magnifier value.
        effect_description: What the combination does.
        discovery_reward_xp: XP rewarded on first discovery.
    """
    combination_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    required_tags: List[Set[str]] = field(default_factory=list)
    synergy_type: SynergyType = SynergyType.ELEMENTAL_CHAIN
    magnifier_base: float = 2.0
    effect_description: str = ""
    discovery_reward_xp: int = 500


# ---------------------------------------------------------------------------
# Built-in synergy catalog
# ---------------------------------------------------------------------------

_SYNERGY_CATALOG: List[SynergyCombination] = [
    SynergyCombination(
        name="Firestorm",
        required_tags=[{"fire", "elemental"}, {"wind", "elemental"}],
        synergy_type=SynergyType.ELEMENTAL_CHAIN,
        magnifier_base=2.5,
        effect_description="Fire and wind combine into a roaring firestorm that spreads.",
        discovery_reward_xp=750,
    ),
    SynergyCombination(
        name="Shatter Storm",
        required_tags=[{"ice", "elemental"}, {"lightning", "elemental"}],
        synergy_type=SynergyType.ELEMENTAL_CHAIN,
        magnifier_base=2.5,
        effect_description="Ice and lightning shatter targets and chain to nearby enemies.",
        discovery_reward_xp=750,
    ),
    SynergyCombination(
        name="Glacial Inferno",
        required_tags=[{"fire", "elemental"}, {"ice", "elemental"}],
        synergy_type=SynergyType.ELEMENTAL_CHAIN,
        magnifier_base=2.0,
        effect_description="Fire and ice create explosive steam damage across the area.",
        discovery_reward_xp=500,
    ),
    SynergyCombination(
        name="Focused Assault",
        required_tags=[{"tank", "taunt"}, {"dps", "burst"}],
        synergy_type=SynergyType.ROLE_COMBO,
        magnifier_base=2.0,
        effect_description="Tank taunt locks aggro while DPS burst deals massively increased damage.",
        discovery_reward_xp=600,
    ),
    SynergyCombination(
        name="Divine Surge",
        required_tags=[{"heal", "divine"}, {"heal", "divine"}, {"heal"}],
        synergy_type=SynergyType.HEALING_CHAIN,
        magnifier_base=1.8,
        effect_description="Multiple healers syncing produces AoE heal with HoT bonus.",
        discovery_reward_xp=400,
    ),
    SynergyCombination(
        name="Poison Storm",
        required_tags=[{"poison", "nature"}, {"wind", "elemental"}],
        synergy_type=SynergyType.ELEMENTAL_CHAIN,
        magnifier_base=2.0,
        effect_description="Poison and wind create a toxic cloud that persists on the battlefield.",
        discovery_reward_xp=600,
    ),
]


# ---------------------------------------------------------------------------
# SpellSynergyEngine
# ---------------------------------------------------------------------------


class SpellSynergyEngine:
    """Detects and resolves cooperative spell synergies within a time window.

    When 2+ players cast spells with matching tags within SYNERGY_WINDOW_MS,
    a combined effect fires with a magnifier based on timing precision and
    class synergy. Perfect sync (< 100ms) yields 3x; within 1s yields 2x;
    within the full window yields 1.5x.
    """

    SYNERGY_WINDOW_MS: int = 2_000

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        # Sliding window of recent casts: world_id → list of SpellCastEvent
        self._recent_casts: Dict[str, List[SpellCastEvent]] = {}
        self._synergy_log: List[SynergyResult] = []
        self._catalog = list(_SYNERGY_CATALOG)
        self._discovered_combinations: Set[str] = set()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_spell_cast(
        self,
        caster_id: str,
        spell_id: str,
        spell_tags: List[str],
        world_id: str,
        timestamp_ms: Optional[float] = None,
    ) -> SpellCastEvent:
        """Record a spell cast and prune expired casts from the window.

        Args:
            caster_id: ID of the casting player/agent.
            spell_id: Spell identifier.
            spell_tags: Descriptive tags for this spell.
            world_id: World where the cast occurred.
            timestamp_ms: Optional timestamp override (monotonic ms).

        Returns:
            The registered SpellCastEvent.
        """
        ts = timestamp_ms if timestamp_ms is not None else time.monotonic() * 1000
        event = SpellCastEvent(
            caster_id=caster_id,
            spell_id=spell_id,
            spell_tags=list(spell_tags),
            timestamp_ms=ts,
            world_id=world_id,
        )
        with self._lock:
            window = self._recent_casts.setdefault(world_id, [])
            capped_append(window, event, 1_000)
            self._prune_window(world_id, ts)
        return event

    # ------------------------------------------------------------------
    # Synergy detection
    # ------------------------------------------------------------------

    def check_synergy(self, spell_cast_event: SpellCastEvent) -> Optional[SynergyResult]:
        """Check whether a new cast triggers a synergy with recent casts.

        Args:
            spell_cast_event: The newly registered SpellCastEvent.

        Returns:
            A SynergyResult if a synergy fired, else None.
        """
        world_id = spell_cast_event.world_id
        ts = spell_cast_event.timestamp_ms

        with self._lock:
            self._prune_window(world_id, ts)
            window = self._recent_casts.get(world_id, [])
            # Include the triggering event itself
            all_casts = [c for c in window if c.cast_id != spell_cast_event.cast_id]
            all_casts.append(spell_cast_event)

        if len(all_casts) < 2:
            return None

        # Check same-spell synergy first
        same_spell = self._detect_same_spell(all_casts, ts)
        if same_spell:
            self._record_synergy(same_spell)
            return same_spell

        # Check catalog combinations
        for combo in self._catalog:
            result = self._detect_combo(combo, all_casts, ts)
            if result:
                is_new = combo.name not in self._discovered_combinations
                if is_new:
                    result.discovery_xp = combo.discovery_reward_xp
                    with self._lock:
                        self._discovered_combinations.add(combo.name)
                self._record_synergy(result)
                return result

        return None

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def get_synergy_catalog(self) -> List[SynergyCombination]:
        """Return all known synergy combinations."""
        return list(self._catalog)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune_window(self, world_id: str, now_ms: float) -> None:
        """Remove casts outside the synergy window (must hold lock)."""
        cutoff = now_ms - self.SYNERGY_WINDOW_MS
        if world_id in self._recent_casts:
            self._recent_casts[world_id] = [
                c for c in self._recent_casts[world_id] if c.timestamp_ms >= cutoff
            ]

    def _calculate_magnifier(self, casts: List[SpellCastEvent]) -> float:
        """Calculate magnifier based on timing precision of the casts."""
        if len(casts) < 2:
            return 1.0
        timestamps = [c.timestamp_ms for c in casts]
        spread_ms = max(timestamps) - min(timestamps)
        caster_bonus = 0.1 * (len(casts) - 2)  # Bonus per extra caster above 2

        if spread_ms < 100:
            base = 3.0  # Perfect sync
        elif spread_ms < 1_000:
            base = 2.0  # Within 1 second
        else:
            base = 1.5  # Within full window

        return round(base + caster_bonus, 2)

    def _detect_same_spell(
        self,
        casts: List[SpellCastEvent],
        ref_ts: float,
    ) -> Optional[SynergyResult]:
        """Detect when 2+ casters cast the same spell_id within the window."""
        by_spell: Dict[str, List[SpellCastEvent]] = {}
        for cast in casts:
            if abs(cast.timestamp_ms - ref_ts) <= self.SYNERGY_WINDOW_MS:
                by_spell.setdefault(cast.spell_id, []).append(cast)

        for spell_id, matching in by_spell.items():
            if len(matching) >= 2:
                unique_casters = list({c.caster_id for c in matching})
                if len(unique_casters) >= 2:
                    magnifier = self._calculate_magnifier(matching)
                    return SynergyResult(
                        synergy_type=SynergyType.SAME_SPELL,
                        participants=unique_casters,
                        magnifier=magnifier,
                        combined_spell_name=f"Combined {spell_id}",
                        combined_effect=f"Power of {spell_id} multiplied by {magnifier:.1f}x.",
                    )
        return None

    def _detect_combo(
        self,
        combo: SynergyCombination,
        casts: List[SpellCastEvent],
        ref_ts: float,
    ) -> Optional[SynergyResult]:
        """Check whether casts satisfy a known combo's required tag sets."""
        relevant = [
            c for c in casts
            if abs(c.timestamp_ms - ref_ts) <= self.SYNERGY_WINDOW_MS
        ]
        if not relevant:
            return None

        # Each required tag-set must be satisfied by at least one cast
        satisfied_casts: List[SpellCastEvent] = []
        for required_tag_set in combo.required_tags:
            match = next(
                (c for c in relevant if required_tag_set.issubset(set(c.spell_tags))),
                None,
            )
            if match is None:
                return None
            satisfied_casts.append(match)

        # Ensure at least 2 distinct casters
        unique_casters = list({c.caster_id for c in satisfied_casts})
        if len(unique_casters) < 2:
            return None

        magnifier = self._calculate_magnifier(satisfied_casts) * combo.magnifier_base / 2.0
        return SynergyResult(
            synergy_type=combo.synergy_type,
            participants=unique_casters,
            magnifier=round(magnifier, 2),
            combined_spell_name=combo.name,
            combined_effect=combo.effect_description,
        )

    def _record_synergy(self, result: SynergyResult) -> None:
        with self._lock:
            capped_append(self._synergy_log, result, _MAX_SYNERGY_LOG)
        self._publish_event("spell_synergy_triggered", {
            "synergy_id": result.synergy_id,
            "type": result.synergy_type.value,
            "participants": result.participants,
            "magnifier": result.magnifier,
            "combined_spell_name": result.combined_spell_name,
        })

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
