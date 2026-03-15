"""
Legacy Compatibility Matrix Adapter for Murphy System Runtime

This module wires legacy orchestration bridge hooks (Modern Arcana / Clockwork)
and compatibility-matrix decisions through profile-governed runtime controls.
Implements Section 15.3.6 and 15.4 of the assessment.

Features:
- Compatibility entry registration with governance policies
- Bridge hook registration and execution for system pairs
- Multi-hop migration path discovery (BFS)
- Readiness scoring based on compatibility, validation, and bridge availability
- Governance validation for role-based bridge access
- Full matrix reporting with statistics and audit trail
"""

import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Governance policy role requirements
# ------------------------------------------------------------------

GOVERNANCE_ROLE_REQUIREMENTS: Dict[str, List[str]] = {
    "open": ["viewer", "operator", "admin", "superadmin"],
    "restricted": ["operator", "admin", "superadmin"],
    "strict": ["admin", "superadmin"],
    "critical": ["superadmin"],
}

# ------------------------------------------------------------------
# Compatibility scoring weights
# ------------------------------------------------------------------

COMPATIBILITY_LEVEL_SCORES: Dict[str, float] = {
    "full": 1.0,
    "partial": 0.5,
    "incompatible": 0.0,
}


@dataclass
class CompatibilityEntry:
    """A single compatibility mapping between two systems."""
    source_system: str
    target_system: str
    compatibility_level: str  # "full", "partial", "incompatible"
    bridge_type: str  # "direct", "adapter", "transform"
    requires_validation: bool
    governance_policy: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class LegacyCompatibilityMatrixAdapter:
    """Manages legacy system compatibility matrix, bridge hooks, and governance.

    Provides entry registration, bridge hook execution, multi-hop migration
    path discovery, readiness scoring, and governance validation for
    cross-system bridging operations.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, CompatibilityEntry] = {}
        self._entry_index: Dict[str, str] = {}  # "source::target" -> entry_id
        self._bridge_hooks: Dict[str, Callable] = {}  # "source::target" -> hook_fn
        self._hook_ids: Dict[str, str] = {}  # "source::target" -> hook_id
        self._execution_history: List[Dict[str, Any]] = []
        self._adjacency: Dict[str, set] = {}  # source -> {targets}

    # ------------------------------------------------------------------
    # Entry registration
    # ------------------------------------------------------------------

    def register_entry(self, entry: CompatibilityEntry) -> str:
        """Register a compatibility entry and return its entry_id."""
        entry_id = f"compat-{uuid.uuid4().hex[:12]}"
        key = f"{entry.source_system}::{entry.target_system}"
        self._entries[entry_id] = entry
        self._entry_index[key] = entry_id
        self._adjacency.setdefault(entry.source_system, set()).add(entry.target_system)
        logger.info("Registered compatibility entry %s for %s", entry_id, key)
        return entry_id

    # ------------------------------------------------------------------
    # Bridge hook registration
    # ------------------------------------------------------------------

    def register_bridge_hook(self, source: str, target: str, hook_fn: Callable) -> str:
        """Register a bridge function for a system pair and return its hook_id."""
        hook_id = f"hook-{uuid.uuid4().hex[:12]}"
        key = f"{source}::{target}"
        self._bridge_hooks[key] = hook_fn
        self._hook_ids[key] = hook_id
        logger.info("Registered bridge hook %s for %s", hook_id, key)
        return hook_id

    # ------------------------------------------------------------------
    # Compatibility evaluation
    # ------------------------------------------------------------------

    def evaluate_compatibility(self, source: str, target: str) -> Dict[str, Any]:
        """Look up compatibility level and bridge requirements for a pair."""
        key = f"{source}::{target}"
        entry_id = self._entry_index.get(key)
        if entry_id is None:
            return {
                "status": "unknown",
                "source": source,
                "target": target,
                "compatibility_level": None,
                "bridge_type": None,
                "requires_validation": None,
                "governance_policy": None,
                "has_bridge_hook": key in self._bridge_hooks,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        entry = self._entries[entry_id]
        return {
            "status": "found",
            "entry_id": entry_id,
            "source": source,
            "target": target,
            "compatibility_level": entry.compatibility_level,
            "bridge_type": entry.bridge_type,
            "requires_validation": entry.requires_validation,
            "governance_policy": entry.governance_policy,
            "has_bridge_hook": key in self._bridge_hooks,
            "metadata": entry.metadata,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Bridge execution
    # ------------------------------------------------------------------

    def execute_bridge(self, source: str, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the bridge hook for a system pair.

        Returns a result dict with status, transformed payload, and audit trail.
        """
        key = f"{source}::{target}"
        timestamp = datetime.now(timezone.utc).isoformat()

        if key not in self._bridge_hooks:
            result = {
                "status": "error",
                "error": f"No bridge hook registered for {source} -> {target}",
                "source": source,
                "target": target,
                "timestamp": timestamp,
            }
            capped_append(self._execution_history, result)
            return result

        hook_fn = self._bridge_hooks[key]
        try:
            transformed = hook_fn(payload)
            result = {
                "status": "success",
                "source": source,
                "target": target,
                "hook_id": self._hook_ids[key],
                "original_payload": payload,
                "transformed_payload": transformed,
                "timestamp": timestamp,
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            result = {
                "status": "error",
                "source": source,
                "target": target,
                "hook_id": self._hook_ids.get(key),
                "error": str(exc),
                "timestamp": timestamp,
            }

        capped_append(self._execution_history, result)
        logger.info("Bridge execution %s -> %s: %s", source, target, result["status"])
        return result

    # ------------------------------------------------------------------
    # Migration path (BFS)
    # ------------------------------------------------------------------

    def get_migration_path(self, source: str, target: str) -> List[str]:
        """Find a multi-hop migration path from source to target using BFS.

        Returns a list of system names representing the path, or an empty
        list if no path exists.
        """
        if source == target:
            return [source]

        visited = {source}
        queue: deque = deque()
        queue.append([source])

        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbour in self._adjacency.get(current, set()):
                if neighbour == target:
                    return path + [neighbour]
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(path + [neighbour])

        return []

    # ------------------------------------------------------------------
    # Readiness scoring
    # ------------------------------------------------------------------

    def score_bridge_readiness(self, source: str, target: str) -> Dict[str, Any]:
        """Score the readiness of a bridge between two systems (0.0 – 1.0).

        The score considers compatibility level, validation requirements,
        and bridge hook availability.
        """
        key = f"{source}::{target}"
        entry_id = self._entry_index.get(key)
        has_hook = key in self._bridge_hooks

        if entry_id is None:
            return {
                "status": "unknown",
                "source": source,
                "target": target,
                "score": 0.0,
                "details": "No compatibility entry registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        entry = self._entries[entry_id]
        compat_score = COMPATIBILITY_LEVEL_SCORES.get(entry.compatibility_level, 0.0)
        validation_score = 1.0 if not entry.requires_validation else 0.5
        hook_score = 1.0 if has_hook else 0.0

        # Weighted average: compatibility 50%, validation 20%, hook 30%
        score = round(compat_score * 0.5 + validation_score * 0.2 + hook_score * 0.3, 4)

        return {
            "status": "scored",
            "source": source,
            "target": target,
            "score": score,
            "compatibility_score": compat_score,
            "validation_score": validation_score,
            "hook_score": hook_score,
            "entry_id": entry_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Matrix report
    # ------------------------------------------------------------------

    def get_matrix_report(self) -> Dict[str, Any]:
        """Return a full matrix report with all entries, hooks, and statistics."""
        entries_list = []
        for eid, entry in self._entries.items():
            entries_list.append({
                "entry_id": eid,
                "source_system": entry.source_system,
                "target_system": entry.target_system,
                "compatibility_level": entry.compatibility_level,
                "bridge_type": entry.bridge_type,
                "requires_validation": entry.requires_validation,
                "governance_policy": entry.governance_policy,
                "metadata": entry.metadata,
            })

        hooks_list = []
        for key, hook_id in self._hook_ids.items():
            src, tgt = key.split("::")
            hooks_list.append({
                "hook_id": hook_id,
                "source": src,
                "target": tgt,
            })

        level_counts: Dict[str, int] = {}
        for entry in self._entries.values():
            level_counts[entry.compatibility_level] = level_counts.get(entry.compatibility_level, 0) + 1

        return {
            "status": "ok",
            "total_entries": len(self._entries),
            "total_hooks": len(self._bridge_hooks),
            "total_executions": len(self._execution_history),
            "entries": entries_list,
            "hooks": hooks_list,
            "execution_history": list(self._execution_history),
            "compatibility_level_counts": level_counts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Governance validation
    # ------------------------------------------------------------------

    def validate_governance(self, source: str, target: str, user_role: str) -> Dict[str, Any]:
        """Check whether *user_role* satisfies the governance policy for a pair."""
        key = f"{source}::{target}"
        entry_id = self._entry_index.get(key)

        if entry_id is None:
            return {
                "status": "no_entry",
                "source": source,
                "target": target,
                "allowed": False,
                "reason": "No compatibility entry registered for this pair",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        entry = self._entries[entry_id]
        policy = entry.governance_policy
        allowed_roles = GOVERNANCE_ROLE_REQUIREMENTS.get(policy)

        if allowed_roles is None:
            return {
                "status": "unknown_policy",
                "source": source,
                "target": target,
                "allowed": False,
                "policy": policy,
                "reason": f"Unknown governance policy: {policy}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        allowed = user_role in allowed_roles
        return {
            "status": "evaluated",
            "source": source,
            "target": target,
            "allowed": allowed,
            "policy": policy,
            "user_role": user_role,
            "reason": "Role permitted" if allowed else f"Role '{user_role}' not permitted under '{policy}' policy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Clear / reset
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all internal state."""
        self._entries.clear()
        self._entry_index.clear()
        self._bridge_hooks.clear()
        self._hook_ids.clear()
        self._execution_history.clear()
        self._adjacency.clear()
        logger.info("LegacyCompatibilityMatrixAdapter state cleared")
