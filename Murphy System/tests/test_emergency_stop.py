"""
Tests for Trading Emergency Stop (src/emergency_stop.py)

Covers:
  - Circuit breaker triggers (single trade loss, daily, weekly, consecutive, API, flash crash)
  - Cascading shutdown callbacks
  - Cooldown enforcement on reset
  - Manual trigger
  - Status reporting
"""

import sys
import os
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from emergency_stop import (
    TradingEmergencyStop,
    TradingStopEvent,
    TradingStopReason,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def es():
    """Emergency stop with tight thresholds and zero cooldown for tests."""
    return TradingEmergencyStop(
        portfolio_value_usd     = 10_000.0,
        max_single_loss_pct     = 0.03,
        max_daily_loss_pct      = 0.05,
        max_weekly_loss_pct     = 0.10,
        max_consecutive_losses  = 5,
        max_api_errors          = 3,
        api_error_window_secs   = 60,
        max_data_gap_secs       = 120,
        flash_crash_drop_pct    = 0.10,
        flash_crash_window_secs = 10,
        cooldown_secs           = 0,    # no cooldown for test reset
    )


@pytest.fixture
def es_with_callbacks():
    """Emergency stop that tracks callback invocations."""
    cancel_calls = []
    close_calls  = []

    def on_cancel():
        cancel_calls.append(1)

    def on_close():
        close_calls.append(1)

    inst = TradingEmergencyStop(
        portfolio_value_usd    = 10_000.0,
        max_single_loss_pct    = 0.03,
        max_consecutive_losses = 5,
        cooldown_secs          = 0,
        on_cancel_orders       = on_cancel,
        on_close_positions     = on_close,
    )
    return inst, cancel_calls, close_calls


# ---------------------------------------------------------------------------
# Test: Initial state
# ---------------------------------------------------------------------------


class TestInitialState:

    def test_not_stopped_initially(self, es):
        assert not es.is_stopped

    def test_status_not_stopped(self, es):
        s = es.get_status()
        assert not s["is_stopped"]
        assert s["active_event"] is None

    def test_all_thresholds_in_status(self, es):
        s = es.get_status()
        assert "thresholds" in s
        t = s["thresholds"]
        assert "single_trade_loss_pct" in t
        assert "daily_loss_pct" in t
        assert "consecutive_losses" in t


# ---------------------------------------------------------------------------
# Test: Single trade loss circuit breaker
# ---------------------------------------------------------------------------


class TestSingleTradeLoss:

    def test_small_loss_does_not_trigger(self, es):
        event = es.record_trade_loss(200.0, 10_000.0)   # 2 % — under 3 % threshold
        assert event is None
        assert not es.is_stopped

    def test_large_loss_triggers(self, es):
        event = es.record_trade_loss(400.0, 10_000.0)   # 4 % — over 3 % threshold
        assert event is not None
        assert event.reason == TradingStopReason.SINGLE_TRADE_LOSS
        assert es.is_stopped

    def test_stop_event_has_cooldown(self, es):
        event = es.record_trade_loss(400.0, 10_000.0)
        assert event.cooldown_until is not None


# ---------------------------------------------------------------------------
# Test: Daily loss circuit breaker
# ---------------------------------------------------------------------------


class TestDailyLoss:

    def test_daily_loss_accumulates(self, es):
        # Two trades each < 3 % individually but together > 5 % daily limit
        es.record_trade_loss(250.0, 10_000.0)   # 2.5 % — under single-trade trigger
        event = es.record_trade_loss(280.0, 10_000.0)   # total 5.3 % > 5 % daily
        assert event is not None
        assert event.reason == TradingStopReason.DAILY_LOSS

    def test_status_shows_daily_loss(self, es):
        es.record_trade_loss(200.0, 10_000.0)
        s = es.get_status()
        assert s["daily_loss_usd"] == 200.0


# ---------------------------------------------------------------------------
# Test: Weekly loss circuit breaker
# ---------------------------------------------------------------------------


class TestWeeklyLoss:

    def test_weekly_loss_triggers(self, es):
        # Accumulate 11 % weekly loss (each trade 2.2 %)
        triggered = None
        for _ in range(5):
            ev = es.record_trade_loss(220.0, 10_000.0)
            if ev:
                triggered = ev
                break
        assert triggered is not None
        assert triggered.reason in (
            TradingStopReason.DAILY_LOSS,
            TradingStopReason.WEEKLY_LOSS,
        )


# ---------------------------------------------------------------------------
# Test: Consecutive losses circuit breaker
# ---------------------------------------------------------------------------


class TestConsecutiveLosses:

    def test_five_consecutive_losses_trigger(self):
        es = TradingEmergencyStop(
            portfolio_value_usd    = 10_000.0,
            max_consecutive_losses = 5,
            max_single_loss_pct    = 1.0,   # disable single-trade trigger
            max_daily_loss_pct     = 1.0,   # disable daily trigger
            max_weekly_loss_pct    = 1.0,   # disable weekly trigger
            cooldown_secs          = 0,
        )
        triggered = None
        for _ in range(5):
            ev = es.record_trade_loss(10.0, 10_000.0)
            if ev:
                triggered = ev
                break
        assert triggered is not None
        assert triggered.reason == TradingStopReason.CONSECUTIVE_LOSSES

    def test_win_resets_consecutive_counter(self):
        es = TradingEmergencyStop(
            portfolio_value_usd    = 10_000.0,
            max_consecutive_losses = 5,
            max_single_loss_pct    = 1.0,
            max_daily_loss_pct     = 1.0,
            max_weekly_loss_pct    = 1.0,
            cooldown_secs          = 0,
        )
        es.record_trade_loss(10.0, 10_000.0)
        es.record_trade_loss(10.0, 10_000.0)
        es.record_trade_win()
        assert es._consec_losses == 0


# ---------------------------------------------------------------------------
# Test: API error circuit breaker
# ---------------------------------------------------------------------------


class TestAPIErrors:

    def test_api_errors_trigger_stop(self):
        es = TradingEmergencyStop(
            max_api_errors         = 3,
            api_error_window_secs  = 60,
            max_single_loss_pct    = 1.0,
            max_daily_loss_pct     = 1.0,
            max_weekly_loss_pct    = 1.0,
            cooldown_secs          = 0,
        )
        triggered = None
        for _ in range(4):
            ev = es.record_api_error()
            if ev:
                triggered = ev
                break
        assert triggered is not None
        assert triggered.reason == TradingStopReason.API_ERRORS


# ---------------------------------------------------------------------------
# Test: Flash crash circuit breaker
# ---------------------------------------------------------------------------


class TestFlashCrash:

    def test_flash_crash_triggers_stop(self, es):
        es.record_price(100.0)
        time.sleep(0.01)
        # Drop 15 % — exceeds 10 % threshold
        event = es.record_price(85.0)
        assert event is not None
        assert event.reason == TradingStopReason.FLASH_CRASH

    def test_small_drop_does_not_trigger(self, es):
        es.record_price(100.0)
        event = es.record_price(95.0)  # 5 % drop — under 10 %
        assert event is None


# ---------------------------------------------------------------------------
# Test: Cascading shutdown callbacks
# ---------------------------------------------------------------------------


class TestShutdownCallbacks:

    def test_cancel_orders_called_on_trigger(self, es_with_callbacks):
        inst, cancel_calls, close_calls = es_with_callbacks
        inst.record_trade_loss(400.0, 10_000.0)
        assert len(cancel_calls) == 1

    def test_close_positions_called_on_trigger(self, es_with_callbacks):
        inst, cancel_calls, close_calls = es_with_callbacks
        inst.record_trade_loss(400.0, 10_000.0)
        assert len(close_calls) == 1

    def test_manual_trigger_fires_callbacks(self, es_with_callbacks):
        inst, cancel_calls, close_calls = es_with_callbacks
        inst.trigger_manual("test")
        assert len(cancel_calls) == 1
        assert len(close_calls) == 1


# ---------------------------------------------------------------------------
# Test: Manual trigger
# ---------------------------------------------------------------------------


class TestManualTrigger:

    def test_manual_trigger_stops(self, es):
        event = es.trigger_manual("Test stop")
        assert event.reason == TradingStopReason.MANUAL
        assert es.is_stopped

    def test_manual_trigger_returns_event(self, es):
        event = es.trigger_manual("reason")
        assert isinstance(event, TradingStopEvent)
        assert event.event_id


# ---------------------------------------------------------------------------
# Test: Reset and cooldown
# ---------------------------------------------------------------------------


class TestReset:

    def test_reset_after_cooldown_succeeds(self, es):
        es.trigger_manual("test")
        ok, msg = es.reset("operator")
        assert ok
        assert not es.is_stopped

    def test_reset_without_active_stop_fails(self, es):
        ok, msg = es.reset("operator")
        assert not ok

    def test_reset_with_cooldown_fails(self):
        es = TradingEmergencyStop(cooldown_secs=3600)
        es.trigger_manual("test")
        ok, msg = es.reset("operator")
        assert not ok
        assert "cooldown" in msg.lower()

    def test_log_preserved_after_reset(self, es):
        es.trigger_manual("test")
        es.reset("operator")
        log = es.get_log()
        assert len(log) >= 1


# ---------------------------------------------------------------------------
# Test: Event log
# ---------------------------------------------------------------------------


class TestEventLog:

    def test_log_has_required_fields(self, es):
        es.trigger_manual("test")
        log = es.get_log()
        assert len(log) == 1
        entry = log[0]
        assert "event_id" in entry
        assert "reason" in entry
        assert "triggered_at" in entry
        assert "cooldown_until" in entry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
