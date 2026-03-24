"""
Founder Update Engine — Digest Generator

Design Label: ARCH-007 — Founder Update Engine: Digest Generator
Owner: Backend Team
Dependencies:
  - ObservabilitySummaryCounters (observability_counters.py)
  - OperatingAnalysisDashboard (ARCH-007)
  - SubsystemRegistry (ARCH-007)

Generates daily and weekly founder digests using real telemetry from
the ObservabilitySummaryCounters and OperatingAnalysisDashboard.

Digest contents:
  - System health overview (healthy/degraded/failed subsystem counts)
  - Agent activity summary (from observability counters)
  - Error rates and behavior fix counts
  - Resource utilisation summary
  - Open recommendation counts
  - Top alerts and SLO compliance status

Safety invariants:
  - Read-only: never modifies source files or system state
  - Thread-safe: all shared state guarded by Lock
  - Bounded: digest history capped

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

_MAX_DIGEST_HISTORY = 100


class DigestPeriod(str, Enum):
    """Period for a founder digest."""
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class FounderDigest:
    """A founder digest snapshot containing real system telemetry."""
    digest_id: str
    period: DigestPeriod
    generated_at: str
    # System health
    total_subsystems: int = 0
    healthy_subsystems: int = 0
    degraded_subsystems: int = 0
    failed_subsystems: int = 0
    # Agent / counter activity
    total_behavior_fixes: int = 0
    total_coverage_events: int = 0
    error_rate_pct: float = 0.0
    # Recommendations
    open_recommendations: int = 0
    # Raw counter summary from ObservabilitySummaryCounters
    counter_summary: Dict[str, int] = field(default_factory=dict)
    # Subsystem health details
    subsystem_health: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "digest_id": self.digest_id,
            "period": self.period.value,
            "generated_at": self.generated_at,
            "total_subsystems": self.total_subsystems,
            "healthy_subsystems": self.healthy_subsystems,
            "degraded_subsystems": self.degraded_subsystems,
            "failed_subsystems": self.failed_subsystems,
            "total_behavior_fixes": self.total_behavior_fixes,
            "total_coverage_events": self.total_coverage_events,
            "error_rate_pct": round(self.error_rate_pct, 4),
            "open_recommendations": self.open_recommendations,
            "counter_summary": self.counter_summary,
            "subsystem_health": self.subsystem_health,
        }


class FounderDigestGenerator:
    """Generates daily/weekly founder digests from real system telemetry.

    Design Label: ARCH-007
    Owner: Backend Team

    Usage::

        generator = FounderDigestGenerator()
        digest = generator.generate(DigestPeriod.DAILY)
    """

    def __init__(
        self,
        observability_counters=None,
        operating_analysis_dashboard=None,
        subsystem_registry=None,
    ) -> None:
        self._lock = threading.Lock()
        self._counters = observability_counters
        self._dashboard = operating_analysis_dashboard
        self._registry = subsystem_registry
        self._digests: List[FounderDigest] = []

        # Lazy-load defaults if not provided
        if self._counters is None:
            self._counters = self._try_load_counters()
        if self._dashboard is None:
            self._dashboard = self._try_load_dashboard()
        if self._registry is None:
            self._registry = self._try_load_registry()

    # ------------------------------------------------------------------
    # Digest generation
    # ------------------------------------------------------------------

    def generate(self, period: DigestPeriod = DigestPeriod.DAILY) -> FounderDigest:
        """Generate a founder digest for the given period using real telemetry."""
        now = datetime.now(timezone.utc).isoformat()
        digest_id = f"digest-{uuid.uuid4().hex[:8]}"

        counter_summary = self._collect_counter_summary()
        subsystem_health, healthy, degraded, failed, total, open_recs = self._collect_subsystem_data()
        error_rate = self._compute_error_rate(counter_summary)

        digest = FounderDigest(
            digest_id=digest_id,
            period=period,
            generated_at=now,
            total_subsystems=total,
            healthy_subsystems=healthy,
            degraded_subsystems=degraded,
            failed_subsystems=failed,
            total_behavior_fixes=counter_summary.get("behavior_fix", 0),
            total_coverage_events=counter_summary.get("coverage", 0),
            error_rate_pct=error_rate,
            open_recommendations=open_recs,
            counter_summary=counter_summary,
            subsystem_health=subsystem_health,
        )

        with self._lock:
            if len(self._digests) >= _MAX_DIGEST_HISTORY:
                self._digests = self._digests[_MAX_DIGEST_HISTORY // 10:]
            self._digests.append(digest)

        logger.info(
            "Generated %s digest %s: %d/%d healthy, %d fixes, error_rate=%.2f%%",
            period.value, digest_id, healthy, total,
            digest.total_behavior_fixes, error_rate,
        )
        return digest

    def get_digests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent digests."""
        with self._lock:
            return [d.to_dict() for d in self._digests[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return generator status."""
        with self._lock:
            return {
                "total_digests": len(self._digests),
                "counters_attached": self._counters is not None,
                "dashboard_attached": self._dashboard is not None,
                "registry_attached": self._registry is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_counter_summary(self) -> Dict[str, int]:
        """Collect category totals from ObservabilitySummaryCounters."""
        if self._counters is None:
            return {}
        try:
            summary = self._counters.get_category_summary()
            return {k: int(v) for k, v in summary.items() if isinstance(v, (int, float))}
        except Exception as exc:
            logger.debug("Counter summary collection failed: %s", exc)
            return {}

    def _collect_subsystem_data(self):
        """Collect subsystem health from OperatingAnalysisDashboard or SubsystemRegistry."""
        subsystem_health = []
        healthy = degraded = failed = total = open_recs = 0

        # Try operating analysis dashboard first
        if self._dashboard is not None:
            try:
                snap = self._dashboard.capture_snapshot()
                for summary in snap.subsystem_health:
                    s = summary.to_dict() if hasattr(summary, "to_dict") else dict(summary)
                    subsystem_health.append(s)
                    status = s.get("health_status", "unknown")
                    if status == "healthy":
                        healthy += 1
                    elif status in ("degraded", "failed"):
                        if status == "degraded":
                            degraded += 1
                        else:
                            failed += 1
                    total += 1
                    open_recs += s.get("pending_recommendations", 0)
                return subsystem_health, healthy, degraded, failed, total, open_recs
            except Exception as exc:
                logger.debug("Dashboard snapshot failed: %s", exc)

        # Fall back to SubsystemRegistry
        if self._registry is not None:
            try:
                for info in self._registry.list_all():
                    s = info.to_dict() if hasattr(info, "to_dict") else dict(info)
                    subsystem_health.append(s)
                    status = s.get("health_status", s.get("status", "unknown"))
                    if status == "healthy":
                        healthy += 1
                    elif status == "degraded":
                        degraded += 1
                    elif status == "failed":
                        failed += 1
                    total += 1
            except Exception as exc:
                logger.debug("Registry list failed: %s", exc)

        return subsystem_health, healthy, degraded, failed, total, open_recs

    def _compute_error_rate(self, counter_summary: Dict[str, int]) -> float:
        """Compute error rate from counter summary."""
        fixes = counter_summary.get("behavior_fix", 0)
        coverage = counter_summary.get("coverage", 0)
        total_events = fixes + coverage
        if total_events == 0:
            return 0.0
        return round((fixes / total_events) * 100.0, 4)

    @staticmethod
    def _try_load_counters():
        try:
            from observability_counters import ObservabilitySummaryCounters
            return ObservabilitySummaryCounters()
        except Exception:
            return None

    @staticmethod
    def _try_load_dashboard():
        try:
            from founder_update_engine.operating_analysis_dashboard import OperatingAnalysisDashboard
            return OperatingAnalysisDashboard()
        except Exception:
            return None

    @staticmethod
    def _try_load_registry():
        try:
            from founder_update_engine.subsystem_registry import SubsystemRegistry
            return SubsystemRegistry()
        except Exception:
            return None
