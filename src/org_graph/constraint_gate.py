"""R615.6 — Constraint gate at function completion.

The R615 canon: DEPARTMENT_MEMBER_OF edges are CONSTRAINT GATES. Before
marking a FUNCTIONAL_DELIVERABLE_OF edge complete, walk the node's
department memberships and run each department's constraint check. If
any check fails, halt and surface to HITL.

V1 implementation (this round):
- For each DEPARTMENT_MEMBER_OF edge on the node, look up the department.
- Check the department's `constraint_set_version` and `observer_status`.
- Run any registered constraint checkers for that dept (extensible
  registry; defaults pass-through if no checker registered yet).
- Return (allowed: bool, blockers: List[str]) — if not allowed, caller
  must NOT mark function complete and SHOULD surface to HITL.

The constraint check registry is intentionally extensible: ambient
observers (R615.9, v2) will register learned constraints here. For
now, we ship a sensible default + manual override.
"""
from __future__ import annotations
from typing import Callable, Dict, List, Tuple
import sqlite3

DB_PATH = "/var/lib/murphy-production/agent_substrate.db"

# Registry of constraint checkers per department.
# Signature: checker(node_id, dept_row) -> (passed: bool, reason: str)
# An empty registry means all gates default-pass (safe v1 stance: don't
# block work until ambient layer is built).
_CONSTRAINT_CHECKERS: Dict[str, Callable] = {}


def register_constraint_checker(dept_id: str, checker: Callable) -> None:
    """Register a constraint checker for a department.

    Used by ambient observers (R615.9) and manual configuration.
    """
    _CONSTRAINT_CHECKERS[dept_id] = checker


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def check_function_completion(node_id: str) -> Tuple[bool, List[str]]:
    """Gate: can this node mark its FUNCTIONAL_DELIVERABLE_OF complete?

    Walks the node's DEPARTMENT_MEMBER_OF edges, runs each dept's
    constraint checker, and aggregates results.

    Returns:
        (allowed: bool, blockers: List[str])
        - allowed=True iff every department's checker passed.
        - blockers: list of human-readable reasons for any failures.
          Always populated when allowed=False; may be empty when True.
    """
    # Import here to avoid circular import on package init
    from org_graph.edges import find_edges_from

    dept_edges = find_edges_from(node_id, edge_type="DEPARTMENT_MEMBER_OF")
    if not dept_edges:
        # No department membership = no constraints. Safe pass.
        return True, []

    blockers: List[str] = []
    with _conn() as c:
        for edge in dept_edges:
            dept_id = edge["to_node"]
            row = c.execute(
                "SELECT dept_id, name, domain, constraint_set_version, observer_status "
                "FROM departments WHERE dept_id=?",
                (dept_id,),
            ).fetchone()
            if not row:
                blockers.append(
                    f"node {node_id} claims DEPARTMENT_MEMBER_OF "
                    f"{dept_id} but no such department exists"
                )
                continue
            # Run the registered checker if any; default-pass otherwise
            checker = _CONSTRAINT_CHECKERS.get(dept_id)
            if checker is None:
                # V1 default: pass (don't block on departments without checkers)
                continue
            try:
                passed, reason = checker(node_id, dict(row))
                if not passed:
                    blockers.append(
                        f"[{row['name']}] {reason}"
                    )
            except Exception as e:
                blockers.append(
                    f"[{row['name']}] constraint checker raised: {type(e).__name__}: {e}"
                )

    return len(blockers) == 0, blockers


def list_checkers() -> List[str]:
    """Return the dept_ids that currently have registered checkers."""
    return sorted(_CONSTRAINT_CHECKERS.keys())


__all__ = [
    "register_constraint_checker",
    "check_function_completion",
    "list_checkers",
]
