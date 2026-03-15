# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Subsystem Registry — MTX-REG-001

Owner: Platform Engineering

A comprehensive registry mapping **every** file and directory under
``src/`` to its Matrix room/space, HiveMind bot domain, and
set of supported commands.

Each :class:`SubsystemEntry` records:
- ``module_path``    — relative path inside ``src/``
- ``matrix_room_alias`` — target Matrix room alias
- ``matrix_space``   — parent space alias
- ``hivemind_bot``   — originating HiveMind bot persona
- ``description``    — short module description
- ``dependencies``   — key Murphy modules it depends on
- ``commands``       — ``!murphy`` command tokens that trigger this module

The registry is grouped into :class:`SubsystemDomain` objects for each
logical domain, exposed via :func:`get_registry`.  Domain data is split
across :mod:`_registry_data_a` (domains 1–13) and
:mod:`_registry_data_b` (domains 14–26) to keep file sizes manageable.

Usage::

    from matrix_bridge.subsystem_registry import get_registry

    reg = get_registry()
    entry = reg.get("security_audit_scanner")
    print(entry.matrix_room_alias)   # murphy-security-alerts

    entries = reg.by_space("murphy-security")
    for e in entries:
        print(e.module_path)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ._registry_data_a import _DOMAINS_A
from ._registry_data_b import _DOMAINS_B
from ._registry_types import SubsystemDomain, SubsystemEntry

logger = logging.getLogger(__name__)

# Combined ordered domain list used by the registry singleton.
_DOMAINS: List[SubsystemDomain] = _DOMAINS_A + _DOMAINS_B


# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------


class SubsystemRegistry:
    """Central registry mapping every Murphy module to its Matrix coordinates.

    Build once via :func:`get_registry`, then query:

    * :meth:`get` — by module_path key
    * :meth:`by_space` — all entries for a Matrix space
    * :meth:`by_bot` — all entries for a HiveMind bot
    * :meth:`by_command` — all entries that handle a command token
    * :meth:`all_entries` — flat list of all entries
    """

    def __init__(self, domains: List[SubsystemDomain]) -> None:
        self._by_module: Dict[str, SubsystemEntry] = {}
        self._domains = domains
        for domain in domains:
            for entry in domain.entries:
                # Use module_path as the primary key (skip duplicates)
                self._by_module.setdefault(entry.module_path, entry)

    # -----------------------------------------------------------------------
    # Lookups
    # -----------------------------------------------------------------------

    def get(self, module_path: str) -> Optional[SubsystemEntry]:
        """Return the :class:`SubsystemEntry` for *module_path*, or ``None``."""
        return self._by_module.get(module_path)

    def all_entries(self) -> List[SubsystemEntry]:
        """Return a flat list of all registered entries."""
        return list(self._by_module.values())

    def all_modules(self) -> List[str]:
        """Return all registered module path keys."""
        return list(self._by_module.keys())

    def by_space(self, space_alias: str) -> List[SubsystemEntry]:
        """Return all entries whose ``matrix_space`` matches *space_alias*."""
        return [e for e in self._by_module.values() if e.matrix_space == space_alias]

    def by_bot(self, hivemind_bot: str) -> List[SubsystemEntry]:
        """Return all entries whose ``hivemind_bot`` matches *hivemind_bot*."""
        return [e for e in self._by_module.values() if e.hivemind_bot == hivemind_bot]

    def by_room(self, room_alias: str) -> List[SubsystemEntry]:
        """Return all entries whose ``matrix_room_alias`` matches *room_alias*."""
        return [e for e in self._by_module.values() if e.matrix_room_alias == room_alias]

    def by_command(self, command: str) -> List[SubsystemEntry]:
        """Return all entries that list *command* in their ``commands``."""
        cmd = command.lower()
        return [e for e in self._by_module.values() if cmd in e.commands]

    def packages(self) -> List[SubsystemEntry]:
        """Return all entries that represent sub-packages (``is_package=True``)."""
        return [e for e in self._by_module.values() if e.is_package]

    def modules(self) -> List[SubsystemEntry]:
        """Return all entries that represent individual modules."""
        return [e for e in self._by_module.values() if not e.is_package]

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def stats(self) -> Dict[str, object]:
        """Return registry statistics."""
        bots: Dict[str, int] = {}
        for e in self._by_module.values():
            bots[e.hivemind_bot] = bots.get(e.hivemind_bot, 0) + 1
        return {
            "total_entries": len(self._by_module),
            "packages": len(self.packages()),
            "modules": len(self.modules()),
            "domains": len(self._domains),
            "by_bot": bots,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_registry_singleton: Optional[SubsystemRegistry] = None


def get_registry() -> SubsystemRegistry:
    """Return the (lazily created) singleton :class:`SubsystemRegistry`."""
    global _registry_singleton  # noqa: PLW0603
    if _registry_singleton is None:
        _registry_singleton = SubsystemRegistry(_DOMAINS)
    return _registry_singleton


def reset_registry() -> None:
    """Clear the cached registry singleton (useful in tests)."""
    global _registry_singleton  # noqa: PLW0603
    _registry_singleton = None
