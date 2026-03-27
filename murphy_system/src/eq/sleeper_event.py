"""
Sleeper Event — The Sleeper (Kerafyrm) World Event System

Implements The Sleeper world event described in §8 of the Experimental
EverQuest Modification Plan.

Key rules:
  - Four Warders guard The Sleeper (Kerafyrm) in Sleeper's Tomb.
  - Engaging and killing warders progresses the event through phases.
  - When warders fall, dragon factions rally and mutual aid activates
    (hostile dragon factions temporarily cooperate).
  - The event resolves when Kerafyrm is either defeated or escapes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SleeperPhase(Enum):
    """Phases of The Sleeper world event (§8)."""

    DORMANT = "dormant"
    WARDERS_ENGAGED = "warders_engaged"
    WARDERS_FALLING = "warders_falling"
    AWAKENING = "awakening"
    RAMPAGING = "rampaging"
    DEFEATED = "defeated"
    ESCAPED = "escaped"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WarderStatus:
    """Status of a single Warder guarding The Sleeper."""

    warder_id: str
    name: str
    alive: bool = True
    zone: str = "sleepers_tomb"


@dataclass
class DragonRally:
    """A dragon rally dispatched in response to warder deaths."""

    source_dragon: str
    target_zone: str
    faction: str
    responding: bool = True


@dataclass
class SleeperEventState:
    """Complete state snapshot of The Sleeper world event."""

    phase: SleeperPhase = SleeperPhase.DORMANT
    warders: List[WarderStatus] = field(default_factory=list)
    rallies: List[DragonRally] = field(default_factory=list)
    mutual_aid_active: bool = False


# ---------------------------------------------------------------------------
# Default Warders
# ---------------------------------------------------------------------------

_DEFAULT_WARDERS = [
    WarderStatus(warder_id="warder_1", name="First Brood"),
    WarderStatus(warder_id="warder_2", name="Second Brood"),
    WarderStatus(warder_id="warder_3", name="Third Brood"),
    WarderStatus(warder_id="warder_4", name="Fourth Brood"),
]


# ---------------------------------------------------------------------------
# Sleeper Event Manager
# ---------------------------------------------------------------------------

class SleeperEventManager:
    """Manages The Sleeper (Kerafyrm) world event lifecycle.

    §8: The Sleeper is a server-wide one-time event.  Engaging the
    warders begins an escalating series of phases that ends when
    Kerafyrm is slain or escapes.
    """

    def __init__(self) -> None:
        self._state = SleeperEventState(
            warders=[
                WarderStatus(
                    warder_id=w.warder_id,
                    name=w.name,
                    alive=True,
                    zone=w.zone,
                )
                for w in _DEFAULT_WARDERS
            ],
        )

    # --- Phase queries ---

    def get_phase(self) -> SleeperPhase:
        """Return the current event phase."""
        return self._state.phase

    # --- Warder operations ---

    def engage_warder(self, warder_id: str) -> SleeperPhase:
        """Engage a warder, starting the event if dormant.

        Returns the updated phase.
        """
        warder = self._find_warder(warder_id)
        if warder is None:
            return self._state.phase
        if self._state.phase == SleeperPhase.DORMANT:
            self._state.phase = SleeperPhase.WARDERS_ENGAGED
        return self._state.phase

    def kill_warder(self, warder_id: str) -> SleeperPhase:
        """Kill a warder, progressing the event and triggering rallies.

        Returns the updated phase.
        """
        warder = self._find_warder(warder_id)
        if warder is None or not warder.alive:
            return self._state.phase

        warder.alive = False

        if self._state.phase == SleeperPhase.DORMANT:
            self._state.phase = SleeperPhase.WARDERS_ENGAGED

        dead_count = len(self.warders_dead)

        if dead_count >= 4:
            self._state.phase = SleeperPhase.AWAKENING
        elif dead_count >= 2:
            self._state.phase = SleeperPhase.WARDERS_FALLING

        # Trigger a default rally for the slain warder's brood
        self.send_dragon_rally(
            source=warder.name,
            target_zone=warder.zone,
            faction=f"{warder.name}_faction",
        )

        return self._state.phase

    # --- Dragon rallies ---

    def send_dragon_rally(
        self,
        source: str,
        target_zone: str,
        faction: str,
    ) -> DragonRally:
        """Dispatch a dragon rally to the target zone."""
        rally = DragonRally(
            source_dragon=source,
            target_zone=target_zone,
            faction=faction,
        )
        self._state.rallies.append(rally)
        return rally

    # --- Mutual aid ---

    def activate_mutual_aid(self) -> None:
        """Activate mutual aid — hostile dragon factions temporarily cooperate."""
        self._state.mutual_aid_active = True

    def deactivate_mutual_aid(self) -> None:
        """Deactivate mutual aid."""
        self._state.mutual_aid_active = False

    # --- Event resolution ---

    def resolve_event(self, kerafyrm_killed: bool) -> SleeperPhase:
        """Resolve the event: Kerafyrm is either defeated or escapes.

        Returns the final phase.
        """
        if kerafyrm_killed:
            self._state.phase = SleeperPhase.DEFEATED
        else:
            self._state.phase = SleeperPhase.ESCAPED
        return self._state.phase

    # --- Properties ---

    @property
    def warders_alive(self) -> List[WarderStatus]:
        """Return all living warders."""
        return [w for w in self._state.warders if w.alive]

    @property
    def warders_dead(self) -> List[WarderStatus]:
        """Return all slain warders."""
        return [w for w in self._state.warders if not w.alive]

    @property
    def rally_count(self) -> int:
        """Return the total number of rallies dispatched."""
        return len(self._state.rallies)

    @property
    def is_active(self) -> bool:
        """Return True if the event is in progress (not dormant/resolved)."""
        return self._state.phase not in (
            SleeperPhase.DORMANT,
            SleeperPhase.DEFEATED,
            SleeperPhase.ESCAPED,
        )

    # --- Internal helpers ---

    def _find_warder(self, warder_id: str) -> Optional[WarderStatus]:
        """Find a warder by ID."""
        for w in self._state.warders:
            if w.warder_id == warder_id:
                return w
        return None
