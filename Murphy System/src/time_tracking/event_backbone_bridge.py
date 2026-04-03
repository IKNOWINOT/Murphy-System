# Copyright © 2020 Inoni Limited Liability Company
# License: BSL 1.1
"""
Time Tracking — EventBackbone Bridge
======================================

Bridges the time-tracking :class:`InvoicingHookManager` internal event
system to the system-wide :class:`EventBackbone`.

Usage::

    from time_tracking.invoicing_hooks import InvoicingHookManager
    from event_backbone import EventBackbone  # system-wide backbone

    hook_manager = InvoicingHookManager()
    backbone = EventBackbone(...)

    bridge_time_tracking_to_backbone(hook_manager, backbone)
    # Now every InvoicingHookManager event is also published to the backbone.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def bridge_time_tracking_to_backbone(
    hook_manager: Any,
    backbone: Any,
) -> None:
    """Bridge :class:`InvoicingHookManager` events to :class:`EventBackbone`.

    For every :class:`~time_tracking.invoicing_hooks.TimeTrackingEvent`
    value, registers a hook on *hook_manager* that publishes the event
    payload to *backbone*.

    Args:
        hook_manager: An :class:`InvoicingHookManager` instance.
        backbone: The system-wide :class:`EventBackbone` instance.
    """
    try:
        from time_tracking.invoicing_hooks import TimeTrackingEvent  # type: ignore[import]
    except ImportError:
        logger.error(
            "time_tracking.invoicing_hooks not available; bridge not installed"
        )
        return

    for event in TimeTrackingEvent:
        def _forwarder(
            event_type: str,
            payload: Dict[str, Any],
            _bb: Any = backbone,
        ) -> None:
            """Forward a single time-tracking event to the EventBackbone.

            ``event_type`` is the string value passed by
            :meth:`InvoicingHookManager.emit` at call time (e.g.
            ``"entry_approved"``).  The loop variable ``event`` is *not*
            captured here; the hook manager always passes the actual event
            type as the first argument to registered callbacks.
            """
            try:
                from event_backbone_client import publish as _bb_publish  # noqa: PLC0415
                _bb_publish(
                    event_type,
                    payload,
                    source="time_tracking_bridge",
                    backbone=_bb,
                )
            except ImportError:
                # Fallback: call backbone.publish directly
                _bb.publish(event_type, payload)
            except Exception:
                logger.debug(
                    "EventBackbone publish skipped for time_tracking event %r",
                    event_type,
                )

        hook_manager.register_hook(event, _forwarder)

    logger.info(
        "Time-tracking bridge installed: %d event type(s) forwarded to EventBackbone",
        len(list(TimeTrackingEvent)),
    )
