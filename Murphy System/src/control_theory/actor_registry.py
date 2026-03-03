"""
Unified Actor Registry and Authority Matrix for the Murphy System.

Provides:
  - Actor — single canonical identity for all agent types.
  - AuthorityMatrix — A[actor, action, resource] → bool.
  - ActorRegistry — single source of truth for all actors in the system.
  - Delegation graph with transitive closure and revocation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


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
