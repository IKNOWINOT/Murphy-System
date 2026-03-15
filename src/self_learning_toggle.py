# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Self-Learning Toggle
====================

Thread-safe singleton that acts as a master on/off switch for all
learning, training-data collection, model retraining, and disk-write
operations across the Murphy System learning subsystems.

Default is **disabled** (False) to protect disk space.  Enable only when
you have confirmed adequate storage and want the system to accumulate
training data and retrain.

When disabled, learning-subsystem code paths should call
``is_enabled()`` as an early-return guard instead of performing any
disk-write or memory-accumulation work.  A lightweight counter
tracks how many operations were *skipped* so the user can see the
activity level without incurring storage cost.

Env var: ``SELF_LEARNING_ENABLED=1`` (or 0)

Usage::

    from src.self_learning_toggle import get_self_learning_toggle

    slt = get_self_learning_toggle()
    if not slt.is_enabled():
        slt.increment_skipped()
        return  # no disk writes

    # ... normal learning logic ...
"""

import logging
import os
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SelfLearningToggle:
    """
    Master on/off switch for all learning subsystems.

    Thread-safe singleton controller.  All public methods are safe to call
    from multiple threads simultaneously.
    """

    def __init__(self, enabled: bool = False) -> None:
        self._lock = threading.Lock()
        self._enabled: bool = enabled
        self._skipped_operations: int = 0

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------

    def is_enabled(self) -> bool:
        """Return True if self-learning is currently active."""
        with self._lock:
            return self._enabled

    def enable(self) -> Dict[str, Any]:
        """Enable all learning subsystems."""
        with self._lock:
            self._enabled = True
        logger.info("Self-learning ENABLED")
        return self.get_status()

    def disable(self) -> Dict[str, Any]:
        """Disable all learning subsystems (no disk writes)."""
        with self._lock:
            self._enabled = False
        logger.info("Self-learning DISABLED")
        return self.get_status()

    def toggle(self) -> Dict[str, Any]:
        """Toggle self-learning on/off and return the new status."""
        with self._lock:
            self._enabled = not self._enabled
        state = "ENABLED" if self._enabled else "DISABLED"
        logger.info("Self-learning toggled → %s", state)
        return self.get_status()

    def increment_skipped(self, count: int = 1) -> None:
        """
        Increment the counter of operations skipped because learning is off.

        Learning subsystems should call this whenever they short-circuit to
        give the user visibility into activity level without storing data.
        """
        with self._lock:
            self._skipped_operations += count

    def reset_skipped_counter(self) -> None:
        """Reset the skipped-operations counter to zero."""
        with self._lock:
            self._skipped_operations = 0

    def get_status(self) -> Dict[str, Any]:
        """
        Return a status snapshot.

        Example::

            {
              "self_learning_enabled": false,
              "skipped_operations": 1247,
              "note": "No disk writes — enable with /toggle self-learning"
            }
        """
        with self._lock:
            enabled = self._enabled
            skipped = self._skipped_operations
        return {
            "self_learning_enabled": enabled,
            "skipped_operations": skipped,
            "note": (
                "Learning active — training data is being collected and stored."
                if enabled
                else (
                    f"Learning disabled — {skipped:,} operations skipped (no disk writes). "
                    "Enable with /toggle self-learning."
                )
            ),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_toggle: Optional[SelfLearningToggle] = None
_toggle_lock = threading.Lock()


def get_self_learning_toggle() -> SelfLearningToggle:
    """Return the process-wide singleton SelfLearningToggle."""
    global _toggle
    if _toggle is None:
        with _toggle_lock:
            if _toggle is None:
                # Check env var first (explicit override), then config.
                # When neither is set, default to ENABLED to preserve existing behavior.
                env_val = os.environ.get("SELF_LEARNING_ENABLED", "").strip().lower()
                if env_val in ("0", "false", "no", "off"):
                    enabled = False
                elif env_val in ("1", "true", "yes", "on"):
                    enabled = True
                else:
                    # No explicit env var set — default to True to preserve existing
                    # behavior for systems that have not yet opted into the toggle.
                    # Users explicitly disable learning via SELF_LEARNING_ENABLED=0.
                    enabled = True
                _toggle = SelfLearningToggle(enabled=enabled)
    return _toggle
