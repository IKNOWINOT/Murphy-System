"""
Tests for OPS-003: AutomationModeController.

Validates outcome recording, EMA calculation, mode progression,
mode downgrade, manual override, persistence, and EventBackbone.

Design Label: TEST-022 / OPS-003
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from automation_mode_controller import (
    AutomationModeController,
    AutomationMode,
    TransitionDirection,
    ModeTransition,
    TaskOutcome,
    DEFAULT_THRESHOLDS,
    DEFAULT_MIN_OBSERVATIONS,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def ctrl():
    return AutomationModeController()


@pytest.fixture
def wired_ctrl(pm, backbone):
    return AutomationModeController(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Initial state
# ------------------------------------------------------------------

class TestInitialState:
    def test_starts_manual(self, ctrl):
        assert ctrl.current_mode == AutomationMode.MANUAL

    def test_initial_ema_zero(self, ctrl):
        assert ctrl.current_ema == 0.0


# ------------------------------------------------------------------
# Outcome recording
# ------------------------------------------------------------------

class TestOutcomeRecording:
    def test_record_success(self, ctrl):
        outcome = ctrl.record_outcome("general", success=True)
        assert outcome.success is True
        assert ctrl.current_ema > 0.0

    def test_record_failure(self, ctrl):
        ctrl.record_outcome("general", success=True)
        ctrl.record_outcome("general", success=False)
        # EMA should be less than 1.0
        assert ctrl.current_ema < 1.0

    def test_ema_converges_on_success(self, ctrl):
        for _ in range(100):
            ctrl.record_outcome("general", success=True)
        assert ctrl.current_ema > 0.95


# ------------------------------------------------------------------
# Mode progression
# ------------------------------------------------------------------

class TestModeProgression:
    def test_no_upgrade_without_observations(self, ctrl):
        result = ctrl.evaluate()
        assert result is None
        assert ctrl.current_mode == AutomationMode.MANUAL

    def test_upgrade_to_supervised(self):
        ctrl = AutomationModeController(
            min_observations={
                0: 0, 1: 5, 2: 10, 3: 20, 4: 30,
            }
        )
        for _ in range(10):
            ctrl.record_outcome("general", success=True)
        t = ctrl.evaluate()
        assert t is not None
        assert ctrl.current_mode == AutomationMode.SUPERVISED

    def test_upgrade_chain(self):
        ctrl = AutomationModeController(
            min_observations={0: 0, 1: 3, 2: 3, 3: 3, 4: 3},
            ema_alpha=0.5,
        )
        for _ in range(50):
            ctrl.record_outcome("general", success=True)
            ctrl.evaluate()
        # Should have upgraded several times
        assert ctrl.current_mode.value >= AutomationMode.AUTO_LOW.value


# ------------------------------------------------------------------
# Mode downgrade
# ------------------------------------------------------------------

class TestModeDowngrade:
    def test_downgrade_on_failures(self):
        ctrl = AutomationModeController(
            min_observations={0: 0, 1: 3, 2: 3, 3: 3, 4: 3},
            ema_alpha=0.5,
        )
        # First upgrade
        for _ in range(20):
            ctrl.record_outcome("general", success=True)
            ctrl.evaluate()
        assert ctrl.current_mode.value > AutomationMode.MANUAL.value

        # Now fail repeatedly
        for _ in range(30):
            ctrl.record_outcome("general", success=False)
            ctrl.evaluate()
        # Should have downgraded
        assert ctrl.current_mode.value < AutomationMode.FULL.value


# ------------------------------------------------------------------
# Manual override
# ------------------------------------------------------------------

class TestManualOverride:
    def test_set_mode(self, ctrl):
        t = ctrl.set_mode(AutomationMode.FULL, reason="testing")
        assert ctrl.current_mode == AutomationMode.FULL
        assert t.direction == TransitionDirection.MANUAL

    def test_transition_to_dict(self, ctrl):
        t = ctrl.set_mode(AutomationMode.SUPERVISED)
        d = t.to_dict()
        assert "transition_id" in d
        assert d["to_mode"] == "SUPERVISED"

    def test_transition_history(self, ctrl):
        ctrl.set_mode(AutomationMode.SUPERVISED)
        ctrl.set_mode(AutomationMode.AUTO_LOW)
        history = ctrl.get_transitions()
        assert len(history) == 2


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_transition_persisted(self, wired_ctrl, pm):
        t = wired_ctrl.set_mode(AutomationMode.SUPERVISED, "test")
        loaded = pm.load_document(t.transition_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_transition_publishes_event(self, wired_ctrl, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_ctrl.set_mode(AutomationMode.SUPERVISED, "test")
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, ctrl):
        s = ctrl.get_status()
        assert s["current_mode"] == "MANUAL"
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_ctrl):
        s = wired_ctrl.get_status()
        assert s["persistence_attached"] is True
