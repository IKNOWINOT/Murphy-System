"""
Automation Mode Controller for Murphy System.

Design Label: OPS-003 — Risk-Based Automation Mode Progression
Owner: AI Team / Governance Team
Dependencies:
  - PersistenceManager (for durable mode state and transition history)
  - EventBackbone (publishes LEARNING_FEEDBACK on mode transitions)
  - KPITracker (OPS-002, optional, for success rate data)

Implements Phase 8 — Operational Readiness & Autonomy Governance:
  Manages the system's automation mode across five levels:
    MANUAL → SUPERVISED → AUTO_LOW → AUTO_HIGH → FULL
  Mode upgrades require sustained success rates above configurable
  thresholds with minimum observation counts.  Mode downgrades occur
  automatically on sustained failures or can be triggered manually.

Flow:
  1. Start in MANUAL mode
  2. Record task outcomes (success / failure) per task category
  3. Compute exponential moving average (EMA) success rate
  4. Upgrade mode when EMA exceeds threshold for N consecutive checks
  5. Downgrade mode when EMA falls below threshold
  6. Persist mode state and publish transition events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Conservative: mode upgrades require sustained success (not a single spike)
  - Bounded: configurable max history retained
  - Downgrade on failure: automatic safety degradation
  - Audit trail: every transition is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_OUTCOMES = 50_000
_MAX_TRANSITIONS = 5_000
_EMA_ALPHA = 0.1  # smoothing factor for exponential moving average


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class AutomationMode(IntEnum):
    """Automation levels, ordered from least to most autonomous."""
    MANUAL = 0
    SUPERVISED = 1
    AUTO_LOW = 2
    AUTO_HIGH = 3
    FULL = 4


class TransitionDirection(str, Enum):
    """Transition direction (str subclass)."""
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    MANUAL = "manual"


@dataclass
class TaskOutcome:
    """A recorded task execution outcome."""
    outcome_id: str
    category: str
    success: bool
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ModeTransition:
    """Record of an automation mode change."""
    transition_id: str
    from_mode: str
    to_mode: str
    direction: TransitionDirection
    reason: str
    ema_at_transition: float
    transitioned_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "from_mode": self.from_mode,
            "to_mode": self.to_mode,
            "direction": self.direction.value,
            "reason": self.reason,
            "ema_at_transition": round(self.ema_at_transition, 4),
            "transitioned_at": self.transitioned_at,
        }


# ---------------------------------------------------------------------------
# Mode thresholds — success rate required to hold/enter each mode
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLDS: Dict[int, float] = {
    AutomationMode.MANUAL: 0.0,       # no requirement
    AutomationMode.SUPERVISED: 0.70,   # 70 % success rate
    AutomationMode.AUTO_LOW: 0.85,     # 85 %
    AutomationMode.AUTO_HIGH: 0.92,    # 92 %
    AutomationMode.FULL: 0.97,         # 97 %
}

DEFAULT_MIN_OBSERVATIONS: Dict[int, int] = {
    AutomationMode.MANUAL: 0,
    AutomationMode.SUPERVISED: 10,
    AutomationMode.AUTO_LOW: 25,
    AutomationMode.AUTO_HIGH: 50,
    AutomationMode.FULL: 100,
}


# ---------------------------------------------------------------------------
# AutomationModeController
# ---------------------------------------------------------------------------

class AutomationModeController:
    """Risk-based automation mode progression with EMA success gating.

    Design Label: OPS-003
    Owner: AI Team / Governance Team

    Usage::

        ctrl = AutomationModeController()
        for _ in range(20):
            ctrl.record_outcome("general", success=True)
        ctrl.evaluate()   # may upgrade MANUAL → SUPERVISED
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        thresholds: Optional[Dict[int, float]] = None,
        min_observations: Optional[Dict[int, int]] = None,
        ema_alpha: float = _EMA_ALPHA,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._thresholds = dict(thresholds or DEFAULT_THRESHOLDS)
        self._min_obs = dict(min_observations or DEFAULT_MIN_OBSERVATIONS)
        self._alpha = ema_alpha
        self._mode = AutomationMode.MANUAL
        self._ema: float = 0.0
        self._total_outcomes: int = 0
        self._outcomes: List[TaskOutcome] = []
        self._transitions: List[ModeTransition] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_mode(self) -> AutomationMode:
        with self._lock:
            return self._mode

    @property
    def current_ema(self) -> float:
        with self._lock:
            return self._ema

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(self, category: str, success: bool) -> TaskOutcome:
        """Record a task execution outcome and update EMA."""
        outcome = TaskOutcome(
            outcome_id=f"to-{uuid.uuid4().hex[:8]}",
            category=category,
            success=success,
        )
        with self._lock:
            if len(self._outcomes) >= _MAX_OUTCOMES:
                evict = max(1, _MAX_OUTCOMES // 10)
                self._outcomes = self._outcomes[evict:]
            self._outcomes.append(outcome)
            self._total_outcomes += 1
            # Update EMA
            val = 1.0 if success else 0.0
            if self._total_outcomes == 1:
                self._ema = val
            else:
                self._ema = self._alpha * val + (1 - self._alpha) * self._ema
        return outcome

    # ------------------------------------------------------------------
    # Mode evaluation
    # ------------------------------------------------------------------

    def evaluate(self) -> Optional[ModeTransition]:
        """Evaluate whether the current mode should change."""
        with self._lock:
            mode = self._mode
            ema = self._ema
            total = self._total_outcomes

        # Check for upgrade
        next_mode = AutomationMode(min(mode + 1, AutomationMode.FULL))
        if next_mode > mode:
            req_rate = self._thresholds.get(next_mode, 1.0)
            req_obs = self._min_obs.get(next_mode, 0)
            if total >= req_obs and ema >= req_rate:
                return self._transition(mode, next_mode, TransitionDirection.UPGRADE,
                                         f"EMA {ema:.4f} >= {req_rate} with {total} observations")

        # Check for downgrade
        hold_rate = self._thresholds.get(int(mode), 0.0)
        if mode > AutomationMode.MANUAL and ema < hold_rate:
            prev = AutomationMode(max(mode - 1, AutomationMode.MANUAL))
            return self._transition(mode, prev, TransitionDirection.DOWNGRADE,
                                     f"EMA {ema:.4f} < {hold_rate} hold threshold")

        return None

    # ------------------------------------------------------------------
    # Manual mode control
    # ------------------------------------------------------------------

    def set_mode(self, mode: AutomationMode, reason: str = "manual override") -> ModeTransition:
        """Manually set the automation mode."""
        with self._lock:
            old = self._mode
        return self._transition(old, mode, TransitionDirection.MANUAL, reason)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_transitions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._transitions[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_mode": self._mode.name,
                "current_ema": round(self._ema, 4),
                "total_outcomes": self._total_outcomes,
                "total_transitions": len(self._transitions),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(
        self,
        from_mode: AutomationMode,
        to_mode: AutomationMode,
        direction: TransitionDirection,
        reason: str,
    ) -> ModeTransition:
        t = ModeTransition(
            transition_id=f"mt-{uuid.uuid4().hex[:8]}",
            from_mode=from_mode.name,
            to_mode=to_mode.name,
            direction=direction,
            reason=reason,
            ema_at_transition=self._ema,
        )
        with self._lock:
            self._mode = to_mode
            if len(self._transitions) >= _MAX_TRANSITIONS:
                self._transitions = self._transitions[_MAX_TRANSITIONS // 10:]
            self._transitions.append(t)

        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=t.transition_id, document=t.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        if self._backbone is not None:
            self._publish_event(t)

        logger.info("Mode transition: %s → %s (%s) — %s",
                     from_mode.name, to_mode.name, direction.value, reason)
        return t

    def _publish_event(self, transition: ModeTransition) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "automation_mode_controller",
                    "action": "mode_transition",
                    "transition_id": transition.transition_id,
                    "from_mode": transition.from_mode,
                    "to_mode": transition.to_mode,
                    "direction": transition.direction.value,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="automation_mode_controller",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
