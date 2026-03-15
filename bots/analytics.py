"""Analytics backend — pluggable event tracking for Murphy System bots."""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class AnalyticsBackend(Protocol):
    """Protocol for analytics backends."""

    def track(self, name: str, data: dict) -> None:
        """Record an analytics event."""
        ...


class LoggingBackend:
    """Default analytics backend — logs events via Python logging."""

    def track(self, name: str, data: dict) -> None:
        logger.info("analytics event=%s data=%s", name, data)


class WebhookBackend:
    """Analytics backend that POSTs events to a configurable webhook URL.

    Designed for future integration with PostHog, Mixpanel, or any
    HTTP-based analytics provider.
    """

    def __init__(self, url: str, timeout: float = 5.0) -> None:
        self._url = url
        self._timeout = timeout

    def track(self, name: str, data: dict) -> None:
        payload = json.dumps({"event": name, "properties": data}).encode()
        req = urllib.request.Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout):
                pass
        except Exception as exc:
            logger.warning("WebhookBackend track failed for event %s: %s", name, exc)


# ---------------------------------------------------------------------------
# Module-level backend registry
# ---------------------------------------------------------------------------

_backend: AnalyticsBackend = LoggingBackend()
_enabled = False


def register_backend(backend: AnalyticsBackend) -> None:
    """Replace the active analytics backend."""
    global _backend
    _backend = backend


def enable(api_key: Optional[str] = None) -> None:
    """Enable analytics event dispatch."""
    global _enabled
    _enabled = True
    logger.info("Analytics enabled")


def track_event(name: str, data: dict) -> None:
    """Track an analytics event via the registered backend."""
    if not _enabled:
        return
    _backend.track(name, data)
