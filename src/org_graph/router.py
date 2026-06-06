"""R615.11 — Chat→exec routing (the visible payoff).

Free-text task input → materialized org-graph response. This is the
"type into chat, the org chart appears" milestone.

The routing logic is intentionally simple v1:
  1. Pick an exec from EXEC_POSITIONS via keyword heuristic
     (CFO for $/money/budget, CTO for code/system/build, CSO for
     security/risk/compliance, CEO for everything else / strategic)
  2. Heuristically pick 1-2 departments from CapabilityCube.Domain
     based on same keyword scan
  3. Generate child_node_id from a task slug
  4. Call record_spawn() to write the multi-edge graph
  5. Run check_function_completion to surface any constraint blockers
  6. Return the materialized graph (node id, edges, blockers)

V2 will replace the heuristic with LLM-based intent classification.
For now, heuristic + safe-by-default makes the loop visible end-to-end.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import re
import uuid

# Lazy imports inside functions to avoid circular import on package init


# Keyword maps for v1 heuristic routing
_EXEC_KEYWORDS = {
    "platform_cfo": [
        "money", "budget", "revenue", "cost", "pricing", "invoice",
        "financial", "accounting", "tax", "spend", "burn",
        # R8a expansion — accounting/reconciliation vocabulary
        "reconcile", "reconciliation", "bookkeeping", "ledger",
        "bank statement", "transaction", "audit trail", "1099",
        "w2", "payroll", "expense", "receivable", "payable", "depreciation",
        "amortization", "p&l", "balance sheet", "gl ", "general ledger",
    ],
    "platform_cto": [
        "code", "system", "build", "deploy", "infrastructure", "api",
        "database", "service", "patch", "bug", "architecture", "tech",
    ],
    "platform_cso": [
        "security", "risk", "compliance", "audit", "vulnerability",
        "access", "permission", "leak", "breach", "incident",
    ],
}

# Department keyword map — multi-match allowed
_DEPT_KEYWORDS = {
    "dept_sales": ["sales", "lead", "deal", "prospect", "outreach", "pipeline"],
    "dept_finance": [
        "money", "budget", "invoice", "tax", "revenue", "cost",
        "reconcile", "bookkeeping", "ledger", "bank", "transaction",
        "1099", "w2", "payroll", "expense", "receivable", "payable",
        "audit", "depreciation", "p&l", "balance sheet",
    ],
    "dept_security": ["security", "vulnerability", "breach", "audit"],
    "dept_robotics": ["robot", "kinematics", "actuator"],
    "dept_ux": ["ui", "design", "interface", "frontend"],
    "dept_identity": ["auth", "oauth", "login", "identity"],
    "dept_observability": ["metric", "log", "trace", "monitoring"],
    "dept_platform": [
        "platform", "infrastructure", "service", "system", "core",
    ],
    "dept_operations": ["ops", "deploy", "incident", "runbook"],
}


def _slug(s: str, max_len: int = 30) -> str:
    """Convert free text → URL-safe slug."""
    s = re.sub(r"[^a-z0-9_]+", "_", s.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:max_len] or "untitled"


def _route_to_exec(task_text: str) -> str:
    """Heuristic: pick the most-keyword-matching exec, default CEO."""
    lower = task_text.lower()
    best_exec = "platform_ceo"
    best_hits = 0
    for exec_id, kws in _EXEC_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in lower)
        if hits > best_hits:
            best_hits = hits
            best_exec = exec_id
    return best_exec


def _route_to_depts(task_text: str) -> List[str]:
    """Heuristic: every dept with >=1 keyword match, capped at 3."""
    lower = task_text.lower()
    matches = []
    for dept_id, kws in _DEPT_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            matches.append(dept_id)
    # Cap at 3 to keep the graph manageable
    return matches[:3] if matches else ["dept_platform"]  # default


def spawn_from_task(
    task_text: str,
    requester: str = "chat_user",
) -> Dict[str, Any]:
    """The R615.11 entry point.

    Takes free-text task, materializes the multi-edge org graph,
    returns everything the caller needs to inspect or act on.
    """
    from org_graph.spawn import record_spawn
    from org_graph.edges import find_edges_from
    from org_graph.constraint_gate import check_function_completion
    from org_graph.exec_root import EXEC_POSITIONS

    if not task_text or not task_text.strip():
        return {"ok": False, "error": "empty task_text"}

    # 1. Route
    chosen_exec = _route_to_exec(task_text)
    chosen_depts = _route_to_depts(task_text)
    task_slug = _slug(task_text)
    task_node_id = f"task_{task_slug}_{uuid.uuid4().hex[:8]}"
    spawn_node_id = f"spawn_{task_slug}_{uuid.uuid4().hex[:8]}"

    # 2. Materialize the spawn (writes 1 SPAWNED_BY + 1
    #    FUNCTIONAL_DELIVERABLE_OF + N DEPARTMENT_MEMBER_OF edges)
    edges_written = record_spawn(
        child_node_id=spawn_node_id,
        spawned_by=chosen_exec,
        deliverable_for=task_node_id,
        departments=chosen_depts,
        inherits_from=[],
        metadata={
            "source": "r615.11_chat_router",
            "task_text": task_text[:500],
            "requester": requester,
        },
    )

    # 3. Run the constraint gate (v1 will mostly pass since no checkers
    #    are registered for the seeded depts yet)
    gate_ok, blockers = check_function_completion(spawn_node_id)

    # 4. Read back the materialized graph for the response
    out_edges = find_edges_from(spawn_node_id)

    return {
        "ok": True,
        "task_node_id": task_node_id,
        "spawn_node_id": spawn_node_id,
        "routed_to_exec": chosen_exec,
        "routed_to_depts": chosen_depts,
        "edges_written": edges_written,
        "materialized_edges": [
            {"from": e["from_node"], "to": e["to_node"],
             "type": e["edge_type"], "id": e["edge_id"]}
            for e in out_edges
        ],
        "constraint_gate": {
            "passed": gate_ok,
            "blockers": blockers,
        },
        "execs_available": sorted(EXEC_POSITIONS),
    }


__all__ = ["spawn_from_task"]
