"""Tests for the Bot Telemetry Normalizer."""

import os

import pytest
from src.bot_telemetry_normalizer import (
    BotTelemetryNormalizer,
    NormalizationRule,
    TelemetryEvent,
)


@pytest.fixture
def normalizer():
    return BotTelemetryNormalizer()


# ------------------------------------------------------------------
# Rule registration
# ------------------------------------------------------------------

class TestRuleRegistration:
    def test_register_custom_rule(self, normalizer):
        rule = normalizer.register_rule(
            source_pattern="custom",
            source_event_type="my_event",
            murphy_event_type="murphy.custom.my_event",
            field_mappings={"foo": "payload.foo"},
            description="custom rule",
        )
        assert isinstance(rule, NormalizationRule)
        assert rule.murphy_event_type == "murphy.custom.my_event"

    def test_register_default_triage_rules(self, normalizer):
        rules = normalizer.register_default_triage_rules()
        assert len(rules) == 4
        types = {r.source_event_type for r in rules}
        assert "rollcall_complete" in types
        assert "candidate_selected" in types

    def test_register_default_rubix_rules(self, normalizer):
        rules = normalizer.register_default_rubix_rules()
        assert len(rules) == 5
        types = {r.source_event_type for r in rules}
        assert "evidence_check" in types
        assert "monte_carlo_complete" in types

    def test_duplicate_rule_ids_unique(self, normalizer):
        r1 = normalizer.register_rule("s", "e1", "m.e1")
        r2 = normalizer.register_rule("s", "e2", "m.e2")
        assert r1.rule_id != r2.rule_id


# ------------------------------------------------------------------
# Event normalization
# ------------------------------------------------------------------

class TestEventNormalization:
    def test_normalize_matching_event(self, normalizer):
        normalizer.register_rule(
            "src", "ping", "murphy.src.ping",
            field_mappings={"ts": "payload.ts"},
        )
        event = normalizer.normalize_event("src", "ping", {"ts": 123})
        assert event.normalized is True
        assert event.murphy_event_type == "murphy.src.ping"

    def test_normalize_unmatched_event(self, normalizer):
        event = normalizer.normalize_event("unknown", "nope", {"a": 1})
        assert event.normalized is False
        assert event.murphy_event_type is None

    def test_normalize_batch_mixed(self, normalizer):
        normalizer.register_rule("s", "ok", "murphy.s.ok")
        batch = [
            {"source": "s", "event_type": "ok", "payload": {}},
            {"source": "s", "event_type": "missing", "payload": {}},
        ]
        results = normalizer.normalize_batch(batch)
        assert len(results) == 2
        assert results[0].normalized is True
        assert results[1].normalized is False

    def test_normalized_event_has_murphy_fields(self, normalizer):
        normalizer.register_rule("x", "y", "murphy.x.y")
        event = normalizer.normalize_event("x", "y", {"val": 1})
        assert event.murphy_payload is not None
        mp = event.murphy_payload
        assert "event_id" in mp
        assert "murphy_event_type" in mp
        assert "timestamp" in mp
        assert "source_system" in mp
        assert "severity" in mp
        assert "category" in mp

    def test_field_mappings_applied(self, normalizer):
        normalizer.register_rule(
            "s", "e", "murphy.s.e",
            field_mappings={"alpha": "payload.alpha", "beta": "payload.beta"},
        )
        event = normalizer.normalize_event("s", "e", {"alpha": 42, "beta": "hello"})
        mapped = event.murphy_payload["payload"]
        assert mapped["alpha"] == 42
        assert mapped["beta"] == "hello"


# ------------------------------------------------------------------
# Default rules
# ------------------------------------------------------------------

class TestDefaultRules:
    def test_triage_rollcall_complete(self, normalizer):
        normalizer.register_default_triage_rules()
        event = normalizer.normalize_event(
            "triage", "rollcall_complete",
            {"participants": 5, "quorum_met": True, "duration_ms": 120},
        )
        assert event.normalized is True
        assert event.murphy_event_type == "murphy.triage.rollcall_complete"

    def test_triage_candidate_selected(self, normalizer):
        normalizer.register_default_triage_rules()
        event = normalizer.normalize_event(
            "triage", "candidate_selected",
            {"candidate_id": "c1", "score": 0.95, "reason": "best fit"},
        )
        assert event.normalized is True

    def test_rubix_evidence_check(self, normalizer):
        normalizer.register_default_rubix_rules()
        event = normalizer.normalize_event(
            "rubix", "evidence_check",
            {"evidence_id": "ev-1", "check_result": "pass", "confidence": 0.88},
        )
        assert event.normalized is True
        assert event.murphy_event_type == "murphy.rubix.evidence_check"

    def test_rubix_monte_carlo_complete(self, normalizer):
        normalizer.register_default_rubix_rules()
        event = normalizer.normalize_event(
            "rubix", "monte_carlo_complete",
            {"iterations": 1000, "mean": 0.5, "std_dev": 0.1, "p95": 0.72},
        )
        assert event.normalized is True
        mapped = event.murphy_payload["payload"]
        assert mapped["iterations"] == 1000


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------

class TestReporting:
    def test_normalization_report_structure(self, normalizer):
        normalizer.register_rule("s", "e", "murphy.s.e")
        normalizer.normalize_event("s", "e", {})
        report = normalizer.get_normalization_report()
        for key in ("total_events", "successful", "failed", "success_rate",
                     "fields_mapped", "fields_dropped", "warnings_count", "registered_rules"):
            assert key in report

    def test_success_rate_computation(self, normalizer):
        normalizer.register_rule("s", "ok", "murphy.s.ok")
        normalizer.normalize_event("s", "ok", {})
        normalizer.normalize_event("s", "bad", {})
        report = normalizer.get_normalization_report()
        assert report["success_rate"] == 0.5

    def test_unmapped_events_tracked(self, normalizer):
        normalizer.normalize_event("a", "b", {})
        normalizer.normalize_event("c", "d", {})
        unmapped = normalizer.get_unmapped_events()
        assert len(unmapped) == 2
        assert all(not e.normalized for e in unmapped)

    def test_event_history_filter_by_source(self, normalizer):
        normalizer.normalize_event("src1", "e", {})
        normalizer.normalize_event("src2", "e", {})
        history = normalizer.get_event_history(source="src1")
        assert len(history) == 1
        assert history[0].source == "src1"

    def test_event_history_filter_by_type(self, normalizer):
        normalizer.normalize_event("s", "type_a", {})
        normalizer.normalize_event("s", "type_b", {})
        history = normalizer.get_event_history(event_type="type_a")
        assert len(history) == 1
        assert history[0].event_type == "type_a"

    def test_event_history_limit(self, normalizer):
        for i in range(10):
            normalizer.normalize_event("s", f"e{i}", {})
        history = normalizer.get_event_history(limit=3)
        assert len(history) == 3


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_has_all_fields(self, normalizer):
        status = normalizer.get_status()
        expected = {
            "registered_rules", "total_events_processed",
            "normalized_events", "unmapped_events", "success_rate",
        }
        assert expected.issubset(status.keys())

    def test_status_counts_update(self, normalizer):
        normalizer.register_rule("s", "e", "murphy.s.e")
        normalizer.normalize_event("s", "e", {})
        normalizer.normalize_event("s", "miss", {})
        status = normalizer.get_status()
        assert status["total_events_processed"] == 2
        assert status["normalized_events"] == 1
        assert status["unmapped_events"] == 1
