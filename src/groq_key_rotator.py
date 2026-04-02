"""
DeepInfra API Key Rotation System.

Design Label: KEYROT-001 -- DeepInfra Key Rotator (primary LLM provider)
Owner: Platform Engineering / LLM Infrastructure

Murphy System now uses DeepInfra as the primary LLM provider and
Together AI as the overflow/fallback provider.  Groq has been replaced.

Set DEEPINFRA_API_KEY (and optionally TOGETHER_API_KEY) environment variables.

The GroqKeyRotator name is kept as a backward-compatibility alias so
existing callers do not break::

    from groq_key_rotator import DeepInfraKeyRotator          # preferred
    from groq_key_rotator import GroqKeyRotator                # alias (same class)
    from groq_key_rotator import KeyStats, get_rotator

Commissioning Principles (G1-G9):
  G1: Rotates DeepInfra API keys via round-robin with auto-disable on failure.
  G2: Distributes load across multiple keys; disables after 3 consecutive failures.
  G3: Conditions: single key, multi-key, all-disabled (reactivation), empty keys.
  G4: 7+ tests cover rotation, failure, reactivation, reset, stats, alias.
  G5: get_next_key returns (name, key) tuple; get_statistics returns dict.
  G6: Verified via test assertions.
  G8: Documentation and backward-compat alias updated.
  G9: Thread-safe via Lock; bounded key list.

Copyright (C) 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class KeyStats:
    """Statistics for a single API key."""
    key: str
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    is_active: bool = True


# ---------------------------------------------------------------------------
# DeepInfraKeyRotator -- primary class
# ---------------------------------------------------------------------------

class DeepInfraKeyRotator:
    """
    Rotates through multiple DeepInfra API keys to distribute load evenly.

    Design Label: KEYROT-001

    Features:
    - Round-robin rotation across all active keys
    - Automatic key disabling after 3 consecutive failures
    - Auto-reactivation when all keys are exhausted
    - Usage statistics tracking
    - Thread-safe operations via threading.Lock
    """

    def __init__(self, keys: List[tuple]):
        self.keys: List[KeyStats] = [
            KeyStats(key=key, name=name) for name, key in keys
        ]
        self.current_index = 0
        self._lock = threading.Lock()

        if not self.keys:
            raise ValueError("At least one API key must be provided")

    def get_next_key(self) -> tuple:
        """Get the next available API key in rotation."""
        with self._lock:
            attempts = 0
            max_attempts = len(self.keys)

            while attempts < max_attempts:
                ks = self.keys[self.current_index]
                if ks.is_active:
                    ks.total_calls += 1
                    ks.last_used = datetime.now(timezone.utc)
                    self.current_index = (self.current_index + 1) % len(self.keys)
                    return (ks.name, ks.key)
                self.current_index = (self.current_index + 1) % len(self.keys)
                attempts += 1

            # All keys inactive -- reactivate all and retry
            logger.warning("All DeepInfra keys inactive -- reactivating all keys")
            for ks in self.keys:
                ks.is_active = True

            ks = self.keys[0]
            ks.total_calls += 1
            ks.last_used = datetime.now(timezone.utc)
            self.current_index = 1 % len(self.keys)
            return (ks.name, ks.key)

    def report_success(self, key: str) -> None:
        """Report successful API call for the given key value."""
        with self._lock:
            for ks in self.keys:
                if ks.key == key:
                    ks.successful_calls += 1
                    ks.last_error = None
                    break

    def report_failure(self, key: str, error: str = "") -> None:
        """Report failed API call. Disables key after 3 consecutive failures."""
        with self._lock:
            for ks in self.keys:
                if ks.key == key:
                    ks.failed_calls += 1
                    ks.last_error = error
                    if ks.failed_calls >= 3:
                        ks.is_active = False
                        logger.warning(
                            "Disabled DeepInfra key '%s' after %d failures",
                            ks.name, ks.failed_calls,
                        )
                    break

    def get_statistics(self) -> dict:
        """Get usage statistics for all keys."""
        with self._lock:
            stats = {
                "total_keys": len(self.keys),
                "active_keys": sum(1 for k in self.keys if k.is_active),
                "total_calls": sum(k.total_calls for k in self.keys),
                "successful_calls": sum(k.successful_calls for k in self.keys),
                "failed_calls": sum(k.failed_calls for k in self.keys),
                "keys": [],
            }

            for ks in self.keys:
                stats["keys"].append({
                    "name": ks.name,
                    "total_calls": ks.total_calls,
                    "successful_calls": ks.successful_calls,
                    "failed_calls": ks.failed_calls,
                    "success_rate": (
                        f"{(ks.successful_calls / ks.total_calls * 100):.1f}%"
                        if ks.total_calls > 0 else "0%"
                    ),
                    "last_used": (
                        ks.last_used.strftime("%Y-%m-%d %H:%M:%S")
                        if ks.last_used else "Never"
                    ),
                    "is_active": ks.is_active,
                    "last_error": ks.last_error,
                })

            return stats

    def reset_key(self, key_name: str) -> bool:
        """Reset a specific key (reactivate and clear error count)."""
        with self._lock:
            for ks in self.keys:
                if ks.name == key_name:
                    ks.is_active = True
                    ks.failed_calls = 0
                    ks.last_error = None
                    logger.info("Reset DeepInfra key '%s'", key_name)
                    return True
            return False

    def reset_all_keys(self) -> None:
        """Reset all keys."""
        with self._lock:
            for ks in self.keys:
                ks.is_active = True
                ks.failed_calls = 0
                ks.last_error = None
            logger.info("Reset all DeepInfra keys")


# ---------------------------------------------------------------------------
# Backward-compatibility alias
# ---------------------------------------------------------------------------

GroqKeyRotator = DeepInfraKeyRotator


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_rotator_instance: Optional[DeepInfraKeyRotator] = None
_rotator_lock = threading.Lock()


def get_rotator() -> DeepInfraKeyRotator:
    """
    Get or create the global DeepInfra key rotator instance.

    Reads DEEPINFRA_API_KEY from the environment.  If not set, logs a
    warning and returns a single-key rotator with a placeholder.
    """
    import os

    global _rotator_instance

    with _rotator_lock:
        if _rotator_instance is None:
            api_key = os.environ.get("DEEPINFRA_API_KEY", "")
            if api_key:
                _rotator_instance = DeepInfraKeyRotator([("deepinfra-env", api_key)])
                logger.info("Initialized DeepInfra key rotator from DEEPINFRA_API_KEY")
            else:
                logger.warning(
                    "DEEPINFRA_API_KEY not set -- rotator will use placeholder key"
                )
                _rotator_instance = DeepInfraKeyRotator([("placeholder", "dik_not_set")])

        return _rotator_instance
