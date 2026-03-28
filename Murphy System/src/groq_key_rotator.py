"""
DeepInfra / Together.ai API Key Rotation System
Evenly distributes API calls across multiple keys to maximize throughput.

This module is retained for backward compatibility. The class was formerly
called ``GroqKeyRotator``; it is now ``DeepInfraKeyRotator``. An alias
``GroqKeyRotator = DeepInfraKeyRotator`` is preserved so existing imports
continue to work without modification.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger("deepinfra_key_rotator")


@dataclass
class KeyStats:
    """Statistics for a single API key"""
    key: str
    name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_used: Optional[datetime] = None
    last_error: Optional[str] = None
    is_active: bool = True


class DeepInfraKeyRotator:
    """
    Rotates through multiple DeepInfra (or Together.ai) API keys to
    distribute load evenly.

    Features:
    - Round-robin rotation
    - Automatic key disabling on repeated failures
    - Usage statistics tracking
    - Thread-safe operations
    """

    def __init__(self, keys: List[tuple]):
        """
        Initialize with list of (name, key) tuples.

        Args:
            keys: List of tuples like [("Murphy DeepInfra Key 1", "dik_..."), ...]
        """
        self.keys = [KeyStats(key=key, name=name) for name, key in keys]
        self.current_index = 0
        self.lock = threading.Lock()

        if not self.keys:
            raise ValueError("At least one API key must be provided")

    def get_next_key(self) -> tuple:
        """
        Get the next available API key in rotation.

        Returns:
            tuple: (key_name, api_key)
        """
        with self.lock:
            attempts = 0
            max_attempts = len(self.keys)

            while attempts < max_attempts:
                key_stats = self.keys[self.current_index]

                if key_stats.is_active:
                    key_stats.total_calls += 1
                    key_stats.last_used = datetime.now(timezone.utc)
                    self.current_index = (self.current_index + 1) % len(self.keys)
                    return (key_stats.name, key_stats.key)

                self.current_index = (self.current_index + 1) % len(self.keys)
                attempts += 1

            # All keys inactive — reactivate all and try again
            logger.warning("All DeepInfra keys inactive, reactivating all keys")
            for key_stats in self.keys:
                key_stats.is_active = True

            key_stats = self.keys[0]
            key_stats.total_calls += 1
            key_stats.last_used = datetime.now(timezone.utc)
            self.current_index = 1
            return (key_stats.name, key_stats.key)

    def report_success(self, key: str):
        """Report successful API call."""
        with self.lock:
            for key_stats in self.keys:
                if key_stats.key == key:
                    key_stats.successful_calls += 1
                    key_stats.last_error = None
                    break

    def report_failure(self, key: str, error: str):
        """
        Report failed API call.
        Automatically disables key after 3 consecutive failures.
        """
        with self.lock:
            for key_stats in self.keys:
                if key_stats.key == key:
                    key_stats.failed_calls += 1
                    key_stats.last_error = error
                    if key_stats.failed_calls >= 3:
                        key_stats.is_active = False
                        logger.warning(
                            "Disabled DeepInfra key '%s' after %d failures",
                            key_stats.name,
                            key_stats.failed_calls,
                        )
                    break

    def get_statistics(self) -> dict:
        """Get usage statistics for all keys."""
        with self.lock:
            stats = {
                "total_keys": len(self.keys),
                "active_keys": sum(1 for k in self.keys if k.is_active),
                "total_calls": sum(k.total_calls for k in self.keys),
                "successful_calls": sum(k.successful_calls for k in self.keys),
                "failed_calls": sum(k.failed_calls for k in self.keys),
                "keys": [],
            }

            for key_stats in self.keys:
                stats["keys"].append({
                    "name": key_stats.name,
                    "total_calls": key_stats.total_calls,
                    "successful_calls": key_stats.successful_calls,
                    "failed_calls": key_stats.failed_calls,
                    "success_rate": (
                        f"{(key_stats.successful_calls / key_stats.total_calls * 100):.1f}%"
                        if key_stats.total_calls > 0 else "0%"
                    ),
                    "last_used": (
                        key_stats.last_used.strftime("%Y-%m-%d %H:%M:%S")
                        if key_stats.last_used else "Never"
                    ),
                    "is_active": key_stats.is_active,
                    "last_error": key_stats.last_error,
                })

            return stats

    def reset_key(self, key_name: str) -> bool:
        """Reset a specific key (reactivate and clear error count)."""
        with self.lock:
            for key_stats in self.keys:
                if key_stats.name == key_name:
                    key_stats.is_active = True
                    key_stats.failed_calls = 0
                    key_stats.last_error = None
                    logger.info("Reset DeepInfra key '%s'", key_name)
                    return True
            return False

    def reset_all_keys(self):
        """Reset all keys."""
        with self.lock:
            for key_stats in self.keys:
                key_stats.is_active = True
                key_stats.failed_calls = 0
                key_stats.last_error = None
            logger.info("Reset all DeepInfra keys")


# ---------------------------------------------------------------------------
# Backward-compatibility alias (formerly GroqKeyRotator)
# ---------------------------------------------------------------------------
GroqKeyRotator = DeepInfraKeyRotator


# ---------------------------------------------------------------------------
# Key loading helpers
# ---------------------------------------------------------------------------

def load_keys_from_file(file_path: str) -> List[tuple]:
    """
    Load API keys from a plaintext file (DEPRECATED — use secure key manager).

    Expected format:
        Murphy DeepInfra Key 1 <dik_...>
        Murphy DeepInfra Key 2 <dik_...>

    Returns:
        List of (name, key) tuples
    """
    keys = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "<" in line and ">" in line:
                name = line.split("<")[0].strip()
                key = line.split("<")[1].split(">")[0].strip()
                keys.append((name, key))
    return keys


def load_keys_from_secure_storage() -> List[tuple]:
    """
    Load API keys from encrypted storage using SecureKeyManager.

    Returns:
        List of (name, key) tuples
    """
    try:
        from secure_key_manager import get_secure_key_manager
        manager = get_secure_key_manager()
        keys = manager.load_keys()
        if not keys:
            raise ValueError("No keys found in encrypted storage")
        return keys
    except Exception as exc:
        logger.warning("Failed to load keys from secure storage: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_rotator_instance: Optional[DeepInfraKeyRotator] = None
_rotator_lock = threading.Lock()


def get_rotator(
    use_secure_storage: bool = True,
    keys_file: Optional[str] = None,
) -> DeepInfraKeyRotator:
    """
    Get or create the global DeepInfra key rotator instance.

    Args:
        use_secure_storage: If True, load keys from encrypted storage (recommended).
        keys_file: Path to plaintext keys file (deprecated, for backward compatibility).

    Returns:
        DeepInfraKeyRotator instance
    """
    global _rotator_instance

    with _rotator_lock:
        if _rotator_instance is None:
            if use_secure_storage:
                keys = load_keys_from_secure_storage()
                logger.info("✅ Loaded %d keys from encrypted storage", len(keys))
            else:
                if keys_file is None:
                    keys_file = "/workspace/Murphy System Keys.txt"
                keys = load_keys_from_file(keys_file)
                logger.warning(
                    "⚠️  Loaded %d keys from plaintext file (DEPRECATED)", len(keys)
                )

            _rotator_instance = DeepInfraKeyRotator(keys)
            logger.info(
                "Initialized DeepInfra key rotator with %d keys", len(keys)
            )

        return _rotator_instance