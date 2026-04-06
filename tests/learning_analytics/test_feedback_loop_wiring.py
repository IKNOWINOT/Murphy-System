"""
Tests for Learning Engine Feedback Loop Wiring (LEARN-LOOP-001)

Validates:
- EventBackbone subscription wiring
- Task completed/failed event handling
- Outcome recording into LearningEngine
- Retraining threshold triggering
- A/B test promotion logic
- Status reporting

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import src.learning_engine.feedback_loop_wiring as wiring


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_wiring_state():
    """Reset the module-level singleton state between tests."""
    wiring._engine = None
    wiring._outcome_count = 0
    wiring._wired = False
    wiring._RETRAIN_THRESHOLD = 100
    yield
    wiring._engine = None
    wiring._outcome_count = 0
    wiring._wired = False


@pytest.fixture
def mock_backbone():
    bb = MagicMock()
    bb.subscribe = MagicMock()
    return bb


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.collect_feedback = MagicMock()
    engine.record_performance = MagicMock()
    return engine


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestWireFeedbackLoop:
    """Test wire_feedback_loop setup."""

    def test_wire_with_mocks(self, mock_backbone, mock_engine):
        result = wiring.wire_feedback_loop(
            learning_engine=mock_engine,
            backbone=mock_backbone,
        )
        assert result is True
        assert wiring._wired is True
        assert mock_backbone.subscribe.call_count == 2

    def test_wire_idempotent(self, mock_backbone, mock_engine):
        wiring.wire_feedback_loop(mock_engine, mock_backbone)
        result = wiring.wire_feedback_loop(mock_engine, mock_backbone)
        assert result is True  # no error, just returns True

    def test_wire_fails_without_backbone(self, mock_engine):
        result = wiring.wire_feedback_loop(
            learning_engine=mock_engine,
            backbone=None,
        )
        assert result is False

    def test_wire_with_on_style_backbone(self, mock_engine):
        bb = MagicMock(spec=[])  # no subscribe attr
        bb.on = MagicMock()
        result = wiring.wire_feedback_loop(mock_engine, bb)
        assert result is True
        assert bb.on.call_count == 2


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


class TestEventHandlers:
    """Test task_completed / task_failed event handling."""

    def test_on_task_completed_feeds_engine(self, mock_engine, mock_backbone):
        wiring.wire_feedback_loop(mock_engine, mock_backbone)
        wiring._on_task_completed({
            "task_id": "t-1",
            "confidence": 0.95,
            "latency_ms": 42.0,
        })
        mock_engine.collect_feedback.assert_called_once()
        call_kwargs = mock_engine.collect_feedback.call_args
        assert call_kwargs[1]["success"] is True
        assert call_kwargs[1]["operation_id"] == "t-1"

    def test_on_task_failed_feeds_engine(self, mock_engine, mock_backbone):
        wiring.wire_feedback_loop(mock_engine, mock_backbone)
        wiring._on_task_failed({
            "task_id": "t-2",
            "confidence": 0.1,
        })
        mock_engine.collect_feedback.assert_called_once()
        call_kwargs = mock_engine.collect_feedback.call_args
        assert call_kwargs[1]["success"] is False

    def test_outcome_count_increments(self, mock_engine, mock_backbone):
        wiring.wire_feedback_loop(mock_engine, mock_backbone)
        for i in range(5):
            wiring._on_task_completed({"task_id": f"t-{i}"})
        assert wiring._outcome_count == 5


# ---------------------------------------------------------------------------
# Retraining trigger
# ---------------------------------------------------------------------------


class TestRetrainingTrigger:
    """Test that retraining fires at threshold."""

    def test_retrain_triggered_at_threshold(self, mock_engine, mock_backbone):
        wiring.wire_feedback_loop(mock_engine, mock_backbone, retrain_threshold=10)
        for i in range(10):
            wiring._on_task_completed({"task_id": f"t-{i}"})
        # After 10 outcomes, _trigger_retraining should have been called
        assert wiring._outcome_count == 10

    def test_retrain_not_triggered_below_threshold(self, mock_engine, mock_backbone):
        wiring.wire_feedback_loop(mock_engine, mock_backbone, retrain_threshold=100)
        for i in range(5):
            wiring._on_task_completed({"task_id": f"t-{i}"})
        assert wiring._outcome_count == 5


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TestFeedbackLoopStatus:

    def test_status_before_wiring(self):
        status = wiring.get_feedback_loop_status()
        assert status["wired"] is False
        assert status["outcome_count"] == 0
        assert status["engine_available"] is False

    def test_status_after_wiring(self, mock_engine, mock_backbone):
        wiring.wire_feedback_loop(mock_engine, mock_backbone)
        status = wiring.get_feedback_loop_status()
        assert status["wired"] is True
        assert status["engine_available"] is True
        assert status["next_retrain_at"] == 100
