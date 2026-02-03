"""Third-party analytics hooks (placeholder)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_enabled = False

def enable(api_key: str) -> None:
    global _enabled
    _enabled = True
    logger.info("Analytics enabled")

def track_event(name: str, data: dict) -> None:
    if not _enabled:
        return
    logger.info("event %s %s", name, data)
