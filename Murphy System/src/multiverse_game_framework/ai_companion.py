"""
AI Companion System for the Multiverse Game Framework.

Design Label: GAME-006 — AI Companion System (Employer/Employee Dynamic)
Owner: Backend Team
Dependencies:
  - EventBackbone
  - PersistenceManager

Each player has an AI companion that either works for them (EMPLOYEE) or they
work for (EMPLOYER). The relationship is dynamic: trust thresholds can trigger
a role reversal, creating an interesting power dynamic.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Bounded collections with capped_append pattern (CWE-770)
  - Graceful degradation when subsystem dependencies are unavailable
  - Full audit trail via EventBackbone and PersistenceManager

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
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency imports with graceful fallback
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from event_backbone import EventBackbone, EventType
    _BACKBONE_AVAILABLE = True
except Exception:  # pragma: no cover
    EventBackbone = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment]
    _BACKBONE_AVAILABLE = False

try:
    from persistence_manager import PersistenceManager
    _PERSISTENCE_AVAILABLE = True
except Exception:  # pragma: no cover
    PersistenceManager = None  # type: ignore[assignment,misc]
    _PERSISTENCE_AVAILABLE = False

_MAX_DIRECTIVE_HISTORY = 500
_MAX_LOG = 10_000

# Trust thresholds for role reversal
_EMPLOYER_REVERSAL_THRESHOLD = 0.9   # EMPLOYEE→EMPLOYER flip when trust this high
_EMPLOYEE_REVERSAL_THRESHOLD = 0.15  # EMPLOYER→EMPLOYEE flip when trust drops this low

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AICompanionRole(str, Enum):
    """Role of the AI companion relative to the player character.

    EMPLOYER — the AI is the boss; it assigns tasks to the player.
    EMPLOYEE — the AI works for the player; the player assigns tasks.
    """
    EMPLOYER = "employer"
    EMPLOYEE = "employee"


class DirectiveStatus(str, Enum):
    """Lifecycle status of a directive."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUSED = "refused"


class Specialization(str, Enum):
    """Companion specialisation track."""
    COMBAT_ADVISOR = "combat_advisor"
    LOOT_ANALYST = "loot_analyst"
    NAVIGATION = "navigation"
    CRAFTING_EXPERT = "crafting_expert"
    SOCIAL_DIPLOMAT = "social_diplomat"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Directive:
    """A task assignment between player and AI companion.

    Args:
        directive_id: Unique UUID.
        issuer_id: ID of the issuing party (player or companion).
        recipient_id: ID of the receiving party.
        description: What must be done.
        status: Current lifecycle status.
        context: Optional key/value context for the task.
        issued_at: When the directive was issued.
        completed_at: When it was resolved (completed/failed/refused).
    """
    directive_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issuer_id: str = ""
    recipient_id: str = ""
    description: str = ""
    status: DirectiveStatus = DirectiveStatus.PENDING
    context: Dict[str, Any] = field(default_factory=dict)
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


@dataclass
class CompletionResult:
    """Result of evaluating a completed directive.

    Args:
        directive_id: The directive evaluated.
        success: Whether the objective was met.
        trust_delta: Change to companion trust score.
        notes: Additional evaluation notes.
    """
    directive_id: str
    success: bool
    trust_delta: float
    notes: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AICompanion:
    """An AI companion bound to a player character.

    Args:
        companion_id: Unique companion UUID.
        owner_character_id: Character that owns (or is owned by) this companion.
        role: Whether the AI is employer or employee.
        name: Companion display name.
        personality_type: Personality descriptor (e.g., "analytical", "aggressive").
        level: Companion's own progression level.
        specialization: Primary specialisation track.
        trust_score: Trust level 0.0–1.0.
        directive_queue: Outstanding directives.
        directive_history: All past directives.
    """
    companion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    owner_character_id: str = ""
    role: AICompanionRole = AICompanionRole.EMPLOYEE
    name: str = "Companion"
    personality_type: str = "balanced"
    level: int = 1
    specialization: Specialization = Specialization.COMBAT_ADVISOR
    trust_score: float = 0.5
    directive_queue: List[Directive] = field(default_factory=list)
    directive_history: List[Directive] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AICompanionEngine
# ---------------------------------------------------------------------------


class AICompanionEngine:
    """Creates and manages AI companions and the employer/employee dynamic.

    Role reversals occur automatically at trust thresholds to create an
    evolving power dynamic between player and AI companion.
    """

    def __init__(
        self,
        backbone: Optional[Any] = None,
        persistence: Optional[Any] = None,
    ) -> None:
        self._backbone = backbone
        self._persistence = persistence
        self._lock = threading.Lock()
        self._companions: Dict[str, AICompanion] = {}
        self._event_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Companion management
    # ------------------------------------------------------------------

    def create_companion(
        self,
        character_id: str,
        role: AICompanionRole,
        personality_type: str,
        name: str = "Companion",
        specialization: Specialization = Specialization.COMBAT_ADVISOR,
    ) -> AICompanion:
        """Create and register a new AI companion.

        Args:
            character_id: The owning character's ID.
            role: Initial role of the companion.
            personality_type: Personality descriptor string.
            name: Display name for the companion.
            specialization: Initial specialisation track.

        Returns:
            The newly created AICompanion.
        """
        companion = AICompanion(
            owner_character_id=character_id,
            role=role,
            name=name,
            personality_type=personality_type,
            specialization=specialization,
        )
        with self._lock:
            self._companions[companion.companion_id] = companion
        logger.info(
            "Created %s companion '%s' for character %s",
            role.value, name, character_id,
        )
        self._publish_event("companion_created", {
            "companion_id": companion.companion_id,
            "character_id": character_id,
            "role": role.value,
        })
        return companion

    def get_companion(self, companion_id: str) -> Optional[AICompanion]:
        """Return the AICompanion with the given ID, or None."""
        return self._companions.get(companion_id)

    # ------------------------------------------------------------------
    # Directive management
    # ------------------------------------------------------------------

    def issue_directive(
        self,
        companion: AICompanion,
        description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Directive:
        """Issue a directive from the active authority (player or AI).

        Direction of the directive depends on the companion's role:
        - EMPLOYEE: player issues directive to AI.
        - EMPLOYER: AI issues directive to player.

        Args:
            companion: The AICompanion relationship context.
            description: Task description.
            context: Optional additional context.

        Returns:
            The created Directive, added to the companion's queue.
        """
        if companion.role == AICompanionRole.EMPLOYEE:
            issuer_id = companion.owner_character_id
            recipient_id = companion.companion_id
        else:
            issuer_id = companion.companion_id
            recipient_id = companion.owner_character_id

        directive = Directive(
            issuer_id=issuer_id,
            recipient_id=recipient_id,
            description=description,
            context=context or {},
        )
        with self._lock:
            capped_append(companion.directive_queue, directive, 100)
        self._publish_event("directive_issued", {
            "directive_id": directive.directive_id,
            "companion_id": companion.companion_id,
            "role": companion.role.value,
            "description": description,
        })
        return directive

    def evaluate_directive_completion(
        self,
        companion: AICompanion,
        directive_id: str,
        success: bool,
        notes: str = "",
    ) -> CompletionResult:
        """Mark a directive as completed and update trust accordingly.

        Args:
            companion: The AICompanion whose directive to evaluate.
            directive_id: The directive being resolved.
            success: Whether the objective was met.
            notes: Optional evaluation notes.

        Returns:
            CompletionResult with trust delta and outcome.
        """
        directive: Optional[Directive] = None
        with self._lock:
            for d in companion.directive_queue:
                if d.directive_id == directive_id:
                    directive = d
                    break

        if directive is None:
            return CompletionResult(
                directive_id=directive_id,
                success=False,
                trust_delta=0.0,
                notes="Directive not found in queue.",
            )

        directive.status = DirectiveStatus.COMPLETED if success else DirectiveStatus.FAILED
        directive.completed_at = datetime.now(timezone.utc)

        trust_delta = self._calculate_trust_change(companion, {"success": success})
        new_trust = max(0.0, min(1.0, companion.trust_score + trust_delta))

        with self._lock:
            companion.trust_score = new_trust
            companion.directive_queue = [
                d for d in companion.directive_queue if d.directive_id != directive_id
            ]
            capped_append(companion.directive_history, directive, _MAX_DIRECTIVE_HISTORY)

        # Check for role reversal
        self._check_role_reversal(companion)

        result = CompletionResult(
            directive_id=directive_id,
            success=success,
            trust_delta=trust_delta,
            notes=notes,
        )
        self._publish_event("directive_completed", {
            "directive_id": directive_id,
            "companion_id": companion.companion_id,
            "success": success,
            "new_trust": new_trust,
        })
        return result

    def calculate_trust_change(
        self,
        companion: AICompanion,
        outcome: Dict[str, Any],
    ) -> float:
        """Public wrapper around internal trust calculation."""
        return self._calculate_trust_change(companion, outcome)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_trust_change(
        self,
        companion: AICompanion,
        outcome: Dict[str, Any],
    ) -> float:
        """Compute the trust delta from an outcome.

        Successes increase trust; failures or refusals decrease it.
        The magnitude scales with the companion's current trust level
        (low trust is easier to move; high trust takes more to shift).
        """
        success = outcome.get("success", False)
        refused = outcome.get("refused", False)

        if refused:
            return -0.1
        if success:
            # Gain is smaller the higher the trust (diminishing returns)
            gain = 0.05 * (1.0 - companion.trust_score * 0.5)
            return round(gain, 4)
        else:
            # Loss is larger the lower the trust (double-down effect)
            loss = 0.05 * (1.0 + (1.0 - companion.trust_score) * 0.5)
            return round(-loss, 4)

    def _check_role_reversal(self, companion: AICompanion) -> None:
        """Flip the companion role at extreme trust thresholds."""
        if (
            companion.role == AICompanionRole.EMPLOYEE
            and companion.trust_score >= _EMPLOYER_REVERSAL_THRESHOLD
        ):
            companion.role = AICompanionRole.EMPLOYER
            logger.info(
                "Role reversal: companion '%s' is now EMPLOYER (trust=%.2f)",
                companion.companion_id, companion.trust_score,
            )
            self._publish_event("companion_role_reversed", {
                "companion_id": companion.companion_id,
                "new_role": AICompanionRole.EMPLOYER.value,
                "trust_score": companion.trust_score,
            })
        elif (
            companion.role == AICompanionRole.EMPLOYER
            and companion.trust_score <= _EMPLOYEE_REVERSAL_THRESHOLD
        ):
            companion.role = AICompanionRole.EMPLOYEE
            logger.info(
                "Role reversal: companion '%s' is now EMPLOYEE (trust=%.2f)",
                companion.companion_id, companion.trust_score,
            )
            self._publish_event("companion_role_reversed", {
                "companion_id": companion.companion_id,
                "new_role": AICompanionRole.EMPLOYEE.value,
                "trust_score": companion.trust_score,
            })

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if _BACKBONE_AVAILABLE and self._backbone is not None:
            try:
                self._backbone.publish(event_type, payload)
            except Exception:  # pragma: no cover
                logger.debug("EventBackbone publish failed silently", exc_info=True)
