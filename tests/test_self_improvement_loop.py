# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for self_improvement_loop module.

Covers retrain triggers (trace count, accuracy drop, human override,
manual, no triggers), model promotion decisions, full retraining cycle
in stub mode, and status reporting.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from murphy_foundation_model.self_improvement_loop import (
    SelfImprovementConfig,
    SelfImprovementLoop,
)


class TestRetrainTriggerTraceCount:
    """Test retrain triggers: trace count threshold."""

    def test_below_threshold_no_trigger(self):
        config = SelfImprovementConfig(retrain_threshold=100)
        loop = SelfImprovementLoop(config=config)
        for _ in range(50):
            loop.record_trace()
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is False

    def test_at_threshold_triggers(self):
        config = SelfImprovementConfig(retrain_threshold=10)
        loop = SelfImprovementLoop(config=config)
        for _ in range(10):
            loop.record_trace()
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is True
        assert any("trace_count" in r for r in result["reasons"])

    def test_above_threshold_triggers(self):
        config = SelfImprovementConfig(retrain_threshold=5)
        loop = SelfImprovementLoop(config=config)
        for _ in range(20):
            loop.record_trace()
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is True


class TestRetrainTriggerAccuracyDrop:
    """Test retrain triggers: accuracy drop."""

    def test_low_accuracy_triggers(self):
        config = SelfImprovementConfig(min_accuracy=0.80)
        # Mock registry with production model having low accuracy
        mock_prod = SimpleNamespace(metrics={"accuracy": 0.60})
        mock_registry = SimpleNamespace(get_current_production=lambda: mock_prod)
        loop = SelfImprovementLoop(config=config, registry=mock_registry)
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is True
        assert any("shadow_accuracy" in r for r in result["reasons"])

    def test_good_accuracy_no_trigger(self):
        config = SelfImprovementConfig(min_accuracy=0.80)
        mock_prod = SimpleNamespace(metrics={"accuracy": 0.95})
        mock_registry = SimpleNamespace(get_current_production=lambda: mock_prod)
        loop = SelfImprovementLoop(config=config, registry=mock_registry)
        result = loop.check_retrain_triggers()
        # No accuracy trigger (others may still be absent)
        accuracy_reasons = [r for r in result["reasons"] if "shadow_accuracy" in r]
        assert len(accuracy_reasons) == 0


class TestRetrainTriggerHumanOverride:
    """Test retrain triggers: human override rate."""

    def test_high_override_rate_triggers(self):
        config = SelfImprovementConfig(max_human_override_rate=0.15)
        mock_prod = SimpleNamespace(metrics={"human_override_rate": 0.30})
        mock_registry = SimpleNamespace(get_current_production=lambda: mock_prod)
        loop = SelfImprovementLoop(config=config, registry=mock_registry)
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is True
        assert any("human_override_rate" in r for r in result["reasons"])

    def test_low_override_rate_no_trigger(self):
        config = SelfImprovementConfig(max_human_override_rate=0.15)
        mock_prod = SimpleNamespace(metrics={"human_override_rate": 0.05})
        mock_registry = SimpleNamespace(get_current_production=lambda: mock_prod)
        loop = SelfImprovementLoop(config=config, registry=mock_registry)
        result = loop.check_retrain_triggers()
        override_reasons = [r for r in result["reasons"] if "human_override_rate" in r]
        assert len(override_reasons) == 0


class TestRetrainTriggerNoTriggers:
    """Test retrain triggers: no triggers met."""

    def test_no_triggers_when_all_ok(self):
        config = SelfImprovementConfig(retrain_threshold=10000)
        loop = SelfImprovementLoop(config=config)
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is False
        assert result["reasons"] == []

    def test_manual_trigger(self):
        config = SelfImprovementConfig(retrain_threshold=10000)
        loop = SelfImprovementLoop(config=config)
        loop.trigger_manual_retrain()
        result = loop.check_retrain_triggers()
        assert result["should_retrain"] is True
        assert "manual_trigger" in result["reasons"]

    def test_manual_trigger_resets_after_check(self):
        config = SelfImprovementConfig(retrain_threshold=10000)
        loop = SelfImprovementLoop(config=config)
        loop.trigger_manual_retrain()
        loop.check_retrain_triggers()
        # Second check: manual trigger should be consumed
        result = loop.check_retrain_triggers()
        assert "manual_trigger" not in result["reasons"]


class TestModelPromotionDecision:
    """Test model promotion decision logic."""

    def test_promote_when_new_model_better(self):
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(min_accuracy=0.80)
        )
        result = loop.should_promote_model(
            new_metrics={"accuracy": 0.90, "loss": 0.3},
            current_metrics={"accuracy": 0.85, "loss": 0.35},
        )
        assert result is True

    def test_no_promote_below_min_accuracy(self):
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(min_accuracy=0.80)
        )
        result = loop.should_promote_model(
            new_metrics={"accuracy": 0.70, "loss": 0.2},
            current_metrics={"accuracy": 0.85, "loss": 0.3},
        )
        assert result is False

    def test_no_promote_worse_than_current(self):
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(min_accuracy=0.80)
        )
        result = loop.should_promote_model(
            new_metrics={"accuracy": 0.82, "loss": 0.3},
            current_metrics={"accuracy": 0.90, "loss": 0.3},
        )
        assert result is False

    def test_no_promote_much_worse_loss(self):
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(min_accuracy=0.80)
        )
        result = loop.should_promote_model(
            new_metrics={"accuracy": 0.90, "loss": 1.0},
            current_metrics={"accuracy": 0.85, "loss": 0.3},
        )
        assert result is False

    def test_promote_with_action_accuracy_key(self):
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(min_accuracy=0.80)
        )
        result = loop.should_promote_model(
            new_metrics={"action_accuracy": 0.90, "loss": 0.3},
            current_metrics={"action_accuracy": 0.85, "loss": 0.35},
        )
        assert result is True

    def test_promote_with_empty_current_metrics(self):
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(min_accuracy=0.80)
        )
        result = loop.should_promote_model(
            new_metrics={"accuracy": 0.90, "loss": 0.3},
            current_metrics={},
        )
        assert result is True

    def test_no_promote_loss_slightly_worse(self):
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(min_accuracy=0.80)
        )
        # Loss is 6% worse (> 5% threshold)
        result = loop.should_promote_model(
            new_metrics={"accuracy": 0.90, "loss": 0.53},
            current_metrics={"accuracy": 0.85, "loss": 0.50},
        )
        assert result is False


class TestFullRetrainingCycle:
    """Test full retraining cycle (stub mode)."""

    def test_cycle_no_collector(self):
        loop = SelfImprovementLoop(config=SelfImprovementConfig())
        result = loop.run_retraining_cycle()
        assert result["success"] is False
        assert result["reason"] == "no_traces"

    def test_cycle_with_mock_collector(self):
        mock_collector = SimpleNamespace(
            get_traces=lambda: [{"input": i} for i in range(10)]
        )
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(),
            collector=mock_collector,
        )
        result = loop.run_retraining_cycle()
        assert result["success"] is True
        assert result["traces_used"] == 10
        assert "new_version" in result

    def test_cycle_increments_iteration(self):
        mock_collector = SimpleNamespace(
            get_traces=lambda: [{"input": 1}]
        )
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(),
            collector=mock_collector,
        )
        assert loop.current_iteration == 0
        loop.run_retraining_cycle()
        assert loop.current_iteration == 1
        loop.run_retraining_cycle()
        assert loop.current_iteration == 2

    def test_cycle_resets_trace_counter(self):
        mock_collector = SimpleNamespace(
            get_traces=lambda: [{"input": 1}]
        )
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(),
            collector=mock_collector,
        )
        for _ in range(50):
            loop.record_trace()
        assert loop._traces_since_retrain == 50
        loop.run_retraining_cycle()
        assert loop._traces_since_retrain == 0


class TestStatusReporting:
    """Test status reporting."""

    def test_initial_status(self):
        loop = SelfImprovementLoop(config=SelfImprovementConfig())
        status = loop.get_status()
        assert status["iteration"] == 0
        assert status["last_retrain"] is None
        assert status["traces_since_retrain"] == 0
        assert "triggers" in status
        assert "config" in status

    def test_status_after_traces(self):
        loop = SelfImprovementLoop(config=SelfImprovementConfig())
        for _ in range(25):
            loop.record_trace()
        status = loop.get_status()
        assert status["traces_since_retrain"] == 25

    def test_status_config_section(self):
        config = SelfImprovementConfig(
            retrain_threshold=5000,
            min_accuracy=0.85,
            max_human_override_rate=0.10,
            check_interval_hours=12.0,
        )
        loop = SelfImprovementLoop(config=config)
        status = loop.get_status()
        assert status["config"]["retrain_threshold"] == 5000
        assert status["config"]["min_accuracy"] == 0.85
        assert status["config"]["max_human_override_rate"] == 0.10
        assert status["config"]["check_interval_hours"] == 12.0

    def test_status_after_retraining(self):
        mock_collector = SimpleNamespace(
            get_traces=lambda: [{"input": 1}]
        )
        loop = SelfImprovementLoop(
            config=SelfImprovementConfig(),
            collector=mock_collector,
        )
        loop.run_retraining_cycle()
        status = loop.get_status()
        assert status["iteration"] == 1
        assert status["last_retrain"] is not None
        assert status["history_count"] == 1
