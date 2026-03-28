"""
KPI Tracker for Murphy System.

Design Label: OPS-002 — Automation KPI Tracking & Target Monitoring
Owner: Platform Engineering / Strategy Team
Dependencies:
  - PersistenceManager (for durable KPI snapshots)
  - EventBackbone (publishes LEARNING_FEEDBACK on KPI snapshots)

Implements Phase 8 — Operational Readiness & Autonomy Governance:
  Tracks key performance indicators defined in Part 7 of the
  Self-Automation Plan: automation rate, success rate, time savings,
  cost savings, error rate, uptime, and response time.  Each KPI has
  a configurable target and the tracker computes whether the target is
  met.  Periodic snapshots are persisted for trend analysis.

Flow:
  1. Define KPIs with name, target, unit, and direction (higher/lower is better)
  2. Record observed values over time
  3. Compute current KPI status (met / not_met)
  4. Generate KPISnapshot with all tracked KPIs
  5. Persist snapshot and publish LEARNING_FEEDBACK event

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only analysis: never modifies source data
  - Bounded: configurable max observations and snapshots
  - Audit trail: every snapshot is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_OBSERVATIONS = 100_000
_MAX_SNAPSHOTS = 1_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class KPIDirection(str, Enum):
    """Whether higher or lower values are better."""
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


class KPIStatus(str, Enum):
    """Whether the KPI target is currently met."""
    MET = "met"
    NOT_MET = "not_met"
    NO_DATA = "no_data"


@dataclass
class KPIDefinition:
    """Definition of a single KPI."""
    kpi_id: str
    name: str
    target: float
    unit: str = ""
    direction: KPIDirection = KPIDirection.HIGHER_IS_BETTER
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "name": self.name,
            "target": self.target,
            "unit": self.unit,
            "direction": self.direction.value,
            "description": self.description,
        }


@dataclass
class KPIObservation:
    """A single observed value for a KPI."""
    observation_id: str
    kpi_id: str
    value: float
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class KPIResult:
    """Computed result for a single KPI at snapshot time."""
    kpi_id: str
    name: str
    target: float
    current_value: float
    status: KPIStatus
    unit: str = ""
    observation_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_id": self.kpi_id,
            "name": self.name,
            "target": self.target,
            "current_value": round(self.current_value, 4),
            "status": self.status.value,
            "unit": self.unit,
            "observation_count": self.observation_count,
        }


@dataclass
class KPISnapshot:
    """Point-in-time snapshot of all tracked KPIs."""
    snapshot_id: str
    total_kpis: int
    met_count: int
    not_met_count: int
    no_data_count: int
    results: List[KPIResult] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "total_kpis": self.total_kpis,
            "met_count": self.met_count,
            "not_met_count": self.not_met_count,
            "no_data_count": self.no_data_count,
            "results": [r.to_dict() for r in self.results],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Default KPI definitions from Part 7 of the Self-Automation Plan
# ---------------------------------------------------------------------------

def _business_kpis() -> List[KPIDefinition]:
    return [
        KPIDefinition("kpi-crm-leads", "CRM Lead Count", 10.0, "leads",
                       KPIDirection.HIGHER_IS_BETTER),
        KPIDefinition("kpi-deal-close-rate", "Deal Close Rate", 20.0, "%",
                       KPIDirection.HIGHER_IS_BETTER),
        KPIDefinition("kpi-ticket-resolution-time", "Ticket Resolution Time", 24.0, "hours",
                       KPIDirection.LOWER_IS_BETTER),
        KPIDefinition("kpi-customer-satisfaction", "Customer Satisfaction Score", 4.0, "score",
                       KPIDirection.HIGHER_IS_BETTER),
        KPIDefinition("kpi-feature-adoption", "Feature Adoption Rate", 60.0, "%",
                       KPIDirection.HIGHER_IS_BETTER),
        KPIDefinition("kpi-monthly-revenue", "Monthly Revenue", 1000.0, "USD",
                       KPIDirection.HIGHER_IS_BETTER),
    ]


def _default_kpis() -> List[KPIDefinition]:
    return [
        KPIDefinition("kpi-automation-rate", "Automation Rate", 80.0, "%",
                       KPIDirection.HIGHER_IS_BETTER,
                       "Percentage of tasks automated"),
        KPIDefinition("kpi-success-rate", "Success Rate", 95.0, "%",
                       KPIDirection.HIGHER_IS_BETTER,
                       "Successful automated tasks / total automated tasks"),
        KPIDefinition("kpi-uptime", "System Uptime", 99.9, "%",
                       KPIDirection.HIGHER_IS_BETTER,
                       "System availability percentage"),
        KPIDefinition("kpi-error-rate", "Error Rate", 0.1, "%",
                       KPIDirection.LOWER_IS_BETTER,
                       "Error rate percentage"),
        KPIDefinition("kpi-response-time-p95", "Response Time (p95)", 1000.0, "ms",
                       KPIDirection.LOWER_IS_BETTER,
                       "95th percentile response time"),
        KPIDefinition("kpi-time-savings", "Time Savings", 50.0, "%",
                       KPIDirection.HIGHER_IS_BETTER,
                       "Reduction in manual effort"),
        KPIDefinition("kpi-cost-savings", "Cost Savings", 30.0, "%",
                       KPIDirection.HIGHER_IS_BETTER,
                       "Reduction in operational costs"),
        KPIDefinition("kpi-test-coverage", "Test Coverage", 90.0, "%",
                       KPIDirection.HIGHER_IS_BETTER,
                       "Test coverage percentage"),
    ] + _business_kpis()


# ---------------------------------------------------------------------------
# KPITracker
# ---------------------------------------------------------------------------

class KPITracker:
    """Automation KPI tracking and target monitoring.

    Design Label: OPS-002
    Owner: Platform Engineering / Strategy Team

    Usage::

        tracker = KPITracker()
        tracker.record("kpi-success-rate", 96.5)
        tracker.record("kpi-error-rate", 0.08)
        snapshot = tracker.snapshot()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        kpi_definitions: Optional[List[KPIDefinition]] = None,
        max_observations: int = _MAX_OBSERVATIONS,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._max_obs = max_observations
        # kpi_id -> KPIDefinition
        self._kpis: Dict[str, KPIDefinition] = {}
        # kpi_id -> list of observations
        self._observations: Dict[str, List[KPIObservation]] = defaultdict(list)
        self._snapshots: List[KPISnapshot] = []

        for kd in (kpi_definitions or _default_kpis()):
            self._kpis[kd.kpi_id] = kd

    # ------------------------------------------------------------------
    # KPI management
    # ------------------------------------------------------------------

    def define_kpi(self, kpi: KPIDefinition) -> None:
        """Add or replace a KPI definition."""
        with self._lock:
            self._kpis[kpi.kpi_id] = kpi

    def remove_kpi(self, kpi_id: str) -> bool:
        with self._lock:
            removed = self._kpis.pop(kpi_id, None) is not None
            self._observations.pop(kpi_id, None)
            return removed

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, kpi_id: str, value: float) -> Optional[KPIObservation]:
        """Record an observed value for a KPI."""
        with self._lock:
            if kpi_id not in self._kpis:
                logger.warning("Unknown KPI %s", kpi_id)
                return None
            obs = KPIObservation(
                observation_id=f"obs-{uuid.uuid4().hex[:8]}",
                kpi_id=kpi_id,
                value=value,
            )
            lst = self._observations[kpi_id]
            if len(lst) >= self._max_obs:
                evict = max(1, self._max_obs // 10)
                self._observations[kpi_id] = lst[evict:]
            self._observations[kpi_id].append(obs)
        return obs

    # ------------------------------------------------------------------
    # Snapshot generation
    # ------------------------------------------------------------------

    def snapshot(self) -> KPISnapshot:
        """Generate a point-in-time KPI snapshot."""
        with self._lock:
            kpis = dict(self._kpis)
            observations = {k: list(v) for k, v in self._observations.items()}

        results: List[KPIResult] = []
        met = not_met = no_data = 0

        for kpi_id, defn in kpis.items():
            obs_list = observations.get(kpi_id, [])
            if not obs_list:
                results.append(KPIResult(
                    kpi_id=kpi_id, name=defn.name, target=defn.target,
                    current_value=0.0, status=KPIStatus.NO_DATA,
                    unit=defn.unit, observation_count=0,
                ))
                no_data += 1
                continue

            # Use latest 10 observations average as current value
            recent = obs_list[-10:]
            current = sum(o.value for o in recent) / (len(recent) or 1)

            if defn.direction == KPIDirection.HIGHER_IS_BETTER:
                is_met = current >= defn.target
            else:
                is_met = current <= defn.target

            status = KPIStatus.MET if is_met else KPIStatus.NOT_MET
            if is_met:
                met += 1
            else:
                not_met += 1

            results.append(KPIResult(
                kpi_id=kpi_id, name=defn.name, target=defn.target,
                current_value=current, status=status,
                unit=defn.unit, observation_count=len(obs_list),
            ))

        snap = KPISnapshot(
            snapshot_id=f"kpi-{uuid.uuid4().hex[:8]}",
            total_kpis=len(kpis),
            met_count=met,
            not_met_count=not_met,
            no_data_count=no_data,
            results=results,
        )

        with self._lock:
            if len(self._snapshots) >= _MAX_SNAPSHOTS:
                self._snapshots = self._snapshots[_MAX_SNAPSHOTS // 10:]
            self._snapshots.append(snap)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=snap.snapshot_id, document=snap.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(snap)

        logger.info(
            "KPI snapshot: %d/%d met, %d no_data",
            met, len(kpis), no_data,
        )
        return snap

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_snapshots(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._snapshots[-limit:]]

    def list_kpis(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [d.to_dict() for d in self._kpis.values()]

    def record_from_source(self, source: str, metrics: Dict[str, float]) -> List[Optional["KPIObservation"]]:
        """Map source-specific metrics to KPI IDs and record observations.

        Args:
            source: Data source identifier ("crm", "service", "billing").
            metrics: Dict of metric name to float value.

        Returns:
            List of KPIObservation (or None for unmapped metrics).
        """
        mapping: Dict[str, str] = {}
        if source == "crm":
            mapping = {
                "lead_count": "kpi-crm-leads",
                "deal_close_rate": "kpi-deal-close-rate",
            }
        elif source == "service":
            mapping = {
                "avg_resolution_hours": "kpi-ticket-resolution-time",
            }
        elif source == "billing":
            mapping = {
                "monthly_revenue_usd": "kpi-monthly-revenue",
            }

        observations = []
        for metric_key, kpi_id in mapping.items():
            value = metrics.get(metric_key)
            if value is not None:
                obs = self.record(kpi_id, float(value))
                observations.append(obs)
        return observations

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_kpis": len(self._kpis),
                "total_observations": sum(len(v) for v in self._observations.values()),
                "total_snapshots": len(self._snapshots),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, snap: KPISnapshot) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "kpi_tracker",
                    "action": "kpi_snapshot",
                    "snapshot_id": snap.snapshot_id,
                    "met_count": snap.met_count,
                    "total_kpis": snap.total_kpis,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="kpi_tracker",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
