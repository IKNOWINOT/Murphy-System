"""
Collaboration System – @Mention Parser
========================================

Extracts @mentions from comment text and resolves them to users/teams.

Mention Syntax:
- ``@username`` — mention a specific user
- ``@team:teamname`` — mention a team
- ``@everyone`` — mention all board members

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from .models import Mention, MentionType

# Pattern: @username, @team:teamname, @everyone
_MENTION_RE = re.compile(
    r"@(everyone|team:[\w.-]+|[\w.-]+)",
    re.UNICODE,
)


class UserResolver:
    """Pluggable user/team name resolver.

    Register lookup callbacks via :meth:`register_user_lookup` and
    :meth:`register_team_lookup`.  If no resolver is registered the raw
    identifier is used as both ``target_id`` and ``target_name``.
    """

    def __init__(self) -> None:
        self._user_lookup: Optional[Callable[[str], Optional[Dict[str, str]]]] = None
        self._team_lookup: Optional[Callable[[str], Optional[Dict[str, str]]]] = None

    def register_user_lookup(self, fn: Callable[[str], Optional[Dict[str, str]]]) -> None:
        self._user_lookup = fn

    def register_team_lookup(self, fn: Callable[[str], Optional[Dict[str, str]]]) -> None:
        self._team_lookup = fn

    def resolve_user(self, username: str) -> Dict[str, str]:
        if self._user_lookup:
            result = self._user_lookup(username)
            if result:
                return result
        return {"id": username, "name": username}

    def resolve_team(self, teamname: str) -> Dict[str, str]:
        if self._team_lookup:
            result = self._team_lookup(teamname)
            if result:
                return result
        return {"id": teamname, "name": teamname}


# Module-level default resolver (can be replaced)
_default_resolver = UserResolver()


def get_default_resolver() -> UserResolver:
    """Return the module-level default resolver."""
    return _default_resolver


def parse_mentions(text: str, resolver: Optional[UserResolver] = None) -> List[Mention]:
    """Extract all @mentions from *text* and resolve them.

    Returns a list of :class:`Mention` instances with ``offset`` and
    ``length`` pointing into the original *text*.
    """
    if resolver is None:
        resolver = _default_resolver

    mentions: List[Mention] = []
    for match in _MENTION_RE.finditer(text):
        raw = match.group(1)
        offset = match.start()
        length = match.end() - match.start()

        if raw == "everyone":
            mentions.append(Mention(
                mention_type=MentionType.EVERYONE,
                target_id="everyone",
                target_name="everyone",
                offset=offset,
                length=length,
            ))
        elif raw.startswith("team:"):
            teamname = raw[5:]
            info = resolver.resolve_team(teamname)
            mentions.append(Mention(
                mention_type=MentionType.TEAM,
                target_id=info["id"],
                target_name=info["name"],
                offset=offset,
                length=length,
            ))
        else:
            info = resolver.resolve_user(raw)
            mentions.append(Mention(
                mention_type=MentionType.USER,
                target_id=info["id"],
                target_name=info["name"],
                offset=offset,
                length=length,
            ))

    return mentions
