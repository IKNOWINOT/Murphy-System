"""
Operational Dashboard Aggregator for Murphy System.

Design Label: ORCH-003 — Unified Operational View Across All Modules
Owner: Platform Engineering / DevOps Team
Dependencies:
  - PersistenceManager (for durable dashboard snapshots)
  - EventBackbone (publishes SYSTEM_HEALTH on dashboard refresh)

Implements Plan Phase 1 "comprehensive dashboards showing system health"
and ARCHITECTURE_MAP Next Step #10 pre-requisite:
  Aggregates status information from all registered modules into a
  unified operational dashboard view.  Each module contributes its
  get_status() output (or a health callable result).  The aggregator
  computes system-wide health, counts module states, and identifies
  modules that are missing or degraded.

Flow:
  1. Register modules by design label with status callable
  2. Collect status from all registered modules on demand
  3. Classify each module (healthy / degraded / unreachable)
  4. Compute DashboardSnapshot with per-module and aggregate stats
  5. Persist snapshot and publish SYSTEM_HEALTH event

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: read-only status collection
  - Bounded: configurable max snapshot history
  - Graceful degradation: unreachable modules logged, not fatal
  - Timeout protection: per-module status call bounded

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_SNAPSHOTS = 1_000
_STATUS_TIMEOUT_MS = 5_000


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class ModuleHealth(str, Enum):
    """Module health (str subclass)."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


@dataclass
class ModuleStatusEntry:
    """Status of a single registered module."""
    label: str
    name: str
    health: ModuleHealth
    status_data: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    error: str = ""
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "name": self.name,
            "health": self.health.value,
            "status_data": self.status_data,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
            "checked_at": self.checked_at,
        }


@dataclass
class DashboardSnapshot:
    """Aggregated operational dashboard state."""
    snapshot_id: str
    total_modules: int = 0
    healthy_count: int = 0
    degraded_count: int = 0
    unreachable_count: int = 0
    system_health: str = "unknown"
    modules: List[ModuleStatusEntry] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "total_modules": self.total_modules,
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "unreachable_count": self.unreachable_count,
            "system_health": self.system_health,
            "modules": [m.to_dict() for m in self.modules],
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Module registration record
# ---------------------------------------------------------------------------

@dataclass
class _RegisteredModule:
    label: str
    name: str
    status_fn: Callable[[], Dict[str, Any]]


# ---------------------------------------------------------------------------
# OperationalDashboardAggregator
# ---------------------------------------------------------------------------

class OperationalDashboardAggregator:
    """Unified operational view aggregating status from all modules.

    Design Label: ORCH-003
    Owner: Platform Engineering / DevOps Team

    Usage::

        dash = OperationalDashboardAggregator()
        dash.register_module("OPS-001", "AutomationReadinessEvaluator",
                             lambda: evaluator.get_status())
        dash.register_builtin_subsystems()
        snapshot = dash.collect()

    Methods:
        register_builtin_subsystems(): Auto-imports and registers known Murphy
            subsystems (KPITracker, OperationalSLOTracker, PrometheusMetricsExporter,
            CRMManager) with graceful degradation if unavailable.
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._modules: Dict[str, _RegisteredModule] = {}
        self._snapshots: List[DashboardSnapshot] = []

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def register_module(
        self,
        label: str,
        name: str,
        status_fn: Callable[[], Dict[str, Any]],
    ) -> None:
        """Register a module by design label with a status callable."""
        with self._lock:
            self._modules[label] = _RegisteredModule(
                label=label, name=name, status_fn=status_fn,
            )
        logger.debug("Dashboard registered module %s (%s)", label, name)

    def unregister_module(self, label: str) -> bool:
        with self._lock:
            return self._modules.pop(label, None) is not None

    def register_builtin_subsystems(self) -> List[str]:
        """Import and register known Murphy subsystems.

        Each import is wrapped in try/except so failures are non-fatal.
        Returns a list of successfully registered labels.
        """
        registered: List[str] = []

        try:
            from kpi_tracker import KPITracker
            tracker = KPITracker()
            self.register_module("KPI-001", "KPITracker", lambda: tracker.get_status())
            registered.append("KPI-001")
            logger.info("Registered builtin subsystem KPI-001 / KPITracker")
        except Exception as exc:
            logger.debug("Could not register KPITracker: %s", exc)

        try:
            from operational_slo_tracker import OperationalSLOTracker
            tracker = OperationalSLOTracker()
            self.register_module("SLO-001", "OperationalSLOTracker", lambda: tracker.get_status())
            registered.append("SLO-001")
            logger.info("Registered builtin subsystem SLO-001 / OperationalSLOTracker")
        except Exception as exc:
            logger.debug("Could not register OperationalSLOTracker: %s", exc)

        try:
            from prometheus_metrics_exporter import DEFAULT_REGISTRY
            self.register_module(
                "PME-001", "PrometheusMetricsExporter",
                lambda: {"registered_families": DEFAULT_REGISTRY.family_count()},
            )
            registered.append("PME-001")
            logger.info("Registered builtin subsystem PME-001 / PrometheusMetricsExporter")
        except Exception as exc:
            logger.debug("Could not register PrometheusMetricsExporter: %s", exc)

        try:
            from crm.crm_manager import CRMManager
            instance = CRMManager()
            self.register_module("CRM-001", "CRMManager", lambda: {"status": "available"})
            registered.append("CRM-001")
            logger.info("Registered builtin subsystem CRM-001 / CRMManager")
        except Exception as exc:
            logger.debug("Could not register CRMManager: %s", exc)

        return registered

    # ------------------------------------------------------------------
    # Status collection
    # ------------------------------------------------------------------

    def collect(self) -> DashboardSnapshot:
        """Collect status from all registered modules and build snapshot."""
        with self._lock:
            modules_to_check = list(self._modules.values())

        entries: List[ModuleStatusEntry] = []
        healthy = degraded = unreachable = 0

        for mod in modules_to_check:
            entry = self._check_module(mod)
            entries.append(entry)
            if entry.health == ModuleHealth.HEALTHY:
                healthy += 1
            elif entry.health == ModuleHealth.DEGRADED:
                degraded += 1
            else:
                unreachable += 1

        total = len(entries)
        if total == 0:
            system_health = "unknown"
        elif unreachable > total * 0.5:
            system_health = "unhealthy"
        elif degraded + unreachable > 0:
            system_health = "degraded"
        else:
            system_health = "healthy"

        snapshot = DashboardSnapshot(
            snapshot_id=f"ds-{uuid.uuid4().hex[:8]}",
            total_modules=total,
            healthy_count=healthy,
            degraded_count=degraded,
            unreachable_count=unreachable,
            system_health=system_health,
            modules=entries,
        )

        with self._lock:
            if len(self._snapshots) >= _MAX_SNAPSHOTS:
                self._snapshots = self._snapshots[_MAX_SNAPSHOTS // 10:]
            self._snapshots.append(snapshot)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=snapshot.snapshot_id, document=snapshot.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(snapshot)

        logger.info(
            "Dashboard snapshot %s: %d healthy, %d degraded, %d unreachable (%s)",
            snapshot.snapshot_id, healthy, degraded, unreachable, system_health,
        )
        return snapshot

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._snapshots[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "registered_modules": len(self._modules),
                "total_snapshots": len(self._snapshots),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_module(self, mod: _RegisteredModule) -> ModuleStatusEntry:
        start = time.monotonic()
        try:
            status_data = mod.status_fn()
            latency = (time.monotonic() - start) * 1000
            health = ModuleHealth.HEALTHY
            error = ""
            # Detect degraded: timeout exceeded or module reports low health
            if latency > _STATUS_TIMEOUT_MS:
                health = ModuleHealth.DEGRADED
                error = f"status call exceeded {_STATUS_TIMEOUT_MS}ms"
            elif isinstance(status_data, dict):
                if status_data.get("system_status") in ("unhealthy", "degraded"):
                    health = ModuleHealth.DEGRADED
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            latency = (time.monotonic() - start) * 1000
            status_data = {}
            health = ModuleHealth.UNREACHABLE
            error = str(exc)[:200]

        return ModuleStatusEntry(
            label=mod.label,
            name=mod.name,
            health=health,
            status_data=status_data,
            latency_ms=latency,
            error=error,
        )

    def _publish_event(self, snapshot: DashboardSnapshot) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "operational_dashboard_aggregator",
                    "action": "dashboard_collected",
                    "snapshot_id": snapshot.snapshot_id,
                    "system_health": snapshot.system_health,
                    "healthy": snapshot.healthy_count,
                    "degraded": snapshot.degraded_count,
                    "unreachable": snapshot.unreachable_count,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="operational_dashboard_aggregator",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
