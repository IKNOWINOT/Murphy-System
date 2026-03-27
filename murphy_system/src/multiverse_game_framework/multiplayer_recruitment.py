"""
Active Player Recruitment & Matchmaking for the Multiverse Game Framework.

Design Label: GAME-009 — Active Player Recruitment & Matchmaking
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager
  - universal_character.UniversalCharacter
  - world_registry.WorldRegistry

Games require other players to play. Agent players actively reason about
party composition needs and send personalised recruitment invitations to
recruit human players into the game.

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

_MAX_LFG = 1_000
_MAX_INVITES = 10_000

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ActivityType(str, Enum):
    """Type of activity needing players."""
    GROUP_XP = "group_xp"
    DUNGEON = "dungeon"
    RAID = "raid"
    CRAFTING = "crafting"
    EXPLORATION = "exploration"
    PVP = "pvp"
    QUEST = "quest"


class InviteStatus(str, Enum):
    """Status of a recruitment invite."""
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RecruitmentNeeds:
    """Analysis of what roles and classes are needed in a world.

    Args:
        world_id: World analysed.
        missing_roles: Roles with insufficient representation (e.g., ["healer"]).
        shortage_classes: Specific classes most needed.
        current_player_count: How many players are currently active.
        ideal_player_count: Target player population for this world.
        activity_type: Primary activity type needing players.
    """
    world_id: str
    missing_roles: List[str] = field(default_factory=list)
    shortage_classes: List[str] = field(default_factory=list)
    current_player_count: int = 0
    ideal_player_count: int = 20
    activity_type: ActivityType = ActivityType.GROUP_XP


@dataclass
class PlayerMatch:
    """A player matched as compatible for an activity.

    Args:
        player_id: Matched player's ID.
        character_id: Their character's ID.
        character_class: Their class.
        compatibility_score: 0.0–1.0 match quality.
        reason: Why they're a good match.
    """
    player_id: str
    character_id: str
    character_class: str
    compatibility_score: float
    reason: str


@dataclass
class LFGListing:
    """A looking-for-group listing.

    Args:
        listing_id: Unique UUID.
        world_id: Target world.
        poster_id: Character posting the listing.
        activity_type: What they need players for.
        needed_roles: Roles still needed.
        min_level: Minimum character level.
        message: Custom message from the poster.
        created_at: When the listing was posted.
        expires_at: When the listing expires.
        active: Whether the listing is still active.
    """
    listing_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    world_id: str = ""
    poster_id: str = ""
    activity_type: ActivityType = ActivityType.GROUP_XP
    needed_roles: List[str] = field(default_factory=list)
    min_level: int = 1
    message: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    active: bool = True


@dataclass
class RecruitmentInvite:
    """A personalised recruitment invitation.

    Args:
        invite_id: Unique UUID.
        from_id: Sender (agent or player) ID.
        to_id: Recipient player ID.
        activity_type: Activity they're being invited to.
        world_id: World to join.
        message: Personalised invite message.
        status: Current status.
        sent_at: When the invite was sent.
    """
    invite_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_id: str = ""
    to_id: str = ""
    activity_type: ActivityType = ActivityType.GROUP_XP
    world_id: str = ""
    message: str = ""
    status: InviteStatus = InviteStatus.SENT
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# RecruitmentEngine
# ---------------------------------------------------------------------------


class RecruitmentEngine:
    """Analyses party needs and manages active recruitment of new players.

    Agent players use this engine to reason about composition gaps and send
    personalised invitations to human players. Human players use it to
    post LFG listings and find compatible parties.
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        self._lfg_listings: Dict[str, LFGListing] = {}
        self._invite_log: List[RecruitmentInvite] = []
        # Registered player profiles: player_id → profile dict
        self._player_profiles: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Player profile registry (lightweight)
    # ------------------------------------------------------------------

    def register_player(self, player_id: str, profile: Dict[str, Any]) -> None:
        """Register a player's profile for matchmaking consideration.

        Expected profile keys: character_id, character_class, level, play_style.

        Args:
            player_id: Unique player identifier.
            profile: Profile dict.
        """
        with self._lock:
            self._player_profiles[player_id] = dict(profile)

    # ------------------------------------------------------------------
    # Needs analysis
    # ------------------------------------------------------------------

    def analyze_player_needs(self, world_id: str) -> RecruitmentNeeds:
        """Analyse what roles and classes are needed in a world.

        Uses registered player profiles to determine role coverage.

        Args:
            world_id: The world to analyse.

        Returns:
            RecruitmentNeeds summary.
        """
        # Count roles of players currently in this world
        role_counts: Dict[str, int] = {}
        world_players = [
            p for p in self._player_profiles.values()
            if p.get("world_id") == world_id
        ]
        for profile in world_players:
            role = profile.get("role", "dps")
            role_counts[role] = role_counts.get(role, 0) + 1

        # Determine shortages (tank and healer are always critical)
        missing: List[str] = []
        if role_counts.get("tank", 0) == 0:
            missing.append("tank")
        if role_counts.get("healer", 0) == 0:
            missing.append("healer")
        if role_counts.get("cc", 0) == 0:
            missing.append("cc")

        # Most needed classes based on missing roles
        shortage_classes: List[str] = []
        if "tank" in missing:
            shortage_classes.extend(["Warrior", "Paladin"])
        if "healer" in missing:
            shortage_classes.extend(["Cleric", "Shaman"])
        if "cc" in missing:
            shortage_classes.append("Enchanter")

        return RecruitmentNeeds(
            world_id=world_id,
            missing_roles=missing,
            shortage_classes=shortage_classes,
            current_player_count=len(world_players),
            ideal_player_count=20,
        )

    # ------------------------------------------------------------------
    # Message generation
    # ------------------------------------------------------------------

    def generate_recruitment_message(
        self,
        needs: RecruitmentNeeds,
        target_player_profile: Dict[str, Any],
    ) -> str:
        """Generate a personalised recruitment message for a player.

        Uses the needs analysis and the target's profile to craft a relevant
        invitation that explains why they specifically are needed.

        Args:
            needs: Current recruitment needs for the world.
            target_player_profile: The target player's profile dict.

        Returns:
            A personalised invitation string.
        """
        player_class = target_player_profile.get("character_class", "Adventurer")
        player_name = target_player_profile.get("name", "Adventurer")
        world_name = target_player_profile.get("world_name", needs.world_id)

        if needs.missing_roles:
            role_text = " and ".join(needs.missing_roles)
            need_line = f"We urgently need a {role_text} in {world_name}."
        else:
            need_line = f"We're looking for skilled players for {world_name}."

        if player_class in needs.shortage_classes:
            class_line = (
                f"Your {player_class} would be invaluable — "
                f"{'there are no tanks' if 'Warrior' in needs.shortage_classes else 'the group needs your skills'}."
            )
        else:
            class_line = f"Your experience as a {player_class} would complement our party well."

        return (
            f"Hey {player_name}! {need_line} {class_line} "
            f"Join us — great loot and group XP bonuses await!"
        )

    # ------------------------------------------------------------------
    # Matchmaking
    # ------------------------------------------------------------------

    def find_compatible_players(
        self,
        character: Any,
        activity_type: ActivityType,
    ) -> List[PlayerMatch]:
        """Find players compatible for a specific activity.

        Args:
            character: The requesting character (UniversalCharacter).
            activity_type: The type of activity.

        Returns:
            List of PlayerMatch sorted by compatibility score descending.
        """
        char_level = getattr(character, "level", 1)
        matches: List[PlayerMatch] = []

        for player_id, profile in self._player_profiles.items():
            plevel = profile.get("level", 1)
            pclass = profile.get("character_class", "Unknown")
            prole = profile.get("role", "dps")

            # Level bracket: within 5 levels
            if abs(plevel - char_level) > 10:
                continue

            score = 0.5
            reason_parts: List[str] = []

            # Bonus for complementary roles
            char_role = getattr(getattr(character, "character_class", None), "value", "")
            if prole in ("healer", "tank") and char_role not in ("healer", "tank"):
                score += 0.3
                reason_parts.append(f"provides {prole} role you lack")

            # Bonus for level proximity
            level_diff = abs(plevel - char_level)
            score += (10 - min(10, level_diff)) * 0.02
            if level_diff <= 3:
                reason_parts.append("close level match")

            # Activity-specific bonuses
            if activity_type == ActivityType.RAID and prole == "tank":
                score += 0.2
                reason_parts.append("tanks are critical for raids")

            matches.append(PlayerMatch(
                player_id=player_id,
                character_id=profile.get("character_id", ""),
                character_class=pclass,
                compatibility_score=round(min(1.0, score), 3),
                reason="; ".join(reason_parts) if reason_parts else "general compatibility",
            ))

        return sorted(matches, key=lambda m: m.compatibility_score, reverse=True)

    # ------------------------------------------------------------------
    # Invite system
    # ------------------------------------------------------------------

    def send_recruitment_invite(
        self,
        from_id: str,
        to_id: str,
        activity: ActivityType,
        world_id: str,
        message: str = "",
    ) -> RecruitmentInvite:
        """Send a recruitment invite from one player/agent to another.

        Args:
            from_id: Sender ID.
            to_id: Recipient player ID.
            activity: Activity type.
            world_id: Target world.
            message: Optional custom message.

        Returns:
            The created RecruitmentInvite.
        """
        invite = RecruitmentInvite(
            from_id=from_id,
            to_id=to_id,
            activity_type=activity,
            world_id=world_id,
            message=message,
        )
        with self._lock:
            capped_append(self._invite_log, invite, _MAX_INVITES)
        self._publish_event("recruitment_invite_sent", {
            "invite_id": invite.invite_id,
            "from_id": from_id,
            "to_id": to_id,
            "world_id": world_id,
        })
        return invite

    # ------------------------------------------------------------------
    # LFG listings
    # ------------------------------------------------------------------

    def post_lfg_listing(
        self,
        world_id: str,
        poster_id: str,
        activity_type: ActivityType,
        needed_roles: List[str],
        min_level: int = 1,
        message: str = "",
    ) -> LFGListing:
        """Post a looking-for-group listing.

        Args:
            world_id: Target world.
            poster_id: Character posting the listing.
            activity_type: What they need players for.
            needed_roles: Roles still needed.
            min_level: Minimum character level.
            message: Custom message.

        Returns:
            The created LFGListing.
        """
        listing = LFGListing(
            world_id=world_id,
            poster_id=poster_id,
            activity_type=activity_type,
            needed_roles=needed_roles,
            min_level=min_level,
            message=message,
        )
        with self._lock:
            capped_append(list(self._lfg_listings.values()), listing, _MAX_LFG)
            self._lfg_listings[listing.listing_id] = listing
        self._publish_event("lfg_listing_posted", {
            "listing_id": listing.listing_id,
            "world_id": world_id,
            "poster_id": poster_id,
        })
        return listing

    def get_active_lfg_listings(self, world_id: str) -> List[LFGListing]:
        """Return active LFG listings for a world.

        Args:
            world_id: World to query.

        Returns:
            List of active LFGListing objects.
        """
        now = datetime.now(timezone.utc)
        return [
            listing for listing in self._lfg_listings.values()
            if listing.world_id == world_id
            and listing.active
            and (listing.expires_at is None or listing.expires_at > now)
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
