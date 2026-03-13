"""
Auth Bridge for the Murphy Matrix Bridge.

Maps Matrix user IDs to Murphy RBAC roles and enforces command-level
permission checks.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from enum import Enum

from .config import MatrixBridgeConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------


class MurphyRole(str, Enum):
    """RBAC roles within the Murphy system.

    Roles are ordered from most to least privileged for comparison purposes:
    ADMIN > OPERATOR > DEVELOPER > VIEWER > BOT > GUEST.
    """

    ADMIN = "admin"
    OPERATOR = "operator"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    BOT = "bot"
    GUEST = "guest"


_ROLE_RANK: dict[MurphyRole, int] = {
    MurphyRole.ADMIN: 100,
    MurphyRole.OPERATOR: 80,
    MurphyRole.DEVELOPER: 60,
    MurphyRole.VIEWER: 40,
    MurphyRole.BOT: 20,
    MurphyRole.GUEST: 0,
}

# ---------------------------------------------------------------------------
# Command → minimum required role
# ---------------------------------------------------------------------------

COMMAND_ROLE_REQUIREMENTS: dict[str, MurphyRole] = {
    # Admin-only
    "security": MurphyRole.ADMIN,
    "keys": MurphyRole.ADMIN,
    "rbac": MurphyRole.ADMIN,
    "shutdown": MurphyRole.ADMIN,
    "restart": MurphyRole.ADMIN,
    "purge": MurphyRole.ADMIN,
    # Operator-level
    "deploy": MurphyRole.OPERATOR,
    "k8s": MurphyRole.OPERATOR,
    "docker": MurphyRole.OPERATOR,
    "scale": MurphyRole.OPERATOR,
    "rollback": MurphyRole.OPERATOR,
    "config": MurphyRole.OPERATOR,
    "recipe": MurphyRole.OPERATOR,
    "workspace": MurphyRole.OPERATOR,
    "board": MurphyRole.OPERATOR,
    "form": MurphyRole.OPERATOR,
    # Developer-level
    "execute": MurphyRole.DEVELOPER,
    "llm": MurphyRole.DEVELOPER,
    "experiment": MurphyRole.DEVELOPER,
    "timeline": MurphyRole.DEVELOPER,
    "doc": MurphyRole.DEVELOPER,
    # Viewer (any authenticated user)
    "health": MurphyRole.VIEWER,
    "status": MurphyRole.VIEWER,
    "help": MurphyRole.VIEWER,
    "version": MurphyRole.VIEWER,
    "list-modules": MurphyRole.VIEWER,
    "list-rooms": MurphyRole.VIEWER,
    "dashboard": MurphyRole.VIEWER,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class UserMapping:
    """Maps a Matrix user to Murphy RBAC roles.

    Attributes:
        matrix_user_id: Fully-qualified Matrix user ID,
            e.g. ``"@alice:example.com"``.
        murphy_user_id: Internal Murphy user identifier.
        roles: List of :class:`MurphyRole` values assigned to this user.
        granted_at: ISO-8601 UTC timestamp of when the mapping was created.
        granted_by: Matrix user ID of the administrator who created the entry.
        active: Whether this mapping is currently active.
    """

    matrix_user_id: str
    murphy_user_id: str
    roles: list[MurphyRole]
    granted_at: str
    granted_by: str
    active: bool = True


# ---------------------------------------------------------------------------
# AuthBridge
# ---------------------------------------------------------------------------


class AuthBridge:
    """Maps Matrix user IDs to Murphy RBAC roles and enforces permissions.

    Args:
        config: The active :class:`~config.MatrixBridgeConfig`.
    """

    def __init__(self, config: MatrixBridgeConfig) -> None:
        self._config = config
        self._mappings: dict[str, UserMapping] = {}
        logger.debug("AuthBridge initialised")

    # ------------------------------------------------------------------
    # Role lookups
    # ------------------------------------------------------------------

    def get_roles(self, matrix_user_id: str) -> list[MurphyRole]:
        """Return the roles assigned to a Matrix user.

        Args:
            matrix_user_id: Fully-qualified Matrix user ID.

        Returns:
            List of :class:`MurphyRole` values; empty list for unknown users.
        """
        mapping = self._mappings.get(matrix_user_id)
        if mapping is None or not mapping.active:
            return []
        return list(mapping.roles)

    def has_role(self, matrix_user_id: str, role: MurphyRole) -> bool:
        """Check whether a user holds *at least* the given role.

        Uses rank-based comparison so that an ``ADMIN`` implicitly satisfies
        an ``OPERATOR`` requirement.

        Args:
            matrix_user_id: Fully-qualified Matrix user ID.
            role: The minimum :class:`MurphyRole` required.

        Returns:
            ``True`` if the user's highest role rank >= the required rank.
        """
        user_roles = self.get_roles(matrix_user_id)
        if not user_roles:
            return False
        required_rank = _ROLE_RANK[role]
        user_rank = max(_ROLE_RANK[r] for r in user_roles)
        return user_rank >= required_rank

    def can_execute_command(self, matrix_user_id: str, command: str) -> bool:
        """Check whether a user is permitted to run a Murphy command.

        Commands not listed in :data:`COMMAND_ROLE_REQUIREMENTS` default
        to requiring the ``VIEWER`` role.

        Args:
            matrix_user_id: Fully-qualified Matrix user ID.
            command: Command token (e.g. ``"deploy"``).

        Returns:
            ``True`` if the user has sufficient privileges.
        """
        required = COMMAND_ROLE_REQUIREMENTS.get(command, MurphyRole.VIEWER)
        allowed = self.has_role(matrix_user_id, required)
        if not allowed:
            logger.info(
                "Access denied: user=%s command=%s requires=%s",
                matrix_user_id,
                command,
                required.value,
            )
        return allowed

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_mapping(self, mapping: UserMapping) -> None:
        """Add or replace a :class:`UserMapping`.

        Args:
            mapping: The :class:`UserMapping` to register.
        """
        self._mappings[mapping.matrix_user_id] = mapping
        logger.info(
            "Added user mapping: %s → roles=%s",
            mapping.matrix_user_id,
            [r.value for r in mapping.roles],
        )

    def remove_mapping(self, matrix_user_id: str) -> None:
        """Deactivate the mapping for a Matrix user.

        The record is retained but marked ``active=False`` for audit
        purposes.

        Args:
            matrix_user_id: The Matrix user ID to deactivate.
        """
        mapping = self._mappings.get(matrix_user_id)
        if mapping:
            mapping.active = False
            logger.info("Deactivated mapping for %s", matrix_user_id)
        else:
            logger.warning(
                "remove_mapping: no mapping found for %s", matrix_user_id
            )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise all user mappings to a JSON-compatible dict.

        Returns:
            Dictionary keyed by Matrix user ID.
        """
        return {
            uid: {
                **asdict(m),
                "roles": [r.value for r in m.roles],
            }
            for uid, m in self._mappings.items()
        }

    @classmethod
    def from_dict(cls, data: dict, config: MatrixBridgeConfig | None = None) -> "AuthBridge":
        """Restore an :class:`AuthBridge` from a serialised dict.

        Args:
            data: Dictionary previously produced by :meth:`to_dict`.
            config: Optional :class:`~config.MatrixBridgeConfig`.

        Returns:
            A new :class:`AuthBridge` with the stored mappings.
        """
        from .config import MatrixBridgeConfig as _Cfg  # local import

        bridge = cls(config or _Cfg())
        for uid, raw in data.items():
            raw = dict(raw)
            raw["roles"] = [MurphyRole(r) for r in raw.get("roles", [])]
            bridge._mappings[uid] = UserMapping(**raw)
        logger.debug("AuthBridge restored from dict with %d mappings", len(bridge._mappings))
        return bridge
