"""
Murphy System - Murphy Sensor Fusion
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

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
# Enums
# ---------------------------------------------------------------------------

class DataType(str, Enum):
    """DataType enumeration."""
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    STRING = "string"
    VECTOR3D = "vector3d"
    QUATERNION = "quaternion"
    IMAGE = "image"
    POINTCLOUD = "pointcloud"
    GPS = "gps"


class ReadingQuality(str, Enum):
    """ReadingQuality enumeration."""
    GOOD = "good"
    UNCERTAIN = "uncertain"
    BAD = "bad"
    STALE = "stale"


class FusionStrategy(str, Enum):
    """FusionStrategy enumeration."""
    KALMAN_FILTER = "kalman_filter"
    WEIGHTED_AVERAGE = "weighted_average"
    MAJORITY_VOTE = "majority_vote"
    COMPLEMENTARY = "complementary"
    BAYESIAN = "bayesian"
    LATEST_VALID = "latest_valid"


class AnomalyType(str, Enum):
    """AnomalyType enumeration."""
    DISAGREEMENT = "disagreement"
    STUCK_SENSOR = "stuck_sensor"
    DRIFT = "drift"
    SPIKE = "spike"
    STALE_DATA = "stale_data"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SensorSource(BaseModel):
    """SensorSource — sensor source definition."""
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    protocol: str = "MQTT"
    address: str = ""
    poll_interval_ms: int = 1000
    data_type: DataType = DataType.NUMERIC
    unit: str = ""
    transform: Optional[Dict[str, Any]] = None


class SensorReading(BaseModel):
    """SensorReading — sensor reading definition."""
    source_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    value: Any = None
    quality: ReadingQuality = ReadingQuality.GOOD
    raw_value: Any = None
    processed_value: Any = None


class FusedState(BaseModel):
    """FusedState — fused state definition."""
    fused_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    readings: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    staleness_ms: float = 0.0
    source_count: int = 0
    disagreement_score: float = 0.0


@dataclass
class AnomalyEvent:
    """Event record for anomaly occurrences."""
    anomaly_id: str
    anomaly_type: AnomalyType
    source_id: str
    description: str
    severity: float  # 0.0 – 1.0
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    value: Any = None


# ---------------------------------------------------------------------------
# Anomaly Detector
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """Detect sensor disagreements, stuck sensors, drift, and spike outliers."""

    def __init__(self, z_score_threshold: float = 3.0, history_size: int = 100) -> None:
        self._z_threshold = z_score_threshold
        self._history_size = history_size
        self._history: Dict[str, List[float]] = {}

    def check(self, source_id: str, value: Any) -> Optional[AnomalyEvent]:
        """Check a new reading for anomalies. Returns an AnomalyEvent or None."""
        if not isinstance(value, (int, float)):
            return None

        numeric_val = float(value)
        history = self._history.setdefault(source_id, [])

        anomaly: Optional[AnomalyEvent] = None

        if len(history) >= 10:
            mean = statistics.mean(history[-50:])
            stdev = statistics.stdev(history[-50:]) if len(history) >= 2 else 0.0
            if stdev > 0:
                z_score = abs((numeric_val - mean) / stdev)
                if z_score > self._z_threshold:
                    anomaly = AnomalyEvent(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type=AnomalyType.SPIKE,
                        source_id=source_id,
                        description=f"Z-score {z_score:.2f} exceeds threshold {self._z_threshold}",
                        severity=min(1.0, z_score / (self._z_threshold * 2)),
                        value=numeric_val,
                    )

            # Stuck sensor: last N values identical
            if len(history) >= 5 and len(set(history[-5:])) == 1 and history[-1] == numeric_val:
                anomaly = AnomalyEvent(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type=AnomalyType.STUCK_SENSOR,
                    source_id=source_id,
                    description="Sensor reading has not changed for 6+ consecutive readings",
                    severity=0.6,
                    value=numeric_val,
                )

        history.append(numeric_val)
        if len(history) > self._history_size:
            history.pop(0)

        return anomaly

    def check_disagreement(
        self, readings: List[SensorReading], threshold: float = 0.2
    ) -> Optional[AnomalyEvent]:
        """Detect disagreement among a set of sensor readings."""
        numeric = [
            float(r.value)
            for r in readings
            if r.quality == ReadingQuality.GOOD and isinstance(r.value, (int, float))
        ]
        if len(numeric) < 2:
            return None
        mean = statistics.mean(numeric)
        if mean == 0:
            return None
        spread = (max(numeric) - min(numeric)) / abs(mean)
        if spread > threshold:
            return AnomalyEvent(
                anomaly_id=str(uuid.uuid4()),
                anomaly_type=AnomalyType.DISAGREEMENT,
                source_id="multi-source",
                description=f"Sensor disagreement spread {spread:.3f} > threshold {threshold}",
                severity=min(1.0, spread),
                value=spread,
            )
        return None


# ---------------------------------------------------------------------------
# Sensor Fusion Pipeline
# ---------------------------------------------------------------------------

class SensorFusionPipeline:
    """Configure multiple sources → fusion strategy → fused output."""

    def __init__(
        self,
        pipeline_id: str,
        sources: List[SensorSource],
        strategy: FusionStrategy = FusionStrategy.WEIGHTED_AVERAGE,
    ) -> None:
        self.pipeline_id = pipeline_id
        self.sources = sources
        self.strategy = strategy
        self._anomaly_detector = AnomalyDetector()
        self._anomalies: List[AnomalyEvent] = []
        self._lock = threading.Lock()

    def fuse(self, readings: List[SensorReading]) -> FusedState:
        """Fuse a list of sensor readings into a FusedState."""
        good = [r for r in readings if r.quality in (ReadingQuality.GOOD, ReadingQuality.UNCERTAIN)]
        if not good:
            return FusedState(
                readings={},
                confidence=0.0,
                source_count=0,
                disagreement_score=1.0,
            )

        fused_readings: Dict[str, Any] = {}

        # Check for disagreement
        disagreement_event = self._anomaly_detector.check_disagreement(good)
        disagreement_score = 0.0
        if disagreement_event:
            disagreement_score = float(disagreement_event.value or 0.0)
            with self._lock:
                capped_append(self._anomalies, disagreement_event)

        if self.strategy == FusionStrategy.LATEST_VALID:
            latest = max(good, key=lambda r: r.timestamp)
            fused_readings = {latest.source_id: latest.value}
        elif self.strategy == FusionStrategy.MAJORITY_VOTE:
            from collections import Counter
            values = [str(r.value) for r in good]
            most_common = Counter(values).most_common(1)
            fused_readings = {"voted_value": most_common[0][0] if most_common else None}
        elif self.strategy == FusionStrategy.KALMAN_FILTER:
            # Simplified 1-D Kalman filter: process model is constant, measurement noise = 1
            numeric_vals = [
                float(r.value) for r in good if isinstance(r.value, (int, float))
            ]
            if numeric_vals:
                # Use iterative Kalman update with process noise Q=0.1, measurement noise R=1
                estimate = numeric_vals[0]
                p = 1.0  # initial error covariance
                q = 0.1  # process noise
                r_noise = 1.0  # measurement noise
                for z in numeric_vals[1:]:
                    p = p + q
                    k = p / (p + r_noise)  # Kalman gain
                    estimate = estimate + k * (z - estimate)
                    p = (1 - k) * p
                fused_readings = {"fused_value": estimate}
            else:
                fused_readings = {r.source_id: r.value for r in good}
        elif self.strategy == FusionStrategy.COMPLEMENTARY:
            # Complementary filter: alpha * high_freq + (1-alpha) * low_freq
            numeric_vals = [
                float(r.value) for r in good if isinstance(r.value, (int, float))
            ]
            if len(numeric_vals) >= 2:
                alpha = 0.98
                # Use first reading as "high frequency" source and average of rest as "low frequency"
                high_freq = numeric_vals[0]
                low_freq = sum(numeric_vals[1:]) / len(numeric_vals[1:])
                fused_readings = {"fused_value": alpha * high_freq + (1 - alpha) * low_freq}
            elif numeric_vals:
                fused_readings = {"fused_value": numeric_vals[0]}
            else:
                fused_readings = {r.source_id: r.value for r in good}
        elif self.strategy == FusionStrategy.BAYESIAN:
            # Bayesian fusion: combine Gaussian likelihoods (equal prior)
            # For N independent Gaussian sensors: fused = weighted mean by inverse variance
            numeric_vals = [
                float(r.value) for r in good if isinstance(r.value, (int, float))
            ]
            if len(numeric_vals) >= 2:
                # Assume measurement variance = 1 for all sensors
                sigma2 = 1.0
                weights = [1.0 / sigma2] * len(numeric_vals)
                total_weight = sum(weights)
                fused_mean = sum(w * v for w, v in zip(weights, numeric_vals)) / total_weight
                fused_readings = {"fused_value": fused_mean}
            elif numeric_vals:
                fused_readings = {"fused_value": numeric_vals[0]}
            else:
                fused_readings = {r.source_id: r.value for r in good}
        else:
            # Weighted average for numeric, latest for others
            numeric_vals = [
                float(r.value) for r in good if isinstance(r.value, (int, float))
            ]
            if numeric_vals:
                avg = sum(numeric_vals) / (len(numeric_vals) or 1)
                fused_readings = {"fused_value": avg}
            else:
                fused_readings = {r.source_id: r.value for r in good}

        # Per-source anomaly checks
        for r in good:
            event = self._anomaly_detector.check(r.source_id, r.value)
            if event:
                with self._lock:
                    capped_append(self._anomalies, event)

        confidence = sum(
            1.0 if r.quality == ReadingQuality.GOOD else 0.5 for r in good
        ) / (len(good) or 1)

        # Staleness: ms since oldest good reading
        now_ts = time.time() * 1000
        staleness_ms = 0.0
        try:
            oldest_ts = min(
                datetime.fromisoformat(r.timestamp).timestamp() * 1000
                for r in good
            )
            staleness_ms = max(0.0, now_ts - oldest_ts)
        except (ValueError, TypeError):
            staleness_ms = 0.0

        return FusedState(
            readings=fused_readings,
            confidence=round(confidence, 4),
            source_count=len(good),
            disagreement_score=round(disagreement_score, 4),
            staleness_ms=round(staleness_ms, 1),
        )

    def get_anomalies(self) -> List[AnomalyEvent]:
        """Return all detected anomalies."""
        with self._lock:
            return list(self._anomalies)


# ---------------------------------------------------------------------------
# Spatial / Environmental models
# ---------------------------------------------------------------------------

class SpatialMap(BaseModel):
    """SpatialMap — spatial map definition."""
    map_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    coordinate_frame: str = "world"
    zones: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def add_zone(self, zone_id: str, bounds: Dict[str, Any]) -> None:
        self.zones[zone_id] = bounds

    def locate(self, x: float, y: float, z: float = 0.0) -> Optional[str]:
        """Return the zone_id containing the given coordinates, or None."""
        for zone_id, bounds in self.zones.items():
            if (
                bounds.get("x_min", float("-inf")) <= x <= bounds.get("x_max", float("inf"))
                and bounds.get("y_min", float("-inf")) <= y <= bounds.get("y_max", float("inf"))
                and bounds.get("z_min", float("-inf")) <= z <= bounds.get("z_max", float("inf"))
            ):
                return zone_id
        return None


class EnvironmentalModel(BaseModel):
    """EnvironmentalModel — environmental model definition."""
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    zones: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def update_zone(self, zone_id: str, readings: Dict[str, Any]) -> None:
        existing = self.zones.get(zone_id, {})
        existing.update(readings)
        self.zones[zone_id] = existing

    def get_zone(self, zone_id: str) -> Dict[str, Any]:
        return self.zones.get(zone_id, {})


# ---------------------------------------------------------------------------
# Pre-built Fusion Profiles
# ---------------------------------------------------------------------------

class VehicleFusionProfile:
    """Pre-built profile for autonomous vehicle sensor fusion."""

    @staticmethod
    def build(vehicle_id: str) -> SensorFusionPipeline:
        sources = [
            SensorSource(source_id=f"{vehicle_id}-lidar", protocol="ROS2", data_type=DataType.POINTCLOUD, unit="meters"),
            SensorSource(source_id=f"{vehicle_id}-camera", protocol="ROS2", data_type=DataType.IMAGE, unit="pixels"),
            SensorSource(source_id=f"{vehicle_id}-radar", protocol="ROS2", data_type=DataType.NUMERIC, unit="m/s"),
            SensorSource(source_id=f"{vehicle_id}-gps", protocol="ROS2", data_type=DataType.GPS, unit="degrees"),
            SensorSource(source_id=f"{vehicle_id}-imu", protocol="ROS2", data_type=DataType.VECTOR3D, unit="m/s2"),
        ]
        return SensorFusionPipeline(
            pipeline_id=f"vehicle-{vehicle_id}",
            sources=sources,
            strategy=FusionStrategy.KALMAN_FILTER,
        )


class BuildingFusionProfile:
    """Pre-built profile for building automation sensor fusion."""

    @staticmethod
    def build(building_id: str) -> SensorFusionPipeline:
        sources = [
            SensorSource(source_id=f"{building_id}-hvac-temp", protocol="BACNET", data_type=DataType.NUMERIC, unit="degF"),
            SensorSource(source_id=f"{building_id}-hvac-humidity", protocol="BACNET", data_type=DataType.NUMERIC, unit="%"),
            SensorSource(source_id=f"{building_id}-power", protocol="MODBUS", data_type=DataType.NUMERIC, unit="kW"),
            SensorSource(source_id=f"{building_id}-occupancy", protocol="MQTT", data_type=DataType.BOOLEAN, unit="bool"),
            SensorSource(source_id=f"{building_id}-co2", protocol="BACNET", data_type=DataType.NUMERIC, unit="ppm"),
        ]
        return SensorFusionPipeline(
            pipeline_id=f"building-{building_id}",
            sources=sources,
            strategy=FusionStrategy.WEIGHTED_AVERAGE,
        )


class FactoryFusionProfile:
    """Pre-built profile for manufacturing environment sensor fusion."""

    @staticmethod
    def build(factory_id: str) -> SensorFusionPipeline:
        sources = [
            SensorSource(source_id=f"{factory_id}-opcua-machine1", protocol="OPCUA", data_type=DataType.NUMERIC, unit="rpm"),
            SensorSource(source_id=f"{factory_id}-modbus-io", protocol="MODBUS", data_type=DataType.BOOLEAN, unit="bool"),
            SensorSource(source_id=f"{factory_id}-mqtt-temp", protocol="MQTT", data_type=DataType.NUMERIC, unit="degC"),
            SensorSource(source_id=f"{factory_id}-robot-telemetry", protocol="ROS2", data_type=DataType.VECTOR3D, unit="mm"),
        ]
        return SensorFusionPipeline(
            pipeline_id=f"factory-{factory_id}",
            sources=sources,
            strategy=FusionStrategy.WEIGHTED_AVERAGE,
        )
