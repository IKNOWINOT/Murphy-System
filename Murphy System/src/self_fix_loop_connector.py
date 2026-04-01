"""
Self-Fix Loop Connector for Murphy System.

Design Label: WIRE-002 — SelfFixLoop → AutomationLoopConnector Bridge
Owner: Platform Engineering
Dependencies:
  - SelfFixLoop (ARCH-005)
  - AutomationLoopConnector (DEV-001)
  - EventBackbone (optional, for event-driven triggering)

Routes SelfFixLoop diagnosed gaps into the AutomationLoopConnector
by publishing TASK_FAILED events for critical/high severity gaps so
that the connector's existing _on_task_failed handler picks them up
naturally without directly manipulating internal state.

Bridge flow:
  1. Subscribed to SELF_FIX_COMPLETED events (if EventBackbone provided)
  2. bridge_gaps() calls self_fix_loop.diagnose() to enumerate gaps
  3. For each critical/high gap: publish TASK_FAILED event
  4. Publishes LEARNING_FEEDBACK summary of all bridged gaps
  5. get_status() exposes gaps_bridged counter, last_bridge_time, etc.

Safety invariants:
  - Never modifies source files on disk
  - Thread-safe operation with Lock
  - Graceful degradation when EventBackbone is None

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_HIGH_SEVERITY_LEVELS = frozenset({"critical", "high"})


class SelfFixLoopConnector:
    """Bridges SelfFixLoop gap diagnosis into AutomationLoopConnector.

    Design Label: WIRE-002
    Owner: Platform Engineering

    Subscribes to SELF_FIX_COMPLETED events and/or accepts manual
    bridge_gaps() calls.  For each gap with severity ``critical`` or
    ``high`` it publishes a TASK_FAILED event so that the
    AutomationLoopConnector's existing subscription handler queues it
    as an outcome for the next improvement cycle.

    Usage::

        connector = SelfFixLoopConnector(
            self_fix_loop=loop,
            automation_connector=auto_connector,
            event_backbone=backbone,
        )
        result = connector.bridge_gaps()
    """

    def __init__(
        self,
        self_fix_loop=None,
        automation_connector=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._fix_loop = self_fix_loop
        self._connector = automation_connector
        self._backbone = event_backbone

        self._gaps_bridged: int = 0
        self._last_bridge_time: Optional[str] = None
        self._bridge_history: List[Dict[str, Any]] = []

        if self._backbone is not None:
            self._subscribe_events()

    # ------------------------------------------------------------------
    # Event subscription
    # ------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        """Subscribe to SELF_FIX_COMPLETED events on the EventBackbone."""
        try:
            from event_backbone import EventType

            def _on_self_fix_completed(event) -> None:
                logger.debug("SelfFixLoopConnector: received SELF_FIX_COMPLETED — running bridge_gaps")
                self.bridge_gaps()

            self._backbone.subscribe(EventType.SELF_FIX_COMPLETED, _on_self_fix_completed)
            logger.info("SelfFixLoopConnector subscribed to SELF_FIX_COMPLETED")
        except Exception as exc:
            logger.warning("SelfFixLoopConnector: failed to subscribe to EventBackbone: %s", exc)

    # ------------------------------------------------------------------
    # Core bridging
    # ------------------------------------------------------------------

    def bridge_gaps(self) -> Dict[str, Any]:
        """Run diagnosis and route critical/high gaps into the connector.

        Returns a summary dict with gaps_found, gaps_bridged, skipped.
        """
        if self._fix_loop is None:
            logger.debug("SelfFixLoopConnector: no SelfFixLoop attached, skipping bridge_gaps")
            return {"gaps_found": 0, "gaps_bridged": 0, "skipped": 0, "error": "no_fix_loop"}

        # Diagnose
        try:
            gaps = self._fix_loop.diagnose()
        except Exception as exc:
            logger.warning("SelfFixLoopConnector: diagnose() failed: %s", exc)
            return {"gaps_found": 0, "gaps_bridged": 0, "skipped": 0, "error": str(exc)}

        bridged = 0
        skipped = 0
        bridged_summaries: List[Dict[str, Any]] = []

        for gap in gaps:
            severity = (gap.severity or "medium").lower()
            if severity not in _HIGH_SEVERITY_LEVELS:
                skipped += 1
                continue

            payload = {
                "task_id": gap.gap_id,
                "task_type": gap.category or "self_fix",
                "failure_category": gap.source,
                "session_id": "self_fix_loop",
                "metrics": {
                    "severity": gap.severity,
                    "source": gap.source,
                    "description": gap.description,
                },
            }

            # Publish TASK_FAILED so AutomationLoopConnector picks it up naturally
            if self._backbone is not None:
                try:
                    from event_backbone import EventType
                    self._backbone.publish(EventType.TASK_FAILED, payload)
                    bridged += 1
                    bridged_summaries.append({
                        "gap_id": gap.gap_id,
                        "severity": severity,
                        "source": gap.source,
                    })
                except Exception as exc:
                    logger.warning(
                        "SelfFixLoopConnector: failed to publish TASK_FAILED for gap %s: %s",
                        gap.gap_id, exc,
                    )
                    skipped += 1
            elif self._connector is not None:
                # Fallback: queue directly into the connector when no backbone
                try:
                    self._connector._queue_outcome(payload, "failure")
                    bridged += 1
                    bridged_summaries.append({
                        "gap_id": gap.gap_id,
                        "severity": severity,
                        "source": gap.source,
                    })
                except Exception as exc:
                    logger.warning(
                        "SelfFixLoopConnector: direct queue fallback failed for gap %s: %s",
                        gap.gap_id, exc,
                    )
                    skipped += 1
            else:
                # No backbone and no connector — nothing we can do
                logger.debug(
                    "SelfFixLoopConnector: no backbone or connector, gap %s not bridged",
                    gap.gap_id,
                )
                skipped += 1

        # Publish LEARNING_FEEDBACK summary
        if self._backbone is not None and bridged_summaries:
            try:
                from event_backbone import EventType
                self._backbone.publish(EventType.LEARNING_FEEDBACK, {
                    "source": "SelfFixLoopConnector",
                    "gaps_bridged": bridged,
                    "gaps_skipped": skipped,
                    "gaps_total": len(gaps),
                    "bridged": bridged_summaries,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as exc:
                logger.debug("SelfFixLoopConnector: LEARNING_FEEDBACK publish failed: %s", exc)

        now = datetime.now(timezone.utc).isoformat()
        bridge_record = {
            "bridge_id": f"bridge-{uuid.uuid4().hex[:8]}",
            "gaps_found": len(gaps),
            "gaps_bridged": bridged,
            "skipped": skipped,
            "timestamp": now,
        }

        with self._lock:
            self._gaps_bridged += bridged
            self._last_bridge_time = now
            capped_append(self._bridge_history, bridge_record, max_size=100)

        logger.info(
            "SelfFixLoopConnector bridge_gaps: found=%d bridged=%d skipped=%d",
            len(gaps), bridged, skipped,
        )
        return bridge_record

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return current status of the connector."""
        with self._lock:
            return {
                "gaps_bridged_total": self._gaps_bridged,
                "last_bridge_time": self._last_bridge_time,
                "bridge_count": len(self._bridge_history),
                "fix_loop_attached": self._fix_loop is not None,
                "automation_connector_attached": self._connector is not None,
                "event_backbone_attached": self._backbone is not None,
            }

    def get_bridge_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent bridge run summaries."""
        with self._lock:
            return list(self._bridge_history[-limit:])
