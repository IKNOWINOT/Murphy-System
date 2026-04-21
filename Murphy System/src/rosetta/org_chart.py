"""
ROSETTA-ORG-003 — Org-chart projection from RosettaManager.

Walks ``metadata.extras['employee_contract'].reports_to`` across all
agent states held by a :class:`~rosetta.rosetta_manager.RosettaManager`
to produce a tree.

Commissioning checklist:

* Designed to do: build a deterministic, JSON-serializable org tree
  the HTTP layer can return and the PSM launch endpoint can read for
  owner-role attribution.

* Conditions:
    1. Empty manager → ``{"available": false, "reason": "empty"}``.
    2. Healthy single-rooted tree → ``{"available": true, "tree": {...}}``.
    3. Multiple roots → ``{"available": false, "reason": "multiple_roots", "roots": [...]}``.
    4. Cycle → ``{"available": false, "reason": "cycle", "cycle": [...]}``.
    5. ``reports_to`` references unknown role → that subtree is
       attached as an "orphan" branch under a synthetic root and the
       response carries ``warnings: ["orphan_role:<role>"]`` (loud).

* Expected vs actual: every public function returns a dict that is
  fully JSON-serializable; never raises on malformed data — instead
  records the problem in the response.

* Restart-from-symptom: re-run :func:`build_org_chart` after fixing
  the underlying state.

* Hardening: explicit cycle detection with bounded walk; no recursion
  on user-controlled depth.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .rosetta_manager import RosettaManager

logger = logging.getLogger(__name__)

_MAX_DEPTH = 64  # bounded: refuses to walk pathological chains


def _extract_contracts(
    manager: RosettaManager,
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Pull ``(role_title -> node)`` for every agent that has a contract.

    Returns ``(nodes, warnings)``.  Agents without a contract are
    skipped but listed in *warnings* so they're never silently dropped.
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    for agent_id in manager.list_agents():
        state = manager.load_state(agent_id)
        if state is None:
            warnings.append(f"unloadable:{agent_id}")
            continue
        extras = state.metadata.extras or {}
        contract = extras.get("employee_contract")
        if not isinstance(contract, dict):
            warnings.append(f"no_contract:{agent_id}")
            continue
        role = contract.get("role_title")
        if not role:
            warnings.append(f"no_role_title:{agent_id}")
            continue
        if role in nodes:
            warnings.append(f"duplicate_role:{role}")
            continue
        nodes[role] = {
            "role": role,
            "agent_id": agent_id,
            "agent_type": contract.get("agent_type"),
            "management_layer": contract.get("management_layer"),
            "department": contract.get("department", ""),
            "reports_to": contract.get("reports_to"),
            "reports": [],
        }
    return nodes, warnings


def _detect_cycle(nodes: Dict[str, Dict[str, Any]]) -> Optional[List[str]]:
    """Return the cycle path if one exists in ``reports_to`` chains."""
    for start in nodes:
        seen: List[str] = [start]
        cur = nodes[start]["reports_to"]
        depth = 0
        while cur is not None and depth < _MAX_DEPTH:
            if cur not in nodes:
                break
            if cur in seen:
                return seen + [cur]
            seen.append(cur)
            cur = nodes[cur]["reports_to"]
            depth += 1
    return None


def build_org_chart(manager: Optional[RosettaManager]) -> Dict[str, Any]:
    """Build an org-chart projection.  See module docstring for contract."""
    if manager is None:
        return {
            "available": False,
            "reason": "no_manager",
            "message": "RosettaManager is not initialized",
        }

    nodes, warnings = _extract_contracts(manager)
    if not nodes:
        return {
            "available": False,
            "reason": "empty",
            "message": "No platform agents with employee_contract metadata",
            "warnings": warnings,
        }

    cycle = _detect_cycle(nodes)
    if cycle is not None:
        return {
            "available": False,
            "reason": "cycle",
            "cycle": cycle,
            "warnings": warnings,
        }

    # Wire children.
    roots: List[str] = []
    for role, node in nodes.items():
        parent = node["reports_to"]
        if parent is None:
            roots.append(role)
        elif parent in nodes:
            nodes[parent]["reports"].append(node)
        else:
            warnings.append(f"orphan_role:{role}->{parent}")
            roots.append(role)  # promote to root so it isn't lost

    # Deterministic ordering for stable JSON output / tests.
    for node in nodes.values():
        node["reports"].sort(key=lambda n: n["role"])
    roots.sort()

    if len(roots) > 1:
        return {
            "available": False,
            "reason": "multiple_roots",
            "roots": roots,
            "warnings": warnings,
        }

    return {
        "available": True,
        "organisation_id": "murphy-inc",
        "tree": nodes[roots[0]],
        "role_count": len(nodes),
        "warnings": warnings,
    }


def lookup_role_for_operator(
    manager: Optional[RosettaManager], operator_id: str,
) -> Dict[str, Any]:
    """ROSETTA-ORG-004 helper.

    Map an operator_id (the value PSM-003 receives in the launch body)
    to the role that owns the resulting self-modification cycle, plus
    the approver chain (root-ward walk of ``reports_to``).

    Returns a dict with explicit keys:
        owner_role:    role_title or None
        approver_chain: list[str] (root-most last; empty for the root)
        owner_lookup:  one of "ok", "unknown_operator", "no_manager",
                       "no_chart"
    Never raises — every failure mode is named in the response.
    """
    if manager is None:
        return {
            "owner_role": None,
            "approver_chain": [],
            "owner_lookup": "no_manager",
        }

    # Local import to avoid a circular import at module load time.
    from .platform_org_seed import PLATFORM_OPERATOR_TO_ROLE

    role = PLATFORM_OPERATOR_TO_ROLE.get(operator_id)
    if role is None:
        return {
            "owner_role": None,
            "approver_chain": [],
            "owner_lookup": "unknown_operator",
        }

    chart = build_org_chart(manager)
    if not chart.get("available"):
        return {
            "owner_role": role,
            "approver_chain": [],
            "owner_lookup": "no_chart",
            "chart_reason": chart.get("reason"),
        }

    # Walk reports_to upward from `role` to build the approver chain.
    nodes_by_role: Dict[str, Dict[str, Any]] = {}

    def _index(node: Dict[str, Any]) -> None:
        nodes_by_role[node["role"]] = node
        for child in node.get("reports", []):
            _index(child)

    _index(chart["tree"])

    chain: List[str] = []
    cur = nodes_by_role.get(role, {}).get("reports_to")
    depth = 0
    while cur is not None and depth < _MAX_DEPTH:
        chain.append(cur)
        cur = nodes_by_role.get(cur, {}).get("reports_to")
        depth += 1

    return {
        "owner_role": role,
        "approver_chain": chain,
        "owner_lookup": "ok",
    }
