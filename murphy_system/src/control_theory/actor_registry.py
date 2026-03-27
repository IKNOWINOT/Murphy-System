"""
Unified Actor Registry and Authority Matrix for the Murphy System.

Provides:
  - Actor — single canonical identity for all agent types.
  - AuthorityMatrix — A[actor, action, resource] → bool.
  - ActorRegistry — single source of truth for all actors in the system.
  - Delegation graph with transitive closure and revocation.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Actor identity
# ------------------------------------------------------------------ #

class ActorKind(Enum):
    """Classification of actor origin."""

    HUMAN = "human"
    BOT = "bot"
    LLM_EXPERT = "llm_expert"
    SYSTEM = "system"


@dataclass
class Actor:
    """
    Canonical actor identity that unifies Identity, BotAgent,
    AvatarProfile, and ProfessionAtom into one model.
    """

    actor_id: str
    name: str
    kind: ActorKind
    role: str = ""
    description: str = ""
    active: bool = True
    metadata: Dict = field(default_factory=dict)


# ------------------------------------------------------------------ #
# Authority matrix  A[actor_id][action][resource] → bool
# ------------------------------------------------------------------ #

class AuthorityMatrix:
    """
    Formal authority matrix.

    Supports:
      - grant(actor, action, resource)
      - revoke(actor, action, resource)
      - is_authorized(actor, action, resource) → bool
    """

    def __init__(self) -> None:
        # actor_id → {action → set_of_resources}
        self._grants: Dict[str, Dict[str, Set[str]]] = {}

    def grant(self, actor_id: str, action: str, resource: str) -> None:
        """Grant *actor_id* permission to perform *action* on *resource*."""
        self._grants.setdefault(actor_id, {}).setdefault(action, set()).add(resource)

    def revoke(self, actor_id: str, action: str, resource: str) -> None:
        """Revoke a specific permission."""
        if actor_id in self._grants and action in self._grants[actor_id]:
            self._grants[actor_id][action].discard(resource)

    def is_authorized(self, actor_id: str, action: str, resource: str) -> bool:
        """True if *actor_id* may perform *action* on *resource*."""
        actor_perms = self._grants.get(actor_id)
        if actor_perms is None:
            return False
        action_perms = actor_perms.get(action)
        if action_perms is None:
            return False
        return resource in action_perms or "*" in action_perms

    def permissions_for(self, actor_id: str) -> Dict[str, Set[str]]:
        """Return all permissions for an actor."""
        return dict(self._grants.get(actor_id, {}))


# ------------------------------------------------------------------ #
# Actor registry
# ------------------------------------------------------------------ #

class ActorRegistry:
    """
    Single source of truth for all actors.

    Combines registration, lookup, and authority management.
    """

    def __init__(self) -> None:
        self._actors: Dict[str, Actor] = {}
        self.authority = AuthorityMatrix()
        # Delegation edges: (delegator, delegate)
        self._delegations: Set[Tuple[str, str]] = set()

    def register(self, actor: Actor) -> None:
        """Register a new actor."""
        self._actors[actor.actor_id] = actor

    def onboard(
        self,
        actor: Actor,
        initial_grants: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        """
        Onboard a new actor with optional initial authority grants.

        *initial_grants*: list of (action, resource) tuples.
        """
        self.register(actor)
        for action, resource in (initial_grants or []):
            self.authority.grant(actor.actor_id, action, resource)

    def get(self, actor_id: str) -> Optional[Actor]:
        return self._actors.get(actor_id)

    def list_actors(self, kind: Optional[ActorKind] = None) -> List[Actor]:
        actors = list(self._actors.values())
        if kind is not None:
            actors = [a for a in actors if a.kind == kind]
        return actors

    def deactivate(self, actor_id: str) -> None:
        actor = self._actors.get(actor_id)
        if actor:
            actor.active = False

    # ---- delegation ----------------------------------------------- #

    def delegate(self, delegator_id: str, delegate_id: str) -> None:
        """Add a delegation edge: *delegator* delegates to *delegate*."""
        if delegator_id not in self._actors or delegate_id not in self._actors:
            raise ValueError("Both actors must be registered.")
        self._delegations.add((delegator_id, delegate_id))

    def revoke_delegation(self, delegator_id: str, delegate_id: str) -> None:
        """Remove a delegation edge."""
        self._delegations.discard((delegator_id, delegate_id))

    def transitive_delegates(self, actor_id: str) -> Set[str]:
        """Compute transitive closure of delegation from *actor_id*."""
        visited: Set[str] = set()
        stack = [actor_id]
        while stack:
            current = stack.pop()
            for src, dst in self._delegations:
                if src == current and dst not in visited:
                    visited.add(dst)
                    stack.append(dst)
        return visited


# ------------------------------------------------------------------ #
# Escalation policy
# ------------------------------------------------------------------ #

@dataclass
class EscalationResult:
    """Outcome of a successful escalation."""

    escalated_to: str    # actor_id of the superior who accepted the action
    reason: str
    authority_level: float


class EscalationPolicy:
    """
    Encapsulates authority-escalation logic for the control loop.

    When an actor's authority is insufficient for a given action, the policy
    searches up the delegation chain until it finds a superior with enough
    authority (or exhausts the chain).

    Usage::

        policy = EscalationPolicy(authority_threshold=0.5, max_delegation_depth=3)
        if policy.should_escalate(actor_id, action, current_authority, depth):
            result = policy.escalate(actor_id, action, registry)
    """

    def __init__(
        self,
        authority_threshold: float,
        max_delegation_depth: int = 5,
        timeout_seconds: float = 30.0,
    ) -> None:
        """
        Args:
            authority_threshold: minimum authority level required to execute
                without escalation (compared against the actor's authority score).
            max_delegation_depth: maximum hops up the delegation chain.
            timeout_seconds: advisory timeout for the escalation handoff.
        """
        if authority_threshold < 0.0:
            raise ValueError("authority_threshold must be >= 0.")
        if max_delegation_depth < 1:
            raise ValueError("max_delegation_depth must be >= 1.")
        self.authority_threshold = authority_threshold
        self.max_delegation_depth = max_delegation_depth
        self.timeout_seconds = timeout_seconds

    def should_escalate(
        self,
        actor_id: str,
        action: str,
        current_authority: float,
        delegation_depth: int = 0,
    ) -> bool:
        """
        Return True if the actor should escalate this action.

        Escalation is required when:
          - current_authority < authority_threshold, OR
          - delegation_depth >= max_delegation_depth.

        Args:
            actor_id: the requesting actor.
            action: the action being requested.
            current_authority: numeric authority level of the actor.
            delegation_depth: current depth in the delegation chain.

        Returns:
            True if escalation is needed.
        """
        if delegation_depth >= self.max_delegation_depth:
            return True
        return current_authority < self.authority_threshold

    def escalate(
        self,
        actor_id: str,
        action: str,
        registry: "ActorRegistry",
        actor_authority_fn: Optional[callable] = None,
    ) -> Optional[EscalationResult]:
        """
        Find the next actor in the delegation chain with sufficient authority.

        The search performs a BFS up the *reverse* delegation graph
        (i.e., looks for actors who have delegated TO *actor_id*).

        Args:
            actor_id: the actor whose authority is insufficient.
            action: the action requiring escalation.
            registry: the full ActorRegistry.
            actor_authority_fn: optional callable ``(actor_id) -> float``
                that returns the authority level of an actor.  Defaults to
                looking at ``actor.metadata.get('authority', 0.0)``.

        Returns:
            An ``EscalationResult`` if a suitable superior is found,
            else ``None``.
        """
        def _authority(aid: str) -> float:
            if actor_authority_fn is not None:
                return float(actor_authority_fn(aid))
            actor = registry.get(aid)
            if actor is None:
                return 0.0
            return float(actor.metadata.get("authority", 0.0))

        # Build reverse delegation map: delegatee → set of delegators
        reverse_map: Dict[str, Set[str]] = {}
        for src, dst in registry._delegations:
            reverse_map.setdefault(dst, set()).add(src)

        visited: Set[str] = set()
        queue = list(reverse_map.get(actor_id, []))
        depth = 0

        while queue and depth < self.max_delegation_depth:
            next_queue: List[str] = []
            for superior_id in queue:
                if superior_id in visited:
                    continue
                visited.add(superior_id)
                auth = _authority(superior_id)
                if auth >= self.authority_threshold:
                    return EscalationResult(
                        escalated_to=superior_id,
                        reason=(
                            f"Actor '{actor_id}' lacked sufficient authority "
                            f"({auth:.2f} >= {self.authority_threshold:.2f}). "
                            f"Escalated to '{superior_id}'."
                        ),
                        authority_level=auth,
                    )
                next_queue.extend(reverse_map.get(superior_id, []))
            queue = next_queue
            depth += 1

        return None
