"""
Role-Based Access Control with Tenant Governance for Murphy System

This module implements multi-tenant RBAC with shadow agent governance,
providing:
- Hierarchical role definitions with fine-grained permissions
- Multi-tenant isolation with separate policy sets per organisation
- Permission checks for automation tasks, approvals, and configuration
- Shadow agent governance (agents as org-chart peers with boundaries)
- Thread-safe state management
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """Hierarchical roles within the Murphy System."""
    OWNER = "owner"
    ADMIN = "admin"
    AUTOMATOR_ADMIN = "automator_admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    SHADOW_AGENT = "shadow_agent"


class Permission(str, Enum):
    """Fine-grained permissions for governance actions."""
    EXECUTE_TASK = "execute_task"
    APPROVE_GATE = "approve_gate"
    CONFIGURE_SYSTEM = "configure_system"
    VIEW_STATUS = "view_status"
    MANAGE_USERS = "manage_users"
    MANAGE_SHADOWS = "manage_shadows"
    MANAGE_BUDGET = "manage_budget"
    APPROVE_DELIVERY = "approve_delivery"
    MANAGE_COMPLIANCE = "manage_compliance"
    ESCALATE = "escalate"
    TOGGLE_FULL_AUTOMATION = "toggle_full_automation"
    VIEW_AUTOMATION_METRICS = "view_automation_metrics"


# ------------------------------------------------------------------
# Default role → permission mapping
# ------------------------------------------------------------------

DEFAULT_ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.OWNER: set(Permission),
    Role.ADMIN: set(Permission) - {Permission.MANAGE_USERS},
    Role.AUTOMATOR_ADMIN: {
        Permission.EXECUTE_TASK,
        Permission.APPROVE_GATE,
        Permission.APPROVE_DELIVERY,
        Permission.VIEW_STATUS,
        Permission.MANAGE_BUDGET,
        Permission.VIEW_AUTOMATION_METRICS,
    },
    Role.OPERATOR: {
        Permission.EXECUTE_TASK,
        Permission.VIEW_STATUS,
        Permission.APPROVE_GATE,
        Permission.VIEW_AUTOMATION_METRICS,
    },
    Role.VIEWER: {
        Permission.VIEW_STATUS,
        Permission.VIEW_AUTOMATION_METRICS,
    },
    Role.SHADOW_AGENT: {
        Permission.EXECUTE_TASK,
        Permission.VIEW_STATUS,
    },
}

# Roles that are authorised to assign / remove roles on other users
_ROLE_MANAGEMENT_ROLES: Set[Role] = {Role.OWNER, Role.ADMIN}


@dataclass
class TenantPolicy:
    """Governance policy for a single tenant (organisation)."""
    tenant_id: str
    name: str
    role_permissions: Dict[Role, Set[Permission]] = field(default_factory=dict)
    max_concurrent_tasks: int = 10
    budget_limit: float = 10000.0
    allowed_domains: List[str] = field(default_factory=list)
    compliance_frameworks: List[str] = field(default_factory=list)
    isolation_level: str = "strict"

    def __post_init__(self):
        if not self.role_permissions:
            self.role_permissions = {
                role: set(perms) for role, perms in DEFAULT_ROLE_PERMISSIONS.items()
            }


@dataclass
class UserIdentity:
    """Represents a human user or shadow agent within a tenant."""
    user_id: str
    tenant_id: str
    roles: List[Role] = field(default_factory=list)
    display_name: str = ""
    is_shadow: bool = False


class RBACGovernance:
    """Multi-tenant role-based access control with shadow agent governance.

    Manages tenants, users, roles, and permissions with thread-safe state.
    Shadow agents are treated as org-chart peers whose governance boundaries
    are enforced identically to human users.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tenants: Dict[str, TenantPolicy] = {}
        self._users: Dict[str, UserIdentity] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Tenant management
    # ------------------------------------------------------------------

    def create_tenant(self, policy: TenantPolicy) -> str:
        """Register a new tenant with its governance policy.

        Returns the tenant_id on success.
        """
        with self._lock:
            if policy.tenant_id in self._tenants:
                logger.warning("Tenant %s already exists", policy.tenant_id)
                return policy.tenant_id
            self._tenants[policy.tenant_id] = policy
            capped_append(self._audit_log, {
                "event": "tenant_created",
                "tenant_id": policy.tenant_id,
                "name": policy.name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        logger.info("Created tenant %s (%s)", policy.tenant_id, policy.name)
        return policy.tenant_id

    # ------------------------------------------------------------------
    # User / shadow registration
    # ------------------------------------------------------------------

    def register_user(self, identity: UserIdentity) -> str:
        """Register a user or shadow agent and return their user_id."""
        with self._lock:
            if identity.tenant_id not in self._tenants:
                raise ValueError(f"Tenant {identity.tenant_id} does not exist")
            if identity.user_id in self._users:
                logger.warning("User %s already registered", identity.user_id)
                return identity.user_id
            self._users[identity.user_id] = identity
            capped_append(self._audit_log, {
                "event": "user_registered",
                "user_id": identity.user_id,
                "tenant_id": identity.tenant_id,
                "is_shadow": identity.is_shadow,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        logger.info("Registered user %s in tenant %s", identity.user_id, identity.tenant_id)
        return identity.user_id

    # ------------------------------------------------------------------
    # Permission checking
    # ------------------------------------------------------------------

    def check_permission(
        self,
        user_id: str,
        permission: Permission,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Check whether *user_id* holds *permission*.

        Returns ``(allowed, reason)`` where *reason* explains the decision.
        """
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return False, "unknown_user"

            tenant = self._tenants.get(user.tenant_id)
            if tenant is None:
                return False, "unknown_tenant"

            role_perms = tenant.role_permissions

            for role in user.roles:
                perms = role_perms.get(role, set())
                if permission in perms:
                    return True, f"granted_by_role:{role.value}"

        return False, "no_role_grants_permission"

    def can_toggle_full_automation(
        self,
        user_id: str,
        tenant_id: str,
        is_organization: bool = True,
    ) -> Tuple[bool, str]:
        """
        Check if a user can toggle full automation mode.

        For organizations: Only admin or owner roles can toggle full automation.
        For non-organizations: Only account owners can toggle full automation.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            is_organization: Whether this is an organization context

        Returns:
            (allowed, reason) tuple
        """
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return False, "unknown_user"

            if user.tenant_id != tenant_id:
                return False, "user_not_in_tenant"

            if is_organization:
                # Only admin or owner can toggle in organizations
                if Role.ADMIN in user.roles or Role.OWNER in user.roles:
                    granting = next(
                        (r for r in user.roles if r in (Role.ADMIN, Role.OWNER)),
                        user.roles[0] if user.roles else Role.ADMIN,
                    )
                    return True, f"granted_by_role:{granting.value}"
                else:
                    return False, "only_admin_or_owner_can_toggle_in_organization"
            else:
                # Only owner can toggle for their own agents
                if Role.OWNER in user.roles:
                    return True, "granted_by_role:owner"
                else:
                    return False, "only_owner_can_toggle_for_own_agents"

    # ------------------------------------------------------------------
    # Tenant isolation
    # ------------------------------------------------------------------

    def enforce_tenant_isolation(self, user_id: str, target_tenant_id: str) -> bool:
        """Return True if *user_id* is allowed to access *target_tenant_id*."""
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return False
            return user.tenant_id == target_tenant_id

    # ------------------------------------------------------------------
    # User capabilities
    # ------------------------------------------------------------------

    def get_user_capabilities(self, user_id: str) -> Dict[str, Any]:
        """Return the full capability set for *user_id*."""
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return {"error": "unknown_user"}

            tenant = self._tenants.get(user.tenant_id)
            if tenant is None:
                return {"error": "unknown_tenant"}

            role_perms = tenant.role_permissions
            all_perms: Set[Permission] = set()
            for role in user.roles:
                all_perms |= role_perms.get(role, set())

        return {
            "user_id": user.user_id,
            "tenant_id": user.tenant_id,
            "display_name": user.display_name,
            "is_shadow": user.is_shadow,
            "roles": [r.value for r in user.roles],
            "permissions": sorted(p.value for p in all_perms),
            "max_concurrent_tasks": tenant.max_concurrent_tasks,
            "budget_limit": tenant.budget_limit,
        }

    # ------------------------------------------------------------------
    # Role assignment / removal
    # ------------------------------------------------------------------

    def assign_role(self, user_id: str, role: Role, assigner_id: str) -> bool:
        """Assign *role* to *user_id* if *assigner_id* is authorised."""
        with self._lock:
            assigner = self._users.get(assigner_id)
            if assigner is None:
                logger.warning("Assigner %s not found", assigner_id)
                return False

            if not any(r in _ROLE_MANAGEMENT_ROLES for r in assigner.roles):
                logger.warning("Assigner %s lacks role-management authority", assigner_id)
                return False

            user = self._users.get(user_id)
            if user is None:
                logger.warning("Target user %s not found", user_id)
                return False

            if user.tenant_id != assigner.tenant_id:
                logger.warning("Cross-tenant role assignment denied")
                return False

            if role not in user.roles:
                user.roles.append(role)
                capped_append(self._audit_log, {
                    "event": "role_assigned",
                    "user_id": user_id,
                    "role": role.value,
                    "assigner_id": assigner_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("Assigned role %s to user %s", role.value, user_id)

        return True

    def remove_role(self, user_id: str, role: Role, remover_id: str) -> bool:
        """Remove *role* from *user_id* if *remover_id* is authorised."""
        with self._lock:
            remover = self._users.get(remover_id)
            if remover is None:
                logger.warning("Remover %s not found", remover_id)
                return False

            if not any(r in _ROLE_MANAGEMENT_ROLES for r in remover.roles):
                logger.warning("Remover %s lacks role-management authority", remover_id)
                return False

            user = self._users.get(user_id)
            if user is None:
                logger.warning("Target user %s not found", user_id)
                return False

            if user.tenant_id != remover.tenant_id:
                logger.warning("Cross-tenant role removal denied")
                return False

            if role in user.roles:
                user.roles.remove(role)
                capped_append(self._audit_log, {
                    "event": "role_removed",
                    "user_id": user_id,
                    "role": role.value,
                    "remover_id": remover_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("Removed role %s from user %s", role.value, user_id)

        return True

    # ------------------------------------------------------------------
    # Tenant status
    # ------------------------------------------------------------------

    def get_tenant_status(self, tenant_id: str) -> Dict[str, Any]:
        """Return governance status for a specific tenant."""
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if tenant is None:
                return {"error": "unknown_tenant"}

            tenant_users = [
                u for u in self._users.values() if u.tenant_id == tenant_id
            ]
            shadow_count = sum(1 for u in tenant_users if u.is_shadow)
            tenant_events = [
                e for e in self._audit_log if e.get("tenant_id") == tenant_id
            ]

        return {
            "tenant_id": tenant_id,
            "name": tenant.name,
            "total_users": len(tenant_users),
            "shadow_agents": shadow_count,
            "max_concurrent_tasks": tenant.max_concurrent_tasks,
            "budget_limit": tenant.budget_limit,
            "allowed_domains": tenant.allowed_domains,
            "compliance_frameworks": tenant.compliance_frameworks,
            "isolation_level": tenant.isolation_level,
            "audit_events": len(tenant_events),
        }

    # ------------------------------------------------------------------
    # Overall status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return overall RBAC governance status."""
        with self._lock:
            total_tenants = len(self._tenants)
            total_users = len(self._users)
            total_shadows = sum(1 for u in self._users.values() if u.is_shadow)
            total_audit_events = len(self._audit_log)

        return {
            "total_tenants": total_tenants,
            "total_users": total_users,
            "total_shadow_agents": total_shadows,
            "audit_log_size": total_audit_events,
        }
