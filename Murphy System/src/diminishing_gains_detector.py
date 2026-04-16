"""
Diminishing Gains Detector — ML-based plateau detection for optimization loops.

Design Label: ADV-004 — Diminishing Returns Detection & Early Stopping
Owner: AI Team / Platform Engineering
Dependencies:
  - SelfOptimisationEngine (ADV-003, for performance sample integration)
  - MSSSequenceOptimizer (MSS-OPT-001, for sequence scoring integration)
  - EventBackbone (publishes LEARNING_FEEDBACK on plateau detection)
  - PersistenceManager (for durable detection history)

Implements the principle: *Maximize to the point of diminishing gains.*

The detector monitors metric improvement across successive optimization
iterations and identifies when marginal gains fall below a configurable
threshold.  It uses:

  1. **Exponential Moving Average (EMA)** of per-iteration improvement deltas
  2. **Derivative analysis** — first and second derivatives of the gain curve
  3. **Plateau window** — consecutive low-gain iterations trigger plateau signal
  4. **Knee-point detection** — finds the elbow where gains diminish fastest

The output is a :class:`DiminishingGainsReport` indicating whether the
optimization loop has reached plateau, should continue, or has converged.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: advisory only — never halts an optimization without
    explicit caller action
  - Bounded: configurable max history (evict oldest 10 % when full)
  - Conservative: requires ``plateau_window`` consecutive below-threshold
    iterations before declaring plateau

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DiminishingGainsConfig:
    """Tuning knobs for diminishing-gains detection.

    Attributes:
        ema_alpha: Smoothing factor for EMA of improvement deltas (0 < α ≤ 1).
            Smaller values react more slowly to noise; larger values respond
            faster.  Default ``0.3`` balances responsiveness with stability.
        gain_threshold: Minimum normalised marginal gain to consider
            an iteration "improving".  Gains below this are treated as
            plateau steps.  Default ``0.01`` (1 % of metric range).
        plateau_window: Number of consecutive below-threshold iterations
            needed to declare a plateau.  Default ``3``.
        convergence_threshold: When EMA gain falls below this, the detector
            considers the series fully converged.  Default ``0.001``.
        max_history: Maximum retained metric observations before eviction.
    """
    ema_alpha: float = 0.3
    gain_threshold: float = 0.01
    plateau_window: int = 3
    convergence_threshold: float = 0.001
    max_history: int = 10_000

    def __post_init__(self) -> None:
        if not (0.0 < self.ema_alpha <= 1.0):
            raise ValueError(f"ema_alpha must be in (0, 1], got {self.ema_alpha}")
        if self.gain_threshold < 0:
            raise ValueError(f"gain_threshold must be ≥ 0, got {self.gain_threshold}")
        if self.plateau_window < 1:
            raise ValueError(f"plateau_window must be ≥ 1, got {self.plateau_window}")
        if self.max_history < 10:
            raise ValueError(f"max_history must be ≥ 10, got {self.max_history}")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class GainStatus:
    """Advisory status constants for optimization loops."""
    IMPROVING = "improving"       # Gains still meaningful — keep going
    PLATEAU = "plateau"           # Marginal gains below threshold for window
    CONVERGED = "converged"       # EMA gain ≈ 0 — fully converged
    INSUFFICIENT = "insufficient"  # Not enough data to judge


@dataclass
class MetricObservation:
    """A single metric value captured at an optimization iteration."""
    observation_id: str
    metric_name: str
    iteration: int
    value: float
    delta: float = 0.0            # raw improvement from previous iteration
    normalised_delta: float = 0.0  # delta / metric range (0–1 scale)
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "metric_name": self.metric_name,
            "iteration": self.iteration,
            "value": self.value,
            "delta": round(self.delta, 6),
            "normalised_delta": round(self.normalised_delta, 6),
            "recorded_at": self.recorded_at,
        }


@dataclass
class DiminishingGainsReport:
    """Result of diminishing-gains analysis on a metric series.

    The ``status`` field contains the advisory recommendation:
      - ``improving`` — continue optimizing
      - ``plateau``   — marginal gains have fallen below threshold
      - ``converged`` — series has fully converged
      - ``insufficient`` — not enough data to decide

    ``knee_point`` (if detected) is the iteration index where gains
    began diminishing fastest — the optimal stopping point.
    """
    report_id: str
    metric_name: str
    status: str                    # GainStatus constant
    total_iterations: int
    ema_gain: float                # current EMA of normalised deltas
    consecutive_low: int           # consecutive iterations below threshold
    peak_value: float              # best value observed in the series
    peak_iteration: int            # iteration at which peak was reached
    knee_point: Optional[int]      # iteration where gains diminish fastest
    gain_curve: List[float]        # normalised deltas per iteration
    improvement_pct: float         # total improvement as % of initial value
    recommendation: str            # human-readable recommendation text
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "metric_name": self.metric_name,
            "status": self.status,
            "total_iterations": self.total_iterations,
            "ema_gain": round(self.ema_gain, 6),
            "consecutive_low": self.consecutive_low,
            "peak_value": round(self.peak_value, 6),
            "peak_iteration": self.peak_iteration,
            "knee_point": self.knee_point,
            "gain_curve": [round(g, 6) for g in self.gain_curve],
            "improvement_pct": round(self.improvement_pct, 4),
            "recommendation": self.recommendation,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# DiminishingGainsDetector
# ---------------------------------------------------------------------------

class DiminishingGainsDetector:
    """ML-based plateau detection for optimization loops.

    Design Label: ADV-004

    Monitors metric improvement across successive optimization iterations
    and identifies when marginal gains fall below a configurable threshold.

    Usage::

        detector = DiminishingGainsDetector()
        detector.record(metric_name="composite_score", iteration=1, value=0.42)
        detector.record(metric_name="composite_score", iteration=2, value=0.58)
        detector.record(metric_name="composite_score", iteration=3, value=0.61)
        detector.record(metric_name="composite_score", iteration=4, value=0.62)
        detector.record(metric_name="composite_score", iteration=5, value=0.622)

        report = detector.analyse("composite_score")
        # report.status == "plateau" — gains have diminished
        # report.knee_point == 2 — iteration where gains were highest

    Args:
        config: :class:`DiminishingGainsConfig` knobs (optional).
        event_backbone: EventBackbone for publishing plateau events (optional).
        persistence_manager: PersistenceManager for durable history (optional).
    """

    def __init__(
        self,
        config: Optional[DiminishingGainsConfig] = None,
        event_backbone: Optional[Any] = None,
        persistence_manager: Optional[Any] = None,
    ) -> None:
        self._config = config or DiminishingGainsConfig()
        self._backbone = event_backbone
        self._pm = persistence_manager
        self._lock = threading.Lock()
        # metric_name -> list of observations in iteration order
        self._series: Dict[str, List[MetricObservation]] = {}
        # metric_name -> latest EMA gain
        self._ema: Dict[str, float] = {}
        # metric_name -> count of consecutive below-threshold iterations
        self._consecutive_low: Dict[str, int] = {}
        # Reports history
        self._reports: List[DiminishingGainsReport] = []

    # ------------------------------------------------------------------
    # Public API: Record
    # ------------------------------------------------------------------

    def record(
        self,
        metric_name: str,
        iteration: int,
        value: float,
    ) -> MetricObservation:
        """Record a metric observation for a given optimization iteration.

        Args:
            metric_name: Name of the metric being tracked (e.g. "composite_score").
            iteration: Zero-based or one-based iteration index.
            value: The metric value at this iteration.

        Returns:
            The created :class:`MetricObservation`.
        """
        with self._lock:
            series = self._series.setdefault(metric_name, [])

            # Compute delta from previous observation
            delta = 0.0
            normalised_delta = 0.0
            if series:
                prev = series[-1]
                delta = value - prev.value
                # Normalise by the range so far
                all_values = [obs.value for obs in series] + [value]
                metric_range = max(all_values) - min(all_values)
                if metric_range > 0:
                    normalised_delta = abs(delta) / metric_range
                # If value is going up, keep sign positive for "gain"
                # If value is going down (for a minimization metric), still
                # treat absolute improvement as gain
                normalised_delta = abs(normalised_delta)

            obs = MetricObservation(
                observation_id=f"obs-{uuid.uuid4().hex[:8]}",
                metric_name=metric_name,
                iteration=iteration,
                value=value,
                delta=delta,
                normalised_delta=normalised_delta,
            )

            if len(series) >= self._config.max_history:
                evict = max(1, self._config.max_history // 10)
                del series[:evict]
            series.append(obs)

            # Update EMA
            alpha = self._config.ema_alpha
            prev_ema = self._ema.get(metric_name, normalised_delta)
            new_ema = alpha * normalised_delta + (1 - alpha) * prev_ema
            self._ema[metric_name] = new_ema

            # Track consecutive low-gain iterations
            if normalised_delta < self._config.gain_threshold:
                self._consecutive_low[metric_name] = (
                    self._consecutive_low.get(metric_name, 0) + 1
                )
            else:
                self._consecutive_low[metric_name] = 0

        logger.debug(
            "Recorded %s iter=%d val=%.6f delta=%.6f norm_delta=%.6f ema=%.6f",
            metric_name, iteration, value, delta, normalised_delta, new_ema,
        )
        return obs

    # ------------------------------------------------------------------
    # Public API: Analyse
    # ------------------------------------------------------------------

    def analyse(self, metric_name: str) -> DiminishingGainsReport:
        """Analyse a metric series for diminishing gains.

        Args:
            metric_name: The metric to analyse.

        Returns:
            A :class:`DiminishingGainsReport` with status, knee-point, and
            a human-readable recommendation.
        """
        with self._lock:
            series = list(self._series.get(metric_name, []))
            ema_gain = self._ema.get(metric_name, 0.0)
            consecutive_low = self._consecutive_low.get(metric_name, 0)

        if len(series) < 2:
            report = DiminishingGainsReport(
                report_id=f"dgr-{uuid.uuid4().hex[:8]}",
                metric_name=metric_name,
                status=GainStatus.INSUFFICIENT,
                total_iterations=len(series),
                ema_gain=ema_gain,
                consecutive_low=consecutive_low,
                peak_value=series[0].value if series else 0.0,
                peak_iteration=series[0].iteration if series else 0,
                knee_point=None,
                gain_curve=[],
                improvement_pct=0.0,
                recommendation="Insufficient data — need at least 2 iterations.",
            )
            self._store_report(report)
            return report

        # Build gain curve and find peak
        gain_curve = [obs.normalised_delta for obs in series]
        values = [obs.value for obs in series]
        peak_value = max(values)
        peak_idx = values.index(peak_value)
        peak_iteration = series[peak_idx].iteration

        # Total improvement
        initial_value = values[0]
        if abs(initial_value) > 1e-12:
            improvement_pct = ((peak_value - initial_value) / abs(initial_value)) * 100.0
        else:
            improvement_pct = 0.0 if peak_value == initial_value else 100.0

        # Knee-point detection: find the iteration where the second derivative
        # of the gain curve is most negative (steepest drop in marginal gain)
        knee_point = self._detect_knee_point(gain_curve, series)

        # Determine status
        if ema_gain < self._config.convergence_threshold:
            status = GainStatus.CONVERGED
            recommendation = (
                f"Converged: EMA gain ({ema_gain:.6f}) is below convergence "
                f"threshold ({self._config.convergence_threshold}). "
                f"No further optimization needed."
            )
        elif consecutive_low >= self._config.plateau_window:
            status = GainStatus.PLATEAU
            recommendation = (
                f"Plateau detected: {consecutive_low} consecutive iterations "
                f"below gain threshold ({self._config.gain_threshold}). "
                f"Peak at iteration {peak_iteration} (value={peak_value:.6f}). "
            )
            if knee_point is not None:
                recommendation += (
                    f"Optimal stopping point was iteration {knee_point}."
                )
        else:
            status = GainStatus.IMPROVING
            recommendation = (
                f"Still improving: EMA gain={ema_gain:.6f}, "
                f"{consecutive_low}/{self._config.plateau_window} "
                f"low-gain iterations. Continue optimizing."
            )

        report = DiminishingGainsReport(
            report_id=f"dgr-{uuid.uuid4().hex[:8]}",
            metric_name=metric_name,
            status=status,
            total_iterations=len(series),
            ema_gain=ema_gain,
            consecutive_low=consecutive_low,
            peak_value=peak_value,
            peak_iteration=peak_iteration,
            knee_point=knee_point,
            gain_curve=gain_curve,
            improvement_pct=improvement_pct,
            recommendation=recommendation,
        )

        self._store_report(report)

        # Publish event on plateau or convergence
        if status in (GainStatus.PLATEAU, GainStatus.CONVERGED):
            self._publish_plateau_event(report)

        logger.info(
            "Diminishing gains analysis for %s: status=%s ema=%.6f knee=%s",
            metric_name, status, ema_gain, knee_point,
        )
        return report

    # ------------------------------------------------------------------
    # Public API: Analyse MSS sequence battery results
    # ------------------------------------------------------------------

    def analyse_sequence_battery(
        self,
        diminishing_returns_data: Dict[str, Any],
    ) -> DiminishingGainsReport:
        """Analyse MSS sequence battery diminishing returns data.

        Takes the ``diminishing_returns`` dict from
        :meth:`MSSSequenceOptimizer.generate_report` and runs
        plateau detection on the best-score-per-length curve.

        Args:
            diminishing_returns_data: Dict mapping sequence length (str) to
                ``{"best_score": float, "best_sequence": str}``.

        Returns:
            A :class:`DiminishingGainsReport` for the "sequence_length_score"
            pseudo-metric.
        """
        metric_name = "sequence_length_score"

        # Feed data sorted by sequence length
        for length_str in sorted(diminishing_returns_data, key=lambda k: int(k)):
            entry = diminishing_returns_data[length_str]
            self.record(
                metric_name=metric_name,
                iteration=int(length_str),
                value=entry["best_score"],
            )

        return self.analyse(metric_name)

    # ------------------------------------------------------------------
    # Public API: Should-stop advisor
    # ------------------------------------------------------------------

    def should_stop(self, metric_name: str) -> bool:
        """Quick check: has the metric reached plateau or convergence?

        Returns ``True`` if the detector recommends stopping,
        ``False`` if the metric is still improving or has insufficient data.
        Requires at least 2 observations before signalling stop.
        """
        with self._lock:
            series = self._series.get(metric_name)
            if not series or len(series) < 2:
                return False
            ema_gain = self._ema.get(metric_name, float("inf"))
            consecutive_low = self._consecutive_low.get(metric_name, 0)

        if ema_gain < self._config.convergence_threshold:
            return True
        if consecutive_low >= self._config.plateau_window:
            return True
        return False

    # ------------------------------------------------------------------
    # Public API: Query
    # ------------------------------------------------------------------

    def get_series(
        self,
        metric_name: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent observations for a metric."""
        with self._lock:
            series = list(self._series.get(metric_name, []))
        return [obs.to_dict() for obs in series[-limit:]]

    def get_reports(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent analysis reports."""
        with self._lock:
            return [r.to_dict() for r in self._reports[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Return detector status summary."""
        with self._lock:
            return {
                "metrics_tracked": list(self._series.keys()),
                "total_observations": sum(
                    len(s) for s in self._series.values()
                ),
                "total_reports": len(self._reports),
                "ema_values": {k: round(v, 6) for k, v in self._ema.items()},
                "consecutive_low": dict(self._consecutive_low),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    def reset(self, metric_name: Optional[str] = None) -> None:
        """Clear tracking state.

        Args:
            metric_name: If given, only clear state for this metric.
                If ``None``, clear everything.
        """
        with self._lock:
            if metric_name:
                self._series.pop(metric_name, None)
                self._ema.pop(metric_name, None)
                self._consecutive_low.pop(metric_name, None)
            else:
                self._series.clear()
                self._ema.clear()
                self._consecutive_low.clear()
                self._reports.clear()

    # ------------------------------------------------------------------
    # Internal: knee-point detection
    # ------------------------------------------------------------------

    def _detect_knee_point(
        self,
        gain_curve: List[float],
        series: List[MetricObservation],
    ) -> Optional[int]:
        """Find the elbow/knee in the gain curve.

        Uses the maximum curvature method: computes the second derivative
        of the normalised gain curve and finds where it is most negative
        (fastest deceleration of gains).

        Returns the iteration index of the knee point, or ``None``
        if the series is too short.
        """
        if len(gain_curve) < 3:
            return None

        # Compute second differences (discrete second derivative)
        second_diffs: List[float] = []
        for i in range(1, len(gain_curve) - 1):
            d2 = gain_curve[i + 1] - 2 * gain_curve[i] + gain_curve[i - 1]
            second_diffs.append(d2)

        if not second_diffs:
            return None

        # The knee is where the second derivative is most negative
        # (fastest drop in marginal gain)
        min_d2 = min(second_diffs)
        if min_d2 >= 0:
            # No deceleration detected — gains are accelerating or flat
            return None

        knee_idx = second_diffs.index(min_d2) + 1  # offset by 1 due to d2 indexing
        if knee_idx < len(series):
            return series[knee_idx].iteration
        return None

    # ------------------------------------------------------------------
    # Internal: persistence & events
    # ------------------------------------------------------------------

    def _store_report(self, report: DiminishingGainsReport) -> None:
        """Store report in memory and optionally persist."""
        with self._lock:
            capped_append(self._reports, report)

        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=report.report_id,
                    document=report.to_dict(),
                )
            except Exception as exc:  # ADV-004-PERSIST-ERR-001
                logger.debug("Persistence skipped for %s: %s", report.report_id, exc)

    def _publish_plateau_event(self, report: DiminishingGainsReport) -> None:
        """Publish a LEARNING_FEEDBACK event when plateau is detected."""
        if self._backbone is None:
            return
        try:
            from event_backbone import EventType
            self._backbone.publish(
                event_type=EventType.LEARNING_FEEDBACK,
                payload={
                    "source": "diminishing_gains_detector",
                    "report": report.to_dict(),
                },
                source="diminishing_gains_detector",
            )
        except Exception as exc:  # ADV-004-EVENT-ERR-001
            logger.debug("EventBackbone publish skipped: %s", exc)
