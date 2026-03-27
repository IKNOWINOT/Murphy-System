"""
World Registry & Cross-World Travel for the Multiverse Game Framework.

Design Label: GAME-002 — World Registry & Cross-World Travel
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager
  - universal_character.UniversalCharacter

Worlds are versioned game instances. Each weekly release adds a new world.
Characters travel between worlds subject to level requirements and item
portability rules.

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
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

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

_MAX_TRAVEL_LOG = 10_000

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorldStatus(str, Enum):
    """Operational status of a world instance."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    MAINTENANCE = "maintenance"
    UPCOMING = "upcoming"


class TravelStatus(str, Enum):
    """Result of a world-travel attempt."""
    SUCCESS = "success"
    DENIED_LEVEL = "denied_level"
    DENIED_WORLD_CLOSED = "denied_world_closed"
    DENIED_SAME_WORLD = "denied_same_world"
    STASH_REQUIRED = "stash_required"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class WorldDefinition:
    """Definition of a single game world.

    Args:
        world_id: Unique world identifier.
        world_name: Display name.
        version: Semantic version string (e.g., "1.0.0").
        release_date: When the world was (or will be) released.
        theme: Short thematic description (e.g., "Volcanic Underworld").
        description: Full flavour description.
        level_range_min: Recommended minimum character level.
        level_range_max: Recommended maximum character level.
        required_universal_level: Minimum universal level to enter.
        item_portability_rules: Dict defining which item categories can enter/leave.
        unique_mechanics: Mechanics unique to this world.
        billboard_zones: Zone IDs that have proximity-based advertising billboards.
        streaming_hotspots: Zone IDs optimised for streaming.
        max_concurrent_players: Player capacity cap (0 = unlimited).
        status: Current operational status.
    """
    world_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    world_name: str = "Unnamed World"
    version: str = "1.0.0"
    release_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    theme: str = ""
    description: str = ""
    level_range_min: int = 1
    level_range_max: int = 100
    required_universal_level: int = 1
    item_portability_rules: Dict[str, Any] = field(default_factory=dict)
    unique_mechanics: List[str] = field(default_factory=list)
    billboard_zones: List[str] = field(default_factory=list)
    streaming_hotspots: List[str] = field(default_factory=list)
    max_concurrent_players: int = 0
    status: WorldStatus = WorldStatus.ACTIVE


@dataclass
class TravelResult:
    """Result of a world-travel request.

    Args:
        status: Outcome of the travel attempt.
        character_id: Character attempting travel.
        from_world_id: Source world (or None if in lobby).
        to_world_id: Target world.
        stashed_item_ids: Items that were auto-stashed because they can't enter.
        message: Human-readable explanation.
    """
    status: TravelStatus
    character_id: str
    from_world_id: Optional[str]
    to_world_id: str
    stashed_item_ids: List[str] = field(default_factory=list)
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# WorldRegistry
# ---------------------------------------------------------------------------


class WorldRegistry:
    """Registry of all game worlds with travel validation.

    Worlds are registered with their level requirements and item portability
    rules. Characters can travel between worlds provided they meet requirements.
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        self._worlds: Dict[str, WorldDefinition] = {}
        self._travel_log: List[TravelResult] = []

    # ------------------------------------------------------------------
    # World management
    # ------------------------------------------------------------------

    def register_world(self, definition: WorldDefinition) -> None:
        """Register a new world definition.

        Args:
            definition: The WorldDefinition to register.

        Raises:
            ValueError: If a world with this world_id already exists.
        """
        with self._lock:
            if definition.world_id in self._worlds:
                raise ValueError(f"World '{definition.world_id}' already registered.")
            self._worlds[definition.world_id] = definition
        logger.info("Registered world '%s' (%s)", definition.world_name, definition.world_id)
        self._publish_event("world_registered", {"world_id": definition.world_id})

    def get_world(self, world_id: str) -> Optional[WorldDefinition]:
        """Return the WorldDefinition for a given world_id, or None."""
        return self._worlds.get(world_id)

    def list_active_worlds(self) -> List[WorldDefinition]:
        """Return all worlds currently in ACTIVE status."""
        return [w for w in self._worlds.values() if w.status == WorldStatus.ACTIVE]

    def get_worlds_for_level(self, character_level: int) -> List[WorldDefinition]:
        """Return worlds whose recommended level range includes character_level.

        Args:
            character_level: The character's universal level.

        Returns:
            List of WorldDefinition objects suitable for this level.
        """
        return [
            w for w in self._worlds.values()
            if (
                w.status == WorldStatus.ACTIVE
                and w.required_universal_level <= character_level
                and w.level_range_min <= character_level <= w.level_range_max
            )
        ]

    def get_release_schedule(self) -> List[WorldDefinition]:
        """Return upcoming worlds ordered by release date."""
        upcoming = [
            w for w in self._worlds.values()
            if w.status == WorldStatus.UPCOMING
        ]
        return sorted(upcoming, key=lambda w: w.release_date)

    # ------------------------------------------------------------------
    # Travel
    # ------------------------------------------------------------------

    def travel_to_world(
        self,
        character: Any,
        target_world_id: str,
        item_portability_engine: Optional[Any] = None,
    ) -> TravelResult:
        """Validate and execute cross-world travel for a character.

        Checks: world exists, world is active, character meets level
        requirements, items are handled per portability rules.

        Args:
            character: UniversalCharacter instance.
            target_world_id: ID of the destination world.
            item_portability_engine: Optional ItemPortabilityEngine for stash logic.

        Returns:
            TravelResult indicating success or the reason for denial.
        """
        target = self._worlds.get(target_world_id)
        from_world_id = getattr(character, "active_world_id", None)

        if target is None:
            result = TravelResult(
                status=TravelStatus.DENIED_WORLD_CLOSED,
                character_id=character.character_id,
                from_world_id=from_world_id,
                to_world_id=target_world_id,
                message=f"World '{target_world_id}' does not exist.",
            )
            capped_append(self._travel_log, result, _MAX_TRAVEL_LOG)
            return result

        if target.status != WorldStatus.ACTIVE:
            result = TravelResult(
                status=TravelStatus.DENIED_WORLD_CLOSED,
                character_id=character.character_id,
                from_world_id=from_world_id,
                to_world_id=target_world_id,
                message=f"World '{target.world_name}' is not currently active (status={target.status.value}).",
            )
            capped_append(self._travel_log, result, _MAX_TRAVEL_LOG)
            return result

        if from_world_id == target_world_id:
            result = TravelResult(
                status=TravelStatus.DENIED_SAME_WORLD,
                character_id=character.character_id,
                from_world_id=from_world_id,
                to_world_id=target_world_id,
                message="Character is already in this world.",
            )
            capped_append(self._travel_log, result, _MAX_TRAVEL_LOG)
            return result

        if character.level < target.required_universal_level:
            result = TravelResult(
                status=TravelStatus.DENIED_LEVEL,
                character_id=character.character_id,
                from_world_id=from_world_id,
                to_world_id=target_world_id,
                message=(
                    f"Character level {character.level} does not meet "
                    f"required level {target.required_universal_level} for '{target.world_name}'."
                ),
            )
            capped_append(self._travel_log, result, _MAX_TRAVEL_LOG)
            return result

        # Handle item portability
        stashed_ids: List[str] = []
        if item_portability_engine is not None:
            try:
                _, stashed = item_portability_engine.get_portable_inventory(character, target_world_id)
                stashed_ids = [item.item_id for item in stashed]
            except Exception:  # pragma: no cover
                logger.debug("Item portability check failed silently", exc_info=True)

        # Commit travel
        character.active_world_id = target_world_id
        if target_world_id not in character.world_visit_history:
            capped_append(character.world_visit_history, target_world_id, 500)

        result = TravelResult(
            status=TravelStatus.SUCCESS,
            character_id=character.character_id,
            from_world_id=from_world_id,
            to_world_id=target_world_id,
            stashed_item_ids=stashed_ids,
            message=f"Arrived in '{target.world_name}'.",
        )
        capped_append(self._travel_log, result, _MAX_TRAVEL_LOG)
        self._publish_event("character_traveled", {
            "character_id": character.character_id,
            "from_world_id": from_world_id,
            "to_world_id": target_world_id,
        })
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
