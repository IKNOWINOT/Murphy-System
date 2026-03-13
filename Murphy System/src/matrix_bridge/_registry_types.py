# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Subsystem Registry — Base Types (MTX-REG-TYPES)

Owner: Platform Engineering

Shared dataclasses and helper used by the subsystem registry data modules.
Imported by ``_registry_data_a.py``, ``_registry_data_b.py``, and
``subsystem_registry.py``.  Has no intra-package imports to avoid
circular dependencies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry dataclass
# ---------------------------------------------------------------------------


@dataclass
class SubsystemEntry:
    """Registry record for one Murphy module or sub-package.

    Attributes
    ----------
    module_path:
        Path relative to ``src/``, e.g. ``security_audit_scanner``.
    matrix_room_alias:
        Target Matrix room alias.
    matrix_space:
        Parent Matrix space alias.
    hivemind_bot:
        HiveMind bot responsible for this module.
    description:
        One-line description.
    dependencies:
        Other Murphy modules this module relies on.
    commands:
        ``!murphy`` sub-command tokens that address this module.
    is_package:
        ``True`` if this entry represents a sub-package (directory).
    """

    module_path: str
    matrix_room_alias: str
    matrix_space: str
    hivemind_bot: str = ""
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    is_package: bool = False


# ---------------------------------------------------------------------------
# Domain grouping
# ---------------------------------------------------------------------------


@dataclass
class SubsystemDomain:
    """A logical grouping of :class:`SubsystemEntry` objects."""

    name: str
    space_alias: str
    hivemind_bot: str
    entries: List[SubsystemEntry] = field(default_factory=list)

    def add(self, entry: SubsystemEntry) -> None:
        self.entries.append(entry)


# ---------------------------------------------------------------------------
# Helper builder
# ---------------------------------------------------------------------------


def _e(
    module_path: str,
    room: str,
    space: str,
    bot: str = "",
    desc: str = "",
    deps: Optional[List[str]] = None,
    cmds: Optional[List[str]] = None,
    pkg: bool = False,
) -> SubsystemEntry:
    """Compact factory for :class:`SubsystemEntry` objects."""
    return SubsystemEntry(
        module_path=module_path,
        matrix_room_alias=room,
        matrix_space=space,
        hivemind_bot=bot,
        description=desc,
        dependencies=deps or [],
        commands=cmds or [],
        is_package=pkg,
    )
