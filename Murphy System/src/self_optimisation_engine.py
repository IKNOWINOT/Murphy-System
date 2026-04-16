"""
Self-Optimisation Engine for Murphy System.

Design Label: ADV-003 — Performance Bottleneck Analysis & Auto-Tuning Proposals
Owner: AI Team / Platform Engineering
Dependencies:
  - SelfImprovementEngine (ARCH-001, for proposal injection)
  - OperationalSLOTracker (for SLO compliance data)
  - EventBackbone (publishes LEARNING_FEEDBACK on optimisation cycles)
  - PersistenceManager (for durable optimisation history)

Implements Phase 6 — Advanced Self-Automation (continued):
  Analyses performance metrics to detect bottlenecks, generates
  tuning proposals, and tracks optimisation history. Bridges
  raw performance data to actionable improvement proposals in
  the SelfImprovementEngine pipeline.

Flow:
  1. Record performance samples (metric_name, value, component, tags)
  2. Run bottleneck detection (identify metrics exceeding thresholds)
  3. Generate tuning proposals for detected bottlenecks
  4. Inject proposals into SelfImprovementEngine (optional)
  5. Track optimisation history with before/after metrics
  6. Publish LEARNING_FEEDBACK events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: proposals are suggestions only, require approval
  - Bounded: configurable max samples and proposals
  - Conservative: only flags metrics consistently above threshold
  - Audit trail: every optimisation cycle is logged

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

# ---------------------------------------------------------------------------
# Severity ratio thresholds for bottleneck classification
# ---------------------------------------------------------------------------

_CRITICAL_RATIO = 2.0
_HIGH_RATIO = 1.5
_MEDIUM_RATIO = 1.2

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PerformanceSample:
    """A single performance metric sample."""
    sample_id: str
    metric_name: str
    value: float
    component: str = ""
    tags: List[str] = field(default_factory=list)
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "component": self.component,
            "tags": list(self.tags),
            "recorded_at": self.recorded_at,
        }


@dataclass
class BottleneckReport:
    """A detected performance bottleneck."""
    report_id: str
    metric_name: str
    component: str
    sample_count: int
    mean_value: float
    p95_value: float
    threshold: float
    severity: str          # critical, high, medium, low
    suggestion: str
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "metric_name": self.metric_name,
            "component": self.component,
            "sample_count": self.sample_count,
            "mean_value": round(self.mean_value, 4),
            "p95_value": round(self.p95_value, 4),
            "threshold": self.threshold,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "created_at": self.created_at,
        }


@dataclass
class OptimisationCycle:
    """Summary of a single optimisation analysis cycle."""
    cycle_id: str
    samples_analysed: int
    bottlenecks_detected: int
    proposals_generated: int
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "samples_analysed": self.samples_analysed,
            "bottlenecks_detected": self.bottlenecks_detected,
            "proposals_generated": self.proposals_generated,
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# SelfOptimisationEngine
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

_DEFAULT_THRESHOLDS: Dict[str, float] = {
    "response_time_ms": 500,
    "error_rate": 0.05,
    "cpu_usage": 0.85,
    "memory_usage": 0.90,
    "queue_depth": 1000,
}


class SelfOptimisationEngine:
    """Performance bottleneck analysis and auto-tuning proposals.

    Design Label: ADV-003
    Owner: AI Team / Platform Engineering

    Usage::

        engine = SelfOptimisationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
            improvement_engine=si_engine,
        )
        engine.record_sample(metric_name="response_time_ms", value=620.0, component="api-gw")
        cycle = engine.run_optimisation_cycle()
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        improvement_engine=None,
        diminishing_gains_detector=None,
        max_samples: int = 50_000,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._improvement_engine = improvement_engine
        self._gains_detector = diminishing_gains_detector
        self._samples: List[PerformanceSample] = []
        self._bottlenecks: List[BottleneckReport] = []
        self._cycles: List[OptimisationCycle] = []
        self._max_samples = max_samples
        self._cycle_count: int = 0

    # ------------------------------------------------------------------
    # Sample recording
    # ------------------------------------------------------------------

    def record_sample(
        self,
        metric_name: str,
        value: float,
        component: str = "",
        tags: Optional[List[str]] = None,
    ) -> PerformanceSample:
        """Record a performance metric sample. Returns the created sample."""
        sample = PerformanceSample(
            sample_id=f"smp-{uuid.uuid4().hex[:8]}",
            metric_name=metric_name,
            value=value,
            component=component,
            tags=tags or [],
        )
        with self._lock:
            if len(self._samples) >= self._max_samples:
                # Evict oldest 10 %
                evict = max(1, self._max_samples // 10)
                self._samples = self._samples[evict:]
            self._samples.append(sample)
        logger.info("Recorded sample %s: %s=%.4f", sample.sample_id, metric_name, value)
        return sample

    # ------------------------------------------------------------------
    # Bottleneck detection
    # ------------------------------------------------------------------

    def detect_bottlenecks(
        self,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> List[BottleneckReport]:
        """Detect performance bottlenecks from recorded samples.

        *thresholds* maps metric names to their maximum acceptable values.
        Metrics whose p95 exceeds the threshold are flagged as bottlenecks.
        """
        effective_thresholds = dict(_DEFAULT_THRESHOLDS)
        if thresholds:
            effective_thresholds.update(thresholds)

        with self._lock:
            samples = list(self._samples)

        # Group samples by (metric_name, component)
        groups: Dict[tuple, List[float]] = defaultdict(list)
        for s in samples:
            groups[(s.metric_name, s.component)].append(s.value)

        reports: List[BottleneckReport] = []
        for (metric_name, component), values in groups.items():
            threshold = effective_thresholds.get(metric_name)
            if threshold is None:
                continue

            sorted_values = sorted(values)
            mean_value = sum(sorted_values) / (len(sorted_values) or 1)
            p95_index = int(len(sorted_values) * 0.95)
            p95_index = min(p95_index, len(sorted_values) - 1)
            p95_value = sorted_values[p95_index]

            if p95_value <= threshold:
                continue

            # Determine severity
            ratio = p95_value / threshold
            if ratio > _CRITICAL_RATIO:
                severity = "critical"
            elif ratio > _HIGH_RATIO:
                severity = "high"
            elif ratio > _MEDIUM_RATIO:
                severity = "medium"
            else:
                severity = "low"

            suggestion = (
                f"Reduce {metric_name} on {component}: "
                f"p95={p95_value:.2f} exceeds threshold {threshold}"
            )

            report = BottleneckReport(
                report_id=f"bnk-{uuid.uuid4().hex[:8]}",
                metric_name=metric_name,
                component=component,
                sample_count=len(values),
                mean_value=mean_value,
                p95_value=p95_value,
                threshold=threshold,
                severity=severity,
                suggestion=suggestion,
            )
            reports.append(report)

        # Sort by severity (critical first)
        reports.sort(key=lambda r: _SEVERITY_ORDER.get(r.severity, 99))

        with self._lock:
            self._bottlenecks.extend(reports)

        logger.info("Detected %d bottleneck(s) from %d samples", len(reports), len(samples))
        return reports

    # ------------------------------------------------------------------
    # Optimisation cycle
    # ------------------------------------------------------------------

    def run_optimisation_cycle(
        self,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> OptimisationCycle:
        """Run a full optimisation analysis cycle.

        Detects bottlenecks, optionally injects proposals into the
        SelfImprovementEngine, persists the cycle, and publishes an event.
        """
        with self._lock:
            samples_analysed = len(self._samples)

        bottlenecks = self.detect_bottlenecks(thresholds=thresholds)

        proposals_generated = 0
        for bnk in bottlenecks:
            if self._improvement_engine is not None:
                try:
                    self._improvement_engine.inject_proposal(
                        title=f"Auto-tune: {bnk.metric_name} on {bnk.component}",
                        description=bnk.suggestion,
                        source="self_optimisation_engine",
                    )
                    proposals_generated += 1
                except Exception as exc:
                    logger.debug("Proposal injection skipped: %s", exc)

        cycle = OptimisationCycle(
            cycle_id=f"cyc-{uuid.uuid4().hex[:8]}",
            samples_analysed=samples_analysed,
            bottlenecks_detected=len(bottlenecks),
            proposals_generated=proposals_generated,
        )

        with self._lock:
            capped_append(self._cycles, cycle)
            self._cycle_count += 1
            cycle_num = self._cycle_count

        # Feed diminishing-gains detector with cycle-level metrics
        if self._gains_detector is not None:
            try:
                # Track how bottleneck count evolves across cycles
                # Fewer bottlenecks = better optimization
                # Normalise so detector sees improvement as value going UP
                effective_score = max(0.0, 1.0 - (len(bottlenecks) / max(samples_analysed, 1)))
                self._gains_detector.record(
                    metric_name="optimisation_effectiveness",
                    iteration=cycle_num,
                    value=effective_score,
                )
            except Exception as exc:
                logger.debug("Diminishing gains recording skipped: %s", exc)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=cycle.cycle_id,
                    document=cycle.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish event
        if self._backbone is not None:
            self._publish_event(cycle)

        logger.info(
            "Optimisation cycle %s complete: %d bottleneck(s), %d proposal(s)",
            cycle.cycle_id,
            cycle.bottlenecks_detected,
            cycle.proposals_generated,
        )
        return cycle

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_samples(
        self,
        metric_name: Optional[str] = None,
        component: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent samples, optionally filtered by metric or component."""
        with self._lock:
            samples = list(self._samples)
        if metric_name:
            samples = [s for s in samples if s.metric_name == metric_name]
        if component:
            samples = [s for s in samples if s.component == component]
        return [s.to_dict() for s in samples[-limit:]]

    def get_bottlenecks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent detected bottleneck reports."""
        with self._lock:
            return [b.to_dict() for b in self._bottlenecks[-limit:]]

    def get_cycles(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent optimisation cycles."""
        with self._lock:
            return [c.to_dict() for c in self._cycles[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return engine status summary."""
        with self._lock:
            status = {
                "total_samples": len(self._samples),
                "total_bottlenecks": len(self._bottlenecks),
                "total_cycles": len(self._cycles),
                "max_samples": self._max_samples,
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
                "improvement_engine_attached": self._improvement_engine is not None,
                "gains_detector_attached": self._gains_detector is not None,
            }
        return status

    def should_stop_optimising(self) -> bool:
        """Check whether optimisation has reached diminishing returns.

        Returns ``True`` if the attached diminishing-gains detector
        recommends stopping, ``False`` otherwise (including when no
        detector is attached).
        """
        if self._gains_detector is None:
            return False
        try:
            return self._gains_detector.should_stop("optimisation_effectiveness")
        except Exception:
            return False

    def get_diminishing_gains_report(self) -> Optional[Dict[str, Any]]:
        """Run diminishing-gains analysis on the optimisation effectiveness
        metric and return the report.

        Returns ``None`` if no detector is attached.
        """
        if self._gains_detector is None:
            return None
        try:
            report = self._gains_detector.analyse("optimisation_effectiveness")
            return report.to_dict()
        except Exception as exc:
            logger.debug("Diminishing gains analysis skipped: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_event(self, cycle: OptimisationCycle) -> None:
        """Publish a LEARNING_FEEDBACK event with cycle summary."""
        try:
            from event_backbone import EventType
            self._backbone.publish(
                event_type=EventType.LEARNING_FEEDBACK,
                payload={
                    "source": "self_optimisation_engine",
                    "cycle": cycle.to_dict(),
                },
                source="self_optimisation_engine",
            )
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
