# Copyright © 2020 Inoni Limited Liability Company
# License: BSL 1.1
"""
EventBackbone Client — lightweight publish facade.

Provides:

* A **global singleton** so modules that are not injected with a backbone
  can still publish events::

      from event_backbone_client import get_backbone, set_backbone, publish

      # At startup (murphy_system_core.py or similar):
      set_backbone(my_backbone_instance)

      # In any module — no constructor injection required:
      publish("task_submitted", {"task_id": "t-1"})

* **String → EventType auto-conversion** — callers may pass either a plain
  string (e.g. ``"task_submitted"`` or ``"TASK_SUBMITTED"``) or the
  ``EventType`` enum member directly.

* **Validation with logging** — unknown event type strings are rejected and
  logged as warnings instead of being silently dropped.

* **Drop logging** — when no backbone is available the event is explicitly
  logged as a warning instead of disappearing without a trace.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_global_backbone: Any = None


def set_backbone(backbone: Any) -> None:
    """Register the global :class:`~event_backbone.EventBackbone` singleton.

    Call this once at application startup (e.g. from
    ``MurphySystemCore._init_event_backbone()``) so all modules can publish
    without explicit injection.

    Args:
        backbone: A live :class:`~event_backbone.EventBackbone` instance.
    """
    global _global_backbone  # noqa: PLW0603
    _global_backbone = backbone
    logger.info(
        "EventBackboneClient: global backbone registered (%s)",
        type(backbone).__name__,
    )


def get_backbone() -> Any:
    """Return the global backbone singleton, or *None* if not yet wired."""
    return _global_backbone


# ---------------------------------------------------------------------------
# Publish helper
# ---------------------------------------------------------------------------


def publish(
    event_type: Union[str, Any],
    payload: Dict[str, Any],
    source: Optional[str] = None,
    session_id: Optional[str] = None,
    backbone: Optional[Any] = None,
) -> bool:
    """Publish an event, accepting both strings and :class:`~event_backbone.EventType` enum members.

    Resolution order for *backbone*:

    1. The explicitly supplied *backbone* argument (useful for injected modules).
    2. The global singleton registered via :func:`set_backbone`.

    Args:
        event_type: Either a :class:`~event_backbone.EventType` member or a
            string (value like ``"task_submitted"`` or name like
            ``"TASK_SUBMITTED"``).
        payload: Arbitrary dict payload attached to the event.
        source: Optional module/component name to embed in the event.
        session_id: Optional session identifier to embed in the event.
        backbone: Optional backbone instance; falls back to the global
            singleton when *None*.

    Returns:
        ``True`` if the event was successfully handed off to the backbone,
        ``False`` if it was dropped (and a warning was logged).
    """
    bb = backbone if backbone is not None else _global_backbone
    if bb is None:
        logger.warning(
            "EventBackboneClient: no backbone available, dropping event %r "
            "(call set_backbone() at startup)",
            event_type,
        )
        return False

    try:
        from event_backbone import EventType  # noqa: PLC0415

        if not isinstance(event_type, EventType):
            resolved = EventType.from_string(str(event_type))
        else:
            resolved = event_type
    except ImportError as exc:
        logger.warning(
            "EventBackboneClient: event_backbone module not importable, "
            "dropping event %r: %s",
            event_type,
            exc,
        )
        return False
    except ValueError:
        logger.warning(
            "EventBackboneClient: unknown event_type %r, dropping event "
            "(valid values: %s)",
            event_type,
            ", ".join(e.value for e in _iter_event_types()),
        )
        return False

    try:
        bb.publish(resolved, payload, session_id=session_id, source=source)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "EventBackboneClient: publish failed for %r: %s", event_type, exc
        )
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_event_types():
    """Yield all EventType members; yields nothing on ImportError."""
    try:
        from event_backbone import EventType  # noqa: PLC0415

        yield from EventType
    except ImportError:
        pass


__all__ = ["set_backbone", "get_backbone", "publish"]
