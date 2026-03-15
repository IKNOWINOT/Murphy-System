"""
Efficiency Orchestrator for Murphy System Runtime

Wires together WingmanProtocol and TelemetryAdapter to monitor resource
consumption and surface optimisation opportunities across six resource types.

Key capabilities:
- Auto-creates baseline from first reading for each resource type
- Anomaly detection via configurable deviation threshold
- Efficiency scoring and trend analysis per resource
- Optimisation opportunity surfacing with estimated savings
- Thread-safe operation

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from telemetry_adapter import TelemetryAdapter
from wingman_protocol import (
    ExecutionRunbook,
    ValidationRule,
    ValidationSeverity,
    WingmanProtocol,
)

logger = logging.getLogger(__name__)

# Anomaly threshold: readings > this many standard deviations from baseline
_DEFAULT_ANOMALY_THRESHOLD: float = 2.0
# Minimum readings before trend analysis is meaningful
_MIN_READINGS_FOR_TREND: int = 3
# Trend detection thresholds
_TREND_INCREASE_THRESHOLD: float = 1.05
_TREND_DECREASE_THRESHOLD: float = 0.95
# Optimization opportunity thresholds
_PEAK_SAVINGS_FACTOR: float = 0.5
_MAX_PEAK_SAVINGS_PCT: float = 30.0


def _build_efficiency_runbook(resource_type: str) -> ExecutionRunbook:
    """Create a resource-specific efficiency validation runbook."""
    return ExecutionRunbook(
        runbook_id=f"efficiency_{resource_type}",
        name=f"Efficiency Runbook — {resource_type.replace('_', ' ').title()}",
        domain=resource_type,
        validation_rules=[
            ValidationRule(
                rule_id="check_has_output",
                description="Efficiency reading must contain a non-empty result",
                check_fn_name="check_has_output",
                severity=ValidationSeverity.BLOCK,
                applicable_domains=[resource_type],
            ),
            ValidationRule(
                rule_id="check_confidence_threshold",
                description="Meter confidence must meet minimum threshold",
                check_fn_name="check_confidence_threshold",
                severity=ValidationSeverity.WARN,
                applicable_domains=[resource_type],
            ),
        ],
    )


def _compute_mean(values: List[float]) -> float:
    """Return the mean of *values*, or 0.0 for an empty list."""
    return sum(values) / (len(values) or 1)


def _compute_stddev(values: List[float], mean: float) -> float:
    """Return population standard deviation of *values*, or 0.0."""
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) or 1)
    return variance ** 0.5


class EfficiencyOrchestrator:
    """Monitors resource consumption and finds optimisation opportunities.

    Starts working immediately — auto-creates baseline from first readings.
    Wires WingmanProtocol + TelemetryAdapter.
    """

    RESOURCE_TYPES = [
        "electricity",
        "gas",
        "water",
        "compressed_air",
        "steam",
        "fuel",
    ]

    def __init__(
        self,
        wingman_protocol: Optional[WingmanProtocol] = None,
        telemetry: Optional[TelemetryAdapter] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.wingman = wingman_protocol or WingmanProtocol()
        self.telemetry = telemetry or TelemetryAdapter()

        # pair_id indexed by resource_type
        self._resource_pairs: Dict[str, str] = {}
        # raw readings: {resource_type: [{value, unit, location, recorded_at}]}
        self._readings: Dict[str, List[Dict[str, Any]]] = {
            r: [] for r in self.RESOURCE_TYPES
        }
        # running baseline (mean) per resource type
        self._baselines: Dict[str, float] = {}

        self._setup()

    def _setup(self) -> None:
        """Register runbooks and create default pairs for all resource types."""
        for resource_type in self.RESOURCE_TYPES:
            runbook = _build_efficiency_runbook(resource_type)
            self.wingman.register_runbook(runbook)
            pair = self.wingman.create_pair(
                subject=f"efficiency_{resource_type}",
                executor_id=f"meter_{resource_type}",
                validator_id=f"efficiency_validator_{resource_type}",
                runbook_id=runbook.runbook_id,
            )
            with self._lock:
                self._resource_pairs[resource_type] = pair.pair_id
        logger.info(
            "EfficiencyOrchestrator ready — %d resource types initialised",
            len(self.RESOURCE_TYPES),
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def record_reading(
        self,
        resource_type: str,
        value: float,
        unit: str,
        location: str = "main",
    ) -> Dict[str, Any]:
        """Store *value*, update baseline, and detect anomalies.

        Returns a dict with:
            recorded           – True on success
            baseline           – current baseline value
            deviation_percent  – how far from baseline (as %)
            anomaly_detected   – True if deviation exceeds threshold
            recommendation     – human-readable action string
        """
        if resource_type not in self.RESOURCE_TYPES:
            return {
                "recorded": False,
                "baseline": None,
                "deviation_percent": None,
                "anomaly_detected": False,
                "recommendation": (
                    f"Unknown resource type '{resource_type}'. "
                    f"Valid types: {', '.join(self.RESOURCE_TYPES)}."
                ),
            }

        with self._lock:
            pair_id = self._resource_pairs.get(resource_type)

        output = {"result": {"value": value, "unit": unit, "location": location}}
        self.wingman.validate_output(pair_id, output)

        reading: Dict[str, Any] = {
            "value": value,
            "unit": unit,
            "location": location,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self._readings[resource_type].append(reading)
            all_values = [r["value"] for r in self._readings[resource_type]]
            baseline = _compute_mean(all_values)
            self._baselines[resource_type] = baseline

        mean = baseline
        stddev = _compute_stddev(all_values, mean)
        deviation_percent = (
            abs(value - mean) / (abs(mean) or 1) * 100
        )
        anomaly_detected = (
            stddev > 0 and abs(value - mean) > _DEFAULT_ANOMALY_THRESHOLD * stddev
        )

        if anomaly_detected:
            direction = "above" if value > mean else "below"
            recommendation = (
                f"Anomalous {resource_type.replace('_', ' ')} reading detected at {location}: "
                f"{value} {unit} is {deviation_percent:.1f}% {direction} the baseline of "
                f"{mean:.2f} {unit}. Inspect meter and connected equipment for leaks or faults."
            )
        else:
            recommendation = (
                f"{resource_type.replace('_', ' ').title()} reading of {value} {unit} at "
                f"{location} is within normal range (baseline: {mean:.2f} {unit}). "
                "No action required."
            )

        self.telemetry.collect_metric(
            metric_type="performance",
            metric_name=f"efficiency_{resource_type}",
            value=value,
            labels={
                "unit": unit,
                "location": location,
                "anomaly": str(anomaly_detected),
            },
        )

        return {
            "recorded": True,
            "baseline": round(baseline, 4),
            "deviation_percent": round(deviation_percent, 2),
            "anomaly_detected": anomaly_detected,
            "recommendation": recommendation,
        }

    def get_efficiency_score(self, resource_type: Optional[str] = None) -> Dict[str, Any]:
        """Return per-resource efficiency scores, trends, and recommendations.

        If *resource_type* is provided, returns data for that resource only.
        """
        with self._lock:
            readings_snapshot = {
                r: list(v) for r, v in self._readings.items()
            }
            baselines_snapshot = dict(self._baselines)

        def _score_resource(rtype: str) -> Dict[str, Any]:
            readings = readings_snapshot.get(rtype, [])
            if not readings:
                return {
                    "score": None,
                    "trend": "no_data",
                    "reading_count": 0,
                    "baseline": None,
                    "recommendation": (
                        f"No readings recorded for {rtype.replace('_', ' ')}. "
                        "Begin recording meter readings to establish a baseline."
                    ),
                }
            values = [r["value"] for r in readings]
            baseline = baselines_snapshot.get(rtype, _compute_mean(values))
            stddev = _compute_stddev(values, baseline)
            # Score: 100 when all readings match baseline exactly; decreases with variance
            cv = stddev / (abs(baseline) or 1)  # coefficient of variation
            score = max(0.0, round(100.0 * (1.0 - min(cv, 1.0)), 1))

            trend = "stable"
            if len(values) >= _MIN_READINGS_FOR_TREND:
                half = len(values) // 2
                recent = _compute_mean(values[-half:])
                early = _compute_mean(values[:half])
                if recent > early * _TREND_INCREASE_THRESHOLD:
                    trend = "increasing"
                elif recent < early * _TREND_DECREASE_THRESHOLD:
                    trend = "decreasing"

            if score >= 90:
                recommendation = (
                    f"{rtype.replace('_', ' ').title()} consumption is highly efficient. "
                    "Maintain current operations."
                )
            elif score >= 70:
                recommendation = (
                    f"{rtype.replace('_', ' ').title()} efficiency is moderate. "
                    "Review peak-usage periods and consider off-peak scheduling."
                )
            else:
                recommendation = (
                    f"{rtype.replace('_', ' ').title()} efficiency is low. "
                    "Conduct an energy audit and identify high-consumption equipment."
                )

            return {
                "score": score,
                "trend": trend,
                "reading_count": len(readings),
                "baseline": round(baseline, 4),
                "recommendation": recommendation,
            }

        if resource_type is not None:
            if resource_type not in self.RESOURCE_TYPES:
                return {
                    "error": f"Unknown resource type: {resource_type}",
                    "valid_types": self.RESOURCE_TYPES,
                }
            return {resource_type: _score_resource(resource_type)}

        return {rtype: _score_resource(rtype) for rtype in self.RESOURCE_TYPES}

    def get_optimization_opportunities(self) -> List[Dict[str, Any]]:
        """Analyse patterns and suggest savings opportunities.

        Each opportunity includes:
            description            – what was detected
            estimated_savings      – rough percentage saving available
            confidence             – 0.0–1.0
            implementation_steps   – list of action strings
        """
        with self._lock:
            readings_snapshot = {
                r: list(v) for r, v in self._readings.items()
            }
            baselines_snapshot = dict(self._baselines)

        opportunities: List[Dict[str, Any]] = []

        for rtype in self.RESOURCE_TYPES:
            readings = readings_snapshot.get(rtype, [])
            if len(readings) < _MIN_READINGS_FOR_TREND:
                continue

            values = [r["value"] for r in readings]
            baseline = baselines_snapshot.get(rtype, _compute_mean(values))
            peak = max(values)
            trough = min(values)

            if baseline > 0 and peak > baseline * 1.2:
                swing_pct = round((peak - baseline) / (baseline or 1) * 100, 1)
                opportunities.append({
                    "resource_type": rtype,
                    "description": (
                        f"{rtype.replace('_', ' ').title()} shows peak consumption "
                        f"{swing_pct}% above baseline — likely from unscheduled high-demand events."
                    ),
                    "estimated_savings": f"{min(swing_pct * _PEAK_SAVINGS_FACTOR, _MAX_PEAK_SAVINGS_PCT):.1f}%",
                    "confidence": min(0.5 + len(values) / 100.0, 0.95),
                    "implementation_steps": [
                        f"Identify equipment driving peak {rtype.replace('_', ' ')} consumption.",
                        "Shift high-demand loads to off-peak hours.",
                        "Install demand-response controls or smart scheduling.",
                        "Re-evaluate baseline after 30 days of optimised operation.",
                    ],
                })

            if trough < baseline * 0.5 and len(values) >= 5:
                opportunities.append({
                    "resource_type": rtype,
                    "description": (
                        f"{rtype.replace('_', ' ').title()} drops to {trough:.2f} during "
                        "low-activity periods — standby waste may be present."
                    ),
                    "estimated_savings": "5.0–15.0%",
                    "confidence": min(0.4 + len(values) / 200.0, 0.85),
                    "implementation_steps": [
                        f"Audit {rtype.replace('_', ' ')} consumers during low-activity windows.",
                        "Enable auto-shutdown or standby mode on idle equipment.",
                        "Install occupancy-based controls.",
                    ],
                })

        return opportunities
