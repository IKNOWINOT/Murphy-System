"""
Tests for Murphy Sensor Fusion (Subsystem 3).
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1
"""

import pytest

from src.murphy_sensor_fusion import (
    AnomalyDetector,
    AnomalyType,
    BuildingFusionProfile,
    DataType,
    EnvironmentalModel,
    FactoryFusionProfile,
    FusedState,
    FusionStrategy,
    ReadingQuality,
    SensorFusionPipeline,
    SensorReading,
    SensorSource,
    SpatialMap,
    VehicleFusionProfile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def source():
    return SensorSource(source_id="s1", protocol="MODBUS", data_type=DataType.NUMERIC, unit="degC")


@pytest.fixture
def good_reading():
    return SensorReading(source_id="s1", value=25.0, quality=ReadingQuality.GOOD)


@pytest.fixture
def pipeline(source):
    return SensorFusionPipeline(
        pipeline_id="test-pipe",
        sources=[source],
        strategy=FusionStrategy.WEIGHTED_AVERAGE,
    )


# ---------------------------------------------------------------------------
# SensorSource
# ---------------------------------------------------------------------------

class TestSensorSource:

    def test_creation(self, source):
        assert source.source_id == "s1"
        assert source.data_type == DataType.NUMERIC

    def test_default_poll_interval(self, source):
        assert source.poll_interval_ms == 1000

    def test_all_data_types(self):
        for dt in DataType:
            s = SensorSource(data_type=dt)
            assert s.data_type == dt


# ---------------------------------------------------------------------------
# SensorReading
# ---------------------------------------------------------------------------

class TestSensorReading:

    def test_good_reading(self, good_reading):
        assert good_reading.value == 25.0
        assert good_reading.quality == ReadingQuality.GOOD

    def test_reading_qualities(self):
        for q in ReadingQuality:
            r = SensorReading(source_id="s", value=0, quality=q)
            assert r.quality == q


# ---------------------------------------------------------------------------
# Sensor Fusion Pipeline
# ---------------------------------------------------------------------------

class TestSensorFusionPipeline:

    def test_fuse_single_reading(self, pipeline):
        readings = [SensorReading(source_id="s1", value=42.0, quality=ReadingQuality.GOOD)]
        state = pipeline.fuse(readings)
        assert state.source_count == 1
        assert state.confidence > 0

    def test_fuse_empty_returns_zero_confidence(self, pipeline):
        state = pipeline.fuse([])
        assert state.confidence == 0.0
        assert state.source_count == 0

    def test_fuse_only_bad_quality(self, pipeline):
        readings = [SensorReading(source_id="s1", value=10.0, quality=ReadingQuality.BAD)]
        state = pipeline.fuse(readings)
        assert state.confidence == 0.0

    def test_fuse_weighted_average(self):
        sources = [
            SensorSource(source_id="s1"),
            SensorSource(source_id="s2"),
        ]
        pipe = SensorFusionPipeline("p", sources, FusionStrategy.WEIGHTED_AVERAGE)
        readings = [
            SensorReading(source_id="s1", value=10.0, quality=ReadingQuality.GOOD),
            SensorReading(source_id="s2", value=20.0, quality=ReadingQuality.GOOD),
        ]
        state = pipe.fuse(readings)
        fused_val = state.readings.get("fused_value")
        assert fused_val is not None
        assert abs(fused_val - 15.0) < 1e-6

    def test_fuse_latest_valid(self):
        sources = [SensorSource(source_id="s1"), SensorSource(source_id="s2")]
        pipe = SensorFusionPipeline("p", sources, FusionStrategy.LATEST_VALID)
        readings = [
            SensorReading(source_id="s1", value=5.0, quality=ReadingQuality.GOOD),
            SensorReading(source_id="s2", value=8.0, quality=ReadingQuality.GOOD),
        ]
        state = pipe.fuse(readings)
        assert state.source_count == 2

    def test_fuse_majority_vote(self):
        sources = [SensorSource(source_id=f"s{i}") for i in range(3)]
        pipe = SensorFusionPipeline("p", sources, FusionStrategy.MAJORITY_VOTE)
        readings = [
            SensorReading(source_id="s0", value="ON", quality=ReadingQuality.GOOD),
            SensorReading(source_id="s1", value="ON", quality=ReadingQuality.GOOD),
            SensorReading(source_id="s2", value="OFF", quality=ReadingQuality.GOOD),
        ]
        state = pipe.fuse(readings)
        assert state.readings.get("voted_value") == "ON"

    def test_anomalies_initially_empty(self, pipeline):
        assert pipeline.get_anomalies() == []


# ---------------------------------------------------------------------------
# Anomaly Detector
# ---------------------------------------------------------------------------

class TestAnomalyDetector:

    def test_no_anomaly_normal_readings(self):
        detector = AnomalyDetector(z_score_threshold=3.0)
        for i in range(15):
            anomaly = detector.check("s1", 20.0 + i * 0.1)
            # Early readings have no history yet
        assert anomaly is None  # last reading should be fine

    def test_spike_detection(self):
        detector = AnomalyDetector(z_score_threshold=2.0)
        # Build history with variance so stdev > 0 and z-score can be computed
        for i in range(20):
            detector.check("s1", 20.0 + i * 0.5)
        # Now inject a spike well beyond the threshold
        anomaly = detector.check("s1", 200.0)
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.SPIKE

    def test_stuck_sensor(self):
        detector = AnomalyDetector()
        for _ in range(12):
            anomaly = detector.check("s2", 50.0)
        # After 6 identical values, stuck sensor should be detected
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.STUCK_SENSOR

    def test_check_disagreement_detected(self):
        detector = AnomalyDetector()
        readings = [
            SensorReading(source_id="s1", value=10.0, quality=ReadingQuality.GOOD),
            SensorReading(source_id="s2", value=50.0, quality=ReadingQuality.GOOD),
        ]
        anomaly = detector.check_disagreement(readings, threshold=0.5)
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.DISAGREEMENT

    def test_check_disagreement_ok(self):
        detector = AnomalyDetector()
        readings = [
            SensorReading(source_id="s1", value=10.0, quality=ReadingQuality.GOOD),
            SensorReading(source_id="s2", value=10.5, quality=ReadingQuality.GOOD),
        ]
        anomaly = detector.check_disagreement(readings, threshold=0.5)
        assert anomaly is None

    def test_non_numeric_value_no_error(self):
        detector = AnomalyDetector()
        anomaly = detector.check("s1", "ON")
        assert anomaly is None


# ---------------------------------------------------------------------------
# SpatialMap
# ---------------------------------------------------------------------------

class TestSpatialMap:

    def test_add_zone_and_locate(self):
        sm = SpatialMap()
        sm.add_zone("zone_A", {"x_min": 0, "x_max": 10, "y_min": 0, "y_max": 10, "z_min": 0, "z_max": 3})
        assert sm.locate(5, 5, 1) == "zone_A"

    def test_locate_outside(self):
        sm = SpatialMap()
        sm.add_zone("zone_A", {"x_min": 0, "x_max": 10, "y_min": 0, "y_max": 10, "z_min": 0, "z_max": 3})
        assert sm.locate(50, 50) is None

    def test_multiple_zones(self):
        sm = SpatialMap()
        sm.add_zone("zone_A", {"x_min": 0, "x_max": 10, "y_min": 0, "y_max": 10})
        sm.add_zone("zone_B", {"x_min": 11, "x_max": 20, "y_min": 0, "y_max": 10})
        assert sm.locate(5, 5) == "zone_A"
        assert sm.locate(15, 5) == "zone_B"


# ---------------------------------------------------------------------------
# EnvironmentalModel
# ---------------------------------------------------------------------------

class TestEnvironmentalModel:

    def test_update_and_get(self):
        em = EnvironmentalModel()
        em.update_zone("zone_1", {"temperature": 72.0, "humidity": 45.0})
        z = em.get_zone("zone_1")
        assert z["temperature"] == 72.0

    def test_missing_zone(self):
        em = EnvironmentalModel()
        assert em.get_zone("nonexistent") == {}


# ---------------------------------------------------------------------------
# Pre-built profiles
# ---------------------------------------------------------------------------

class TestPrebuiltProfiles:

    def test_vehicle_profile(self):
        pipe = VehicleFusionProfile.build("truck-1")
        assert pipe.pipeline_id == "vehicle-truck-1"
        assert len(pipe.sources) == 5
        assert pipe.strategy == FusionStrategy.KALMAN_FILTER

    def test_building_profile(self):
        pipe = BuildingFusionProfile.build("bldg-A")
        assert pipe.pipeline_id == "building-bldg-A"
        assert len(pipe.sources) == 5
        assert pipe.strategy == FusionStrategy.WEIGHTED_AVERAGE

    def test_factory_profile(self):
        pipe = FactoryFusionProfile.build("factory-1")
        assert pipe.pipeline_id == "factory-factory-1"
        assert len(pipe.sources) == 4
