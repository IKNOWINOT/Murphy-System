"""
Tests for SAF-004: AlertRulesEngine.

Validates rule management, evaluation logic, cooldown behavior,
severity filtering, persistence, and EventBackbone integration.

Design Label: TEST-027 / SAF-004
Owner: QA Team
"""

import os
import pytest


from alert_rules_engine import (
    AlertRulesEngine,
    AlertRule,
    AlertSeverity,
    Comparator,
    FiredAlert,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))

@pytest.fixture
def backbone():
    return EventBackbone()

@pytest.fixture
def engine():
    return AlertRulesEngine()

@pytest.fixture
def wired_engine(pm, backbone):
    return AlertRulesEngine(persistence_manager=pm, event_backbone=backbone)


class TestRuleManagement:
    def test_default_rules_loaded(self, engine):
        rules = engine.list_rules()
        assert len(rules) >= 5

    def test_add_rule(self, engine):
        rule = AlertRule("custom-1", "Custom", AlertSeverity.INFO,
                         "custom_metric", Comparator.GT, 50.0)
        engine.add_rule(rule)
        assert any(r["rule_id"] == "custom-1" for r in engine.list_rules())

    def test_remove_rule(self, engine):
        assert engine.remove_rule("rule-sys-down") is True
        assert engine.remove_rule("rule-sys-down") is False

    def test_enable_disable(self, engine):
        engine.disable_rule("rule-sys-down")
        rules = {r["rule_id"]: r for r in engine.list_rules()}
        assert rules["rule-sys-down"]["enabled"] is False
        engine.enable_rule("rule-sys-down")
        rules = {r["rule_id"]: r for r in engine.list_rules()}
        assert rules["rule-sys-down"]["enabled"] is True


class TestEvaluation:
    def test_no_metrics_no_alerts(self, engine):
        fired = engine.evaluate({})
        assert len(fired) == 0

    def test_critical_alert_fires(self, engine):
        fired = engine.evaluate({"uptime_pct": 95.0})
        critical = [a for a in fired if a.severity == AlertSeverity.CRITICAL]
        assert len(critical) >= 1

    def test_warning_alert_fires(self, engine):
        fired = engine.evaluate({"error_rate_pct": 5.0})
        warnings = [a for a in fired if a.severity == AlertSeverity.WARNING]
        assert len(warnings) >= 1

    def test_condition_not_met(self):
        engine = AlertRulesEngine(rules=[
            AlertRule("r1", "Test", AlertSeverity.INFO, "val", Comparator.GT, 100.0),
        ])
        fired = engine.evaluate({"val": 50.0})
        assert len(fired) == 0

    def test_all_comparators(self):
        for comp, val, thresh, expected in [
            (Comparator.GT, 10, 5, True),
            (Comparator.LT, 3, 5, True),
            (Comparator.GTE, 5, 5, True),
            (Comparator.LTE, 5, 5, True),
            (Comparator.EQ, 5, 5, True),
            (Comparator.GT, 5, 10, False),
        ]:
            engine = AlertRulesEngine(rules=[
                AlertRule("test", "T", AlertSeverity.INFO, "m", comp, thresh, cooldown_seconds=0),
            ])
            fired = engine.evaluate({"m": val})
            assert (len(fired) > 0) == expected, f"Failed for {comp.value} {val} vs {thresh}"

    def test_cooldown_prevents_duplicate(self, engine):
        engine.evaluate({"uptime_pct": 95.0})
        fired2 = engine.evaluate({"uptime_pct": 95.0})
        assert len(fired2) == 0  # cooldown active

    def test_disabled_rule_skipped(self, engine):
        engine.disable_rule("rule-sys-down")
        fired = engine.evaluate({"uptime_pct": 95.0})
        assert all(a.rule_id != "rule-sys-down" for a in fired)


class TestFiltering:
    def test_filter_by_severity(self, engine):
        engine.evaluate({"uptime_pct": 95.0, "error_rate_pct": 5.0})
        critical = engine.get_alerts(severity=AlertSeverity.CRITICAL)
        assert all(a["severity"] == "critical" for a in critical)

    def test_alert_to_dict(self, engine):
        fired = engine.evaluate({"uptime_pct": 95.0})
        assert len(fired) > 0
        d = fired[0].to_dict()
        assert "alert_id" in d
        assert "severity" in d


class TestPersistence:
    def test_alert_persisted(self, wired_engine, pm):
        fired = wired_engine.evaluate({"uptime_pct": 95.0})
        assert len(fired) > 0
        loaded = pm.load_document(fired[0].alert_id)
        assert loaded is not None


class TestEventBackbone:
    def test_alert_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: received.append(e))
        wired_engine.evaluate({"uptime_pct": 95.0})
        backbone.process_pending()
        assert len(received) >= 1


class TestStatus:
    def test_status(self, engine):
        s = engine.get_status()
        assert s["total_rules"] >= 5
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_engine):
        s = wired_engine.get_status()
        assert s["persistence_attached"] is True
