"""R615.2 — Exec-root validator.

The R615 canon non-negotiable: every task tree MUST root at an executive
position. No spawn may originate from a node whose ancestry doesn't trace
back to {platform_ceo, platform_cto, platform_cfo, platform_cso}.

This module provides:
- EXEC_POSITIONS: the canonical set of root positions.
- can_spawn(parent_node, lineage_lookup) -> (bool, root_position_id):
  walks SPAWNED_BY lineage upward, returns whether spawn is permitted
  and the discovered root position.

Lineage lookup is dependency-injected so this module stays storage-agnostic
(works with dlf_r weaves, with the agent_substrate shell_registry, or with
a future task_lineage table). The caller passes a function:
    lineage_lookup(node_id) -> Optional[parent_node_id]
"""
from __future__ import annotations
from typing import Callable, Optional, Tuple

# Canonical executive positions — R615 canon, R610 shell-registry compatible.
EXEC_POSITIONS = frozenset({
    "platform_ceo",
    "platform_cto",
    "platform_cfo",
    "platform_cso",
})

# Safety cap on lineage chain walk — prevents infinite loops on bad data.
MAX_LINEAGE_DEPTH = 64


def is_exec(position_id: Optional[str]) -> bool:
    """True iff position_id is one of the canonical executive positions."""
    return position_id in EXEC_POSITIONS


def can_spawn(
    parent_node_id: str,
    lineage_lookup: Callable[[str], Optional[str]],
    position_of: Callable[[str], Optional[str]],
) -> Tuple[bool, Optional[str]]:
    """Walk SPAWNED_BY lineage from parent_node_id to its root.

    Args:
        parent_node_id: node attempting to spawn a child.
        lineage_lookup: function (node_id) -> parent_node_id or None at root.
        position_of: function (node_id) -> position_id (e.g. "platform_cto").

    Returns:
        (allowed: bool, root_position_id: Optional[str])
        - allowed=True iff the root position is in EXEC_POSITIONS.
        - root_position_id is whatever the root resolves to (for audit).
    """
    current = parent_node_id
    seen = set()
    depth = 0
    while current is not None and depth < MAX_LINEAGE_DEPTH:
        if current in seen:
            # Cycle in lineage — treat as invalid root.
            return False, None
        seen.add(current)
        parent = lineage_lookup(current)
        if parent is None:
            # Reached the root.
            root_pos = position_of(current)
            return is_exec(root_pos), root_pos
        current = parent
        depth += 1
    # Hit depth cap without finding a root — fail closed.
    return False, None


def can_spawn_multi(
    parent_node_id: str,
    lineages_lookup,
    position_of,
) -> tuple:
    """R615 multi-edge variant of can_spawn.

    A node can have multiple SPAWNED_BY parents in the R615 multi-edge
    graph. This variant walks ALL ancestry chains and requires at least
    ONE of them to root at an executive position.

    Args:
        parent_node_id: node attempting to spawn a child.
        lineages_lookup: function (node_id) -> List[parent_node_id].
            Returns [] at root.
        position_of: function (node_id) -> Optional[position_id].

    Returns:
        (allowed: bool, root_position_ids: List[str])
        - allowed=True iff at least one ancestry chain roots at an exec.
        - root_position_ids: every distinct root position discovered.
    """
    seen = set()
    roots = []
    # BFS over multi-parent lineage
    queue = [(parent_node_id, 0)]
    while queue:
        node, depth = queue.pop(0)
        if depth > MAX_LINEAGE_DEPTH:
            continue
        if node in seen:
            continue
        seen.add(node)
        parents = lineages_lookup(node) or []
        if not parents:
            # This node is a root in its chain
            pos = position_of(node)
            if pos:
                roots.append(pos)
            continue
        for p in parents:
            queue.append((p, depth + 1))
    allowed = any(is_exec(r) for r in roots)
    # Dedupe roots, preserve order
    seen_roots = set()
    distinct = []
    for r in roots:
        if r not in seen_roots:
            seen_roots.add(r)
            distinct.append(r)
    return allowed, distinct


__all__ = ["EXEC_POSITIONS", "MAX_LINEAGE_DEPTH", "is_exec", "can_spawn", "can_spawn_multi"]

