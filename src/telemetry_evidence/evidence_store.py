"""
Telemetry Evidence Store

Design Label: ARCH-007 — Telemetry Evidence Storage
Owner: Backend Team
Dependencies:
  - PersistenceManager (optional, for durable storage)
  - EventBackbone (optional, for event publishing)

Stores real telemetry snapshots for historical analysis, trend detection,
and evidence retrieval for incident investigation.

Flow:
  1. Record telemetry snapshots from any subsystem
  2. Store snapshots durably via PersistenceManager (if available)
  3. Query snapshots by time range, kind, or source
  4. Detect trends across snapshot history
  5. Retrieve evidence for incident investigation

Safety invariants:
  - Read-only analysis on stored snapshots
  - Thread-safe: all shared state guarded by Lock
  - Bounded: configurable max snapshot history (CWE-770)
  - No source file modification

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_SNAPSHOTS = 10_000

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


class SnapshotKind(str, Enum):
    """Kind of telemetry snapshot."""
    SYSTEM_HEALTH = "system_health"
    AGENT_METRICS = "agent_metrics"
    SLO_COMPLIANCE = "slo_compliance"
    KPI_SNAPSHOT = "kpi_snapshot"
    MAINTENANCE_ALERT = "maintenance_alert"
    FOUNDER_DIGEST = "founder_digest"
    CUSTOM = "custom"


@dataclass
class TelemetrySnapshot:
    """A single telemetry evidence snapshot."""
    snapshot_id: str
    kind: SnapshotKind
    source: str
    payload: Dict[str, Any]
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "kind": self.kind.value,
            "source": self.source,
            "payload": self.payload,
            "recorded_at": self.recorded_at,
            "tags": self.tags,
        }


@dataclass
class EvidenceQuery:
    """Query parameters for evidence retrieval."""
    kind: Optional[SnapshotKind] = None
    source: Optional[str] = None
    since: Optional[str] = None          # ISO timestamp lower bound
    until: Optional[str] = None          # ISO timestamp upper bound
    tags: Optional[List[str]] = None     # all tags must be present
    limit: int = 50


class TelemetryEvidenceStore:
    """Stores and retrieves real telemetry snapshots for evidence.

    Design Label: ARCH-007
    Owner: Backend Team

    Usage::

        store = TelemetryEvidenceStore()
        snap = store.record(SnapshotKind.SYSTEM_HEALTH, "operational_dashboard",
                            {"healthy": 5, "degraded": 1})
        results = store.query(EvidenceQuery(kind=SnapshotKind.SYSTEM_HEALTH))
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        max_snapshots: int = _MAX_SNAPSHOTS,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._max_snapshots = max_snapshots
        self._snapshots: List[TelemetrySnapshot] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        kind: SnapshotKind,
        source: str,
        payload: Dict[str, Any],
        tags: Optional[List[str]] = None,
    ) -> TelemetrySnapshot:
        """Record a telemetry snapshot and return it."""
        snap = TelemetrySnapshot(
            snapshot_id=f"ev-{uuid.uuid4().hex[:8]}",
            kind=kind,
            source=source,
            payload=payload,
            tags=tags or [],
        )

        with self._lock:
            capped_append(self._snapshots, snap, self._max_snapshots)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=snap.snapshot_id, document=snap.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(snap)

        logger.debug(
            "Recorded telemetry evidence %s kind=%s source=%s",
            snap.snapshot_id, kind.value, source,
        )
        return snap

    # ------------------------------------------------------------------
    # Query / retrieval
    # ------------------------------------------------------------------

    def query(self, q: Optional[EvidenceQuery] = None) -> List[Dict[str, Any]]:
        """Query stored snapshots.  Returns a list of snapshot dicts."""
        if q is None:
            q = EvidenceQuery()

        with self._lock:
            candidates = list(self._snapshots)

        results: List[TelemetrySnapshot] = []
        for snap in reversed(candidates):
            if q.kind and snap.kind != q.kind:
                continue
            if q.source and snap.source != q.source:
                continue
            if q.since:
                try:
                    if snap.recorded_at < q.since:
                        continue
                except Exception:
                    pass
            if q.until:
                try:
                    if snap.recorded_at > q.until:
                        continue
                except Exception:
                    pass
            if q.tags:
                if not all(t in snap.tags for t in q.tags):
                    continue
            results.append(snap)
            if len(results) >= q.limit:
                break

        return [s.to_dict() for s in results]

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single snapshot by ID."""
        with self._lock:
            for snap in self._snapshots:
                if snap.snapshot_id == snapshot_id:
                    return snap.to_dict()
        return None

    # ------------------------------------------------------------------
    # Trend detection
    # ------------------------------------------------------------------

    def detect_trend(self, kind: SnapshotKind, field_path: str, limit: int = 20) -> Dict[str, Any]:
        """Detect trend for a numeric field across recent snapshots.

        Args:
            kind: SnapshotKind to filter by.
            field_path: Dot-separated path into payload (e.g. "healthy_count").
            limit: Max snapshots to consider.

        Returns:
            Dict with keys: values, trend (rising/falling/stable), delta, count.
        """
        snaps = self.query(EvidenceQuery(kind=kind, limit=limit))
        values = []
        for s in reversed(snaps):  # chronological order
            payload = s.get("payload", {})
            v = _extract_field(payload, field_path)
            if v is not None:
                values.append(float(v))

        if len(values) < 2:
            return {"values": values, "trend": "insufficient_data", "delta": 0.0, "count": len(values)}

        delta = values[-1] - values[0]
        if abs(delta) < 0.001:
            trend = "stable"
        elif delta > 0:
            trend = "rising"
        else:
            trend = "falling"

        return {"values": values, "trend": trend, "delta": round(delta, 4), "count": len(values)}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return store status."""
        with self._lock:
            total = len(self._snapshots)
            by_kind: Dict[str, int] = {}
            for snap in self._snapshots:
                k = snap.kind.value
                by_kind[k] = by_kind.get(k, 0) + 1

        return {
            "total_snapshots": total,
            "by_kind": by_kind,
            "max_snapshots": self._max_snapshots,
            "persistence_attached": self._pm is not None,
            "backbone_attached": self._backbone is not None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, snap: TelemetrySnapshot) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "telemetry_evidence_store",
                    "action": "snapshot_recorded",
                    "snapshot_id": snap.snapshot_id,
                    "kind": snap.kind.value,
                    "evidence_source": snap.source,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="telemetry_evidence_store",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_field(obj: Any, path: str) -> Optional[float]:
    """Extract a numeric value from a nested dict using dot-separated path."""
    parts = path.split(".")
    current = obj
    for p in parts:
        if isinstance(current, dict):
            current = current.get(p)
        else:
            return None
    if isinstance(current, (int, float)):
        return float(current)
    return None
