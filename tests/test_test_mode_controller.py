# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for TestModeController (Facet 1)
"""

import time
import pytest
import sys
import os

# Ensure the Murphy System package root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.test_mode_controller import TestModeController, get_test_mode_controller


# ---------------------------------------------------------------------------
# Basic lifecycle
# ---------------------------------------------------------------------------

class TestTestModeControllerLifecycle:
    def test_initial_state_inactive(self):
        ctrl = TestModeController()
        assert ctrl.is_active() is False

    def test_start_session_activates(self):
        ctrl = TestModeController()
        ctrl.start_session()
        assert ctrl.is_active() is True

    def test_end_session_deactivates(self):
        ctrl = TestModeController()
        ctrl.start_session()
        ctrl.end_session()
        assert ctrl.is_active() is False

    def test_start_returns_status(self):
        ctrl = TestModeController(max_calls=10, max_seconds=60)
        status = ctrl.start_session()
        assert status["test_mode"] is True
        assert status["calls_used"] == 0
        assert status["calls_remaining"] == 10
        assert status["max_calls"] == 10

    def test_end_returns_status(self):
        ctrl = TestModeController()
        ctrl.start_session()
        status = ctrl.end_session()
        assert status["session_ended"] is True
        assert status["test_mode"] is False


# ---------------------------------------------------------------------------
# Call counting
# ---------------------------------------------------------------------------

class TestCallCounting:
    def test_record_call_increments(self):
        ctrl = TestModeController(max_calls=50)
        ctrl.start_session()
        ctrl.record_call()
        ctrl.record_call()
        ctrl.record_call()
        assert ctrl.get_status()["calls_used"] == 3

    def test_record_call_when_inactive_increments_skipped(self):
        ctrl = TestModeController()
        ctrl.record_call()
        ctrl.record_call()
        assert ctrl.get_status()["skipped_calls"] == 2

    def test_calls_remaining_decrements(self):
        ctrl = TestModeController(max_calls=5)
        ctrl.start_session()
        ctrl.record_call()
        ctrl.record_call()
        assert ctrl.get_status()["calls_remaining"] == 3


# ---------------------------------------------------------------------------
# Limit enforcement
# ---------------------------------------------------------------------------

class TestLimits:
    def test_call_limit_triggers_end(self):
        ctrl = TestModeController(max_calls=3)
        ctrl.start_session()
        ctrl.record_call()
        ctrl.record_call()
        ctrl.record_call()
        ok, reason = ctrl.check_limits()
        assert ok is False
        assert reason == "call_limit_reached"
        assert ctrl.is_active() is False

    def test_time_limit_triggers_end(self):
        ctrl = TestModeController(max_calls=1000, max_seconds=0)
        ctrl.start_session()
        # max_seconds=0 means immediately expired
        ok, reason = ctrl.check_limits()
        assert ok is False
        assert reason == "time_limit_reached"

    def test_within_limits_returns_true(self):
        ctrl = TestModeController(max_calls=100, max_seconds=300)
        ctrl.start_session()
        ok, reason = ctrl.check_limits()
        assert ok is True
        assert reason is None

    def test_check_limits_when_inactive(self):
        ctrl = TestModeController()
        ok, reason = ctrl.check_limits()
        assert ok is False
        assert reason == "session_not_active"


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------

class TestApiKeys:
    def test_keys_stored(self):
        ctrl = TestModeController()
        ctrl.start_session(api_keys=["key1", "key2"])
        assert ctrl.get_test_api_keys() == ["key1", "key2"]

    def test_keys_count_in_status(self):
        ctrl = TestModeController()
        ctrl.start_session(api_keys=["k1", "k2", "k3"])
        assert ctrl.get_status()["keys_count"] == 3

    def test_no_keys_is_ok(self):
        ctrl = TestModeController()
        ctrl.start_session()
        assert ctrl.get_test_api_keys() == []


# ---------------------------------------------------------------------------
# Toggle helper
# ---------------------------------------------------------------------------

class TestToggle:
    def test_toggle_starts_inactive_session(self):
        ctrl = TestModeController()
        result = ctrl.toggle()
        assert result["test_mode"] is True

    def test_toggle_ends_active_session(self):
        ctrl = TestModeController()
        ctrl.start_session()
        result = ctrl.toggle()
        assert result["test_mode"] is False

    def test_toggle_twice_is_on_then_off(self):
        ctrl = TestModeController()
        ctrl.toggle()
        assert ctrl.is_active() is True
        ctrl.toggle()
        assert ctrl.is_active() is False


# ---------------------------------------------------------------------------
# Status structure
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_has_recommended_provider(self):
        ctrl = TestModeController()
        status = ctrl.get_status()
        rec = status.get("recommended_provider", {})
        assert "DeepInfra" in rec.get("name", "")
        assert "deepinfra.com" in rec.get("url", "")

    def test_status_seconds_remaining_non_negative(self):
        ctrl = TestModeController(max_seconds=1)
        ctrl.start_session()
        time.sleep(2)
        status = ctrl.get_status()
        assert status["seconds_remaining"] >= 0


# ---------------------------------------------------------------------------
# Thread safety (smoke test)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_record_calls(self):
        import threading
        ctrl = TestModeController(max_calls=1000)
        ctrl.start_session()
        threads = [threading.Thread(target=ctrl.record_call) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert ctrl.get_status()["calls_used"] == 50


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_test_mode_controller_returns_same_instance(self):
        a = get_test_mode_controller()
        b = get_test_mode_controller()
        assert a is b
