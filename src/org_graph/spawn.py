"""R615.5 — Spawn API convenience helper.

The R615 canon: every spawn writes multiple edges:
  - SPAWNED_BY (lineage)
  - FUNCTIONAL_DELIVERABLE_OF (output flow)
  - 0+ DEPARTMENT_MEMBER_OF (constraint gates)

This module wraps those writes into a single `record_spawn()` call so
caller code (R610 shell registry, UnifiedIntegrationEngine, future
spawn flows) writes the multi-edge metadata uniformly.

Composable with R615.2 (exec_root.can_spawn) and R615.6 (constraint_gate).
Callers should check can_spawn BEFORE record_spawn, then check_function_completion
BEFORE marking work done.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from org_graph.edges import add_edge


def record_spawn(
    child_node_id: str,
    spawned_by: str,
    deliverable_for: str,
    departments: Optional[List[str]] = None,
    inherits_from: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Write the full multi-edge spawn record in one call.

    Args:
        child_node_id: the new node being spawned
        spawned_by: parent node (SPAWNED_BY edge target)
        deliverable_for: task/spec the spawn is producing for
            (FUNCTIONAL_DELIVERABLE_OF target)
        departments: list of dept_ids the child belongs to
            (one DEPARTMENT_MEMBER_OF edge per dept)
        inherits_from: list of capability nodes the child reuses
            (one INHERITS_CAPABILITY edge per source)
        metadata: optional dict attached to every edge

    Returns:
        Dict[edge_role, edge_id] for audit / rollback.
    """
    meta = metadata or {}
    edges_written: Dict[str, str] = {}

    edges_written["spawned_by"] = add_edge(
        child_node_id, spawned_by, "SPAWNED_BY", meta
    )
    edges_written["deliverable_for"] = add_edge(
        child_node_id, deliverable_for, "FUNCTIONAL_DELIVERABLE_OF", meta
    )

    for i, dept_id in enumerate(departments or []):
        edges_written[f"dept_{i}"] = add_edge(
            child_node_id, dept_id, "DEPARTMENT_MEMBER_OF", meta
        )

    for i, src in enumerate(inherits_from or []):
        edges_written[f"inherits_{i}"] = add_edge(
            child_node_id, src, "INHERITS_CAPABILITY", meta
        )

    return edges_written


__all__ = ["record_spawn"]
