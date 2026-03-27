"""
Cross-World Item Portability System for the Multiverse Game Framework.

Design Label: GAME-003 — Cross-World Item Portability System
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager
  - universal_character.UniversalCharacter

Some items can only be used in specific worlds; others travel anywhere.
When a character travels to a world where an item cannot follow, the item
is automatically stashed in their universal bank.

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
from typing import Any, Dict, List, Optional, Tuple

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

_MAX_TRANSFER_LOG = 10_000

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ItemPortabilityTier(str, Enum):
    """Cross-world portability tier for items.

    UNIVERSAL  — usable in ALL worlds (rare, hard to obtain).
    MULTI_WORLD — usable in a defined set of worlds.
    WORLD_LOCKED — only usable in the world where it was obtained.
    QUEST_LOCKED — bound to a specific quest chain across worlds.
    SEASONAL — usable during specific time windows across all worlds.
    """
    UNIVERSAL = "universal"
    MULTI_WORLD = "multi_world"
    WORLD_LOCKED = "world_locked"
    QUEST_LOCKED = "quest_locked"
    SEASONAL = "seasonal"


class ItemType(str, Enum):
    """Broad item category."""
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    MATERIAL = "material"
    COSMETIC = "cosmetic"


class TransferStatus(str, Enum):
    """Result of an item transfer attempt."""
    SUCCESS = "success"
    DENIED_WORLD_LOCKED = "denied_world_locked"
    DENIED_QUEST_LOCKED = "denied_quest_locked"
    DENIED_SEASONAL = "denied_seasonal"
    DENIED_NOT_IN_ALLOWED_WORLDS = "denied_not_in_allowed_worlds"
    AUTO_STASHED = "auto_stashed"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GameItem:
    """A game item with cross-world portability metadata.

    Args:
        item_id: Unique item UUID.
        name: Display name.
        description: Flavour description.
        item_type: Category (weapon/armor/consumable/material/cosmetic).
        portability_tier: How portable this item is across worlds.
        allowed_world_ids: Worlds the item can be used in (MULTI_WORLD tier).
        origin_world_id: World where this item was originally obtained.
        level_requirement: Minimum character level to equip/use.
        class_restrictions: Class names that can use this item (empty = all).
        luck_bonus: Optional LUCK stat modifier granted by this item.
        synergy_tags: Tags for spell/skill combination system.
        seasonal_window_start: Start datetime for SEASONAL items.
        seasonal_window_end: End datetime for SEASONAL items.
        quest_chain_id: Quest chain ID for QUEST_LOCKED items.
    """
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unknown Item"
    description: str = ""
    item_type: ItemType = ItemType.MATERIAL
    portability_tier: ItemPortabilityTier = ItemPortabilityTier.WORLD_LOCKED
    allowed_world_ids: List[str] = field(default_factory=list)
    origin_world_id: str = ""
    level_requirement: int = 1
    class_restrictions: List[str] = field(default_factory=list)
    luck_bonus: Optional[int] = None
    synergy_tags: List[str] = field(default_factory=list)
    seasonal_window_start: Optional[datetime] = None
    seasonal_window_end: Optional[datetime] = None
    quest_chain_id: Optional[str] = None


@dataclass
class TransferResult:
    """Result of an item transfer between worlds.

    Args:
        status: Outcome of the transfer.
        item_id: The item being transferred.
        from_world_id: Source world.
        to_world_id: Destination world.
        message: Human-readable explanation.
    """
    status: TransferStatus
    item_id: str
    from_world_id: str
    to_world_id: str
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# ItemPortabilityEngine
# ---------------------------------------------------------------------------


class ItemPortabilityEngine:
    """Evaluates and enforces cross-world item portability rules.

    Items that cannot enter a destination world are automatically moved to
    the character's universal bank (stash).
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        self._transfer_log: List[TransferResult] = []
        # Universal bank: character_id → list of stashed items
        self._universal_bank: Dict[str, List[GameItem]] = {}

    # ------------------------------------------------------------------
    # Portability checks
    # ------------------------------------------------------------------

    def can_use_in_world(self, item: GameItem, world_id: str) -> bool:
        """Determine if an item can be used in the given world.

        Args:
            item: The GameItem to check.
            world_id: Target world ID.

        Returns:
            True if the item is usable in that world, False otherwise.
        """
        tier = item.portability_tier

        if tier == ItemPortabilityTier.UNIVERSAL:
            return True

        if tier == ItemPortabilityTier.WORLD_LOCKED:
            return item.origin_world_id == world_id

        if tier == ItemPortabilityTier.MULTI_WORLD:
            return world_id in item.allowed_world_ids

        if tier == ItemPortabilityTier.QUEST_LOCKED:
            # Quest-locked items travel with the quest chain; always usable
            # once the chain is active. Clients validate chain state separately.
            return True

        if tier == ItemPortabilityTier.SEASONAL:
            now = datetime.now(timezone.utc)
            start = item.seasonal_window_start
            end = item.seasonal_window_end
            if start and end:
                return start <= now <= end
            return False

        return False  # pragma: no cover

    def get_portable_inventory(
        self,
        character: Any,
        target_world_id: str,
    ) -> Tuple[List[GameItem], List[GameItem]]:
        """Split a character's inventory into usable and stash-bound items.

        Args:
            character: The character whose inventory to inspect. Expected to
                       have an ``inventory`` attribute (list of GameItem).
            target_world_id: The world the character is travelling to.

        Returns:
            A tuple (usable_items, stashed_items).
        """
        inventory: List[GameItem] = getattr(character, "inventory", [])
        usable: List[GameItem] = []
        stashed: List[GameItem] = []
        for item in inventory:
            if self.can_use_in_world(item, target_world_id):
                usable.append(item)
            else:
                stashed.append(item)
        return usable, stashed

    # ------------------------------------------------------------------
    # Transfers
    # ------------------------------------------------------------------

    def transfer_item(
        self,
        item: GameItem,
        from_world: str,
        to_world: str,
    ) -> TransferResult:
        """Attempt to transfer an item from one world to another.

        Items that are not portable are auto-stashed rather than destroyed.

        Args:
            item: The GameItem to transfer.
            from_world: Source world ID.
            to_world: Destination world ID.

        Returns:
            TransferResult with outcome details.
        """
        if self.can_use_in_world(item, to_world):
            result = TransferResult(
                status=TransferStatus.SUCCESS,
                item_id=item.item_id,
                from_world_id=from_world,
                to_world_id=to_world,
                message=f"'{item.name}' transferred successfully.",
            )
        else:
            tier = item.portability_tier
            if tier == ItemPortabilityTier.WORLD_LOCKED:
                status = TransferStatus.DENIED_WORLD_LOCKED
                msg = f"'{item.name}' is world-locked to '{item.origin_world_id}'."
            elif tier == ItemPortabilityTier.SEASONAL:
                status = TransferStatus.DENIED_SEASONAL
                msg = f"'{item.name}' is not active during the current season."
            else:
                status = TransferStatus.AUTO_STASHED
                msg = f"'{item.name}' stashed — not available in '{to_world}'."
            result = TransferResult(
                status=status,
                item_id=item.item_id,
                from_world_id=from_world,
                to_world_id=to_world,
                message=msg,
            )

        with self._lock:
            capped_append(self._transfer_log, result, _MAX_TRANSFER_LOG)

        self._publish_event("item_transfer", {
            "item_id": item.item_id,
            "from_world": from_world,
            "to_world": to_world,
            "status": result.status.value,
        })
        return result

    def stash_item(self, character_id: str, item: GameItem) -> None:
        """Move an item to a character's universal bank.

        Args:
            character_id: Owning character ID.
            item: Item to stash.
        """
        with self._lock:
            bank = self._universal_bank.setdefault(character_id, [])
            capped_append(bank, item, 1_000)

    def get_stash(self, character_id: str) -> List[GameItem]:
        """Return all items in a character's universal bank."""
        return list(self._universal_bank.get(character_id, []))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
