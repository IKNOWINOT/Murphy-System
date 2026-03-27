# © 2020 Inoni Limited Liability Company by Corey Post — License: BSL 1.1
"""
Bot Room Registry — Murphy System
===================================

Maps every bot persona to all the rooms it operates in, and every room to all
the bots serving it.  A single bot can appear in multiple rooms — this module
makes that relationship explicit and queryable.

Bot personas are defined in the module manifest (``MODULE_MANIFEST``).  This
registry builds two inverse indices:

  ``BOT_TO_ROOMS``  — {persona_name: [room_key, ...]}
  ``ROOM_TO_BOTS``  — {room_key: [persona_name, ...]}

It also exposes per-persona capability cards that describe:
  - Which rooms the bot monitors
  - Which MSS cognitive roles it primarily uses
  - Which event types it emits and consumes across all rooms
  - Its primary domain of responsibility

Design:  BOT-REG-001
Owner:   Platform AI
License: BSL 1.1
Copyright © 2020 Inoni Limited Liability Company — Created by Corey Post
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class BotCapabilityCard:
    """Full capability profile for a bot persona."""

    persona: str
    rooms: List[str]                           = field(default_factory=list)
    primary_domains: List[str]                 = field(default_factory=list)
    cognitive_roles: List[str]                 = field(default_factory=list)   # MAGNIFY/SIMPLIFY/SOLIDIFY
    emits: List[str]                           = field(default_factory=list)   # all event types across rooms
    consumes: List[str]                        = field(default_factory=list)
    commands: List[str]                        = field(default_factory=list)
    room_count: int                            = 0
    description: str                           = ""

    def __post_init__(self) -> None:
        self.room_count = len(self.rooms)


@dataclass
class RoomBotProfile:
    """All bots serving a single room."""

    room_key: str
    bots: List[str]                            = field(default_factory=list)
    primary_bot: str                           = "TriageBot"
    cognitive_role: str                        = "magnify"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class BotRoomRegistry:
    """
    Bidirectional index of bot personas ↔ Matrix rooms.

    Built from the module manifest on first access.  Thread-safe for reads
    (no writes after construction).

    Usage::

        reg = BotRoomRegistry.from_manifest()
        card = reg.get_bot_card("ExecutionBot")
        bots = reg.bots_for_room("execution-engine")
        rooms = reg.rooms_for_bot("SecurityBot")
    """

    def __init__(self) -> None:
        self._bot_to_rooms:  Dict[str, List[str]]          = {}
        self._room_to_bots:  Dict[str, List[str]]          = {}
        self._bot_cards:     Dict[str, BotCapabilityCard]  = {}
        self._room_profiles: Dict[str, RoomBotProfile]     = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_manifest(cls) -> "BotRoomRegistry":
        """Build the registry from MODULE_MANIFEST + ROOM_COGNITIVE_ROLES."""
        try:
            from src.matrix_bridge.module_manifest import MODULE_MANIFEST
        except ImportError:
            from matrix_bridge.module_manifest import MODULE_MANIFEST

        try:
            from src.matrix_bridge.room_cognitive_roles import ROOM_COGNITIVE_ROLES
        except ImportError:
            try:
                from matrix_bridge.room_cognitive_roles import ROOM_COGNITIVE_ROLES
            except ImportError:
                ROOM_COGNITIVE_ROLES = {}

        instance = cls()

        # ── Collect per-bot data ─────────────────────────────────────────
        bot_rooms:    Dict[str, Set[str]]  = {}
        bot_emits:    Dict[str, Set[str]]  = {}
        bot_consumes: Dict[str, Set[str]]  = {}
        bot_commands: Dict[str, Set[str]]  = {}

        for entry in MODULE_MANIFEST:
            p = entry.persona
            bot_rooms   .setdefault(p, set()).add(entry.room)
            bot_emits   .setdefault(p, set()).update(entry.emits)
            bot_consumes.setdefault(p, set()).update(entry.consumes)
            bot_commands.setdefault(p, set()).update(entry.commands)

        # ── Build bot cards ──────────────────────────────────────────────
        _PERSONA_DOMAINS: Dict[str, str] = {
            "TriageBot":       "General triage and routing",
            "ExecutionBot":    "Task execution and orchestration",
            "ComplianceBot":   "Governance, compliance and gate synthesis",
            "EngineeringBot":  "Domain engineering and technical delivery",
            "FinanceBot":      "Financial planning, billing and economics",
            "MonitoringBot":   "Observability, alerting and telemetry",
            "LibrarianBot":    "Knowledge management and semantic search",
            "SecurityBot":     "Security hardening, auditing and key management",
            "OnboardingBot":   "Onboarding flows and new-user automation",
            "CADBot":          "Digital-twin, drawing and asset generation",
            "KeyManagerBot":   "Credential rotation and secret management",
            "MarketingBot":    "Self-marketing and outreach orchestration",
            "GovernanceBot":   "Outreach compliance and contact governance",
            "FounderBot":      "Founder-level updates and health reporting",
        }

        for persona, rooms in bot_rooms.items():
            sorted_rooms = sorted(rooms)
            # Determine cognitive roles used across these rooms
            roles_used: Set[str] = set()
            for r in sorted_rooms:
                role = ROOM_COGNITIVE_ROLES.get(r)
                if role:
                    roles_used.add(role.value if hasattr(role, "value") else str(role))

            card = BotCapabilityCard(
                persona         = persona,
                rooms           = sorted_rooms,
                primary_domains = [_PERSONA_DOMAINS.get(persona, "General automation")],
                cognitive_roles = sorted(roles_used),
                emits           = sorted(bot_emits.get(persona, set())),
                consumes        = sorted(bot_consumes.get(persona, set())),
                commands        = sorted(bot_commands.get(persona, set())),
                description     = _PERSONA_DOMAINS.get(persona, ""),
            )
            instance._bot_cards[persona]     = card
            instance._bot_to_rooms[persona]  = sorted_rooms

        # ── Build room profiles ──────────────────────────────────────────
        room_bots: Dict[str, Set[str]] = {}
        for persona, rooms in bot_rooms.items():
            for r in rooms:
                room_bots.setdefault(r, set()).add(persona)

        for room, bots in room_bots.items():
            sorted_bots = sorted(bots)
            # Primary bot = the one with the most room assignments (most specialised last)
            primary = sorted_bots[0]
            max_rooms = 0
            for b in sorted_bots:
                n = len(bot_rooms.get(b, set()))
                if n > max_rooms:
                    max_rooms, primary = n, b

            role_obj = ROOM_COGNITIVE_ROLES.get(room)
            role_str = role_obj.value if role_obj and hasattr(role_obj, "value") else "magnify"

            instance._room_profiles[room]  = RoomBotProfile(
                room_key     = room,
                bots         = sorted_bots,
                primary_bot  = primary,
                cognitive_role = role_str,
            )
            instance._room_to_bots[room] = sorted_bots

        logger.info(
            "BotRoomRegistry built: %d personas × %d rooms",
            len(instance._bot_cards),
            len(instance._room_profiles),
        )
        return instance

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def get_bot_card(self, persona: str) -> Optional[BotCapabilityCard]:
        """Return the capability card for *persona*, or ``None``."""
        return self._bot_cards.get(persona)

    def rooms_for_bot(self, persona: str) -> List[str]:
        """Return all rooms the bot operates in."""
        return self._bot_to_rooms.get(persona, [])

    def bots_for_room(self, room_key: str) -> List[str]:
        """Return all bots serving a room."""
        return self._room_to_bots.get(room_key, [])

    def primary_bot(self, room_key: str) -> str:
        """Return the primary bot for *room_key*."""
        profile = self._room_profiles.get(room_key)
        return profile.primary_bot if profile else "TriageBot"

    def all_personas(self) -> List[str]:
        """Return all registered persona names, sorted."""
        return sorted(self._bot_cards)

    def all_rooms(self) -> List[str]:
        """Return all rooms with at least one bot, sorted."""
        return sorted(self._room_profiles)

    def multi_room_bots(self, min_rooms: int = 5) -> List[BotCapabilityCard]:
        """Return bots that operate in at least *min_rooms* rooms."""
        return sorted(
            [c for c in self._bot_cards.values() if c.room_count >= min_rooms],
            key=lambda c: c.room_count,
            reverse=True,
        )

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict."""
        return {
            "total_personas": len(self._bot_cards),
            "total_rooms_with_bots": len(self._room_profiles),
            "personas": {
                p: {"room_count": c.room_count, "domains": c.primary_domains}
                for p, c in self._bot_cards.items()
            },
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

import threading as _threading
_default_registry: Optional[BotRoomRegistry] = None
_reg_lock = _threading.Lock()


def get_bot_room_registry() -> BotRoomRegistry:
    """Return (and lazily build) the default :class:`BotRoomRegistry`."""
    global _default_registry
    with _reg_lock:
        if _default_registry is None:
            _default_registry = BotRoomRegistry.from_manifest()
    return _default_registry


__all__ = [
    "BotCapabilityCard",
    "RoomBotProfile",
    "BotRoomRegistry",
    "get_bot_room_registry",
]
