"""
Unmaking Escalation System — Card-Count Scaling and Server Announcements

Implements the Unmaking Escalation system described in §9.10 of the
Experimental EverQuest Modification Plan.

Key rules:
  - Capabilities and threats scale with the number of Cards of Unmaking held.
  - 1 card: 6 origin NPCs summoned, hostile city armies mobilize.
  - 2 cards: origin zone rallied, dragon dispatched (3-day timer).
  - 3 cards: full origin + faction zone summoned, attackable by all,
    god + dragon dispatched (3-day timer).
  - 4 cards: unmaker immune, full faction mobilization.
  - Server-wide announcement when a card trade brings a holder to 3+ cards.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

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

class EscalationTier(Enum):
    """Escalation tiers based on Cards of Unmaking held (§9.10)."""

    NONE = 0
    ONE_CARD = 1
    TWO_CARDS = 2
    THREE_CARDS = 3
    FOUR_CARDS = 4


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EscalationCapability:
    """Capabilities granted to the card holder at a given tier."""

    tier: EscalationTier
    description: str
    npc_summon_count: int = 0
    origin_zone_rallied: bool = False
    faction_mobilized: bool = False
    unmaker_immune: bool = False


@dataclass
class EscalationThreat:
    """Threats directed at the card holder at a given tier."""

    tier: EscalationTier
    description: str
    hostile_armies: bool = False
    dragon_dispatched: bool = False
    god_dispatched: bool = False
    dragon_timer_days: int = 0
    attackable_by_all: bool = False


@dataclass
class ServerAnnouncement:
    """A server-wide announcement triggered by a card trade."""

    message: str
    entity_name: str
    card_count: int
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Capability / Threat Tables
# ---------------------------------------------------------------------------

_CAPABILITY_TABLE: Dict[EscalationTier, EscalationCapability] = {
    EscalationTier.NONE: EscalationCapability(
        tier=EscalationTier.NONE,
        description="No Cards of Unmaking held.",
    ),
    EscalationTier.ONE_CARD: EscalationCapability(
        tier=EscalationTier.ONE_CARD,
        description="6 origin NPCs summoned to aid the holder.",
        npc_summon_count=6,
    ),
    EscalationTier.TWO_CARDS: EscalationCapability(
        tier=EscalationTier.TWO_CARDS,
        description="Origin zone rallied to defend the holder.",
        npc_summon_count=6,
        origin_zone_rallied=True,
    ),
    EscalationTier.THREE_CARDS: EscalationCapability(
        tier=EscalationTier.THREE_CARDS,
        description="Origin city + faction zone summoned to defend.",
        npc_summon_count=6,
        origin_zone_rallied=True,
        faction_mobilized=True,
    ),
    EscalationTier.FOUR_CARDS: EscalationCapability(
        tier=EscalationTier.FOUR_CARDS,
        description="Unmaker immune, full faction mobilization.",
        npc_summon_count=6,
        origin_zone_rallied=True,
        faction_mobilized=True,
        unmaker_immune=True,
    ),
}

_THREAT_TABLE: Dict[EscalationTier, EscalationThreat] = {
    EscalationTier.NONE: EscalationThreat(
        tier=EscalationTier.NONE,
        description="No threats — no cards held.",
    ),
    EscalationTier.ONE_CARD: EscalationThreat(
        tier=EscalationTier.ONE_CARD,
        description="Hostile city armies mobilize against the holder.",
        hostile_armies=True,
    ),
    EscalationTier.TWO_CARDS: EscalationThreat(
        tier=EscalationTier.TWO_CARDS,
        description="Dragon dispatched with a 3-day timer.",
        hostile_armies=True,
        dragon_dispatched=True,
        dragon_timer_days=3,
    ),
    EscalationTier.THREE_CARDS: EscalationThreat(
        tier=EscalationTier.THREE_CARDS,
        description="God + dragon dispatched, attackable by all players.",
        hostile_armies=True,
        dragon_dispatched=True,
        god_dispatched=True,
        dragon_timer_days=3,
        attackable_by_all=True,
    ),
    EscalationTier.FOUR_CARDS: EscalationThreat(
        tier=EscalationTier.FOUR_CARDS,
        description="Full escalation — god + dragon dispatched, attackable by all.",
        hostile_armies=True,
        dragon_dispatched=True,
        god_dispatched=True,
        dragon_timer_days=3,
        attackable_by_all=True,
    ),
}


# ---------------------------------------------------------------------------
# Escalation Manager
# ---------------------------------------------------------------------------

class EscalationManager:
    """Manages escalation tiers, capabilities, threats, and announcements.

    §9.10: As a player collects more Cards of Unmaking, both their
    capabilities and the threats arrayed against them scale upward.
    """

    def __init__(self) -> None:
        self._announcements: List[ServerAnnouncement] = []

    # --- Tier resolution ---

    @staticmethod
    def get_tier(card_count: int) -> EscalationTier:
        """Return the escalation tier for a given card count."""
        if card_count <= 0:
            return EscalationTier.NONE
        if card_count == 1:
            return EscalationTier.ONE_CARD
        if card_count == 2:
            return EscalationTier.TWO_CARDS
        if card_count == 3:
            return EscalationTier.THREE_CARDS
        return EscalationTier.FOUR_CARDS

    # --- Capability / Threat lookup ---

    @staticmethod
    def get_capabilities(tier: EscalationTier) -> EscalationCapability:
        """Return the capabilities granted at the given tier."""
        return _CAPABILITY_TABLE[tier]

    @staticmethod
    def get_threats(tier: EscalationTier) -> EscalationThreat:
        """Return the threats directed at the holder at the given tier."""
        return _THREAT_TABLE[tier]

    # --- Announcements ---

    def announce_card_trade(
        self,
        player_name: str,
        entity_name: str,
        new_count: int,
    ) -> ServerAnnouncement:
        """Create a server-wide announcement for a card trade.

        Only meaningful at 3+ cards, but the announcement is always created
        so callers can decide whether to broadcast.
        """
        announcement = ServerAnnouncement(
            message=(
                f"{player_name} now holds {new_count} Card(s) of Unmaking "
                f"after trading with {entity_name}!"
            ),
            entity_name=entity_name,
            card_count=new_count,
        )
        capped_append(self._announcements, announcement)
        return announcement

    @staticmethod
    def should_announce(card_count: int) -> bool:
        """Return True if the card count warrants a server announcement."""
        return card_count >= 3

    # --- Origin NPC summoning ---

    @staticmethod
    def get_origin_npcs(origin_city: str, count: int) -> List[str]:
        """Return NPC IDs for summoning from the holder's origin city.

        In production this would query the game connector; here we
        generate placeholder IDs.
        """
        return [f"{origin_city}_npc_{i}" for i in range(count)]

    # --- Properties ---

    @property
    def current_announcements(self) -> List[ServerAnnouncement]:
        """Return all announcements issued so far."""
        return list(self._announcements)
