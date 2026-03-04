"""
Shadow-Agent + Account-Plane Integration for Murphy System

This module implements shadow-agent management with org-chart parity,
treating shadow agents as peers of their mapped primary roles rather
than subordinate assistants.  It provides:

- Account management with user/org separation (RFI-012)
- Shadow agent lifecycle (create, suspend, revoke, reactivate)
- Governance boundary enforcement identical to primary roles
- Department-scoped shadow bindings
- Thread-safe operation with immutable audit trail
"""

import uuid
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from thread_safe_operations import capped_append

logger = logging.getLogger(__name__)


class AccountType(str, Enum):
    """Type of account in the Murphy account plane."""
    USER = "user"
    ORGANIZATION = "organization"


class ShadowStatus(str, Enum):
    """Lifecycle status of a shadow agent."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


@dataclass
class Account:
    """An account in the Murphy account plane (user or organization)."""
    account_id: str
    account_type: AccountType
    display_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShadowAgent:
    """A shadow agent mapped to a primary role as an org-chart peer."""
    agent_id: str
    primary_role_id: str
    account_id: str
    org_id: Optional[str]
    department: str
    permissions: List[str] = field(default_factory=list)
    status: ShadowStatus = ShadowStatus.ACTIVE
    governance_boundary: str = "standard"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ShadowBinding:
    """Binds a shadow agent to a target role within a given scope."""
    binding_id: str
    shadow_agent_id: str
    target_role_id: str
    scope: str = "department"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ShadowAgentIntegration:
    """Manages shadow-agent lifecycle, bindings, and governance checks.

    Shadow agents are treated as org-chart peers of their mapped primary
    roles and are subject to identical governance boundary enforcement.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._accounts: Dict[str, Account] = {}
        self._shadow_agents: Dict[str, ShadowAgent] = {}
        self._bindings: Dict[str, ShadowBinding] = {}
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def create_account(
        self,
        display_name: str,
        account_type: AccountType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Account:
        """Create a new user or organization account."""
        account = Account(
            account_id=uuid.uuid4().hex[:12],
            account_type=account_type,
            display_name=display_name,
            metadata=metadata or {},
        )
        with self._lock:
            self._accounts[account.account_id] = account
            self._emit_audit("account_created", {
                "account_id": account.account_id,
                "account_type": account.account_type.value,
                "display_name": display_name,
            })
        logger.info(
            "Account created: id=%s type=%s name=%s",
            account.account_id, account.account_type.value, display_name,
        )
        return account

    # ------------------------------------------------------------------
    # Shadow agent lifecycle
    # ------------------------------------------------------------------

    def create_shadow_agent(
        self,
        primary_role_id: str,
        account_id: str,
        department: str,
        permissions: Optional[List[str]] = None,
        org_id: Optional[str] = None,
    ) -> ShadowAgent:
        """Create a shadow agent as an org-chart peer of a primary role."""
        with self._lock:
            if account_id not in self._accounts:
                raise ValueError(f"account '{account_id}' does not exist")

            if org_id is not None and org_id not in self._accounts:
                raise ValueError(f"org account '{org_id}' does not exist")

            agent = ShadowAgent(
                agent_id=uuid.uuid4().hex[:12],
                primary_role_id=primary_role_id,
                account_id=account_id,
                org_id=org_id,
                department=department,
                permissions=list(permissions) if permissions else [],
            )
            self._shadow_agents[agent.agent_id] = agent
            self._emit_audit("shadow_agent_created", {
                "agent_id": agent.agent_id,
                "primary_role_id": primary_role_id,
                "account_id": account_id,
                "department": department,
            })

        logger.info(
            "Shadow agent created: id=%s primary=%s dept=%s",
            agent.agent_id, primary_role_id, department,
        )
        return agent

    def suspend_shadow(self, agent_id: str, reason: str = "") -> bool:
        """Suspend an active shadow agent."""
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None or agent.status != ShadowStatus.ACTIVE:
                return False
            agent.status = ShadowStatus.SUSPENDED
            self._emit_audit("shadow_suspended", {
                "agent_id": agent_id,
                "reason": reason,
            })
        logger.info("Shadow agent suspended: id=%s reason=%s", agent_id, reason)
        return True

    def revoke_shadow(self, agent_id: str, reason: str = "") -> bool:
        """Permanently revoke a shadow agent."""
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None or agent.status == ShadowStatus.REVOKED:
                return False
            agent.status = ShadowStatus.REVOKED
            self._emit_audit("shadow_revoked", {
                "agent_id": agent_id,
                "reason": reason,
            })
        logger.info("Shadow agent revoked: id=%s reason=%s", agent_id, reason)
        return True

    def reactivate_shadow(self, agent_id: str) -> bool:
        """Reactivate a suspended shadow agent."""
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None or agent.status != ShadowStatus.SUSPENDED:
                return False
            agent.status = ShadowStatus.ACTIVE
            self._emit_audit("shadow_reactivated", {"agent_id": agent_id})
        logger.info("Shadow agent reactivated: id=%s", agent_id)
        return True

    # ------------------------------------------------------------------
    # Shadow bindings
    # ------------------------------------------------------------------

    def bind_shadow_to_role(
        self,
        shadow_agent_id: str,
        target_role_id: str,
        scope: str = "department",
    ) -> ShadowBinding:
        """Bind a shadow agent to a target role within a scope."""
        with self._lock:
            agent = self._shadow_agents.get(shadow_agent_id)
            if agent is None:
                raise ValueError(f"shadow agent '{shadow_agent_id}' does not exist")
            if agent.status != ShadowStatus.ACTIVE:
                raise ValueError(
                    f"shadow agent '{shadow_agent_id}' is {agent.status.value}; "
                    "only active agents can be bound"
                )

            binding = ShadowBinding(
                binding_id=uuid.uuid4().hex[:12],
                shadow_agent_id=shadow_agent_id,
                target_role_id=target_role_id,
                scope=scope,
            )
            self._bindings[binding.binding_id] = binding
            self._emit_audit("shadow_bound", {
                "binding_id": binding.binding_id,
                "shadow_agent_id": shadow_agent_id,
                "target_role_id": target_role_id,
                "scope": scope,
            })

        logger.info(
            "Shadow binding created: id=%s shadow=%s target=%s scope=%s",
            binding.binding_id, shadow_agent_id, target_role_id, scope,
        )
        return binding

    # ------------------------------------------------------------------
    # Permission enforcement (org-chart parity)
    # ------------------------------------------------------------------

    def check_shadow_permission(
        self,
        agent_id: str,
        action: str,
    ) -> Tuple[bool, str]:
        """Check whether a shadow agent is permitted to perform *action*.

        Shadow agents receive the SAME permission checks as their primary
        roles (org-chart parity).  Suspended or revoked agents are always
        denied.
        """
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None:
                return False, f"shadow agent '{agent_id}' not found"

            if agent.status == ShadowStatus.SUSPENDED:
                return False, "shadow agent is suspended"

            if agent.status == ShadowStatus.REVOKED:
                return False, "shadow agent is revoked"

            # Org-chart parity: identical permission check as primary role
            if action in agent.permissions:
                return True, "permission granted (org-chart parity with primary role)"

            return False, (
                f"action '{action}' not in shadow agent permissions "
                f"(same check applied to primary role '{agent.primary_role_id}')"
            )

    # ------------------------------------------------------------------
    # Governance boundary
    # ------------------------------------------------------------------

    def get_shadow_governance_boundary(self, agent_id: str) -> Optional[str]:
        """Return the governance boundary for a shadow agent."""
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None:
                return None
            return agent.governance_boundary

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_shadows_for_account(self, account_id: str) -> List[ShadowAgent]:
        """Return all shadow agents belonging to an account."""
        with self._lock:
            return [
                a for a in self._shadow_agents.values()
                if a.account_id == account_id
            ]

    def get_shadows_for_org(self, org_id: str) -> List[ShadowAgent]:
        """Return all shadow agents belonging to an organization."""
        with self._lock:
            return [
                a for a in self._shadow_agents.values()
                if a.org_id == org_id
            ]

    # ------------------------------------------------------------------
    # Status / summary
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return overall integration status."""
        with self._lock:
            total_accounts = len(self._accounts)
            total_shadows = len(self._shadow_agents)
            total_bindings = len(self._bindings)
            total_audit_entries = len(self._audit_log)
            active = sum(
                1 for a in self._shadow_agents.values()
                if a.status == ShadowStatus.ACTIVE
            )
            suspended = sum(
                1 for a in self._shadow_agents.values()
                if a.status == ShadowStatus.SUSPENDED
            )
            revoked = sum(
                1 for a in self._shadow_agents.values()
                if a.status == ShadowStatus.REVOKED
            )

        return {
            "total_accounts": total_accounts,
            "total_shadow_agents": total_shadows,
            "active_shadows": active,
            "suspended_shadows": suspended,
            "revoked_shadows": revoked,
            "total_bindings": total_bindings,
            "total_audit_entries": total_audit_entries,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_audit(self, event: str, details: Dict[str, Any]) -> None:
        """Append an audit entry. Must be called under lock."""
        capped_append(self._audit_log, {
            "event": event,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
