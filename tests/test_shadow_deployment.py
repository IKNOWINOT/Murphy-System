# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for shadow_deployment module.

Covers ShadowComparison creation, Jaccard action similarity,
comparison logging to JSONL, metrics aggregation, promotion logic,
empty comparisons handling, and similar vs dissimilar outputs.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from murphy_foundation_model.shadow_deployment import (
    ShadowComparison,
    ShadowConfig,
    ShadowDeployment,
)


class TestShadowComparisonDataclass:
    """Test ShadowComparison dataclass creation."""

    def test_create_comparison(self):
        comp = ShadowComparison(
            request_id="r-001",
            timestamp="2025-06-01T12:00:00Z",
            mfm_output={"action_plan": [], "confidence": 0.8},
            external_output={"action_plan": [], "confidence": 0.7},
            action_similarity=0.9,
            confidence_diff=0.1,
            mfm_latency_ms=50.0,
            external_latency_ms=200.0,
        )
        assert comp.request_id == "r-001"
        assert comp.action_similarity == 0.9
        assert comp.confidence_diff == 0.1
        assert comp.mfm_correct is None

    def test_comparison_with_mfm_correct(self):
        comp = ShadowComparison(
            request_id="r-002",
            timestamp="2025-06-01T12:00:00Z",
            mfm_output={},
            external_output={},
            action_similarity=1.0,
            confidence_diff=0.0,
            mfm_latency_ms=10.0,
            external_latency_ms=100.0,
            mfm_correct=True,
        )
        assert comp.mfm_correct is True


class TestJaccardSimilarity:
    """Test action similarity computation (Jaccard)."""

    def test_identical_plans(self):
        sd = ShadowDeployment(config=ShadowConfig())
        sim = sd._jaccard_action_similarity(
            [{"type": "api_call"}, {"type": "command"}],
            [{"type": "api_call"}, {"type": "command"}],
        )
        assert sim == 1.0

    def test_completely_different_plans(self):
        sd = ShadowDeployment(config=ShadowConfig())
        sim = sd._jaccard_action_similarity(
            [{"type": "api_call"}],
            [{"type": "actuator"}],
        )
        assert sim == 0.0

    def test_partial_overlap(self):
        sd = ShadowDeployment(config=ShadowConfig())
        sim = sd._jaccard_action_similarity(
            [{"type": "api_call"}, {"type": "command"}],
            [{"type": "api_call"}, {"type": "data"}],
        )
        # intersection={api_call}, union={api_call, command, data} → 1/3
        assert sim == pytest.approx(1 / 3)

    def test_both_empty(self):
        sd = ShadowDeployment(config=ShadowConfig())
        sim = sd._jaccard_action_similarity([], [])
        assert sim == 1.0

    def test_one_empty(self):
        sd = ShadowDeployment(config=ShadowConfig())
        sim = sd._jaccard_action_similarity(
            [{"type": "api_call"}], []
        )
        assert sim == 0.0

    def test_string_steps(self):
        sd = ShadowDeployment(config=ShadowConfig())
        sim = sd._jaccard_action_similarity(
            ["api_call", "command"],
            ["api_call", "command"],
        )
        assert sim == 1.0

    def test_duplicate_types_dont_inflate(self):
        sd = ShadowDeployment(config=ShadowConfig())
        sim = sd._jaccard_action_similarity(
            [{"type": "api_call"}, {"type": "api_call"}],
            [{"type": "api_call"}],
        )
        assert sim == 1.0


class TestComparisonLogging:
    """Test comparison logging to JSONL."""

    def test_log_creates_file(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path))
        sd = ShadowDeployment(config=config)
        sd.compare_outputs(
            {"request_id": "r1"},
            {"action_plan": [{"type": "api_call"}], "confidence": 0.8, "latency_ms": 50},
            {"action_plan": [{"type": "api_call"}], "confidence": 0.7, "latency_ms": 200},
        )
        log_path = tmp_path / "shadow_comparisons.jsonl"
        assert log_path.exists()

    def test_log_contains_valid_json(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path))
        sd = ShadowDeployment(config=config)
        for i in range(3):
            sd.compare_outputs(
                {"request_id": f"r{i}"},
                {"action_plan": [], "confidence": 0.5, "latency_ms": 50},
                {"action_plan": [], "confidence": 0.5, "latency_ms": 100},
            )

        log_path = tmp_path / "shadow_comparisons.jsonl"
        with open(log_path) as fh:
            lines = [l.strip() for l in fh if l.strip()]
        assert len(lines) == 3
        for line in lines:
            record = json.loads(line)
            assert "request_id" in record
            assert "action_similarity" in record

    def test_log_record_fields(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path))
        sd = ShadowDeployment(config=config)
        sd.compare_outputs(
            {"request_id": "check"},
            {"action_plan": [{"type": "x"}], "confidence": 0.9, "latency_ms": 30},
            {"action_plan": [{"type": "x"}], "confidence": 0.8, "latency_ms": 60},
        )
        log_path = tmp_path / "shadow_comparisons.jsonl"
        record = json.loads(log_path.read_text().strip())
        assert record["request_id"] == "check"
        assert "timestamp" in record
        assert "mfm_output" in record
        assert "external_output" in record


class TestMetricsAggregation:
    """Test metrics aggregation."""

    def test_empty_metrics(self):
        sd = ShadowDeployment(config=ShadowConfig())
        metrics = sd.get_metrics()
        assert metrics["total_comparisons"] == 0
        assert metrics["similarity_rate"] == 0.0
        assert metrics["confidence_accuracy"] == 0.0

    def test_metrics_with_comparisons(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path), similarity_threshold=0.5)
        sd = ShadowDeployment(config=config)

        # Add high-similarity comparisons
        for _ in range(5):
            sd.compare_outputs(
                {},
                {"action_plan": [{"type": "api_call"}], "confidence": 0.8, "latency_ms": 50},
                {"action_plan": [{"type": "api_call"}], "confidence": 0.75, "latency_ms": 100},
            )

        metrics = sd.get_metrics()
        assert metrics["total_comparisons"] == 5
        assert metrics["similarity_rate"] == 1.0
        assert metrics["confidence_accuracy"] > 0.9

    def test_latency_comparison_in_metrics(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path))
        sd = ShadowDeployment(config=config)
        sd.compare_outputs(
            {},
            {"action_plan": [], "confidence": 0.5, "latency_ms": 50},
            {"action_plan": [], "confidence": 0.5, "latency_ms": 200},
        )
        metrics = sd.get_metrics()
        lat = metrics["latency_comparison"]
        assert lat["mfm_avg_ms"] == 50.0
        assert lat["external_avg_ms"] == 200.0
        assert lat["mfm_faster"] is True


class TestShouldPromote:
    """Test should_promote logic."""

    def test_not_enough_comparisons(self, tmp_path):
        config = ShadowConfig(
            log_dir=str(tmp_path),
            comparison_window=100,
        )
        sd = ShadowDeployment(config=config)
        sd.compare_outputs(
            {},
            {"action_plan": [{"type": "a"}], "confidence": 0.9, "latency_ms": 10},
            {"action_plan": [{"type": "a"}], "confidence": 0.9, "latency_ms": 10},
        )
        assert sd.should_promote() is False

    def test_promote_when_criteria_met(self, tmp_path):
        config = ShadowConfig(
            log_dir=str(tmp_path),
            comparison_window=5,
            similarity_threshold=0.7,
        )
        sd = ShadowDeployment(config=config)
        for _ in range(5):
            sd.compare_outputs(
                {},
                {"action_plan": [{"type": "api_call"}], "confidence": 0.85, "latency_ms": 50},
                {"action_plan": [{"type": "api_call"}], "confidence": 0.85, "latency_ms": 100},
            )
        assert sd.should_promote() is True

    def test_no_promote_low_similarity(self, tmp_path):
        config = ShadowConfig(
            log_dir=str(tmp_path),
            comparison_window=5,
            similarity_threshold=0.9,
        )
        sd = ShadowDeployment(config=config)
        for _ in range(5):
            sd.compare_outputs(
                {},
                {"action_plan": [{"type": "api_call"}], "confidence": 0.8, "latency_ms": 50},
                {"action_plan": [{"type": "actuator"}], "confidence": 0.8, "latency_ms": 100},
            )
        assert sd.should_promote() is False

    def test_no_promote_low_confidence_accuracy(self, tmp_path):
        config = ShadowConfig(
            log_dir=str(tmp_path),
            comparison_window=5,
            similarity_threshold=0.5,
        )
        sd = ShadowDeployment(config=config)
        for _ in range(5):
            sd.compare_outputs(
                {},
                {"action_plan": [{"type": "api_call"}], "confidence": 0.9, "latency_ms": 50},
                {"action_plan": [{"type": "api_call"}], "confidence": 0.1, "latency_ms": 100},
            )
        # confidence_diff = 0.8 → confidence_accuracy = 0.2 < 0.8
        assert sd.should_promote() is False


class TestSimilarVsDissimilar:
    """Test similar vs dissimilar outputs."""

    def test_identical_outputs(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path))
        sd = ShadowDeployment(config=config)
        out = {"action_plan": [{"type": "api_call"}], "confidence": 0.8, "latency_ms": 50}
        comp = sd.compare_outputs({}, out, out)
        assert comp.action_similarity == 1.0
        assert comp.confidence_diff == 0.0

    def test_completely_different_outputs(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path))
        sd = ShadowDeployment(config=config)
        comp = sd.compare_outputs(
            {},
            {"action_plan": [{"type": "api_call"}], "confidence": 1.0, "latency_ms": 10},
            {"action_plan": [{"type": "actuator"}], "confidence": 0.0, "latency_ms": 500},
        )
        assert comp.action_similarity == 0.0
        assert comp.confidence_diff == 1.0

    def test_comparison_window_limit(self, tmp_path):
        config = ShadowConfig(log_dir=str(tmp_path), comparison_window=3)
        sd = ShadowDeployment(config=config)
        for i in range(10):
            sd.compare_outputs(
                {},
                {"action_plan": [], "confidence": 0.5, "latency_ms": 50},
                {"action_plan": [], "confidence": 0.5, "latency_ms": 100},
            )
        assert len(sd._comparisons) == 3


class TestStartStop:
    """Test start/stop shadow mode."""

    def test_start_stop_cycle(self, tmp_path):
        sd = ShadowDeployment(config=ShadowConfig(log_dir=str(tmp_path)))
        assert sd.is_active is False
        sd.start()
        assert sd.is_active is True
        sd.stop()
        assert sd.is_active is False

    def test_double_start(self, tmp_path):
        sd = ShadowDeployment(config=ShadowConfig(log_dir=str(tmp_path)))
        sd.start()
        sd.start()
        assert sd.is_active is True
