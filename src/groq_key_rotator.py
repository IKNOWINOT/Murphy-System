"""
Deprecated: Groq key rotation is no longer used.
Murphy System now uses DeepInfra (primary) and Together AI (overflow).
Set DEEPINFRA_API_KEY and TOGETHER_API_KEY environment variables.
This module is kept for import compatibility only.
"""
import logging

logger = logging.getLogger(__name__)


class KeyStats:
    """Deprecated stub."""
    def __init__(self, key="", name=""):
        self.key = key
        self.name = name
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.last_used = None
        self.last_error = None
        self.is_active = False


class GroqKeyRotator:
    """Deprecated stub — kept for import compatibility."""

    def __init__(self, keys=None):
        logger.warning(
            "GroqKeyRotator is deprecated. Use DEEPINFRA_API_KEY / TOGETHER_API_KEY instead."
        )
        self.keys = []
        self.current_index = 0

    def get_next_key(self):
        return None

    def report_success(self, key):
        pass

    def report_failure(self, key, error=""):
        pass

    def reset_key(self, name):
        return False

    def get_statistics(self):
        return {"keys": [], "total_calls": 0, "successful_calls": 0, "failed_calls": 0}


def get_rotator():
    """Deprecated — returns a stub rotator."""
    logger.warning("get_rotator() is deprecated. Use DEEPINFRA_API_KEY instead.")
    return GroqKeyRotator()
