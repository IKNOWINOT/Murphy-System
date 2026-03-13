"""
Unmaker NPC — The Unmaker NPC and Related Systems

Implements The Unmaker NPC, armor sets, card conversion, banning,
and boss configuration described in §9.7–9.8 of the Experimental
EverQuest Modification Plan.

Key rules:
  - The Unmaker is a level 1 NPC with a 1% random spawn rate.
  - Trading 4 universal cards of the same entity yields a Card of Unmaking.
  - The Unmaker drops 7-piece armor (5 AC each, Unmaker Aura set bonus).
  - The Unmaker boss has a 30% random attack proc, 1% ban proc, and
    15% 4th Card of Unmaking drop rate.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNMAKER_SPAWN_RATE = 0.01  # 1% random spawn chance
UNMAKER_NPC_LEVEL = 1
UNMAKER_NPC_NAME = "The Unmaker"
ARMOR_AC_PER_PIECE = 5
REQUIRED_SAME_CARDS = 4


# ---------------------------------------------------------------------------
# Dataclasses — NPC Config
# ---------------------------------------------------------------------------

@dataclass
class UnmakerNPCConfig:
    """Configuration for The Unmaker NPC (§9.7)."""

    level: int = UNMAKER_NPC_LEVEL
    spawn_rate: float = UNMAKER_SPAWN_RATE
    name: str = UNMAKER_NPC_NAME


# ---------------------------------------------------------------------------
# Dataclasses — Armor
# ---------------------------------------------------------------------------

@dataclass
class UnmakerArmorPiece:
    """A single piece of Unmaker armor."""

    name: str
    slot: str
    ac: int = ARMOR_AC_PER_PIECE
    set_piece: bool = True


UNMAKER_ARMOR_SET: List[UnmakerArmorPiece] = [
    UnmakerArmorPiece(name="Helm of the Unmaker", slot="head"),
    UnmakerArmorPiece(name="Breastplate of the Unmaker", slot="chest"),
    UnmakerArmorPiece(name="Vambraces of the Unmaker", slot="arms"),
    UnmakerArmorPiece(name="Bracers of the Unmaker", slot="wrists"),
    UnmakerArmorPiece(name="Gauntlets of the Unmaker", slot="hands"),
    UnmakerArmorPiece(name="Greaves of the Unmaker", slot="legs"),
    UnmakerArmorPiece(name="Boots of the Unmaker", slot="feet"),
]

UNMAKER_AURA_BONUS: Dict[str, str] = {
    "name": "Unmaker Aura",
    "description": (
        "Personal aura granted by the full Unmaker armor set. "
        "Converts to a group-wide aura when combined with the Megaphone item."
    ),
}


# ---------------------------------------------------------------------------
# Dataclasses — Ban & Boss Config
# ---------------------------------------------------------------------------

@dataclass
class BannedByUnmaker:
    """Record of a player banned by The Unmaker boss proc."""

    player_id: str
    banned_at: float = field(default_factory=time.time)
    ban_duration_days: int = 2
    reason: str = "Struck by The Unmaker's ban proc"


@dataclass
class UnmakerBossConfig:
    """Configuration for The Unmaker boss encounter (§9.8)."""

    random_attack_proc_rate: float = 0.30
    item_disintegration_enabled: bool = True
    ban_proc_rate: float = 0.01
    fourth_card_drop_rate: float = 0.15


# ---------------------------------------------------------------------------
# Card of Unmaking (local reference for conversion result)
# ---------------------------------------------------------------------------

@dataclass
class CardOfUnmaking:
    """A Card of Unmaking produced by the conversion process."""

    card_id: str
    source_entity_id: str
    obtained_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Unmaker NPC
# ---------------------------------------------------------------------------

class UnmakerNPC:
    """The Unmaker NPC — spawns randomly and converts cards.

    §9.7: The Unmaker is a level 1 NPC that appears with a 1% random
    spawn rate.  Players trade 4 universal cards of the same entity
    to receive a Card of Unmaking.
    """

    def __init__(self, config: Optional[UnmakerNPCConfig] = None) -> None:
        self.config = config or UnmakerNPCConfig()

    @staticmethod
    def can_spawn() -> bool:
        """Roll a 1% chance to determine if The Unmaker spawns."""
        return random.random() < UNMAKER_SPAWN_RATE

    @staticmethod
    def convert_cards_to_unmaking(
        universal_cards: Dict[str, int],
        entity_id: str,
    ) -> Optional[CardOfUnmaking]:
        """Convert 4 same-entity universal cards into a Card of Unmaking.

        Returns a CardOfUnmaking if the entity has 4+ cards, else None.
        """
        count = universal_cards.get(entity_id, 0)
        if count < REQUIRED_SAME_CARDS:
            return None
        return CardOfUnmaking(
            card_id=f"unmaking_{entity_id}_{int(time.time())}",
            source_entity_id=entity_id,
        )

    @staticmethod
    def get_loot_table() -> List[UnmakerArmorPiece]:
        """Return the Unmaker armor set loot table."""
        return list(UNMAKER_ARMOR_SET)

    @staticmethod
    def get_card_conversion_result(card_count: int) -> str:
        """Describe the outcome of a card conversion attempt."""
        if card_count < REQUIRED_SAME_CARDS:
            return (
                f"Insufficient cards ({card_count}/{REQUIRED_SAME_CARDS}). "
                f"The Unmaker requires {REQUIRED_SAME_CARDS} cards of the same entity."
            )
        return (
            "The Unmaker accepts your cards and forges a Card of Unmaking!"
        )
