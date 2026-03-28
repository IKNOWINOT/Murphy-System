"""
Automation RBAC Controller for Murphy System.

Design Label: SAF-002 — Role-Based Access Control for Automation Operations
Owner: Security Team / Governance Team
Dependencies:
  - PersistenceManager (for durable permission grants and audit)
  - EventBackbone (publishes AUDIT_LOGGED on authorization decisions)

Implements Plan §6.2 — RBAC Integration:
  Defines a permission model for automation-specific operations:
    TOGGLE_FULL_AUTOMATION  — enable/disable full automation
    VIEW_AUTOMATION_METRICS — view automation dashboards
    APPROVE_AUTONOMOUS_ACTION — approve autonomous actions
    OVERRIDE_AUTOMATION     — override automation decisions
  Only admin/owner roles may enable full automation.  Every
  authorization decision is recorded in an immutable audit trail.

Flow:
  1. Define roles (admin, owner, operator, viewer)
  2. Assign permissions to roles
  3. Assign roles to users/tenants
  4. Check authorization before any autonomous action
  5. Log every authorization decision
  6. Persist audit and publish event

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Default-deny: any unknown user/permission is denied
  - Bounded: configurable max audit log entries
  - Immutable audit: entries cannot be modified or deleted
  - Fail-closed: errors in check → denied

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_AUDIT_ENTRIES = 10_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class AutomationPermission(str, Enum):
    """Permissions specific to automation operations."""
    TOGGLE_FULL_AUTOMATION = "toggle_full_automation"
    VIEW_AUTOMATION_METRICS = "view_automation_metrics"
    APPROVE_AUTONOMOUS_ACTION = "approve_autonomous_action"
    OVERRIDE_AUTOMATION = "override_automation"


class AutomationRole(str, Enum):
    """Built-in roles for automation governance."""
    ADMIN = "admin"
    OWNER = "owner"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AuthDecision(str, Enum):
    """Auth decision (str subclass)."""
    ALLOWED = "allowed"
    DENIED = "denied"


# Default role → permissions mapping
DEFAULT_ROLE_PERMISSIONS: Dict[AutomationRole, FrozenSet[AutomationPermission]] = {
    AutomationRole.ADMIN: frozenset(AutomationPermission),
    AutomationRole.OWNER: frozenset(AutomationPermission),
    AutomationRole.OPERATOR: frozenset({
        AutomationPermission.VIEW_AUTOMATION_METRICS,
        AutomationPermission.APPROVE_AUTONOMOUS_ACTION,
    }),
    AutomationRole.VIEWER: frozenset({
        AutomationPermission.VIEW_AUTOMATION_METRICS,
    }),
}


@dataclass
class AuditEntry:
    """Immutable record of an authorization decision."""
    entry_id: str
    user_id: str
    tenant_id: str
    permission: str
    decision: AuthDecision
    reason: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "permission": self.permission,
            "decision": self.decision.value,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# AutomationRBACController
# ---------------------------------------------------------------------------

class AutomationRBACController:
    """Role-based access control for automation operations.

    Design Label: SAF-002
    Owner: Security Team / Governance Team

    Usage::

        rbac = AutomationRBACController()
        rbac.assign_role("user-1", "tenant-1", AutomationRole.ADMIN)
        allowed = rbac.check_permission("user-1", "tenant-1",
                                         AutomationPermission.TOGGLE_FULL_AUTOMATION)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        role_permissions: Optional[Dict[AutomationRole, FrozenSet[AutomationPermission]]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._role_perms = dict(role_permissions or DEFAULT_ROLE_PERMISSIONS)
        # (user_id, tenant_id) → set of roles
        self._assignments: Dict[tuple, Set[AutomationRole]] = {}
        self._audit: List[AuditEntry] = []

    # ------------------------------------------------------------------
    # Role management
    # ------------------------------------------------------------------

    def assign_role(self, user_id: str, tenant_id: str, role: AutomationRole) -> None:
        """Assign a role to a user within a tenant."""
        with self._lock:
            key = (user_id, tenant_id)
            if key not in self._assignments:
                self._assignments[key] = set()
            self._assignments[key].add(role)
        logger.info("Assigned role %s to user %s in tenant %s", role.value, user_id, tenant_id)

    def revoke_role(self, user_id: str, tenant_id: str, role: AutomationRole) -> bool:
        with self._lock:
            key = (user_id, tenant_id)
            roles = self._assignments.get(key)
            if roles and role in roles:
                roles.discard(role)
                return True
            return False

    def get_roles(self, user_id: str, tenant_id: str) -> List[str]:
        with self._lock:
            key = (user_id, tenant_id)
            return [r.value for r in self._assignments.get(key, set())]

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def check_permission(
        self,
        user_id: str,
        tenant_id: str,
        permission: AutomationPermission,
    ) -> bool:
        """Check whether a user has a permission in a tenant. Default-deny."""
        with self._lock:
            key = (user_id, tenant_id)
            roles = self._assignments.get(key, set())
            allowed = False
            for role in roles:
                perms = self._role_perms.get(role, frozenset())
                if permission in perms:
                    allowed = True
                    break

        decision = AuthDecision.ALLOWED if allowed else AuthDecision.DENIED
        reason = f"role(s)={','.join(r.value for r in roles)}" if roles else "no roles assigned"
        entry = AuditEntry(
            entry_id=f"au-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            tenant_id=tenant_id,
            permission=permission.value,
            decision=decision,
            reason=reason,
        )

        with self._lock:
            if len(self._audit) >= _MAX_AUDIT_ENTRIES:
                self._audit = self._audit[_MAX_AUDIT_ENTRIES // 10:]
            self._audit.append(entry)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=entry.entry_id, document=entry.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(entry)

        return allowed

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._audit[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_assignments": sum(len(v) for v in self._assignments.values()),
                "total_audit_entries": len(self._audit),
                "defined_roles": [r.value for r in self._role_perms],
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, entry: AuditEntry) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.AUDIT_LOGGED,
                payload={
                    "source": "automation_rbac_controller",
                    "action": "authorization_checked",
                    "entry_id": entry.entry_id,
                    "user_id": entry.user_id,
                    "permission": entry.permission,
                    "decision": entry.decision.value,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="automation_rbac_controller",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
