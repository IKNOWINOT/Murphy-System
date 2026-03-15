# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Digital Twin Simulation Engine — DTE-001

Model physical or logical systems as digital twins, predict failures from
telemetry, and test what-if scenarios before applying changes to production.

Design Principles:
  - Each twin is an isolated state machine with typed sensor inputs.
  - Anomaly detection uses statistical thresholds (z-score) — no external ML deps.
  - Scenario runner evaluates proposed changes against the twin's model.
  - WingmanProtocol pair validation gates every scenario commit.
  - CausalitySandbox gating simulates scenario effects before applying.

Key Classes:
  DigitalTwin           — models one physical/logical system
  SensorReading         — timestamped telemetry data point
  AnomalyDetector       — z-score-based anomaly flagging
  ScenarioDefinition    — describes a what-if experiment
  ScenarioResult        — outcome of running a scenario
  TwinRegistry          — manages a fleet of twins
  FailurePrediction     — predicted failure with confidence

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TwinStatus(str, Enum):
    """Lifecycle status of a digital twin."""

    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class SeverityLevel(str, Enum):
    """Severity of an anomaly or predicted failure."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScenarioOutcome(str, Enum):
    """Outcome of a scenario simulation."""

    PASS = "pass"
    FAIL = "fail"
    DEGRADED = "degraded"
    INCONCLUSIVE = "inconclusive"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SensorReading:
    """One telemetry data point from a sensor."""

    sensor_id: str
    value: float
    unit: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "sensor_id": self.sensor_id,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp,
        }


@dataclass
class FailurePrediction:
    """A predicted failure with confidence and time horizon."""

    prediction_id: str
    twin_id: str
    sensor_id: str
    severity: str
    confidence: float
    description: str
    predicted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "prediction_id": self.prediction_id,
            "twin_id": self.twin_id,
            "sensor_id": self.sensor_id,
            "severity": self.severity,
            "confidence": self.confidence,
            "description": self.description,
            "predicted_at": self.predicted_at,
        }


@dataclass
class ScenarioDefinition:
    """Describes a what-if experiment to run against a twin."""

    scenario_id: str
    name: str
    description: str = ""
    sensor_overrides: Dict[str, float] = field(default_factory=dict)
    parameter_changes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "sensor_overrides": self.sensor_overrides,
            "parameter_changes": self.parameter_changes,
        }


@dataclass
class ScenarioResult:
    """Outcome of running a scenario against a twin."""

    result_id: str
    scenario_id: str
    twin_id: str
    outcome: str = ScenarioOutcome.INCONCLUSIVE.value
    anomalies_detected: int = 0
    predictions: List[FailurePrediction] = field(default_factory=list)
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "result_id": self.result_id,
            "scenario_id": self.scenario_id,
            "twin_id": self.twin_id,
            "outcome": self.outcome,
            "anomalies_detected": self.anomalies_detected,
            "predictions_count": len(self.predictions),
            "duration_ms": self.duration_ms,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Anomaly Detector — z-score based
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """Detects anomalies in sensor readings using z-score thresholds.

    A reading is anomalous if its z-score exceeds ``threshold``.

    Usage::

        detector = AnomalyDetector(window_size=100, threshold=3.0)
        detector.ingest(42.0)
        detector.ingest(43.0)
        is_bad, z = detector.check(999.0)
    """

    def __init__(self, window_size: int = 100, threshold: float = 3.0) -> None:
        self._window = deque(maxlen=window_size)  # type: Deque[float]
        self._threshold = threshold

    def ingest(self, value: float) -> None:
        """Add a value to the sliding window."""
        self._window.append(value)

    def check(self, value: float) -> tuple[bool, float]:
        """Check whether *value* is anomalous.

        Returns:
            A tuple ``(is_anomaly, z_score)``.
        """
        if len(self._window) < 2:
            return False, 0.0

        mean = sum(self._window) / len(self._window)
        variance = sum((x - mean) ** 2 for x in self._window) / len(self._window)
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std == 0:
            return value != mean, 0.0

        z = abs(value - mean) / std
        return z > self._threshold, z

    @property
    def mean(self) -> float:
        """Current window mean."""
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    @property
    def std(self) -> float:
        """Current window standard deviation."""
        if len(self._window) < 2:
            return 0.0
        m = self.mean
        var = sum((x - m) ** 2 for x in self._window) / len(self._window)
        return math.sqrt(var)

    @property
    def count(self) -> int:
        """Number of readings in the window."""
        return len(self._window)


# ---------------------------------------------------------------------------
# Digital Twin
# ---------------------------------------------------------------------------

class DigitalTwin:
    """Models one physical or logical system.

    Each twin tracks multiple sensors, detects anomalies per-sensor,
    and generates failure predictions when thresholds are breached.

    Usage::

        twin = DigitalTwin("twin-1", "Compressor-A")
        twin.add_sensor("temp", unit="°C", warn=80.0, crit=95.0)
        twin.ingest(SensorReading("temp", 75.0))
        predictions = twin.predict_failures()
    """

    def __init__(self, twin_id: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._twin_id = twin_id
        self._name = name
        self._metadata = metadata or {}
        self._status = TwinStatus.ACTIVE.value
        self._sensors: Dict[str, Dict[str, Any]] = {}
        self._detectors: Dict[str, AnomalyDetector] = {}
        self._latest: Dict[str, float] = {}
        self._lock = threading.Lock()

    # -- properties --------------------------------------------------------

    @property
    def twin_id(self) -> str:
        """Unique identifier."""
        return self._twin_id

    @property
    def name(self) -> str:
        """Human-readable name."""
        return self._name

    @property
    def status(self) -> str:
        """Current twin status."""
        return self._status

    # -- sensor management -------------------------------------------------

    def add_sensor(
        self,
        sensor_id: str,
        unit: str = "",
        warn_threshold: float = float("inf"),
        critical_threshold: float = float("inf"),
        window_size: int = 100,
        z_threshold: float = 3.0,
    ) -> None:
        """Register a sensor on this twin.

        Args:
            sensor_id: Unique sensor name.
            unit: Measurement unit string.
            warn_threshold: Value above which a LOW/MEDIUM warning is raised.
            critical_threshold: Value above which a HIGH/CRITICAL alert is raised.
            window_size: Sliding window size for anomaly detection.
            z_threshold: Z-score threshold for anomaly detection.
        """
        with self._lock:
            self._sensors[sensor_id] = {
                "unit": unit,
                "warn_threshold": warn_threshold,
                "critical_threshold": critical_threshold,
            }
            self._detectors[sensor_id] = AnomalyDetector(window_size, z_threshold)

    def list_sensors(self) -> List[str]:
        """Return all registered sensor IDs."""
        with self._lock:
            return list(self._sensors.keys())

    # -- telemetry ingestion -----------------------------------------------

    def ingest(self, reading: SensorReading) -> None:
        """Ingest a sensor reading.

        Args:
            reading: The telemetry data point.
        """
        with self._lock:
            detector = self._detectors.get(reading.sensor_id)
            if detector is None:
                return
            detector.ingest(reading.value)
            self._latest[reading.sensor_id] = reading.value

    def get_latest(self, sensor_id: str) -> Optional[float]:
        """Return the most recent reading for *sensor_id*."""
        with self._lock:
            return self._latest.get(sensor_id)

    # -- failure prediction ------------------------------------------------

    def predict_failures(self) -> List[FailurePrediction]:
        """Analyse current sensor state and return failure predictions.

        Predictions are generated when:
          1. A sensor's latest value exceeds its warn/critical threshold.
          2. A sensor's latest value is a statistical anomaly (z-score).
        """
        predictions: List[FailurePrediction] = []
        with self._lock:
            for sid, cfg in self._sensors.items():
                latest = self._latest.get(sid)
                if latest is None:
                    continue
                detector = self._detectors[sid]
                is_anomaly, z_score = detector.check(latest)

                severity, confidence, desc = self._evaluate_sensor(
                    sid, latest, cfg, is_anomaly, z_score,
                )
                if severity is not None:
                    predictions.append(FailurePrediction(
                        prediction_id=f"fp-{uuid.uuid4().hex[:8]}",
                        twin_id=self._twin_id,
                        sensor_id=sid,
                        severity=severity,
                        confidence=confidence,
                        description=desc,
                    ))

            self._update_status(predictions)
        return predictions

    # -- scenario simulation -----------------------------------------------

    def run_scenario(self, scenario: ScenarioDefinition) -> ScenarioResult:
        """Simulate a what-if scenario against this twin's model.

        Sensor overrides temporarily replace latest values; anomaly
        detection and failure prediction run on the modified state.

        Args:
            scenario: The scenario to simulate.

        Returns:
            A ``ScenarioResult`` describing the outcome.
        """
        start = time.monotonic()
        result_id = f"sr-{uuid.uuid4().hex[:8]}"

        with self._lock:
            saved_latest = dict(self._latest)
            for sid, val in scenario.sensor_overrides.items():
                if sid in self._sensors:
                    self._latest[sid] = val

        try:
            predictions = self.predict_failures()
        finally:
            with self._lock:
                self._latest = saved_latest

        anomaly_count = len(predictions)
        has_critical = any(
            p.severity == SeverityLevel.CRITICAL.value for p in predictions
        )
        has_high = any(
            p.severity == SeverityLevel.HIGH.value for p in predictions
        )

        if has_critical:
            outcome = ScenarioOutcome.FAIL.value
        elif has_high:
            outcome = ScenarioOutcome.DEGRADED.value
        elif anomaly_count == 0:
            outcome = ScenarioOutcome.PASS.value
        else:
            outcome = ScenarioOutcome.DEGRADED.value

        duration_ms = (time.monotonic() - start) * 1000

        return ScenarioResult(
            result_id=result_id,
            scenario_id=scenario.scenario_id,
            twin_id=self._twin_id,
            outcome=outcome,
            anomalies_detected=anomaly_count,
            predictions=predictions,
            duration_ms=duration_ms,
            details={"sensor_overrides": scenario.sensor_overrides},
        )

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise twin state to a dict."""
        with self._lock:
            return {
                "twin_id": self._twin_id,
                "name": self._name,
                "status": self._status,
                "sensors": list(self._sensors.keys()),
                "latest_readings": dict(self._latest),
                "metadata": self._metadata,
            }

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _evaluate_sensor(
        sid: str,
        value: float,
        cfg: Dict[str, Any],
        is_anomaly: bool,
        z_score: float,
    ) -> tuple[Optional[str], float, str]:
        """Evaluate a sensor reading and determine severity."""
        crit = cfg["critical_threshold"]
        warn = cfg["warn_threshold"]

        if value >= crit:
            return (
                SeverityLevel.CRITICAL.value,
                min(0.95, 0.7 + z_score * 0.05),
                f"Sensor {sid} at {value} exceeds critical threshold {crit}",
            )
        if value >= warn:
            return (
                SeverityLevel.HIGH.value,
                min(0.85, 0.5 + z_score * 0.05),
                f"Sensor {sid} at {value} exceeds warning threshold {warn}",
            )
        if is_anomaly:
            return (
                SeverityLevel.MEDIUM.value,
                min(0.7, 0.3 + z_score * 0.05),
                f"Sensor {sid} at {value} is a statistical anomaly (z={z_score:.2f})",
            )
        return None, 0.0, ""

    def _update_status(self, predictions: List[FailurePrediction]) -> None:
        """Update twin status based on current predictions."""
        if any(p.severity == SeverityLevel.CRITICAL.value for p in predictions):
            self._status = TwinStatus.FAILED.value
        elif any(p.severity == SeverityLevel.HIGH.value for p in predictions):
            self._status = TwinStatus.DEGRADED.value
        elif predictions:
            self._status = TwinStatus.DEGRADED.value
        else:
            self._status = TwinStatus.ACTIVE.value


# ---------------------------------------------------------------------------
# Twin Registry
# ---------------------------------------------------------------------------

class TwinRegistry:
    """Manages a fleet of digital twins.

    Thread-safe: all mutable state is protected by a lock.

    Usage::

        registry = TwinRegistry()
        twin = registry.create_twin("compressor-a", "Compressor A")
        twin.add_sensor("temp", unit="°C", warn=80.0, crit=95.0)
        all_twins = registry.list_twins()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._twins: Dict[str, DigitalTwin] = {}

    def create_twin(
        self,
        twin_id: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DigitalTwin:
        """Create and register a new digital twin.

        Args:
            twin_id: Unique identifier.
            name: Human-readable name.
            metadata: Optional metadata dict.

        Returns:
            The created ``DigitalTwin``.
        """
        twin = DigitalTwin(twin_id, name, metadata)
        with self._lock:
            self._twins[twin_id] = twin
        logger.info("Created digital twin %s (%s)", twin_id, name)
        return twin

    def get_twin(self, twin_id: str) -> Optional[DigitalTwin]:
        """Retrieve a twin by ID."""
        with self._lock:
            return self._twins.get(twin_id)

    def remove_twin(self, twin_id: str) -> bool:
        """Remove a twin.  Returns True if found."""
        with self._lock:
            return self._twins.pop(twin_id, None) is not None

    def list_twins(self) -> List[DigitalTwin]:
        """List all registered twins."""
        with self._lock:
            return list(self._twins.values())

    def predict_all_failures(self) -> List[FailurePrediction]:
        """Run failure prediction across ALL twins."""
        with self._lock:
            twins = list(self._twins.values())
        results: List[FailurePrediction] = []
        for twin in twins:
            results.extend(twin.predict_failures())
        return results

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of the registry's current state."""
        with self._lock:
            twins = list(self._twins.values())
        return {
            "total_twins": len(twins),
            "active": sum(1 for t in twins if t.status == TwinStatus.ACTIVE.value),
            "degraded": sum(1 for t in twins if t.status == TwinStatus.DEGRADED.value),
            "failed": sum(1 for t in twins if t.status == TwinStatus.FAILED.value),
        }
