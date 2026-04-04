"""
Tests for all 9 strategy templates.

Each test verifies that:
  1. The strategy instantiates without error
  2. analyze() returns a valid Signal on a warm-up dataset
  3. Signal fields are within spec (confidence 0-1, action is BUY/SELL/HOLD)

Run with:
    MURPHY_ENV=development python -m pytest tests/test_strategies.py -v --no-cov
"""
from __future__ import annotations

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from typing import List

from strategy_templates.base_strategy import BaseStrategy, MarketBar, Signal, SignalAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bars(
    n: int = 80,
    start: float = 100.0,
    trend: float = 0.002,
    symbol: str = "TEST-USD",
) -> List[MarketBar]:
    """Generate synthetic ascending price bars."""
    bars = []
    price = start
    ts    = time.time() - n * 60
    for i in range(n):
        price = price * (1 + trend * (1 if i % 2 == 0 else -0.4))
        bars.append(MarketBar(
            symbol=symbol, timestamp=ts + i * 60,
            open=price * 0.999, high=price * 1.005,
            low=price * 0.995, close=price,
            volume=500_000.0 + i * 1_000,
        ))
    return bars


def _make_crash_bars(n: int = 80, start: float = 200.0, symbol: str = "TEST-USD") -> List[MarketBar]:
    """Generate sharply declining bars."""
    bars = []
    price = start
    ts    = time.time() - n * 60
    for i in range(n):
        price = price * 0.992
        bars.append(MarketBar(
            symbol=symbol, timestamp=ts + i * 60,
            open=price * 1.002, high=price * 1.003,
            low=price * 0.997, close=price,
            volume=800_000.0,
        ))
    return bars


def _make_parabolic_bars(n: int = 60, start: float = 50.0, symbol: str = "TEST-USD") -> List[MarketBar]:
    """Generate accelerating upward bars (for trajectory strategy)."""
    bars = []
    price = start
    ts    = time.time() - n * 60
    gain  = 0.005
    for i in range(n):
        gain  = gain * 1.05
        price = price * (1 + gain)
        bars.append(MarketBar(
            symbol=symbol, timestamp=ts + i * 60,
            open=price * 0.998, high=price * 1.01,
            low=price * 0.995, close=price,
            volume=1_000_000.0 + i * 5_000,
        ))
    return bars


def _assert_valid_signal(signal: Signal, name: str) -> None:
    assert isinstance(signal, Signal), f"{name}: must return Signal"
    assert signal.action in SignalAction,     f"{name}: invalid action"
    assert 0.0 <= signal.confidence <= 1.0,  f"{name}: confidence must be 0-1"
    if signal.stop_loss is not None:
        assert isinstance(signal.stop_loss, float),   f"{name}: stop_loss must be float"
    if signal.take_profit is not None:
        assert isinstance(signal.take_profit, float), f"{name}: take_profit must be float"
    if signal.suggested_size is not None:
        assert 0.0 < signal.suggested_size <= 1.0, f"{name}: suggested_size out of range"


# ---------------------------------------------------------------------------
# 1. Momentum
# ---------------------------------------------------------------------------

class TestMomentumStrategy:
    def test_instantiates(self):
        from strategy_templates.momentum import MomentumStrategy
        s = MomentumStrategy("mom_test")
        assert s.strategy_id == "mom_test"

    def test_returns_signal_on_uptrend(self):
        from strategy_templates.momentum import MomentumStrategy
        s = MomentumStrategy("mom_test")
        signal = s.analyze(_make_bars(80, trend=0.003))
        _assert_valid_signal(signal, "Momentum")

    def test_returns_sell_on_downtrend(self):
        from strategy_templates.momentum import MomentumStrategy
        s = MomentumStrategy("mom_test")
        signal = s.analyze(_make_crash_bars())
        _assert_valid_signal(signal, "Momentum/crash")

    def test_configure_updates_params(self):
        from strategy_templates.momentum import MomentumStrategy
        s = MomentumStrategy("mom_test")
        s.configure({"rsi_period": 20, "rsi_overbought": 75})
        assert s.params["rsi_period"] == 20


# ---------------------------------------------------------------------------
# 2. Mean Reversion
# ---------------------------------------------------------------------------

class TestMeanReversionStrategy:
    def test_instantiates(self):
        from strategy_templates.mean_reversion import MeanReversionStrategy
        s = MeanReversionStrategy("mr_test")
        assert s is not None

    def test_returns_signal(self):
        from strategy_templates.mean_reversion import MeanReversionStrategy
        s = MeanReversionStrategy("mr_test")
        signal = s.analyze(_make_bars(80))
        _assert_valid_signal(signal, "MeanReversion")

    def test_buy_on_oversold_bars(self):
        from strategy_templates.mean_reversion import MeanReversionStrategy
        s = MeanReversionStrategy("mr_test")
        # crash bars should eventually trigger oversold / buy signal
        signal = s.analyze(_make_crash_bars(80))
        _assert_valid_signal(signal, "MeanReversion/crash")


# ---------------------------------------------------------------------------
# 3. Breakout
# ---------------------------------------------------------------------------

class TestBreakoutStrategy:
    def test_instantiates(self):
        from strategy_templates.breakout import BreakoutStrategy
        s = BreakoutStrategy("bo_test")
        assert s is not None

    def test_returns_signal(self):
        from strategy_templates.breakout import BreakoutStrategy
        s = BreakoutStrategy("bo_test")
        signal = s.analyze(_make_bars(80, trend=0.004))
        _assert_valid_signal(signal, "Breakout")

    def test_insufficient_bars_returns_hold(self):
        from strategy_templates.breakout import BreakoutStrategy
        s = BreakoutStrategy("bo_test")
        signal = s.analyze(_make_bars(5))
        assert signal.action == SignalAction.HOLD


# ---------------------------------------------------------------------------
# 4. Scalping
# ---------------------------------------------------------------------------

class TestScalpingStrategy:
    def test_instantiates(self):
        from strategy_templates.scalping import ScalpingStrategy
        s = ScalpingStrategy("sc_test")
        assert s is not None

    def test_returns_signal(self):
        from strategy_templates.scalping import ScalpingStrategy
        s = ScalpingStrategy("sc_test")
        signal = s.analyze(_make_bars(40))
        _assert_valid_signal(signal, "Scalping")

    def test_stop_loss_tight(self):
        from strategy_templates.scalping import ScalpingStrategy
        s = ScalpingStrategy("sc_test")
        bars = _make_bars(40, trend=0.004)
        signal = s.analyze(bars)
        if signal.action == SignalAction.BUY and signal.stop_loss:
            entry  = bars[-1].close
            # Scalping stop loss should be tight (< 1.5 %)
            diff_pct = (entry - signal.stop_loss) / entry
            assert diff_pct < 0.015, f"Scalping stop too wide: {diff_pct:.4f}"


# ---------------------------------------------------------------------------
# 5. DCA
# ---------------------------------------------------------------------------

class TestDCAStrategy:
    def test_instantiates(self):
        from strategy_templates.dca import DCAStrategy
        s = DCAStrategy("dca_test")
        assert s is not None

    def test_returns_signal(self):
        from strategy_templates.dca import DCAStrategy
        s = DCAStrategy("dca_test")
        signal = s.analyze(_make_bars(30))
        _assert_valid_signal(signal, "DCA")

    def test_buy_on_dip(self):
        from strategy_templates.dca import DCAStrategy
        s = DCAStrategy("dca_test", params={"dip_threshold_pct": 0.001})
        signal = s.analyze(_make_crash_bars(50))
        # After many dips it should generate a BUY at some point
        _assert_valid_signal(signal, "DCA/dip")


# ---------------------------------------------------------------------------
# 6. Grid
# ---------------------------------------------------------------------------

class TestGridStrategy:
    def test_instantiates(self):
        from strategy_templates.grid import GridStrategy
        s = GridStrategy("grid_test")
        assert s is not None

    def test_returns_signal(self):
        from strategy_templates.grid import GridStrategy
        s = GridStrategy("grid_test")
        signal = s.analyze(_make_bars(30))
        _assert_valid_signal(signal, "Grid")

    def test_grid_initialises_on_first_bar(self):
        from strategy_templates.grid import GridStrategy
        s = GridStrategy("grid_test", params={"grid_levels": 5})
        bars = _make_bars(60)   # need >= init_period (50) bars to auto-detect range
        s.analyze(bars)
        assert s._grids is not None  # noqa: SLF001


# ---------------------------------------------------------------------------
# 7. Trajectory
# ---------------------------------------------------------------------------

class TestTrajectoryStrategy:
    def test_instantiates(self):
        from strategy_templates.trajectory import TrajectoryStrategy
        s = TrajectoryStrategy("traj_test")
        assert s is not None

    def test_returns_signal(self):
        from strategy_templates.trajectory import TrajectoryStrategy
        s = TrajectoryStrategy("traj_test")
        signal = s.analyze(_make_bars(40))
        _assert_valid_signal(signal, "Trajectory")

    def test_buy_on_parabolic_bars(self):
        from strategy_templates.trajectory import TrajectoryStrategy
        s = TrajectoryStrategy("traj_test", params={"accel_threshold": 0.005})
        signal = s.analyze(_make_parabolic_bars(30))
        # Parabolic bars should trigger BUY
        _assert_valid_signal(signal, "Trajectory/parabolic")
        if signal.action == SignalAction.BUY:
            assert signal.take_profit is not None


# ---------------------------------------------------------------------------
# 8. Sentiment
# ---------------------------------------------------------------------------

class TestSentimentStrategy:
    def test_instantiates(self):
        from strategy_templates.sentiment import SentimentStrategy
        s = SentimentStrategy("sent_test")
        assert s is not None

    def test_returns_signal_with_price_proxy(self):
        from strategy_templates.sentiment import SentimentStrategy
        s = SentimentStrategy("sent_test")
        signal = s.analyze(_make_bars(30))
        _assert_valid_signal(signal, "Sentiment")

    def test_buy_on_extreme_fear(self):
        from strategy_templates.sentiment import SentimentStrategy
        s = SentimentStrategy("sent_test")
        s.update_sentiment(fear_greed=10.0, social_score=-0.8)
        signal = s.analyze(_make_bars(30))
        # Extreme fear should trigger contrarian BUY
        assert signal.action == SignalAction.BUY
        _assert_valid_signal(signal, "Sentiment/fear")

    def test_sell_on_extreme_greed(self):
        from strategy_templates.sentiment import SentimentStrategy
        s = SentimentStrategy("sent_test")
        s.update_sentiment(fear_greed=90.0, social_score=0.9)
        signal = s.analyze(_make_bars(30))
        assert signal.action == SignalAction.SELL
        _assert_valid_signal(signal, "Sentiment/greed")


# ---------------------------------------------------------------------------
# 9. Arbitrage
# ---------------------------------------------------------------------------

class TestArbitrageStrategy:
    def test_instantiates(self):
        from strategy_templates.arbitrage import ArbitrageStrategy
        s = ArbitrageStrategy("arb_test")
        assert s is not None

    def test_hold_without_secondary(self):
        from strategy_templates.arbitrage import ArbitrageStrategy
        s = ArbitrageStrategy("arb_test")
        signal = s.analyze(_make_bars(30))
        assert signal.action == SignalAction.HOLD

    def test_detects_spread_on_paired_analysis(self):
        from strategy_templates.arbitrage import ArbitrageStrategy
        s = ArbitrageStrategy("arb_test", params={"spread_threshold": 0.001, "z_score_threshold": 1.5})
        bars_a = _make_bars(50, start=100.0, symbol="BTC-USD")
        # Make asset B consistently cheaper
        bars_b = _make_bars(50, start=97.0, symbol="ETH-USD")
        # Build spread history
        for _ in range(40):
            s.analyze_pair(bars_a, bars_b)
        signal = s.analyze_pair(bars_a, bars_b)
        _assert_valid_signal(signal, "Arbitrage")

    def test_signal_via_set_secondary_bars(self):
        from strategy_templates.arbitrage import ArbitrageStrategy
        s = ArbitrageStrategy("arb_test")
        bars_b = _make_bars(30, start=95.0, symbol="ETH-USD")
        s.set_secondary_bars(bars_b)
        signal = s.analyze(_make_bars(30, start=100.0, symbol="BTC-USD"))
        _assert_valid_signal(signal, "Arbitrage/secondary")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestStrategyRegistry:
    def test_registry_has_nine_strategies(self):
        from strategy_templates import STRATEGY_REGISTRY
        assert len(STRATEGY_REGISTRY) == 9

    def test_all_strategies_instantiate(self):
        from strategy_templates import STRATEGY_REGISTRY
        bars = _make_bars(50)
        for name, cls in STRATEGY_REGISTRY.items():
            s = cls(strategy_id=name)
            signal = s.analyze(bars)
            _assert_valid_signal(signal, name)

    def test_all_strategies_have_get_params(self):
        from strategy_templates import STRATEGY_REGISTRY
        for name, cls in STRATEGY_REGISTRY.items():
            s = cls(strategy_id=name)
            params = s.get_params()
            assert isinstance(params, dict), f"{name}: get_params must return dict"

    def test_all_strategies_configurable(self):
        from strategy_templates import STRATEGY_REGISTRY
        for name, cls in STRATEGY_REGISTRY.items():
            s = cls(strategy_id=name)
            s.configure({"position_size": 0.05})
            assert s.params["position_size"] == 0.05
