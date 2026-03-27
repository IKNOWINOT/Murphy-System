# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Space Manager — manages Matrix Spaces for the Murphy System.

Creates a top-level ``Murphy System`` space with sub-spaces for each
subsystem category, and manages room membership within those spaces.

Matrix Spaces require ``matrix-nio >= 0.20`` and a homeserver with Spaces
support (MSC1772 / stable).

Power levels
------------
Bot users receive PL 100 (admin) so they can manage the space structure.
Human admin users receive PL 50 (moderator) by default.
Regular users receive PL 0.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .matrix_client import MatrixClient
from .room_registry import SUBSYSTEM_ROOMS, RoomRegistry

logger = logging.getLogger(__name__)

#: Power level for bot accounts (admin)
PL_BOT = 100
#: Power level for human admin users
PL_ADMIN = 50
#: Power level for regular users
PL_USER = 0

# ---------------------------------------------------------------------------
# Category display names
# ---------------------------------------------------------------------------

CATEGORY_DISPLAY: Dict[str, str] = {
    "core-engines":          "Core Engines",
    "governance":            "Governance & Compliance",
    "safety-hitl":           "Safety & HITL",
    "automation":            "Automation & Execution",
    "llm-ai":                "LLM & AI",
    "swarm-agents":          "Swarm & Agent Systems",
    "business-finance":      "Business & Finance",
    "comms-notifications":   "Communication & Notifications",
    "infrastructure":        "Infrastructure & DevOps",
    "security":              "Security",
    "data-knowledge":        "Data & Knowledge",
    "monitoring":            "Monitoring & Observability",
    "self-healing":          "Self-Healing & Resilience",
    "domain-expert":         "Domain & Expert Systems",
    "org-workflow":          "Org & Workflow",
    "module-system":         "Module System",
    "misc-systems":          "Misc Systems",
    "runtime-state":         "Runtime & State",
    "integrations-adapters": "Integration & Adapters",
    "iot-industrial":        "IoT & Industrial",
    "crm-account":           "CRM & Account",
    "board-portfolio":       "Board & Portfolio",
    "comms-subsystems":      "Communication Subsystems",
    "additional":            "Additional Systems",
    "system":                "System Rooms",
}


@dataclass
class SpaceInfo:
    """Metadata about a Murphy Matrix space."""

    category: str
    display_name: str
    space_id: Optional[str] = field(default=None)
    room_ids: List[str] = field(default_factory=list)


class SpaceManager:
    """Creates and manages the Murphy Matrix Spaces hierarchy.

    Hierarchy::

        Murphy System (top-level space)
        ├── Core Engines (sub-space)
        │   ├── #murphy-confidence-engine:domain
        │   └── ...
        ├── Security (sub-space, encrypted)
        │   ├── #murphy-security-plane:domain
        │   └── ...
        └── ...

    Parameters
    ----------
    client:
        Connected :class:`~murphy.matrix_bridge.MatrixClient`.
    registry:
        :class:`~murphy.matrix_bridge.RoomRegistry` with room IDs populated.
    space_name:
        Top-level space display name.  Defaults to ``MATRIX_SPACE_NAME`` env
        var or ``"murphy_system"``.
    admin_users:
        Matrix user IDs to grant ``PL_ADMIN`` in all spaces.
    """

    def __init__(
        self,
        client: MatrixClient,
        registry: RoomRegistry,
        space_name: Optional[str] = None,
        admin_users: Optional[List[str]] = None,
    ) -> None:
        self._client = client
        self._registry = registry
        self.space_name: str = (
            space_name
            or os.environ.get("MATRIX_SPACE_NAME", "murphy_system")
        )
        raw_admins = os.environ.get("MATRIX_ADMIN_USERS", "")
        self.admin_users: List[str] = admin_users or [
            u.strip() for u in raw_admins.split(",") if u.strip()
        ]
        self._top_level_space_id: Optional[str] = None
        self._sub_spaces: Dict[str, SpaceInfo] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_all_spaces(self) -> Dict[str, Optional[str]]:
        """Create the top-level space and all category sub-spaces.

        Returns ``category → space_id`` mapping.
        """
        self._top_level_space_id = await self._ensure_space(
            alias="murphy-system",
            name=self.space_name,
            topic="Murphy System — Complete Automation Platform",
        )

        results: Dict[str, Optional[str]] = {
            "__top__": self._top_level_space_id
        }

        for category, display_name in CATEGORY_DISPLAY.items():
            alias = f"murphy-space-{category}"
            space_id = await self._ensure_space(
                alias=alias,
                name=display_name,
                topic=f"Murphy System — {display_name}",
            )
            info = self._sub_spaces.setdefault(
                category,
                SpaceInfo(category=category, display_name=display_name),
            )
            info.space_id = space_id
            results[category] = space_id

            # Add sub-space to top-level space
            if self._top_level_space_id and space_id:
                await self._add_child_to_space(self._top_level_space_id, space_id)

        # Populate sub-spaces with their rooms
        await self._add_rooms_to_spaces()

        return results

    async def get_space_id(self, category: str) -> Optional[str]:
        """Return the space ID for *category*, or ``None``."""
        return self._sub_spaces.get(category, SpaceInfo(category=category, display_name="")).space_id

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all spaces."""
        return {
            "top_level": self._top_level_space_id,
            "sub_spaces": {
                cat: {"display": info.display_name, "space_id": info.space_id}
                for cat, info in self._sub_spaces.items()
            },
        }

    # ------------------------------------------------------------------
    # Power levels
    # ------------------------------------------------------------------

    async def set_power_levels(self, room_id: str, users: Dict[str, int]) -> bool:
        """Set power levels for *users* in *room_id*.

        *users* maps Matrix user IDs to their desired power level.
        """
        if not self._client.is_connected():
            return False
        try:
            content: Dict[str, Any] = {
                "users": users,
                "users_default": PL_USER,
                "events_default": PL_USER,
                "state_default": PL_ADMIN,
                "ban": PL_ADMIN,
                "kick": PL_ADMIN,
                "redact": PL_ADMIN,
                "invite": PL_USER,
            }
            await self._client._client.room_put_state(  # type: ignore[union-attr]
                room_id, "m.room.power_levels", content
            )
            return True
        except Exception as exc:
            logger.warning("set_power_levels(%s) failed: %s", room_id, exc)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_space(
        self, alias: str, name: str, topic: str = ""
    ) -> Optional[str]:
        """Create a Matrix Space (room with ``m.space`` type)."""
        creation_content = {"type": "m.space"}
        try:
            room_id = await self._client.create_room(
                alias=alias,
                name=name,
                topic=topic,
                is_public=False,
                invite=self.admin_users,
            )
            if room_id:
                # Mark the room as a space via state event
                try:
                    await self._client._client.room_put_state(  # type: ignore[union-attr]
                        room_id,
                        "m.room.create",
                        creation_content,
                    )
                except Exception as exc:
                    logger.debug("Non-critical error: %s", exc)
            return room_id
        except Exception as exc:
            logger.warning("_ensure_space(%s) failed: %s", alias, exc)
            return None

    async def _add_child_to_space(self, space_id: str, child_id: str) -> None:
        """Add *child_id* as a child of *space_id*."""
        try:
            await self._client._client.room_put_state(  # type: ignore[union-attr]
                space_id,
                "m.space.child",
                {"via": [self._registry.domain], "suggested": True},
                state_key=child_id,
            )
        except Exception as exc:
            logger.debug("_add_child_to_space(%s, %s) failed: %s", space_id, child_id, exc)

    async def _add_rooms_to_spaces(self) -> None:
        """Add every room to its category sub-space."""
        for subsystem, (category, _encrypted) in SUBSYSTEM_ROOMS.items():
            room_id = self._registry.get_room_id(subsystem)
            info = self._sub_spaces.get(category)
            if room_id and info and info.space_id:
                await self._add_child_to_space(info.space_id, room_id)
                if room_id not in info.room_ids:
                    info.room_ids.append(room_id)


__all__ = ["SpaceManager", "SpaceInfo", "CATEGORY_DISPLAY", "PL_BOT", "PL_ADMIN", "PL_USER"]
