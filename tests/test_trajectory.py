"""
Tests for Trajectory Engine (src/trajectory_engine.py)

Covers:
  - Parabolic detection signals
  - Volume surge detection
  - Standard deviation break detection
  - Green candle run detection
  - Trajectory projection
  - Trailing stop activation, update, and exit logic
  - Risk guardrails (max chase price, position size factor)
"""

import sys
import os
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trajectory_engine import (
    TrajectoryEngine,
    TrajectoryAnalysis,
    TrajectorySignal,
    Candle,
    TrailingStopState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_candles(prices: list, base_vol: float = 1000.0) -> list:
    """Convert a price list to green candles with constant volume."""
    candles = []
    for i, p in enumerate(prices):
        prev = prices[i - 1] if i > 0 else p * 0.99
        candles.append(Candle(open=prev, high=max(p, prev) * 1.001, low=min(p, prev) * 0.999, close=p, volume=base_vol))
    return candles


def _make_surge_candles(prices: list, surge_at: int = -1) -> list:
    """Create candles with a volume spike on the last candle."""
    candles = _make_candles(prices, base_vol=1000.0)
    if surge_at == -1:
        surge_at = len(candles) - 1
    candles[surge_at] = Candle(
        open   = candles[surge_at].open,
        high   = candles[surge_at].high,
        low    = candles[surge_at].low,
        close  = candles[surge_at].close,
        volume = 5000.0,  # 5× surge
    )
    return candles


def _parabolic_prices(n: int = 30) -> list:
    """Exponentially rising price series to trigger parabolic detection."""
    return [100.0 * (1.05 ** i) for i in range(n)]


def _flat_prices(n: int = 30, base: float = 100.0) -> list:
    """Oscillating flat price series."""
    return [base + math.sin(i * 0.3) * 0.1 for i in range(n)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    return TrajectoryEngine(
        volume_surge_mult      = 2.0,
        std_dev_break          = 2.0,
        min_green_candles      = 3,
        trail_pct              = 0.05,
        max_chase_pct          = 0.10,
        trajectory_size_factor = 0.50,
    )


# ---------------------------------------------------------------------------
# Test: TrajectoryAnalysis structure
# ---------------------------------------------------------------------------


class TestAnalysisStructure:

    def test_returns_trajectory_analysis(self, engine):
        candles = _make_candles(_flat_prices(25))
        result  = engine.analyze("TEST-USD", candles)
        assert isinstance(result, TrajectoryAnalysis)

    def test_all_required_fields(self, engine):
        candles = _make_candles(_flat_prices(25))
        result  = engine.analyze("TEST-USD", candles)
        assert result.product_id == "TEST-USD"
        assert isinstance(result.signal, TrajectorySignal)
        assert isinstance(result.reasoning, list)
        assert isinstance(result.position_size_factor, float)

    def test_to_dict_serializable(self, engine):
        import json
        candles = _make_candles(_flat_prices(25))
        result  = engine.analyze("BTC-USD", candles)
        d = result.to_dict()
        json.dumps(d)  # must not raise

    def test_flat_market_no_signal(self, engine):
        candles = _make_candles(_flat_prices(30))
        result  = engine.analyze("BTC-USD", candles)
        assert result.signal == TrajectorySignal.NONE


# ---------------------------------------------------------------------------
# Test: Parabolic detection
# ---------------------------------------------------------------------------


class TestParabolicDetection:

    def test_parabolic_prices_raise_signal(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        assert result.signal != TrajectorySignal.NONE

    def test_volume_surge_boosts_signal(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_surge_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        assert result.volume_surge is True

    def test_strong_signal_has_non_none_stop(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_surge_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        if result.signal in (TrajectorySignal.STRONG, TrajectorySignal.PARABOLIC):
            assert result.hard_stop_loss is not None

    def test_green_candle_run_counted(self, engine):
        # All-green candles should register a green run
        prices  = [100 + i * 1.5 for i in range(30)]
        candles = _make_candles(prices)
        result  = engine.analyze("SOL-USD", candles)
        assert result.green_candle_run > 0


# ---------------------------------------------------------------------------
# Test: Projection
# ---------------------------------------------------------------------------


class TestProjection:

    def test_projected_target_above_current_for_uptrend(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        if result.projected_target:
            assert result.projected_target > prices[-1]

    def test_optimal_exit_between_current_and_target(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        if result.optimal_exit and result.projected_target:
            assert result.current_price <= result.optimal_exit <= result.projected_target

    def test_no_projection_for_flat_market(self, engine):
        candles = _make_candles(_flat_prices(30))
        result  = engine.analyze("ETH-USD", candles)
        # For NONE signal, exit should also be None
        if result.signal == TrajectorySignal.NONE:
            assert result.optimal_exit is None


# ---------------------------------------------------------------------------
# Test: Risk guardrails
# ---------------------------------------------------------------------------


class TestRiskGuardrails:

    def test_max_chase_price_set(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_surge_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        if result.signal != TrajectorySignal.NONE:
            assert result.max_chase_price is not None
            assert result.max_chase_price > result.current_price

    def test_position_size_factor_reduced_for_strong_signal(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_surge_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        if result.signal in (TrajectorySignal.STRONG, TrajectorySignal.PARABOLIC):
            assert result.position_size_factor < 1.0

    def test_position_size_factor_one_for_no_signal(self, engine):
        candles = _make_candles(_flat_prices(30))
        result  = engine.analyze("MATIC-USD", candles)
        if result.signal == TrajectorySignal.NONE:
            assert result.position_size_factor == 1.0

    def test_hard_stop_below_entry(self, engine):
        prices  = _parabolic_prices(30)
        candles = _make_surge_candles(prices)
        result  = engine.analyze("BTC-USD", candles)
        if result.hard_stop_loss and result.current_price:
            assert result.hard_stop_loss < result.current_price


# ---------------------------------------------------------------------------
# Test: Trailing stop
# ---------------------------------------------------------------------------


class TestTrailingStop:

    def test_activate_trailing_stop(self, engine):
        state = engine.activate_trailing_stop("BTC-USD", entry_price=50_000.0, target=55_000.0)
        assert state.is_active
        assert state.stop_price < 50_000.0

    def test_stop_trails_up(self, engine):
        engine.activate_trailing_stop("BTC-USD", entry_price=50_000.0, trail_pct=0.05)
        stop1, _ = engine.update_trailing_stop("BTC-USD", 52_000.0)
        stop2, _ = engine.update_trailing_stop("BTC-USD", 55_000.0)
        assert stop2 > stop1

    def test_stop_does_not_trail_down(self, engine):
        engine.activate_trailing_stop("BTC-USD", entry_price=50_000.0, trail_pct=0.05)
        stop1, _ = engine.update_trailing_stop("BTC-USD", 55_000.0)
        stop2, _ = engine.update_trailing_stop("BTC-USD", 52_000.0)  # price drops
        assert stop2 == stop1  # stop should not move down

    def test_stop_triggers_exit(self, engine):
        engine.activate_trailing_stop("BTC-USD", entry_price=50_000.0, trail_pct=0.05)
        engine.update_trailing_stop("BTC-USD", 55_000.0)
        stop, should_exit = engine.update_trailing_stop("BTC-USD", 52_000.0 * 0.90)  # big drop
        assert should_exit

    def test_get_trailing_stop_state(self, engine):
        engine.activate_trailing_stop("ETH-USD", entry_price=3_000.0)
        state = engine.get_trailing_stop("ETH-USD")
        assert state is not None
        assert state["product_id"] == "ETH-USD"

    def test_deactivate_trailing_stop(self, engine):
        engine.activate_trailing_stop("SOL-USD", entry_price=100.0)
        engine.deactivate_trailing_stop("SOL-USD")
        assert engine.get_trailing_stop("SOL-USD") is None

    def test_missing_product_returns_none(self, engine):
        stop, exit_ = engine.update_trailing_stop("NONE-USD", 1000.0)
        assert stop is None
        assert not exit_


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
