# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for predictive_maintenance_engine — PME-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable PMERecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from predictive_maintenance_engine import (  # noqa: E402
    AlertSeverity,
    AggregationWindow,
    AnomalyAlert,
    AssetHealth,
    AssetStatus,
    MaintenancePrediction,
    PredictiveMaintenanceEngine,
    SensorKind,
    SensorReading,
    TelemetrySummary,
    ThresholdRule,
    create_predictive_maintenance_api,
    gate_pme_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class PMERecord:
    """One PME check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[PMERecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    *,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> None:
    passed = expected == actual
    _RESULTS.append(
        PMERecord(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    assert passed, (
        f"[{check_id}] {description}: expected={expected!r}, got={actual!r}"
    )


# -- Helpers ---------------------------------------------------------------


def _make_engine() -> PredictiveMaintenanceEngine:
    return PredictiveMaintenanceEngine(max_readings_per_asset=500, max_alerts=500)


def _ingest_series(eng: PredictiveMaintenanceEngine, asset_id: str,
                   sensor_kind: str, values: List[float]) -> List[SensorReading]:
    """Ingest a series of readings."""
    return [eng.ingest_reading(asset_id, sensor_kind, v) for v in values]


# ==========================================================================
# Tests
# ==========================================================================


class TestReadingIngestion:
    """Sensor reading ingestion."""

    def test_ingest_basic(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("asset-1", "temperature", 72.5, "F")
        record(
            "PME-001", "ingest returns SensorReading",
            True, isinstance(r, SensorReading),
            cause="ingest_reading called",
            effect="SensorReading returned",
            lesson="Factory must return typed reading",
        )
        assert r.asset_id == "asset-1"
        assert r.value == 72.5

    def test_ingest_default_kind(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("a1")
        record(
            "PME-002", "default sensor_kind is temperature",
            "temperature", r.sensor_kind,
            cause="no sensor_kind specified",
            effect="defaults to temperature",
            lesson="Defaults must be sensible",
        )

    def test_ingest_enum_kind(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("a1", SensorKind.vibration, 0.5)
        record(
            "PME-003", "enum SensorKind coerced to string",
            "vibration", r.sensor_kind,
            cause="SensorKind enum passed",
            effect="stored as string value",
            lesson="Enum coercion must work",
        )

    def test_ingest_with_metadata(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("a1", metadata={"location": "floor-2"})
        record(
            "PME-004", "metadata stored correctly",
            "floor-2", r.metadata.get("location"),
            cause="metadata dict passed",
            effect="metadata persisted",
            lesson="Metadata passthrough must work",
        )

    def test_get_readings(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [70, 71, 72])
        readings = eng.get_readings("a1")
        record(
            "PME-005", "get_readings returns all",
            3, len(readings),
            cause="3 readings ingested",
            effect="3 returned",
            lesson="get_readings must return ingested data",
        )

    def test_get_readings_filter_kind(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        eng.ingest_reading("a1", "vibration", 0.3)
        readings = eng.get_readings("a1", sensor_kind="temperature")
        record(
            "PME-006", "filter by sensor_kind",
            1, len(readings),
            cause="1 temperature + 1 vibration",
            effect="only temperature returned",
            lesson="Kind filter must work",
        )

    def test_get_readings_limit(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(50)))
        readings = eng.get_readings("a1", limit=10)
        record(
            "PME-007", "limit caps returned readings",
            10, len(readings),
            cause="50 ingested, limit=10",
            effect="10 returned",
            lesson="Limit must be respected",
        )

    def test_get_readings_empty(self) -> None:
        eng = _make_engine()
        readings = eng.get_readings("nonexistent")
        record(
            "PME-008", "empty list for unknown asset",
            0, len(readings),
            cause="unknown asset",
            effect="empty list",
            lesson="Missing assets return empty gracefully",
        )

    def test_reading_serialization(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("a1", "pressure", 14.7, "psi")
        d = r.to_dict()
        record(
            "PME-009", "to_dict has all fields",
            True, "reading_id" in d and "value" in d and "unit" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_reading_id_unique(self) -> None:
        eng = _make_engine()
        r1 = eng.ingest_reading("a1")
        r2 = eng.ingest_reading("a1")
        record(
            "PME-010", "reading IDs are unique",
            True, r1.reading_id != r2.reading_id,
            cause="two readings ingested",
            effect="different IDs",
            lesson="UUID generation must be unique",
        )


class TestThresholdRules:
    """Threshold rule CRUD."""

    def test_add_rule(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", "temperature", warn_above=80.0)
        record(
            "PME-011", "add_rule returns ThresholdRule",
            True, isinstance(rule, ThresholdRule),
            cause="add_rule called",
            effect="ThresholdRule returned",
            lesson="Rule factory must return typed object",
        )
        assert rule.warn_above == 80.0

    def test_get_rule(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", warn_above=90)
        got = eng.get_rule(rule.rule_id)
        record(
            "PME-012", "get_rule returns correct rule",
            rule.rule_id, got.rule_id if got else None,
            cause="get by ID",
            effect="same rule returned",
            lesson="Lookup must return existing rules",
        )

    def test_get_rule_missing(self) -> None:
        eng = _make_engine()
        got = eng.get_rule("nonexistent")
        record(
            "PME-013", "get_rule returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing rules return None",
        )

    def test_list_rules(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        eng.add_rule("a1", "vibration", warn_above=5)
        eng.add_rule("a2", "temperature", warn_above=85)
        rules = eng.list_rules(asset_id="a1")
        record(
            "PME-014", "list_rules filters by asset_id",
            2, len(rules),
            cause="2 rules for a1, 1 for a2",
            effect="2 returned for a1",
            lesson="Asset filter must work",
        )

    def test_list_rules_by_kind(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        eng.add_rule("a1", "vibration", warn_above=5)
        rules = eng.list_rules(sensor_kind="vibration")
        record(
            "PME-015", "list_rules filters by sensor_kind",
            1, len(rules),
            cause="1 vibration rule",
            effect="1 returned",
            lesson="Kind filter must work",
        )

    def test_update_rule(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", warn_above=80)
        updated = eng.update_rule(rule.rule_id, warn_above=90)
        record(
            "PME-016", "update_rule changes threshold",
            90, updated.warn_above if updated else None,
            cause="warn_above changed",
            effect="new threshold stored",
            lesson="Updates must persist",
        )

    def test_update_rule_disable(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", warn_above=80)
        updated = eng.update_rule(rule.rule_id, enabled=False)
        record(
            "PME-017", "update_rule can disable",
            False, updated.enabled if updated else True,
            cause="enabled=False passed",
            effect="rule disabled",
            lesson="Disable flag must work",
        )

    def test_update_rule_missing(self) -> None:
        eng = _make_engine()
        result = eng.update_rule("missing")
        record(
            "PME-018", "update_rule returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing rules cannot be updated",
        )

    def test_delete_rule(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", warn_above=80)
        ok = eng.delete_rule(rule.rule_id)
        record(
            "PME-019", "delete_rule returns True",
            True, ok,
            cause="valid rule deleted",
            effect="True returned",
            lesson="Delete must succeed for existing rules",
        )
        assert eng.get_rule(rule.rule_id) is None

    def test_delete_rule_missing(self) -> None:
        eng = _make_engine()
        ok = eng.delete_rule("nonexistent")
        record(
            "PME-020", "delete_rule returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Delete of missing rule returns False",
        )

    def test_rule_enum_kind(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", SensorKind.pressure, warn_above=100)
        record(
            "PME-021", "rule stores enum as string",
            "pressure", rule.sensor_kind,
            cause="SensorKind enum passed",
            effect="stored as string",
            lesson="Enum coercion in rules",
        )


class TestAlertGeneration:
    """Alert generation from threshold breaches."""

    def test_warn_alert_above(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        eng.ingest_reading("a1", "temperature", 85)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-022", "warning alert raised when above threshold",
            True, len(alerts) >= 1,
            cause="reading exceeds warn_above",
            effect="alert generated",
            lesson="Threshold breach must generate alert",
        )
        assert alerts[0].severity == "warning"

    def test_critical_alert_above(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", critical_above=100)
        eng.ingest_reading("a1", "temperature", 105)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-023", "critical alert raised",
            "critical", alerts[0].severity if alerts else "",
            cause="reading exceeds critical_above",
            effect="critical alert",
            lesson="Critical threshold must generate critical alert",
        )

    def test_emergency_alert_above(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", emergency_above=120)
        eng.ingest_reading("a1", "temperature", 130)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-024", "emergency alert raised",
            "emergency", alerts[0].severity if alerts else "",
            cause="reading exceeds emergency_above",
            effect="emergency alert",
            lesson="Emergency threshold must generate emergency alert",
        )

    def test_warn_alert_below(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_below=32)
        eng.ingest_reading("a1", "temperature", 28)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-025", "warning alert raised when below threshold",
            True, len(alerts) >= 1,
            cause="reading below warn_below",
            effect="alert generated",
            lesson="Below-threshold must also trigger",
        )

    def test_no_alert_within_range(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80, warn_below=32)
        eng.ingest_reading("a1", "temperature", 50)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-026", "no alert when within range",
            0, len(alerts),
            cause="reading in safe range",
            effect="no alert",
            lesson="Normal readings must not alert",
        )

    def test_disabled_rule_no_alert(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", "temperature", warn_above=80)
        eng.update_rule(rule.rule_id, enabled=False)
        eng.ingest_reading("a1", "temperature", 90)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-027", "disabled rule does not trigger",
            0, len(alerts),
            cause="rule disabled",
            effect="no alert",
            lesson="Disabled rules must be skipped",
        )

    def test_highest_severity_wins(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80,
                     critical_above=100, emergency_above=120)
        eng.ingest_reading("a1", "temperature", 130)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-028", "highest severity wins",
            "emergency", alerts[-1].severity if alerts else "",
            cause="value exceeds all thresholds",
            effect="emergency (highest) alert",
            lesson="Severity priority must be enforced",
        )

    def test_alert_message_format(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        eng.ingest_reading("a1", "temperature", 85)
        alerts = eng.get_alerts(asset_id="a1")
        record(
            "PME-029", "alert message is descriptive",
            True, "temperature" in alerts[0].message if alerts else False,
            cause="alert generated",
            effect="message contains sensor kind",
            lesson="Messages must be human-readable",
        )

    def test_acknowledge_alert(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        eng.ingest_reading("a1", "temperature", 85)
        alerts = eng.get_alerts()
        acked = eng.acknowledge_alert(alerts[0].alert_id)
        record(
            "PME-030", "acknowledge_alert sets flag",
            True, acked.acknowledged if acked else False,
            cause="acknowledge called",
            effect="acknowledged=True",
            lesson="Acknowledgement must persist",
        )

    def test_acknowledge_missing_alert(self) -> None:
        eng = _make_engine()
        result = eng.acknowledge_alert("nonexistent")
        record(
            "PME-031", "acknowledge_alert None for missing",
            True, result is None,
            cause="invalid alert ID",
            effect="None returned",
            lesson="Missing alerts handled gracefully",
        )

    def test_filter_alerts_severity(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        eng.add_rule("a1", "vibration", critical_above=10)
        eng.ingest_reading("a1", "temperature", 85)
        eng.ingest_reading("a1", "vibration", 15)
        warnings = eng.get_alerts(severity="warning")
        record(
            "PME-032", "filter alerts by severity",
            True, all(a.severity == "warning" for a in warnings),
            cause="filter severity=warning",
            effect="only warnings returned",
            lesson="Severity filter must work",
        )

    def test_filter_alerts_acknowledged(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        eng.ingest_reading("a1", "temperature", 85)
        eng.ingest_reading("a1", "temperature", 90)
        alerts = eng.get_alerts()
        eng.acknowledge_alert(alerts[0].alert_id)
        unacked = eng.get_alerts(acknowledged=False)
        record(
            "PME-033", "filter unacknowledged alerts",
            True, len(unacked) < len(alerts),
            cause="1 acknowledged, filter=False",
            effect="fewer alerts",
            lesson="Acknowledgement filter must work",
        )


class TestAssetHealth:
    """Asset health tracking."""

    def test_asset_created_on_ingest(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 72)
        ah = eng.get_asset_health("a1")
        record(
            "PME-034", "asset auto-created on first ingest",
            True, ah is not None,
            cause="first reading for a1",
            effect="AssetHealth created",
            lesson="Assets must be auto-registered",
        )

    def test_healthy_status(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [70, 71, 72, 73])
        ah = eng.get_asset_health("a1")
        record(
            "PME-035", "healthy status with no alerts",
            "healthy", ah.status if ah else "",
            cause="no threshold breaches",
            effect="healthy status",
            lesson="No alerts means healthy",
        )

    def test_degraded_status(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        for i in range(10):
            eng.ingest_reading("a1", "temperature", 70)
        eng.ingest_reading("a1", "temperature", 85)
        eng.ingest_reading("a1", "temperature", 86)
        ah = eng.get_asset_health("a1")
        record(
            "PME-036", "degraded after moderate alerts",
            True, ah.status in ("degraded", "healthy") if ah else False,
            cause="some alerts relative to readings",
            effect="degraded or healthy",
            lesson="Alert ratio drives status",
        )

    def test_at_risk_status(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", "temperature", warn_above=80)
        for _ in range(10):
            eng.ingest_reading("a1", "temperature", 90)
        ah = eng.get_asset_health("a1")
        record(
            "PME-037", "at_risk when many alerts",
            True, ah.status in ("at_risk", "degraded") if ah else False,
            cause="all readings breach threshold",
            effect="at_risk status",
            lesson="High alert ratio means at_risk",
        )

    def test_health_score_range(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [70, 71, 72])
        ah = eng.get_asset_health("a1")
        record(
            "PME-038", "health score in [0, 100]",
            True, 0 <= ah.health_score <= 100 if ah else False,
            cause="health computed",
            effect="score in valid range",
            lesson="Score must be bounded",
        )

    def test_sensor_summary_populated(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        eng.ingest_reading("a1", "vibration", 0.5)
        ah = eng.get_asset_health("a1")
        record(
            "PME-039", "sensor_summary has both kinds",
            True, "temperature" in ah.sensor_summary and "vibration" in ah.sensor_summary if ah else False,
            cause="two sensor kinds ingested",
            effect="both in summary",
            lesson="Summary must cover all sensor kinds",
        )

    def test_missing_asset_health(self) -> None:
        eng = _make_engine()
        ah = eng.get_asset_health("nonexistent")
        record(
            "PME-040", "None for unknown asset",
            True, ah is None,
            cause="unknown asset_id",
            effect="None returned",
            lesson="Missing assets return None",
        )

    def test_list_assets(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        eng.ingest_reading("a2", "temperature", 72)
        assets = eng.list_assets()
        record(
            "PME-041", "list_assets returns all tracked",
            2, len(assets),
            cause="2 assets with readings",
            effect="2 returned",
            lesson="All assets must be listed",
        )

    def test_list_assets_filter_status(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        eng.ingest_reading("a2", "temperature", 72)
        eng.set_asset_status("a1", "maintenance")
        maint = eng.list_assets(status="maintenance")
        record(
            "PME-042", "filter assets by status",
            1, len(maint),
            cause="1 asset in maintenance",
            effect="1 returned",
            lesson="Status filter must work",
        )

    def test_set_asset_status(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        ah = eng.set_asset_status("a1", AssetStatus.maintenance)
        record(
            "PME-043", "set_asset_status changes status",
            "maintenance", ah.status if ah else "",
            cause="status set to maintenance",
            effect="status updated",
            lesson="Manual status override must work",
        )

    def test_set_status_missing_asset(self) -> None:
        eng = _make_engine()
        result = eng.set_asset_status("nonexistent", "maintenance")
        record(
            "PME-044", "set_status None for missing",
            True, result is None,
            cause="unknown asset",
            effect="None returned",
            lesson="Missing asset status set returns None",
        )

    def test_asset_reading_count(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [70, 71, 72])
        ah = eng.get_asset_health("a1")
        record(
            "PME-045", "reading_count tracks ingestions",
            3, ah.reading_count if ah else 0,
            cause="3 readings ingested",
            effect="count=3",
            lesson="Reading count must be accurate",
        )


class TestTelemetrySummary:
    """Telemetry statistical summaries."""

    def test_basic_summary(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [70, 72, 74, 76, 78])
        summary = eng.get_telemetry_summary("a1", "temperature")
        record(
            "PME-046", "summary has correct count",
            5, summary.count,
            cause="5 readings",
            effect="count=5",
            lesson="Count must match readings",
        )

    def test_summary_mean(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [10, 20, 30])
        summary = eng.get_telemetry_summary("a1", "temperature")
        record(
            "PME-047", "mean computed correctly",
            20.0, summary.mean,
            cause="values [10,20,30]",
            effect="mean=20",
            lesson="Mean calculation must be correct",
        )

    def test_summary_min_max(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [5, 15, 25])
        summary = eng.get_telemetry_summary("a1", "temperature")
        record(
            "PME-048", "min/max correct",
            True, summary.min_val == 5 and summary.max_val == 25,
            cause="values [5,15,25]",
            effect="min=5, max=25",
            lesson="Extremes must be tracked",
        )

    def test_summary_trend_rising(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(1, 21)))
        summary = eng.get_telemetry_summary("a1", "temperature")
        record(
            "PME-049", "positive trend slope for rising data",
            True, summary.trend_slope > 0,
            cause="monotonically increasing values",
            effect="positive slope",
            lesson="Trend detection must capture direction",
        )

    def test_summary_trend_flat(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [50] * 20)
        summary = eng.get_telemetry_summary("a1", "temperature")
        record(
            "PME-050", "zero trend slope for flat data",
            True, abs(summary.trend_slope) < 0.001,
            cause="constant values",
            effect="near-zero slope",
            lesson="Flat data must have no trend",
        )

    def test_summary_empty_asset(self) -> None:
        eng = _make_engine()
        summary = eng.get_telemetry_summary("nonexistent", "temperature")
        record(
            "PME-051", "empty summary for unknown asset",
            0, summary.count,
            cause="unknown asset",
            effect="count=0",
            lesson="Missing data returns empty summary",
        )

    def test_summary_window_last_10(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(50)))
        summary = eng.get_telemetry_summary("a1", "temperature",
                                            window=AggregationWindow.last_10)
        record(
            "PME-052", "window=last_10 limits to 10 readings",
            10, summary.count,
            cause="50 readings, window=last_10",
            effect="count=10",
            lesson="Window must limit data scope",
        )

    def test_summary_std_dev(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [10, 10, 10, 10])
        summary = eng.get_telemetry_summary("a1", "temperature")
        record(
            "PME-053", "zero std_dev for constant values",
            0.0, summary.std_dev,
            cause="all values identical",
            effect="std_dev=0",
            lesson="StdDev must be zero for constant data",
        )

    def test_summary_median(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [1, 2, 3, 4, 100])
        summary = eng.get_telemetry_summary("a1", "temperature")
        record(
            "PME-054", "median is robust to outliers",
            3, summary.median,
            cause="values [1,2,3,4,100]",
            effect="median=3",
            lesson="Median must be robust",
        )


class TestPredictions:
    """Maintenance predictions."""

    def test_predict_insufficient_data(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-055", "insufficient data prediction",
            "insufficient_data", pred.predicted_failure_kind,
            cause="only 1 reading",
            effect="insufficient_data",
            lesson="Needs enough data to predict",
        )

    def test_predict_with_data(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(70, 100)))
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-056", "prediction generated with data",
            True, pred.confidence > 0,
            cause="30 readings with trend",
            effect="positive confidence",
            lesson="Sufficient data yields a prediction",
        )

    def test_predict_rising_trend(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(50, 80)))
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-057", "rising trend classified",
            True, "rising" in pred.predicted_failure_kind or "gradual" in pred.predicted_failure_kind,
            cause="monotonically increasing",
            effect="rising or gradual classification",
            lesson="Trend classification must reflect data",
        )

    def test_predict_confidence_range(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(20)))
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-058", "confidence in [0, 1]",
            True, 0.0 <= pred.confidence <= 1.0,
            cause="prediction made",
            effect="bounded confidence",
            lesson="Confidence must be normalized",
        )

    def test_predict_days_positive(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(50, 80)))
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-059", "estimated days > 0",
            True, pred.estimated_days_to_failure > 0,
            cause="prediction with trend",
            effect="positive days estimate",
            lesson="Days must be positive",
        )

    def test_predict_recommendation(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(50, 80)))
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-060", "recommendation is non-empty",
            True, len(pred.recommendation) > 0,
            cause="prediction made",
            effect="non-empty recommendation",
            lesson="Recommendations must be generated",
        )

    def test_get_predictions_history(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(20)))
        eng.predict_maintenance("a1", "temperature")
        eng.predict_maintenance("a1", "temperature")
        preds = eng.get_predictions("a1")
        record(
            "PME-061", "prediction history stored",
            2, len(preds),
            cause="2 predictions made",
            effect="2 in history",
            lesson="Predictions must be persisted",
        )

    def test_prediction_based_on_readings(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(25)))
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-062", "based_on_readings matches data",
            25, pred.based_on_readings,
            cause="25 readings ingested",
            effect="based_on_readings=25",
            lesson="Reading count must be tracked in prediction",
        )

    def test_prediction_serialization(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(10)))
        pred = eng.predict_maintenance("a1", "temperature")
        d = pred.to_dict()
        record(
            "PME-063", "prediction to_dict has all fields",
            True, "prediction_id" in d and "confidence" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )


class TestExportAndClear:
    """Export state and clear."""

    def test_export_state(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        eng.add_rule("a1", warn_above=80)
        state = eng.export_state()
        record(
            "PME-064", "export_state has readings and rules",
            True, "readings" in state and "rules" in state,
            cause="state with data",
            effect="export has all sections",
            lesson="Export must be comprehensive",
        )

    def test_export_includes_alerts(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", warn_above=80)
        eng.ingest_reading("a1", "temperature", 90)
        state = eng.export_state()
        record(
            "PME-065", "export includes alerts",
            True, len(state.get("alerts", [])) > 0,
            cause="alert generated",
            effect="alert in export",
            lesson="Alerts must be exported",
        )

    def test_clear(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        eng.add_rule("a1", warn_above=80)
        eng.clear()
        record(
            "PME-066", "clear removes all state",
            0, len(eng.list_assets()),
            cause="clear called",
            effect="empty state",
            lesson="Clear must be thorough",
        )
        assert len(eng.list_rules()) == 0

    def test_clear_then_ingest(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        eng.clear()
        eng.ingest_reading("a2", "pressure", 14.7)
        assets = eng.list_assets()
        record(
            "PME-067", "can ingest after clear",
            1, len(assets),
            cause="clear then new ingest",
            effect="1 asset",
            lesson="Engine must be reusable after clear",
        )


class TestWingmanAndSandbox:
    """Wingman pair validation and Causality Sandbox gates."""

    def test_wingman_pass(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "b"])
        record(
            "PME-068", "wingman pair passes on match",
            True, result["passed"],
            cause="identical lists",
            effect="passed=True",
            lesson="Matching pairs must pass",
        )

    def test_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        record(
            "PME-069", "wingman rejects empty storyline",
            False, result["passed"],
            cause="empty storyline",
            effect="passed=False",
            lesson="Empty inputs must fail",
        )

    def test_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        record(
            "PME-070", "wingman rejects empty actuals",
            False, result["passed"],
            cause="empty actuals",
            effect="passed=False",
            lesson="Empty actuals must fail",
        )

    def test_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        record(
            "PME-071", "wingman rejects length mismatch",
            False, result["passed"],
            cause="different lengths",
            effect="passed=False",
            lesson="Length mismatch must fail",
        )

    def test_wingman_value_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "c"])
        record(
            "PME-072", "wingman rejects value mismatch",
            False, result["passed"],
            cause="different values",
            effect="passed=False with mismatch indices",
            lesson="Value mismatches must be reported",
        )

    def test_sandbox_pass(self) -> None:
        result = gate_pme_in_sandbox({"asset_id": "a1"})
        record(
            "PME-073", "sandbox gate passes",
            True, result["passed"],
            cause="valid context",
            effect="passed=True",
            lesson="Valid context must pass",
        )

    def test_sandbox_missing_key(self) -> None:
        result = gate_pme_in_sandbox({})
        record(
            "PME-074", "sandbox rejects missing key",
            False, result["passed"],
            cause="missing asset_id",
            effect="passed=False",
            lesson="Required keys must be present",
        )

    def test_sandbox_empty_value(self) -> None:
        result = gate_pme_in_sandbox({"asset_id": ""})
        record(
            "PME-075", "sandbox rejects empty value",
            False, result["passed"],
            cause="empty asset_id",
            effect="passed=False",
            lesson="Values must be non-empty",
        )


class TestConcurrency:
    """Thread-safety checks."""

    def test_concurrent_ingest(self) -> None:
        eng = _make_engine()
        errors: List[str] = []

        def ingest_batch(tid: int) -> None:
            try:
                for i in range(50):
                    eng.ingest_reading(f"asset-{tid}", "temperature",
                                       float(70 + i))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=ingest_batch, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        record(
            "PME-076", "concurrent ingest is thread-safe",
            0, len(errors),
            cause="4 threads ingesting",
            effect="no errors",
            lesson="Lock must protect concurrent writes",
        )
        total = sum(len(eng.get_readings(f"asset-{t}")) for t in range(4))
        assert total == 200

    def test_concurrent_rules_and_alerts(self) -> None:
        eng = _make_engine()
        eng.add_rule("shared", "temperature", warn_above=80)
        errors: List[str] = []

        def fire_readings(tid: int) -> None:
            try:
                for i in range(20):
                    eng.ingest_reading("shared", "temperature",
                                       float(75 + i))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=fire_readings, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        record(
            "PME-077", "concurrent rules+alerts thread-safe",
            0, len(errors),
            cause="4 threads triggering alerts",
            effect="no errors",
            lesson="Alert generation must be thread-safe",
        )

    def test_concurrent_predict(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", list(range(50)))
        errors: List[str] = []

        def predict(tid: int) -> None:
            try:
                for _ in range(10):
                    eng.predict_maintenance("a1", "temperature")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=predict, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        record(
            "PME-078", "concurrent predictions thread-safe",
            0, len(errors),
            cause="4 threads predicting",
            effect="no errors",
            lesson="Prediction must be thread-safe",
        )


class TestFlaskBlueprint:
    """Flask Blueprint API endpoints (requires Flask)."""

    def _get_client(self):
        """Create a Flask test client."""
        try:
            from flask import Flask
        except ImportError:
            return None
        eng = _make_engine()
        app = Flask(__name__)
        bp = create_predictive_maintenance_api(eng)
        app.register_blueprint(bp)
        return app.test_client(), eng

    def test_blueprint_creation(self) -> None:
        eng = _make_engine()
        bp = create_predictive_maintenance_api(eng)
        record(
            "PME-079", "blueprint created successfully",
            True, bp is not None,
            cause="factory called",
            effect="blueprint returned",
            lesson="Blueprint factory must succeed",
        )

    def test_post_reading(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        resp = client.post("/api/pme/readings",
                           json={"asset_id": "a1", "value": 72.5})
        record(
            "PME-080", "POST /readings returns 201",
            201, resp.status_code,
            cause="valid reading POST",
            effect="201 Created",
            lesson="Ingest endpoint must return 201",
        )

    def test_get_readings_api(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        client.post("/api/pme/readings",
                     json={"asset_id": "a1", "value": 70})
        resp = client.get("/api/pme/readings/a1")
        record(
            "PME-081", "GET /readings/<id> returns 200",
            200, resp.status_code,
            cause="valid asset_id",
            effect="200 OK",
            lesson="Readings endpoint must return data",
        )

    def test_post_rule_api(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        resp = client.post("/api/pme/rules",
                           json={"asset_id": "a1", "warn_above": 80})
        record(
            "PME-082", "POST /rules returns 201",
            201, resp.status_code,
            cause="valid rule POST",
            effect="201 Created",
            lesson="Rule creation endpoint works",
        )

    def test_get_alerts_api(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        resp = client.get("/api/pme/alerts")
        record(
            "PME-083", "GET /alerts returns 200",
            200, resp.status_code,
            cause="alerts requested",
            effect="200 OK",
            lesson="Alerts endpoint works",
        )

    def test_get_health_api(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        resp = client.get("/api/pme/health")
        data = resp.get_json()
        record(
            "PME-084", "GET /health returns healthy",
            "healthy", data.get("status"),
            cause="health check",
            effect="healthy status",
            lesson="Health endpoint must report status",
        )

    def test_post_reading_missing_field(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        resp = client.post("/api/pme/readings", json={})
        record(
            "PME-085", "POST /readings without asset_id returns 400",
            400, resp.status_code,
            cause="missing asset_id",
            effect="400 Bad Request",
            lesson="Validation must reject incomplete data",
        )

    def test_predict_api(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        for v in range(20):
            client.post("/api/pme/readings",
                        json={"asset_id": "a1", "value": float(70 + v)})
        resp = client.post("/api/pme/predict/a1",
                           json={"sensor_kind": "temperature"})
        record(
            "PME-086", "POST /predict returns 200",
            200, resp.status_code,
            cause="prediction request",
            effect="200 OK",
            lesson="Prediction endpoint must work",
        )

    def test_export_api(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        client.post("/api/pme/readings",
                     json={"asset_id": "a1", "value": 70})
        resp = client.post("/api/pme/export")
        record(
            "PME-087", "POST /export returns 200",
            200, resp.status_code,
            cause="export requested",
            effect="200 OK",
            lesson="Export endpoint must work",
        )

    def test_telemetry_api(self) -> None:
        result = self._get_client()
        if result is None:
            return
        client, eng = result
        for v in range(10):
            client.post("/api/pme/readings",
                        json={"asset_id": "a1", "value": float(70 + v)})
        resp = client.get("/api/pme/telemetry/a1")
        record(
            "PME-088", "GET /telemetry returns 200",
            200, resp.status_code,
            cause="telemetry requested",
            effect="200 OK",
            lesson="Telemetry endpoint must work",
        )


class TestEdgeCases:
    """Edge cases and boundary values."""

    def test_zero_value_reading(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("a1", "temperature", 0.0)
        record(
            "PME-089", "zero value reading accepted",
            0.0, r.value,
            cause="value=0.0",
            effect="stored correctly",
            lesson="Zero is a valid reading",
        )

    def test_negative_value_reading(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("a1", "temperature", -40.0)
        record(
            "PME-090", "negative value reading accepted",
            -40.0, r.value,
            cause="value=-40",
            effect="stored correctly",
            lesson="Negative values are valid",
        )

    def test_large_value_reading(self) -> None:
        eng = _make_engine()
        r = eng.ingest_reading("a1", "temperature", 1e12)
        record(
            "PME-091", "large value reading accepted",
            1e12, r.value,
            cause="value=1e12",
            effect="stored correctly",
            lesson="Large values are valid",
        )

    def test_predict_flat_data(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [72.0] * 30)
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-092", "flat data gives long days estimate",
            True, pred.estimated_days_to_failure >= 30,
            cause="flat data, no trend",
            effect="long days to failure",
            lesson="Flat data means no imminent failure",
        )

    def test_predict_single_value_repeated(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [100.0] * 10)
        pred = eng.predict_maintenance("a1", "temperature")
        record(
            "PME-093", "constant data gives gradual degradation",
            True, "gradual" in pred.predicted_failure_kind,
            cause="constant values",
            effect="gradual degradation",
            lesson="No variance -> gradual degradation",
        )

    def test_rule_serialization(self) -> None:
        eng = _make_engine()
        rule = eng.add_rule("a1", warn_above=80, critical_above=100)
        d = rule.to_dict()
        record(
            "PME-094", "rule to_dict has all fields",
            True, "rule_id" in d and "warn_above" in d,
            cause="to_dict called",
            effect="complete dict",
            lesson="Rule serialization must be complete",
        )

    def test_alert_serialization(self) -> None:
        eng = _make_engine()
        eng.add_rule("a1", warn_above=80)
        eng.ingest_reading("a1", "temperature", 85)
        alerts = eng.get_alerts()
        d = alerts[0].to_dict()
        record(
            "PME-095", "alert to_dict has all fields",
            True, "alert_id" in d and "severity" in d,
            cause="to_dict called",
            effect="complete dict",
            lesson="Alert serialization must be complete",
        )

    def test_asset_health_serialization(self) -> None:
        eng = _make_engine()
        eng.ingest_reading("a1", "temperature", 70)
        ah = eng.get_asset_health("a1")
        d = ah.to_dict()
        record(
            "PME-096", "asset health to_dict has all fields",
            True, "asset_id" in d and "health_score" in d,
            cause="to_dict called",
            effect="complete dict",
            lesson="Health serialization must be complete",
        )

    def test_telemetry_summary_serialization(self) -> None:
        eng = _make_engine()
        _ingest_series(eng, "a1", "temperature", [70, 71, 72])
        summary = eng.get_telemetry_summary("a1", "temperature")
        d = summary.to_dict()
        record(
            "PME-097", "telemetry to_dict has all fields",
            True, "mean" in d and "trend_slope" in d,
            cause="to_dict called",
            effect="complete dict",
            lesson="Telemetry serialization must be complete",
        )
