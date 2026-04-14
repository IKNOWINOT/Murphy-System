# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Rosetta Org Chart Lookup — ROSETTA-ORG-LOOKUP-001

Owner: Platform Engineering
Dep: blockchain_audit_trail (BAT sealing)

Replaces hardcoded HITL role strings with live org chart lookups.
When the org chart changes, gate routing updates automatically.

Functions
---------
resolve_hitl_authority(action_type, risk_level, org_chart) -> str
    Walk the org chart and return the correct authority node_id for the
    given risk level.

get_rosetta_state_hash() -> str
    SHA-256 hash of the current Rosetta world-state snapshot.

Exceptions
----------
OrgChartLookupError
    Raised when the org chart is empty, malformed, or the requested
    authority node cannot be found.  Never silent.

BATSealError
    Raised when the BAT seal of a lookup fails.  We do not proceed
    silently if the audit trail is unavailable.

Risk-level mapping
------------------
  critical → Executive node
  high     → Department head node
  medium   → Team lead node
  low      → Direct manager node

Error codes: ROSETTA-ORG-ERR-001 through ROSETTA-ORG-ERR-006.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions  (ROSETTA-ORG-EXC-001)
# ---------------------------------------------------------------------------


class OrgChartLookupError(Exception):
    """Raised when org chart lookup fails — never silent."""
    pass


class BATSealError(Exception):
    """Raised when BAT seal of a lookup fails — do not proceed."""
    pass


# ---------------------------------------------------------------------------
# Risk-level → node-type mapping  (ROSETTA-ORG-MAP-001)
# ---------------------------------------------------------------------------

_RISK_TO_NODE_TYPE: Dict[str, str] = {
    "critical": "executive",
    "high": "department_head",
    "medium": "team_lead",
    "low": "direct_manager",
}

_VALID_RISK_LEVELS = frozenset(_RISK_TO_NODE_TYPE.keys())


# ---------------------------------------------------------------------------
# BAT sealing helper  (ROSETTA-ORG-BAT-001)
# ---------------------------------------------------------------------------

# Default BAT recorder — replaced in production via set_bat_recorder()
_bat_recorder: Optional[Callable[..., Any]] = None


def set_bat_recorder(recorder: Callable[..., Any]) -> None:
    """Wire the BAT record_entry function at startup.

    In production this is ``BlockchainAuditTrail.record_entry``.
    In tests, pass a mock or stub.
    """
    global _bat_recorder
    _bat_recorder = recorder


def _seal_to_bat(action: str, resource: str, metadata: Dict[str, Any]) -> None:
    """Seal a lookup event to the BAT audit trail.

    Raises BATSealError if the recorder is not wired or the seal fails.
    """
    if _bat_recorder is None:
        raise BATSealError(
            "ROSETTA-ORG-ERR-005: BAT recorder not wired — "
            "call set_bat_recorder() at startup"
        )
    try:
        _bat_recorder(
            entry_type="security_event",
            actor="rosetta_org_lookup",
            action=action,
            resource=resource,
            metadata=metadata,
        )
    except Exception as exc:  # ROSETTA-ORG-ERR-006
        raise BATSealError(
            f"ROSETTA-ORG-ERR-006: BAT seal failed — {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Matrix notification helper  (ROSETTA-ORG-MATRIX-001)
# ---------------------------------------------------------------------------

_matrix_notifier: Optional[Callable[[str, str], Any]] = None


def set_matrix_notifier(notifier: Callable[[str, str], Any]) -> None:
    """Wire the Matrix message sender at startup.

    Signature: notifier(room_id, message_body) -> None
    """
    global _matrix_notifier
    _matrix_notifier = notifier


def _post_matrix_alert(message: str) -> None:
    """Post to the HITL Matrix room.  Best-effort — logged but not fatal."""
    if _matrix_notifier is not None:
        try:
            _matrix_notifier("!hitl-alerts:murphy.systems", message)
        except Exception as exc:  # ROSETTA-ORG-ERR-007
            logger.error("ROSETTA-ORG-ERR-007: Matrix alert failed — %s", exc)


# ---------------------------------------------------------------------------
# Org chart walker  (ROSETTA-ORG-WALK-001)
# ---------------------------------------------------------------------------

def _validate_org_chart(org_chart: Dict[str, Any]) -> None:
    """Validate org chart structure.  Raises OrgChartLookupError."""
    if not org_chart:
        raise OrgChartLookupError(
            "ROSETTA-ORG-ERR-001: org_chart is empty — "
            "cannot resolve HITL authority without an org chart"
        )
    if not isinstance(org_chart, dict):
        raise OrgChartLookupError(
            "ROSETTA-ORG-ERR-002: org_chart must be a dict — "
            f"got {type(org_chart).__name__}"
        )
    if "nodes" not in org_chart:
        raise OrgChartLookupError(
            "ROSETTA-ORG-ERR-003: org_chart missing required 'nodes' key — "
            "expected dict with 'nodes' list"
        )
    if not isinstance(org_chart["nodes"], list) or len(org_chart["nodes"]) == 0:
        raise OrgChartLookupError(
            "ROSETTA-ORG-ERR-003: org_chart 'nodes' must be a non-empty list"
        )


def _find_node_by_type(nodes: List[Dict[str, Any]], node_type: str) -> Optional[str]:
    """Walk the org chart nodes and find the first node matching the type.

    Returns the node_id or None.
    """
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") == node_type and node.get("node_id"):
            return node["node_id"]
    return None


def resolve_hitl_authority(
    action_type: str,
    risk_level: str,
    org_chart: Dict[str, Any],
) -> str:
    """Resolve the HITL authority node_id from the live org chart.

    Args:
        action_type: What the agent is trying to do (for audit trail).
        risk_level: One of "critical", "high", "medium", "low".
        org_chart: Live org chart dict with "nodes" list.

    Returns:
        The authority node_id string.

    Raises:
        OrgChartLookupError: If the org chart is empty, malformed, or no
            matching authority node is found.
        BATSealError: If the BAT seal of the lookup fails.
    """
    # 1. Validate risk level
    risk_lower = risk_level.lower().strip()
    if risk_lower not in _VALID_RISK_LEVELS:
        raise OrgChartLookupError(
            f"ROSETTA-ORG-ERR-004: invalid risk_level '{risk_level}' — "
            f"must be one of {sorted(_VALID_RISK_LEVELS)}"
        )

    # 2. Validate org chart structure
    _validate_org_chart(org_chart)

    # 3. Map risk level to node type and walk the chart
    target_type = _RISK_TO_NODE_TYPE[risk_lower]
    authority_node_id = _find_node_by_type(org_chart["nodes"], target_type)

    if authority_node_id is None:
        msg = (
            f"ROSETTA-ORG-ERR-004: no {target_type} node found in org chart "
            f"for risk_level='{risk_lower}', action_type='{action_type}'"
        )
        _post_matrix_alert(f"⚠️ HITL authority resolution FAILED: {msg}")
        raise OrgChartLookupError(msg)

    # 4. Seal the lookup to BAT
    _seal_to_bat(
        action=f"hitl_authority_resolved:{action_type}",
        resource=authority_node_id,
        metadata={
            "action_type": action_type,
            "risk_level": risk_lower,
            "target_type": target_type,
            "resolved_node_id": authority_node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    logger.info(
        "ROSETTA-ORG-001: Resolved HITL authority — "
        "action=%s risk=%s type=%s node=%s",
        action_type, risk_lower, target_type, authority_node_id,
    )
    return authority_node_id


# ---------------------------------------------------------------------------
# Rosetta state hash  (ROSETTA-STATE-HASH-001)
# ---------------------------------------------------------------------------

# Default state provider — returns the aggregate state dict.
# Wire at startup via set_rosetta_state_provider().
_state_provider: Optional[Callable[[], Dict[str, Any]]] = None


def set_rosetta_state_provider(provider: Callable[[], Dict[str, Any]]) -> None:
    """Wire the Rosetta state provider at startup.

    In production, pass ``RosettaManager.aggregate``.
    """
    global _state_provider
    _state_provider = provider


def get_rosetta_state_hash() -> str:
    """Return a SHA-256 hash of the current Rosetta world-state snapshot.

    The hash is deterministic for the same state (sorted JSON serialisation).
    If the state provider is not wired, returns a hash of an empty snapshot
    with a sentinel key so callers always get a valid hash string.

    Returns:
        64-character hex SHA-256 digest.
    """
    if _state_provider is not None:
        try:
            state = _state_provider()
        except Exception as exc:  # ROSETTA-STATE-ERR-001
            logger.error("ROSETTA-STATE-ERR-001: state provider failed — %s", exc)
            state = {"_error": str(exc), "_ts": time.time()}
    else:
        state = {"_empty": True, "_ts": time.time()}

    canonical = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
