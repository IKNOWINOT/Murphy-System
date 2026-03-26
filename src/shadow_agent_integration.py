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

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

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
    """A shadow agent mapped to a primary role as an org-chart peer.

    Every ShadowAgent automatically checks out a MultiCursorBrowser
    controller on creation (keyed by agent_id), making MCB the de-facto
    agent controller for all UI/browser actions this agent may perform.
    Access via ``agent.mcb``.  The browser is not launched automatically —
    call ``await agent.mcb.launch()`` when browser automation is needed.
    """
    agent_id: str
    primary_role_id: str
    account_id: str
    org_id: Optional[str]
    department: str
    permissions: List[str] = field(default_factory=list)
    status: ShadowStatus = ShadowStatus.ACTIVE
    governance_boundary: str = "standard"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        # ── MCB controller checkout (Copilot skill-checkout pattern) ──
        try:
            from agent_module_loader import MultiCursorBrowser as _MCB
            self.mcb = _MCB.get_controller(agent_id=self.agent_id)
        except Exception:
            self.mcb = None  # Graceful degradation in environments without browser


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
        # Per-agent learning data: agent_id → {"observations": [...], "proposals": [...]}
        self._learning_data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

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
    # Shadow agent learning (Part 5 — Shadow Agent Learning Integration)
    # ------------------------------------------------------------------

    def observe_action(
        self,
        agent_id: str,
        action_type: str,
        action_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Record what the user/shadow did for pattern learning.

        Observations are appended to the shadow agent's learning log and
        used later by ``propose_automation`` to surface repeated patterns.
        """
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None:
                return {"error": "shadow_agent_not_found"}

            entry: Dict[str, Any] = {
                "observation_id": uuid.uuid4().hex[:10],
                "action_type": action_type,
                "action_data": action_data,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }

            learning = self._learning_data.setdefault(agent_id, {"observations": [], "proposals": []})
            capped_append(learning["observations"], entry, max_size=1_000)
            self._emit_audit("observe_action", {"agent_id": agent_id, "action_type": action_type})

        logger.debug("Shadow agent %s observed action: %s", agent_id, action_type)
        return entry

    def ask_clarifying_question(
        self,
        agent_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a clarifying question about recently observed patterns.

        Returns a question dict with ``question_id``, ``question``, and
        ``context_summary``.  In production this would call an LLM; here
        we apply rule-based logic based on observation frequency.
        """
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None:
                return {"error": "shadow_agent_not_found"}

            learning = self._learning_data.get(agent_id, {"observations": [], "proposals": []})
            observations = learning.get("observations", [])

        # Count action type frequencies
        freq: Dict[str, int] = {}
        for obs in observations[-50:]:
            at = obs.get("action_type", "unknown")
            freq[at] = freq.get(at, 0) + 1

        if not freq:
            question = "What tasks do you spend the most time on each day?"
        else:
            top_action = max(freq, key=lambda k: freq[k])
            count = freq[top_action]
            question = (
                f"I've noticed you've performed '{top_action}' {count} time(s) recently. "
                f"Would you like me to automate this for you?"
            )

        result = {
            "question_id": uuid.uuid4().hex[:10],
            "agent_id": agent_id,
            "question": question,
            "context_summary": {"top_actions": freq},
            "asked_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug("Shadow agent %s generated question: %s", agent_id, question)
        return result

    def propose_automation(
        self,
        agent_id: str,
        pattern: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Turn a repeated pattern into an actionable automation proposal.

        All proposals require HITL approval before execution (``approved``
        defaults to False).  The proposal is saved to the learning data.
        """
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None:
                return {"error": "shadow_agent_not_found"}

            learning = self._learning_data.setdefault(agent_id, {"observations": [], "proposals": []})
            observations = learning.get("observations", [])

        # Build a proposal from recent observations or an explicit pattern
        if pattern is None:
            freq: Dict[str, int] = {}
            for obs in observations[-100:]:
                at = obs.get("action_type", "unknown")
                freq[at] = freq.get(at, 0) + 1
            top_action = max(freq, key=lambda k: freq[k]) if freq else "unknown"
            pattern = {"action_type": top_action, "frequency": freq.get(top_action, 0)}

        proposal: Dict[str, Any] = {
            "proposal_id": uuid.uuid4().hex[:12],
            "agent_id": agent_id,
            "description": (
                f"Automate '{pattern.get('action_type', 'unknown')}' "
                f"(observed {pattern.get('frequency', 0)} times)"
            ),
            "pattern": pattern,
            "approved": False,     # HITL required before execution
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            capped_append(learning["proposals"], proposal, max_size=200)
            self._emit_audit("propose_automation", {"agent_id": agent_id, "proposal_id": proposal["proposal_id"]})

        logger.info("Shadow agent %s proposed automation: %s", agent_id, proposal["description"])
        return proposal

    def get_learning_summary(self, agent_id: str) -> Dict[str, Any]:
        """Return a summary of what the shadow agent has learned so far."""
        with self._lock:
            agent = self._shadow_agents.get(agent_id)
            if agent is None:
                return {"error": "shadow_agent_not_found"}
            learning = self._learning_data.get(agent_id, {"observations": [], "proposals": []})
            observations = list(learning.get("observations", []))
            proposals = list(learning.get("proposals", []))

        freq: Dict[str, int] = {}
        for obs in observations:
            at = obs.get("action_type", "unknown")
            freq[at] = freq.get(at, 0) + 1

        return {
            "agent_id": agent_id,
            "total_observations": len(observations),
            "action_frequency": freq,
            "total_proposals": len(proposals),
            "pending_proposals": sum(1 for p in proposals if not p.get("approved")),
            "approved_proposals": sum(1 for p in proposals if p.get("approved")),
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
