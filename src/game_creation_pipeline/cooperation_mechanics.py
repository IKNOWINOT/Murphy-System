"""
Cooperation Mechanics — Core Cooperation Systems

Implements the group formation, simultaneous cast detection, combination
skill registry, and cooperation-gated progression system.

Groups are the core loop. Simultaneous spells from multiple players
within a narrow timing window produce magnified effects.

Provides:
  - Group formation and synergy calculation
  - Simultaneous spell casting detection and magnifier computation
  - Combination skill registry
  - Cooperation progression gates (content requiring N players + roles)
  - AI companion cooperation (AI + player synergy)
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .class_balance_engine import (
    ClassBalanceEngine,
    CombinationSpell,
    RoleArchetype,
    SpellElement,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Two casts within this window count as "simultaneous"
SYNERGY_WINDOW_SECONDS: float = 2.0

# Minimum magnifier for any synergy cast (even slight overlap)
MIN_SYNERGY_MAGNIFIER: float = 1.2

# Perfect simultaneous cast (within 0.1s) → maximum bonus
PERFECT_SYNC_THRESHOLD_SECONDS: float = 0.1
PERFECT_SYNC_MAGNIFIER: float = 3.0


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GroupRole(Enum):
    """Assigned position in a group for content matching."""

    MAIN_TANK = "main_tank"
    OFF_TANK = "off_tank"
    MAIN_HEALER = "main_healer"
    SECONDARY_HEALER = "secondary_healer"
    DPS = "dps"
    CROWD_CONTROL = "crowd_control"
    SUPPORT = "support"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class GroupMember:
    """A single member of a group."""

    character_id: str
    class_id: str
    primary_role: RoleArchetype
    assigned_group_role: GroupRole
    is_ai_companion: bool = False
    level: int = 1


@dataclass
class Group:
    """An active player group."""

    group_id: str
    members: List[GroupMember] = field(default_factory=list)
    formed_at: float = field(default_factory=time.time)
    active_zone: str = ""
    synergy_multiplier: float = 1.0

    def role_set(self) -> Set[RoleArchetype]:
        """Return the set of primary roles present in the group."""
        return {m.primary_role for m in self.members}

    def has_role(self, role: RoleArchetype) -> bool:
        """Check if any member fills the given role."""
        return role in self.role_set()

    def size(self) -> int:
        return len(self.members)


@dataclass
class SimultaneousCastEvent:
    """
    Tracks a simultaneous cast window for a spell element.

    Accumulates casters and computes the final magnifier.
    """

    window_id: str
    element: SpellElement
    first_cast_time: float
    casters: List[str] = field(default_factory=list)   # character_ids
    ability_ids: List[str] = field(default_factory=list)
    closed: bool = False
    magnifier: float = 1.0
    combination: Optional[CombinationSpell] = None


@dataclass
class CooperationGate:
    """
    A piece of content that requires specific group composition to attempt.
    """

    gate_id: str
    name: str
    required_min_players: int
    required_roles: List[RoleArchetype]
    min_average_level: int
    description: str
    reward_tier: str = "normal"   # "normal", "elite", "legendary"


@dataclass
class CooperationEvent:
    """Audit record for a cooperation interaction."""

    event_id: str
    event_type: str   # "group_formed", "synergy_cast", "gate_attempt", etc.
    timestamp: float
    participant_ids: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class CooperationMechanics:
    """
    Manages group cooperation, synergy casting, and gated content.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_EVENTS = 5_000
    _MAX_CAST_WINDOWS = 1_000

    def __init__(self, balance_engine: Optional[ClassBalanceEngine] = None) -> None:
        self._lock = threading.Lock()
        self._balance = balance_engine or ClassBalanceEngine()
        self._groups: Dict[str, Group] = {}
        self._cast_windows: Dict[str, SimultaneousCastEvent] = {}   # element → window
        self._events: List[CooperationEvent] = []
        self._gates: Dict[str, CooperationGate] = {}

    # ------------------------------------------------------------------
    # Group management
    # ------------------------------------------------------------------

    def form_group(self, members: List[GroupMember], zone: str = "") -> Group:
        """Create a new group and calculate its synergy multiplier."""
        group = Group(
            group_id=str(uuid.uuid4()),
            members=list(members),
            active_zone=zone,
        )
        roles = [m.primary_role for m in members]
        group.synergy_multiplier = self._balance.role_synergy_multiplier(roles)

        with self._lock:
            self._groups[group.group_id] = group
            self._emit_event("group_formed", [m.character_id for m in members], {
                "group_id": group.group_id,
                "synergy_multiplier": group.synergy_multiplier,
                "zone": zone,
            })
        logger.info(
            "Group %s formed with %d members, synergy=%.2f",
            group.group_id, len(members), group.synergy_multiplier,
        )
        return group

    def disband_group(self, group_id: str) -> None:
        """Remove a group."""
        with self._lock:
            self._groups.pop(group_id, None)

    def get_group(self, group_id: str) -> Optional[Group]:
        """Return a group by ID."""
        with self._lock:
            return self._groups.get(group_id)

    # ------------------------------------------------------------------
    # Simultaneous cast detection
    # ------------------------------------------------------------------

    def register_cast(
        self,
        character_id: str,
        ability_id: str,
        element: SpellElement,
        cast_time: Optional[float] = None,
    ) -> SimultaneousCastEvent:
        """
        Register a spell cast and return the active cast window.

        If a window for this element is open and within SYNERGY_WINDOW_SECONDS,
        the cast is added to it. Otherwise a new window is opened.

        The caller is responsible for calling ``close_window`` after the window
        expires.
        """
        now = cast_time or time.time()
        window_key = element.value

        with self._lock:
            existing = self._cast_windows.get(window_key)
            if existing and not existing.closed:
                age = now - existing.first_cast_time
                if age <= SYNERGY_WINDOW_SECONDS:
                    # Add to existing window
                    existing.casters.append(character_id)
                    existing.ability_ids.append(ability_id)
                    existing.magnifier = self._compute_magnifier(existing)
                    return existing
                else:
                    # Window expired, close it and start fresh
                    existing.closed = True

            # New window
            window = SimultaneousCastEvent(
                window_id=str(uuid.uuid4()),
                element=element,
                first_cast_time=now,
                casters=[character_id],
                ability_ids=[ability_id],
            )
            window.magnifier = 1.0  # single caster, no bonus yet
            self._cast_windows[window_key] = window
            return window

    def close_window(
        self,
        element: SpellElement,
        elements_in_window: Optional[List[SpellElement]] = None,
    ) -> Optional[SimultaneousCastEvent]:
        """
        Close the cast window for an element and compute the final result.

        ``elements_in_window`` can include other simultaneously-active
        elements to check for combination spells.
        """
        window_key = element.value
        with self._lock:
            window = self._cast_windows.get(window_key)
            if not window or window.closed:
                return None
            window.closed = True

            # Check for element combinations
            if elements_in_window:
                combo = self._balance.find_combination(elements_in_window)
                if combo and len(window.casters) >= combo.min_casters:
                    window.combination = combo
                    window.magnifier = max(window.magnifier, combo.magnifier)

            n = len(window.casters)
            if n > 1:
                self._emit_event(
                    "synergy_cast",
                    list(window.casters),
                    {
                        "element": element.value,
                        "window_id": window.window_id,
                        "caster_count": n,
                        "magnifier": window.magnifier,
                        "combination": window.combination.name if window.combination else None,
                    },
                )
                logger.info(
                    "Synergy cast closed: %s x%d casters → %.2fx magnifier%s",
                    element.value, n, window.magnifier,
                    f" [{window.combination.name}]" if window.combination else "",
                )
        return window

    # ------------------------------------------------------------------
    # Cooperation gates
    # ------------------------------------------------------------------

    def register_gate(self, gate: CooperationGate) -> None:
        """Register a cooperation-gated content encounter."""
        with self._lock:
            self._gates[gate.gate_id] = gate

    def can_attempt_gate(
        self, gate_id: str, group: Group
    ) -> Tuple[bool, List[str]]:
        """
        Check if a group meets the requirements for a cooperation gate.

        Returns (can_attempt, list_of_failure_reasons).
        """
        with self._lock:
            gate = self._gates.get(gate_id)
        if not gate:
            return False, [f"Gate '{gate_id}' not found."]

        reasons: List[str] = []
        if group.size() < gate.required_min_players:
            reasons.append(
                f"Need at least {gate.required_min_players} players "
                f"(have {group.size()})."
            )

        missing_roles = [
            r for r in gate.required_roles if not group.has_role(r)
        ]
        if missing_roles:
            reasons.append(
                f"Missing required roles: {[r.value for r in missing_roles]}"
            )

        avg_level = (
            sum(m.level for m in group.members) / max(1, group.size())
        )
        if avg_level < gate.min_average_level:
            reasons.append(
                f"Average level {avg_level:.1f} below minimum {gate.min_average_level}."
            )

        return len(reasons) == 0, reasons

    # ------------------------------------------------------------------
    # AI companion synergy
    # ------------------------------------------------------------------

    def ai_cooperation_bonus(self, group: Group) -> float:
        """
        Extra synergy multiplier when AI companions fill critical roles.

        AI companions filling required roles (tank/healer) add 0.05 each.
        """
        bonus = 0.0
        critical_roles = {RoleArchetype.TANK, RoleArchetype.HEALER}
        for m in group.members:
            if m.is_ai_companion and m.primary_role in critical_roles:
                bonus += 0.05
        return round(bonus, 3)

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def recent_events(self, limit: int = 50) -> List[CooperationEvent]:
        """Return the most recent cooperation events."""
        with self._lock:
            return list(self._events[-limit:])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_magnifier(self, window: SimultaneousCastEvent) -> float:
        """Compute magnifier based on caster count and timing precision."""
        n = len(window.casters)
        if n < 2:
            return 1.0

        # Base magnifier scales with caster count
        base = MIN_SYNERGY_MAGNIFIER + (n - 2) * 0.3

        # Check timing precision for the last two casts — approximate here
        # by assuming casts that arrive within the window are "tight"
        if n >= 2 and window.first_cast_time > 0:
            # Heuristic: if many casters in a short window → near-perfect
            density = n / SYNERGY_WINDOW_SECONDS
            if density >= 3.0:
                return min(PERFECT_SYNC_MAGNIFIER, base * 1.5)

        return min(PERFECT_SYNC_MAGNIFIER, base)

    def _emit_event(
        self, event_type: str, participants: List[str], details: Dict[str, Any]
    ) -> None:
        """Internal: append an auditable cooperation event."""
        event = CooperationEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=time.time(),
            participant_ids=list(participants),
            details=details,
        )
        capped_append(self._events, event, self._MAX_EVENTS)
