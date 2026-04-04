# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Test Suite: Digital Twin Simulation Engine — DTE-001

Comprehensive tests for the digital_twin_engine module:
  - Data model serialisation (SensorReading, FailurePrediction, ScenarioDefinition)
  - AnomalyDetector (z-score, windowing, edge cases)
  - DigitalTwin lifecycle (sensor registration, ingestion, prediction, scenarios)
  - TwinRegistry fleet management
  - Thread safety under concurrent access
  - Wingman pair validation gate
  - Causality Sandbox gating simulation

Tests use the storyline-actuals record() pattern for cause/effect/lesson tracking.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import datetime
import math
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from digital_twin_engine import (
    AnomalyDetector,
    DigitalTwin,
    FailurePrediction,
    ScenarioDefinition,
    ScenarioOutcome,
    ScenarioResult,
    SensorReading,
    SeverityLevel,
    TwinRegistry,
    TwinStatus,
)


# ---------------------------------------------------------------------------
# Record infrastructure (storyline-actuals pattern)
# ---------------------------------------------------------------------------

@dataclass
class DTERecord:
    """One DTE check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


_records: List[DTERecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    """Record a check and return whether expected == actual."""
    passed = expected == actual
    _records.append(DTERecord(
        check_id=check_id,
        description=description,
        expected=expected,
        actual=actual,
        passed=passed,
        cause=cause,
        effect=effect,
        lesson=lesson,
    ))
    return passed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def detector() -> AnomalyDetector:
    """Return a fresh anomaly detector."""
    return AnomalyDetector(window_size=50, threshold=3.0)


@pytest.fixture()
def twin() -> DigitalTwin:
    """Return a twin with a temperature and pressure sensor pre-configured."""
    t = DigitalTwin("tw-1", "Compressor-A")
    t.add_sensor("temp", unit="°C", warn_threshold=80.0, critical_threshold=95.0)
    t.add_sensor("pressure", unit="bar", warn_threshold=10.0, critical_threshold=15.0)
    return t


@pytest.fixture()
def registry() -> TwinRegistry:
    """Return a registry with two twins."""
    r = TwinRegistry()
    t1 = r.create_twin("tw-1", "Compressor-A")
    t1.add_sensor("temp", unit="°C", warn_threshold=80.0, critical_threshold=95.0)
    t2 = r.create_twin("tw-2", "Pump-B")
    t2.add_sensor("flow", unit="L/min", warn_threshold=50.0, critical_threshold=70.0)
    return r


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

class TestDataModels:
    """DTE-010–012: Data model serialisation."""

    def test_sensor_reading_to_dict(self):
        """DTE-010: SensorReading serialises correctly."""
        r = SensorReading("temp", 42.5, "°C")
        d = r.to_dict()
        assert record(
            "DTE-010", "SensorReading.to_dict has sensor_id",
            "temp", d["sensor_id"],
            cause="Serialisation contract",
            effect="Telemetry points are JSON-serialisable",
            lesson="Every data model needs a dict serialiser",
        )

    def test_failure_prediction_to_dict(self):
        """DTE-011: FailurePrediction serialises correctly."""
        fp = FailurePrediction("fp-1", "tw-1", "temp", "high", 0.85, "Too hot")
        d = fp.to_dict()
        assert record(
            "DTE-011", "FailurePrediction.to_dict has twin_id",
            "tw-1", d["twin_id"],
            cause="Serialisation contract",
            effect="Predictions are JSON-serialisable",
            lesson="Failure predictions must be machine-readable",
        )

    def test_scenario_result_to_dict(self):
        """DTE-012: ScenarioResult serialises correctly."""
        sr = ScenarioResult("sr-1", "sc-1", "tw-1", outcome="pass")
        d = sr.to_dict()
        assert record(
            "DTE-012", "ScenarioResult.to_dict has outcome",
            "pass", d["outcome"],
            cause="Serialisation contract",
            effect="Scenario results are JSON-serialisable",
            lesson="All results must be exportable for dashboards",
        )


# ============================================================================
# ANOMALY DETECTOR TESTS
# ============================================================================

class TestAnomalyDetector:
    """DTE-020–024: Z-score anomaly detection."""

    def test_not_enough_data(self, detector: AnomalyDetector):
        """DTE-020: With < 2 readings, nothing is anomalous."""
        detector.ingest(10.0)
        is_anom, z = detector.check(100.0)
        assert record(
            "DTE-020", "Insufficient data → not anomalous",
            False, is_anom,
            cause="Only 1 reading in window",
            effect="Cannot compute z-score",
            lesson="Need a baseline before flagging anomalies",
        )

    def test_normal_reading(self, detector: AnomalyDetector):
        """DTE-021: A reading within normal range is not anomalous."""
        for v in [50.0, 51.0, 49.0, 50.5, 49.5]:
            detector.ingest(v)
        is_anom, z = detector.check(50.2)
        assert record(
            "DTE-021", "Normal reading is not flagged",
            False, is_anom,
            cause="Value close to mean",
            effect="No anomaly",
            lesson="z-score must exceed threshold to flag",
        )

    def test_anomalous_reading(self, detector: AnomalyDetector):
        """DTE-022: An extreme reading is flagged as anomalous."""
        for v in [50.0] * 30:
            detector.ingest(v)
        # Inject slight variance to avoid zero std
        detector.ingest(50.1)
        detector.ingest(49.9)
        is_anom, z = detector.check(999.0)
        assert record(
            "DTE-022", "Extreme value is flagged",
            True, is_anom,
            cause="Value far from mean",
            effect="Anomaly detected",
            lesson="Statistical outliers indicate potential failures",
        )

    def test_mean_and_std(self, detector: AnomalyDetector):
        """DTE-023: Mean and std are computed correctly."""
        for v in [10.0, 20.0, 30.0]:
            detector.ingest(v)
        assert record(
            "DTE-023", "Mean of [10,20,30] is 20.0",
            True, abs(detector.mean - 20.0) < 1e-6,
            cause="Simple arithmetic mean",
            effect="Correct baseline",
            lesson="Verify statistical primitives",
        )

    def test_window_bounded(self):
        """DTE-024: Window doesn't grow beyond max size."""
        d = AnomalyDetector(window_size=5, threshold=3.0)
        for i in range(20):
            d.ingest(float(i))
        assert record(
            "DTE-024", "Window bounded to 5",
            5, d.count,
            cause="window_size=5, 20 readings ingested",
            effect="Only most recent 5 kept",
            lesson="Bounded windows prevent memory leaks",
        )


# ============================================================================
# DIGITAL TWIN TESTS
# ============================================================================

class TestDigitalTwinSensors:
    """DTE-030–032: Sensor management."""

    def test_add_sensor(self, twin: DigitalTwin):
        """DTE-030: Sensors can be registered."""
        sensors = twin.list_sensors()
        assert record(
            "DTE-030", "Twin has 2 sensors",
            2, len(sensors),
            cause="Two add_sensor calls",
            effect="Both registered",
            lesson="Sensors are the twin's input channels",
        )

    def test_ingest_and_get_latest(self, twin: DigitalTwin):
        """DTE-031: Ingested reading is retrievable."""
        twin.ingest(SensorReading("temp", 72.5))
        assert record(
            "DTE-031", "Latest temp is 72.5",
            72.5, twin.get_latest("temp"),
            cause="One reading ingested",
            effect="Retrievable via get_latest",
            lesson="Latest values drive real-time status",
        )

    def test_ingest_unknown_sensor_ignored(self, twin: DigitalTwin):
        """DTE-032: Reading for unregistered sensor is silently ignored."""
        twin.ingest(SensorReading("unknown_sensor", 99.0))
        assert record(
            "DTE-032", "Unknown sensor reading ignored",
            None, twin.get_latest("unknown_sensor"),
            cause="Sensor not registered",
            effect="No crash, value not stored",
            lesson="Gracefully ignore unexpected inputs",
        )


class TestDigitalTwinPredictions:
    """DTE-040–044: Failure prediction."""

    def test_no_predictions_when_normal(self, twin: DigitalTwin):
        """DTE-040: Normal readings produce no predictions."""
        for v in range(20, 40):
            twin.ingest(SensorReading("temp", float(v)))
        preds = twin.predict_failures()
        assert record(
            "DTE-040", "No predictions for normal range",
            0, len(preds),
            cause="All temp readings 20-39°C, well below warn=80",
            effect="No failure predicted",
            lesson="Low false-positive rate is critical",
        )

    def test_warn_threshold_prediction(self, twin: DigitalTwin):
        """DTE-041: Value at warning threshold generates a prediction."""
        for v in [50.0] * 10:
            twin.ingest(SensorReading("temp", v))
        twin.ingest(SensorReading("temp", 85.0))
        preds = twin.predict_failures()
        temp_preds = [p for p in preds if p.sensor_id == "temp"]
        assert record(
            "DTE-041", "Warning threshold triggers prediction",
            True, len(temp_preds) >= 1,
            cause="temp=85 > warn=80",
            effect="HIGH severity prediction",
            lesson="Graduated thresholds provide early warning",
        )

    def test_critical_threshold_prediction(self, twin: DigitalTwin):
        """DTE-042: Value at critical threshold generates CRITICAL prediction."""
        for v in [50.0] * 10:
            twin.ingest(SensorReading("temp", v))
        twin.ingest(SensorReading("temp", 100.0))
        preds = twin.predict_failures()
        critical = [p for p in preds if p.severity == SeverityLevel.CRITICAL.value]
        assert record(
            "DTE-042", "Critical threshold → CRITICAL severity",
            True, len(critical) >= 1,
            cause="temp=100 > crit=95",
            effect="CRITICAL failure predicted",
            lesson="Critical alerts demand immediate action",
        )

    def test_status_updates_on_predictions(self, twin: DigitalTwin):
        """DTE-043: Twin status reflects worst prediction."""
        for v in [50.0] * 10:
            twin.ingest(SensorReading("temp", v))
        twin.ingest(SensorReading("temp", 100.0))
        twin.predict_failures()
        assert record(
            "DTE-043", "Twin status is FAILED after critical prediction",
            TwinStatus.FAILED.value, twin.status,
            cause="Critical prediction generated",
            effect="Status updated to FAILED",
            lesson="Twin status is a derived property of predictions",
        )

    def test_to_dict(self, twin: DigitalTwin):
        """DTE-044: Twin serialises to dict."""
        d = twin.to_dict()
        assert record(
            "DTE-044", "to_dict has twin_id",
            "tw-1", d["twin_id"],
            cause="Serialisation contract",
            effect="Twin state is exportable",
            lesson="Status dashboards need serialisable state",
        )


class TestDigitalTwinScenarios:
    """DTE-050–053: What-if scenario simulation."""

    def test_scenario_pass(self, twin: DigitalTwin):
        """DTE-050: Scenario with normal values passes."""
        # Use varied baseline so std > 0 and z-score works properly
        for v in [48.0, 49.0, 50.0, 51.0, 52.0, 50.0, 49.5, 50.5, 51.5, 48.5]:
            twin.ingest(SensorReading("temp", v))
        scenario = ScenarioDefinition("sc-1", "Normal load", sensor_overrides={"temp": 51.0})
        result = twin.run_scenario(scenario)
        assert record(
            "DTE-050", "Normal scenario passes",
            ScenarioOutcome.PASS.value, result.outcome,
            cause="Override temp=51 within normal range, well below warn=80",
            effect="Scenario outcome is PASS",
            lesson="Scenarios validate safe operating conditions",
        )

    def test_scenario_fail(self, twin: DigitalTwin):
        """DTE-051: Scenario with critical values fails."""
        for v in [50.0] * 10:
            twin.ingest(SensorReading("temp", v))
        scenario = ScenarioDefinition("sc-2", "Overload", sensor_overrides={"temp": 100.0})
        result = twin.run_scenario(scenario)
        assert record(
            "DTE-051", "Critical scenario fails",
            ScenarioOutcome.FAIL.value, result.outcome,
            cause="Override temp=100 > crit=95",
            effect="Scenario outcome is FAIL",
            lesson="Scenario testing prevents real-world failures",
        )

    def test_scenario_preserves_state(self, twin: DigitalTwin):
        """DTE-052: Scenario does not modify actual twin state."""
        twin.ingest(SensorReading("temp", 50.0))
        scenario = ScenarioDefinition("sc-3", "Test", sensor_overrides={"temp": 200.0})
        twin.run_scenario(scenario)
        assert record(
            "DTE-052", "Latest temp unchanged after scenario",
            50.0, twin.get_latest("temp"),
            cause="Scenario uses temporary overrides",
            effect="Real state preserved",
            lesson="Simulation must never corrupt production state",
        )

    def test_scenario_result_has_duration(self, twin: DigitalTwin):
        """DTE-053: ScenarioResult includes duration_ms."""
        for v in [50.0] * 5:
            twin.ingest(SensorReading("temp", v))
        scenario = ScenarioDefinition("sc-4", "Quick", sensor_overrides={"temp": 55.0})
        result = twin.run_scenario(scenario)
        assert record(
            "DTE-053", "duration_ms is non-negative",
            True, result.duration_ms >= 0,
            cause="Timing is always tracked",
            effect="Duration measurable",
            lesson="Track latency for every operation",
        )


# ============================================================================
# TWIN REGISTRY TESTS
# ============================================================================

class TestTwinRegistry:
    """DTE-060–064: Fleet management."""

    def test_create_and_list(self, registry: TwinRegistry):
        """DTE-060: Registry lists all created twins."""
        assert record(
            "DTE-060", "Registry has 2 twins",
            2, len(registry.list_twins()),
            cause="Two create_twin calls",
            effect="Both listed",
            lesson="Registry is the single source of truth for the fleet",
        )

    def test_get_twin(self, registry: TwinRegistry):
        """DTE-061: get_twin retrieves by ID."""
        twin = registry.get_twin("tw-1")
        assert record(
            "DTE-061", "Retrieved twin has correct name",
            "Compressor-A", twin.name if twin else "",
            cause="Twin exists in registry",
            effect="Retrieved successfully",
            lesson="ID-based lookup must be O(1)",
        )

    def test_remove_twin(self, registry: TwinRegistry):
        """DTE-062: remove_twin removes the twin."""
        removed = registry.remove_twin("tw-1")
        assert record(
            "DTE-062", "remove_twin returns True",
            True, removed,
            cause="Twin exists",
            effect="Twin removed",
            lesson="Removal must clean up all references",
        )

    def test_predict_all_failures(self, registry: TwinRegistry):
        """DTE-063: predict_all_failures aggregates across fleet."""
        # Inject normal readings — no failures expected
        tw1 = registry.get_twin("tw-1")
        for v in [50.0] * 10:
            tw1.ingest(SensorReading("temp", v))
        preds = registry.predict_all_failures()
        assert record(
            "DTE-063", "No failures in healthy fleet",
            0, len(preds),
            cause="All readings normal",
            effect="Zero predictions",
            lesson="Fleet-wide prediction enables proactive maintenance",
        )

    def test_get_status(self, registry: TwinRegistry):
        """DTE-064: get_status returns structured summary."""
        status = registry.get_status()
        keys_ok = all(k in status for k in ("total_twins", "active", "degraded", "failed"))
        assert record(
            "DTE-064", "Status has expected keys",
            True, keys_ok,
            cause="get_status contract",
            effect="Machine-readable fleet summary",
            lesson="Always expose operational stats",
        )


# ============================================================================
# THREAD SAFETY
# ============================================================================

class TestThreadSafety:
    """DTE-070: Concurrent access."""

    def test_concurrent_ingest(self):
        """DTE-070: Concurrent sensor ingestion doesn't corrupt state."""
        twin = DigitalTwin("tw-thread", "ThreadTest")
        twin.add_sensor("temp", unit="°C", warn_threshold=80.0, critical_threshold=95.0)
        barrier = threading.Barrier(5)

        def worker(start: int) -> None:
            barrier.wait()
            for v in range(start, start + 20):
                twin.ingest(SensorReading("temp", float(v)))

        threads = [threading.Thread(target=worker, args=(i * 20,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Should have some latest value, no crashes
        latest = twin.get_latest("temp")
        assert record(
            "DTE-070", "Concurrent ingest produces a latest value",
            True, latest is not None,
            cause="5 threads × 20 readings",
            effect="Latest reading present, no corruption",
            lesson="Lock-protected state handles concurrent writes",
        )


# ============================================================================
# WINGMAN PAIR VALIDATION GATE
# ============================================================================

class TestWingmanGate:
    """DTE-080: Wingman pair validation for scenario results."""

    def test_wingman_validates_scenario(self, twin: DigitalTwin):
        """DTE-080: Wingman protocol validates a scenario result."""
        from wingman_protocol import (
            ExecutionRunbook,
            ValidationRule,
            ValidationSeverity,
            WingmanProtocol,
        )

        for v in [50.0] * 10:
            twin.ingest(SensorReading("temp", v))
        scenario = ScenarioDefinition("sc-w1", "Load test", sensor_overrides={"temp": 55.0})
        result = twin.run_scenario(scenario)

        protocol = WingmanProtocol()
        runbook = ExecutionRunbook(
            runbook_id="rb-dt-v1",
            name="Scenario Validator",
            domain="digital_twin",
            validation_rules=[
                ValidationRule(
                    "r-001", "Must produce output",
                    "check_has_output", ValidationSeverity.BLOCK,
                ),
                ValidationRule(
                    "r-002", "No PII in output",
                    "check_no_pii", ValidationSeverity.WARN,
                ),
            ],
        )
        protocol.register_runbook(runbook)
        pair = protocol.create_pair(
            subject="digital-twin-scenario",
            executor_id="twin-engine",
            validator_id="scenario-integrity-checker",
            runbook_id="rb-dt-v1",
        )

        output = {"result": result.to_dict(), "confidence": 0.90}
        validation = protocol.validate_output(pair.pair_id, output)

        assert record(
            "DTE-080", "Wingman approves scenario result",
            True, validation["approved"],
            cause="Scenario result passes runbook checks",
            effect="Scenario approved by wingman validator",
            lesson="Gate all scenario commits through Wingman pairs",
        )


# ============================================================================
# CAUSALITY SANDBOX GATING
# ============================================================================

class TestCausalitySandboxGate:
    """DTE-090: Causality Sandbox simulates scenario before committing."""

    def test_sandbox_simulates_scenario(self):
        """DTE-090: CausalitySandboxEngine runs a cycle for scenario validation."""
        from causality_sandbox import CausalitySandboxEngine

        class _ScenarioGap:
            gap_id = "gap-dt-scenario-001"
            category = "digital_twin"
            severity = "medium"
            description = "Proposed operating parameter change needs simulation"

        class _FakeLoop:
            config = {"state": "nominal"}
            metrics = {"uptime": 99.9}
            def get_state(self):
                return {"healthy": True}

        engine = CausalitySandboxEngine(
            self_fix_loop_factory=lambda: _FakeLoop(),
        )

        report = engine.run_sandbox_cycle([_ScenarioGap()], _FakeLoop())

        assert record(
            "DTE-090", "Sandbox cycle completes for scenario gap",
            True, report.gaps_analyzed >= 1,
            cause="One scenario gap submitted",
            effect="Sandbox simulates candidate actions",
            lesson="Never apply operating changes without sandbox validation",
        )


# ============================================================================
# SUMMARY
# ============================================================================

@pytest.fixture(autouse=True, scope="session")
def print_summary():
    """Print a summary at the end of the session."""
    yield
    total = len(_records)
    passed = sum(1 for r in _records if r.passed)
    failed = total - passed
    print(f"\n{'=' * 70}")
    print(f" Digital Twin Simulation Engine: {passed}/{total} passed, {failed} failed")
    for r in _records:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} {r.check_id}: {r.description}")
    print(f"{'=' * 70}")
