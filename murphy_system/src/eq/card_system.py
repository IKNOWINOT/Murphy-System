"""
Card System — Core Card Collection and Unmaking Logic

Implements the universal card system, god card collection, Card of Unmaking
mechanics, cooldown timers, and death-redistribution rules described in
§9.4, §9.7, §9.10, §9.14, and §9.22 of the Experimental EverQuest
Modification Plan.

Key rules:
  - Max 3 Cards of Unmaking from entities below level 60 (§9.7).
  - 4th Card of Unmaking only from the Tower of the Unmaker raid (§9.8).
  - Holding 3+ Cards of Unmaking flags the holder as attackable by everyone.
  - On death the cards are silently redistributed to zero-card killers (§9.22).
  - The dead holder respawns at bind with no cards/buffs but keeps 3rd-card
    enchanted items.
  - Tower of the Unmaker entry: 1 Card of Unmaking OR 4 same-type universal
    cards (not traded to Unmaker).  Levitation required.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNIVERSAL_CARD_DROP_RATE = 0.01  # 1% per kill
GOD_CARD_DROP_RATE_MIN = 0.05   # 5–10% per deity kill
GOD_CARD_DROP_RATE_MAX = 0.10
CARD_ABILITY_COOLDOWN_DAYS = 7
TIER1_COOLDOWN_HOURS = 24
SUB_60_UNMAKING_CAP = 3  # Max Cards of Unmaking from entities below level 60
CORE_UNMAKING_4TH_DROP_RATE = 0.15  # 15% from True Form boss
TOWER_SAME_TYPE_ENTRY_COUNT = 4  # 4 same-type universal cards to enter Tower


class CardType(Enum):
    """Card type (Enum subclass)."""
    UNIVERSAL = "universal"
    GOD = "god"
    UNMAKING = "unmaking"


class UnmakingBuff(Enum):
    """Unmaking buff (Enum subclass)."""
    VOID_SPELL = "void_of_unmaking"
    SHIELD = "shield_of_the_unmaker"
    DISINTEGRATION = "disintegration_proc"


# ---------------------------------------------------------------------------
# Card Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UniversalCard:
    """A card dropped by any entity at 1% rate."""
    entity_id: str
    entity_name: str
    entity_level: int
    dropped_at: float = field(default_factory=time.time)


@dataclass
class GodCard:
    """A card dropped from a deity encounter."""
    card_id: str
    deity_source: str
    card_type: str  # e.g. "hate", "fear", "war"
    collected_at: float = field(default_factory=time.time)
    collection_count: int = 1
    unlocks: Dict[str, bool] = field(default_factory=lambda: {
        "skill": False,
        "buff": False,
        "enchantment": False,
        "card_of_unmaking": False,
    })


@dataclass
class CardOfUnmaking:
    """The most powerful item in the game."""
    card_id: str
    source_entity_level: int  # Level of the entity that was unmade to create this card
    source_is_core_drop: bool = False  # True if obtained from Tower of the Unmaker
    obtained_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Cooldown Tracker
# ---------------------------------------------------------------------------

@dataclass
class CooldownTracker:
    """Tracks real-time cooldowns for card abilities."""
    _cooldowns: Dict[str, float] = field(default_factory=dict)

    def activate(self, ability_key: str, cooldown_seconds: float) -> None:
        self._cooldowns[ability_key] = time.time() + cooldown_seconds

    def is_ready(self, ability_key: str) -> bool:
        expiry = self._cooldowns.get(ability_key, 0.0)
        return time.time() >= expiry

    def remaining_seconds(self, ability_key: str) -> float:
        expiry = self._cooldowns.get(ability_key, 0.0)
        return max(0.0, expiry - time.time())


# ---------------------------------------------------------------------------
# Card Collection (per-player/agent)
# ---------------------------------------------------------------------------

@dataclass
class CardCollection:
    """All cards held by a single player or agent.

    This is the runtime representation of the ``card_collection`` field
    in the Soul Document Schema (§12.1).
    """

    holder_id: str

    # Universal cards: entity_id → count
    universal_cards: Dict[str, int] = field(default_factory=dict)

    # God cards: deity_name → GodCard
    god_cards: Dict[str, GodCard] = field(default_factory=dict)

    # Cards of Unmaking held (0–4)
    cards_of_unmaking: List[CardOfUnmaking] = field(default_factory=list)

    # 3rd-card enchanted item IDs (survive death/reboot)
    enchanted_items: Set[str] = field(default_factory=set)

    # Cooldowns
    cooldowns: CooldownTracker = field(default_factory=CooldownTracker)

    # State flags
    is_the_unmaker: bool = False
    attackable_by_all: bool = False

    # Tracking sub-60 unmaking card count
    sub_60_unmaking_count: int = 0

    # --- Universal card operations ---

    def add_universal_card(self, entity_id: str) -> None:
        self.universal_cards[entity_id] = self.universal_cards.get(entity_id, 0) + 1

    def get_universal_card_count(self, entity_id: str) -> int:
        return self.universal_cards.get(entity_id, 0)

    # --- God card operations ---

    def add_god_card(self, card: GodCard) -> None:
        self.god_cards[card.deity_source] = card
        self._update_god_card_unlocks(card)

    def _update_god_card_unlocks(self, card: GodCard) -> None:
        count = card.collection_count
        if count >= 1:
            card.unlocks["skill"] = True
        if count >= 2:
            card.unlocks["buff"] = True
        if count >= 3:
            card.unlocks["enchantment"] = True
        if count >= 4:
            card.unlocks["card_of_unmaking"] = True

    # --- Card of Unmaking operations ---

    @property
    def unmaking_card_count(self) -> int:
        return len(self.cards_of_unmaking)

    def can_obtain_unmaking_card(self, source_entity_level: int, is_core_drop: bool = False) -> bool:
        """Check whether the holder can obtain a new Card of Unmaking.

        §9.7: max 3 from entities below level 60.
        """
        if is_core_drop:
            return True  # Core drops bypass the sub-60 cap
        if source_entity_level >= 60:
            return True  # Level 60+ entities are not subject to the cap
        return self.sub_60_unmaking_count < SUB_60_UNMAKING_CAP

    def add_unmaking_card(self, card: CardOfUnmaking) -> bool:
        """Add a Card of Unmaking, respecting the level-60 cap.

        Returns True if the card was added, False if rejected.
        """
        if not self.can_obtain_unmaking_card(card.source_entity_level, card.source_is_core_drop):
            return False
        self.cards_of_unmaking.append(card)
        if card.source_entity_level < 60 and not card.source_is_core_drop:
            self.sub_60_unmaking_count += 1
        self._update_attackable_flag()
        return True

    def _update_attackable_flag(self) -> None:
        """§9.10: 3+ Cards of Unmaking = attackable by everyone."""
        self.attackable_by_all = self.unmaking_card_count >= 3

    # --- Enchanted item management ---

    def add_enchanted_item(self, item_id: str) -> None:
        """Register an item enchanted with a 3rd-card enchantment."""
        self.enchanted_items.add(item_id)

    # --- Active buffs from unmaking cards ---

    def active_unmaking_buffs(self) -> Set[UnmakingBuff]:
        """Return the set of buffs currently active based on held cards."""
        count = self.unmaking_card_count
        buffs: Set[UnmakingBuff] = set()
        if count >= 1:
            buffs.add(UnmakingBuff.VOID_SPELL)
        if count >= 2:
            buffs.add(UnmakingBuff.SHIELD)
        if count >= 3:
            buffs.add(UnmakingBuff.DISINTEGRATION)
        return buffs

    # --- Tower of the Unmaker entry (§9.8) ---

    def has_four_same_type_cards(self) -> bool:
        """Check if the holder has 4+ universal cards of any single entity type.

        These must not have been traded to The Unmaker (they are still in
        the universal_cards collection).
        """
        return any(count >= TOWER_SAME_TYPE_ENTRY_COUNT
                    for count in self.universal_cards.values())

    def can_enter_tower(self, has_levitation: bool = True) -> bool:
        """Check whether the holder meets Tower of the Unmaker entry requirements.

        §9.8: Entry requires levitation AND one of:
          - At least 1 Card of Unmaking, OR
          - 4 universal cards of the same entity type (not traded to Unmaker)
        """
        if not has_levitation:
            return False
        if self.unmaking_card_count >= 1:
            return True
        return self.has_four_same_type_cards()


# ---------------------------------------------------------------------------
# Death & Silent Redistribution (§9.22)
# ---------------------------------------------------------------------------

@dataclass
class DeathRedistributionResult:
    """Outcome of a 3-card holder being killed."""
    dead_holder_id: str
    cards_redistributed: int
    recipients: Dict[str, int]  # holder_id → count received
    cards_destroyed: int
    silent: bool = True  # always silent


def handle_unmaking_death(
    dead_holder: CardCollection,
    killers: List[CardCollection],
) -> DeathRedistributionResult:
    """Process the death of a player/agent holding 3+ Cards of Unmaking.

    §9.22: Cards are silently redistributed to zero-card killers.
    The dead holder respawns at bind with no cards/buffs but keeps enchanted items.
    """
    cards_to_distribute = list(dead_holder.cards_of_unmaking)
    total = len(cards_to_distribute)

    # Identify eligible recipients: killers with zero Cards of Unmaking
    eligible = [k for k in killers if k.unmaking_card_count == 0]

    recipients: Dict[str, int] = {}
    cards_distributed = 0

    if eligible and cards_to_distribute:
        random.shuffle(cards_to_distribute)
        for card in cards_to_distribute:
            recipient = random.choice(eligible)
            card_copy = CardOfUnmaking(
                card_id=card.card_id,
                source_entity_level=card.source_entity_level,
                source_is_core_drop=card.source_is_core_drop,
            )
            added = recipient.add_unmaking_card(card_copy)
            if added:
                cards_distributed += 1
                recipients[recipient.holder_id] = recipients.get(recipient.holder_id, 0) + 1
                # If recipient now has cards, they may no longer be eligible
                if recipient.unmaking_card_count > 0:
                    eligible = [k for k in eligible if k.unmaking_card_count == 0]
                    if not eligible:
                        break

    cards_destroyed = total - cards_distributed

    # Strip the dead holder
    _strip_unmaking_state(dead_holder)

    return DeathRedistributionResult(
        dead_holder_id=dead_holder.holder_id,
        cards_redistributed=cards_distributed,
        recipients=recipients,
        cards_destroyed=cards_destroyed,
    )


def _strip_unmaking_state(collection: CardCollection) -> None:
    """Remove all unmaking cards, buffs, and flags from the dead holder.

    Enchanted items are preserved (§9.22).
    """
    collection.cards_of_unmaking.clear()
    collection.sub_60_unmaking_count = 0
    collection.attackable_by_all = False
    collection.is_the_unmaker = False
    # Note: enchanted_items are NOT cleared — they survive death


# ---------------------------------------------------------------------------
# Drop-roll helpers
# ---------------------------------------------------------------------------

def roll_universal_card_drop() -> bool:
    """Roll for a 1% universal card drop."""
    return random.random() < UNIVERSAL_CARD_DROP_RATE


def roll_god_card_drop() -> bool:
    """Roll for a 5–10% god card drop."""
    rate = random.uniform(GOD_CARD_DROP_RATE_MIN, GOD_CARD_DROP_RATE_MAX)
    return random.random() < rate
