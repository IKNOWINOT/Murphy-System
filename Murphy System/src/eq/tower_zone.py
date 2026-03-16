"""
Tower Zone — Tower of the Unmaker Zone Mechanics

Implements the Tower of the Unmaker roaming-zone behaviour described in
§9.8 of the Experimental EverQuest Modification Plan.

Key rules:
  - The Tower spawns at pre-defined locations and relocates on a timer.
  - Entry requires levitation AND (1 Card of Unmaking OR 4 same-type
    universal cards) — delegated to CardCollection.can_enter_tower.
  - The Tower never spawns at the same location twice in a row.
  - A steam-whistle arrival signal announces the Tower.
  - Despawn interval defaults to 120 minutes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class TowerLocation:
    """A potential spawn point for the Tower of the Unmaker."""

    zone_name: str
    x: float
    y: float
    z: float
    wall_direction: str = "north"


class TowerState(Enum):
    """Lifecycle states for the Tower."""

    SPAWNED = "spawned"
    DESPAWNING = "despawning"
    DESPAWNED = "despawned"
    SPAWNING = "spawning"


@dataclass
class TowerConfig:
    """Configuration for the Tower of the Unmaker zone."""

    despawn_interval_minutes: int = 120
    spawn_locations: List[TowerLocation] = field(default_factory=list)
    arrival_signal: str = "steam_whistle"
    requires_levitation: bool = True


# ---------------------------------------------------------------------------
# Tower Zone Controller
# ---------------------------------------------------------------------------

class TowerZone:
    """Runtime controller for the Tower of the Unmaker.

    §9.8: The Tower roams between spawn locations, requires levitation,
    and card-based entry qualifications.
    """

    def __init__(self, config: TowerConfig) -> None:
        self._config = config
        self._state: TowerState = TowerState.SPAWNED
        self._current_location: Optional[TowerLocation] = (
            config.spawn_locations[0] if config.spawn_locations else None
        )
        self._location_index: int = 0
        self._spawn_count: int = 1 if self._current_location else 0
        self._relocate_count: int = 0

    # --- Location ---

    @property
    def current_location(self) -> Optional[TowerLocation]:
        return self._current_location

    @property
    def state(self) -> TowerState:
        return self._state

    @property
    def is_available(self) -> bool:
        """True when the Tower is spawned and can be entered."""
        return self._state is TowerState.SPAWNED

    # --- Lifecycle ---

    def despawn(self) -> None:
        """Despawn the Tower at its current location."""
        self._state = TowerState.DESPAWNED
        self._current_location = None

    def spawn_at(self, location: TowerLocation) -> None:
        """Spawn the Tower at *location*."""
        self._state = TowerState.SPAWNED
        self._current_location = location
        self._spawn_count += 1

    def relocate(self) -> TowerLocation:
        """Despawn, pick the next eligible location, and spawn there.

        §9.8: The Tower never spawns at the same location twice in a row.
        """
        eligible = self.get_eligible_spawn_locations()
        if not eligible:
            # Fallback: if only one location exists, reuse it
            eligible = list(self._config.spawn_locations)

        self._location_index = (self._location_index + 1) % len(eligible)
        next_loc = eligible[self._location_index % len(eligible)]

        self.despawn()
        self.spawn_at(next_loc)
        self._relocate_count += 1
        return next_loc

    # --- Entry checks ---

    def can_enter(self, card_collection: Any, has_levitation: bool) -> bool:
        """Check whether a holder may enter the Tower.

        Delegates the card-qualification check to
        ``card_collection.can_enter_tower(has_levitation)``.
        """
        return card_collection.can_enter_tower(has_levitation)

    # --- Eligible locations ---

    def get_eligible_spawn_locations(self) -> List[TowerLocation]:
        """Return all spawn locations except the current one."""
        if self._current_location is None:
            return list(self._config.spawn_locations)
        return [
            loc for loc in self._config.spawn_locations
            if loc is not self._current_location
        ]

    # --- Counters ---

    @property
    def spawn_count(self) -> int:
        return self._spawn_count

    @property
    def relocate_count(self) -> int:
        return self._relocate_count
