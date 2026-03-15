"""
Board System – Permissions
============================

Role-based access control for boards, groups, and items.
Supports user-level and team-level permission grants.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import Board, BoardPermission, Permission

# Permission hierarchy: ADMIN > EDIT_STRUCTURE > EDIT > VIEW
_PERMISSION_RANK: Dict[Permission, int] = {
    Permission.VIEW: 1,
    Permission.EDIT: 2,
    Permission.EDIT_STRUCTURE: 3,
    Permission.ADMIN: 4,
}


class PermissionManager:
    """Evaluates and manages board-level permissions."""

    @staticmethod
    def has_permission(
        board: Board,
        user_id: str,
        required: Permission,
        user_teams: Optional[List[str]] = None,
    ) -> bool:
        """Check whether *user_id* holds at least *required* permission on *board*.

        The owner always has ADMIN access.  Otherwise the highest grant
        across user and team permissions is used.
        """
        if board.owner_id == user_id:
            return True

        best_rank = 0
        for perm in board.permissions:
            if perm.user_id == user_id:
                best_rank = max(best_rank, _PERMISSION_RANK.get(perm.permission, 0))
            if user_teams and perm.team_id in user_teams:
                best_rank = max(best_rank, _PERMISSION_RANK.get(perm.permission, 0))

        return best_rank >= _PERMISSION_RANK.get(required, 0)

    @staticmethod
    def grant(
        board: Board,
        *,
        user_id: str = "",
        team_id: str = "",
        permission: Permission = Permission.VIEW,
        granted_by: str = "",
    ) -> BoardPermission:
        """Grant a permission to a user or team on *board*.

        If an existing grant for the same user/team exists it is replaced.
        """
        # Remove previous grant for this user/team
        board.permissions = [
            p for p in board.permissions
            if not (p.user_id == user_id and p.team_id == team_id)
            or (not user_id and not team_id)
        ]
        bp = BoardPermission(
            user_id=user_id,
            team_id=team_id,
            permission=permission,
            granted_by=granted_by,
        )
        board.permissions.append(bp)
        return bp

    @staticmethod
    def revoke(board: Board, *, user_id: str = "", team_id: str = "") -> bool:
        """Remove all permission grants for a user or team.

        Returns ``True`` if at least one grant was removed.
        """
        before = len(board.permissions)
        board.permissions = [
            p for p in board.permissions
            if not (
                (user_id and p.user_id == user_id)
                or (team_id and p.team_id == team_id)
            )
        ]
        return len(board.permissions) < before

    @staticmethod
    def effective_permission(
        board: Board,
        user_id: str,
        user_teams: Optional[List[str]] = None,
    ) -> Optional[Permission]:
        """Return the effective (highest) permission for *user_id*."""
        if board.owner_id == user_id:
            return Permission.ADMIN

        best: Optional[Permission] = None
        best_rank = 0
        for perm in board.permissions:
            match = (perm.user_id == user_id) or (
                user_teams and perm.team_id in user_teams
            )
            if match:
                rank = _PERMISSION_RANK.get(perm.permission, 0)
                if rank > best_rank:
                    best_rank = rank
                    best = perm.permission
        return best
