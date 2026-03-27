# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Test Mode Controller
====================

Thread-safe controller that manages disposable test API key sessions with
hard call-count and time limits.  When either limit is reached, the session
is automatically ended and all further API calls receive a 429 response.

Recommended free-tier key provider: DeepInfra (https://console.deepinfra.com/keys)
  - Generous rate limits, fast inference, zero cost
  - Register 2-3 keys for round-robin via the key-rotation system

Usage::

    from src.test_mode_controller import get_test_mode_controller

    ctrl = get_test_mode_controller()
    ctrl.start_session(api_keys=["gsk_test_key_1"])
    ok, reason = ctrl.check_limits()          # True if within limits
    ctrl.record_call()                        # count every /api/* hit
    print(ctrl.get_status())
    ctrl.end_session()
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------

_SENTINEL = object()


class TestModeController:
    """
    Manages a disposable test API key session.

    Parameters
    ----------
    max_calls:   Hard call-count limit per session (default 50).
    max_seconds: Hard time limit per session in seconds (default 300 = 5 min).
    """

    def __init__(self, max_calls: int = 50, max_seconds: int = 300) -> None:
        self._lock = threading.Lock()
        self._max_calls = max_calls
        self._max_seconds = max_seconds

        # Session state
        self._active: bool = False
        self._session_ended: bool = False
        self._calls_used: int = 0
        self._session_start: Optional[float] = None
        self._test_api_keys: List[str] = []
        self._skipped_calls: int = 0  # calls that would have run if active

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_session(
        self,
        api_keys: Optional[List[str]] = None,
        max_calls: Optional[int] = None,
        max_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Start a new test session, optionally overriding limits and keys.

        Returns the session status dict.
        """
        with self._lock:
            if max_calls is not None:
                self._max_calls = max_calls
            if max_seconds is not None:
                self._max_seconds = max_seconds
            self._test_api_keys = list(api_keys or [])
            self._active = True
            self._session_ended = False
            self._calls_used = 0
            self._session_start = time.monotonic()

        logger.info(
            "Test session started — max_calls=%d, max_seconds=%d, keys=%d",
            self._max_calls,
            self._max_seconds,
            len(self._test_api_keys),
        )
        return self.get_status()

    def end_session(self) -> Dict[str, Any]:
        """Explicitly end the test session."""
        with self._lock:
            self._active = False
            self._session_ended = True
        logger.info("Test session ended — %d calls used", self._calls_used)
        return self.get_status()

    def is_active(self) -> bool:
        """Return True if a test session is currently active."""
        with self._lock:
            return self._active and not self._session_ended

    def record_call(self) -> None:
        """Increment the call counter.  Should be called on every /api/* hit."""
        with self._lock:
            if self._active and not self._session_ended:
                self._calls_used += 1
            else:
                self._skipped_calls += 1

    def check_limits(self) -> Tuple[bool, Optional[str]]:
        """
        Check whether the session is still within its limits.

        Returns
        -------
        (within_limits, reason)
            within_limits: True if session is OK to continue.
            reason:        None if OK; "call_limit_reached" or
                           "time_limit_reached" when the session must end.
        """
        with self._lock:
            if not self._active or self._session_ended:
                return False, "session_not_active"

            if self._calls_used >= self._max_calls:
                self._active = False
                self._session_ended = True
                logger.warning(
                    "Test session ended: call_limit_reached (%d/%d)",
                    self._calls_used,
                    self._max_calls,
                )
                return False, "call_limit_reached"

            elapsed = time.monotonic() - (self._session_start or 0.0)
            if elapsed >= self._max_seconds:
                self._active = False
                self._session_ended = True
                logger.warning(
                    "Test session ended: time_limit_reached (%.0fs/%ds)",
                    elapsed,
                    self._max_seconds,
                )
                return False, "time_limit_reached"

            return True, None

    def get_status(self) -> Dict[str, Any]:
        """
        Return a status snapshot.

        Example::

            {
              "test_mode": true,
              "calls_used": 12,
              "calls_remaining": 38,
              "seconds_elapsed": 42,
              "seconds_remaining": 258,
              "session_ended": false,
              "keys_count": 2
            }
        """
        with self._lock:
            elapsed = (
                time.monotonic() - self._session_start
                if self._session_start is not None
                else 0.0
            )
            seconds_remaining = max(0.0, self._max_seconds - elapsed)
            calls_remaining = max(0, self._max_calls - self._calls_used)
            return {
                "test_mode": self._active,
                "active": self._active,
                "session_ended": self._session_ended,
                "calls_used": self._calls_used,
                "calls_remaining": calls_remaining,
                "max_calls": self._max_calls,
                "seconds_elapsed": round(elapsed, 1),
                "seconds_remaining": round(seconds_remaining, 1),
                "max_seconds": self._max_seconds,
                "keys_count": len(self._test_api_keys),
                "skipped_calls": self._skipped_calls,
                "recommended_provider": {
                    "name": "DeepInfra (Free Tier)",
                    "url": "https://console.deepinfra.com/keys",
                    "note": (
                        "Generous free rate limits + fast inference. "
                        "Register 2-3 keys for round-robin key rotation."
                    ),
                },
            }

    def get_test_api_keys(self) -> List[str]:
        """Return the list of test API keys (safe to expose — disposable only)."""
        with self._lock:
            return list(self._test_api_keys)

    def toggle(self) -> Dict[str, Any]:
        """
        Toggle the test session on/off.

        If active, ends the session.  If inactive, starts a session using
        keys / limits from the module-level config.
        """
        with self._lock:
            currently_active = self._active and not self._session_ended

        if currently_active:
            return self.end_session()

        # Reload config so the latest env vars / .env settings are used
        try:
            from src.config import get_settings
            cfg = get_settings()
            raw_keys = cfg.test_mode_api_keys or ""
            keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
            max_calls = cfg.test_mode_max_calls
            max_seconds = cfg.test_mode_max_seconds
        except Exception:
            keys = []
            max_calls = self._max_calls
            max_seconds = self._max_seconds

        return self.start_session(api_keys=keys, max_calls=max_calls, max_seconds=max_seconds)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_controller: Optional[TestModeController] = None
_controller_lock = threading.Lock()


def get_test_mode_controller() -> TestModeController:
    """Return the process-wide singleton TestModeController."""
    global _controller
    if _controller is None:
        with _controller_lock:
            if _controller is None:
                try:
                    from src.config import get_settings
                    cfg = get_settings()
                    _controller = TestModeController(
                        max_calls=cfg.test_mode_max_calls,
                        max_seconds=cfg.test_mode_max_seconds,
                    )
                    # Auto-start if already enabled in env
                    if cfg.test_mode_enabled:
                        raw_keys = cfg.test_mode_api_keys or ""
                        keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
                        _controller.start_session(api_keys=keys)
                except Exception:
                    _controller = TestModeController()
    return _controller
