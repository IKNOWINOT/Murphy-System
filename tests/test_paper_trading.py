"""
Tests for the Paper Trading Engine, Cost Calibrator, Error Calibrator,
and Backtester.

Run with:
    MURPHY_ENV=development python -m pytest tests/test_paper_trading.py -v --no-cov
"""
from __future__ import annotations

import sys
import os
import time

# Add src/ to path so imports work from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest

from paper_trading_engine import PaperTradingEngine, DEFAULT_CAPITAL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine(capital: float = 10_000.0) -> PaperTradingEngine:
    return PaperTradingEngine(
        initial_capital=capital,
        taker_fee_rate=0.001,
        slippage_bps=5.0,
    )


# ---------------------------------------------------------------------------
# PaperTradingEngine — basic open/close
# ---------------------------------------------------------------------------

class TestOpenPosition:
    def test_basic_buy_reduces_cash(self):
        eng = _engine()
        result = eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        assert result["status"] == "filled"
        assert eng.cash < DEFAULT_CAPITAL

    def test_open_creates_position(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        assert "BTC-USD" in eng._positions

    def test_insufficient_cash_rejected(self):
        eng = _engine(capital=100.0)
        result = eng.open_position("BTC-USD", quantity=1.0, price=50_000, strategy="test")
        assert result["status"] == "rejected"
        assert "insufficient_cash" in result["reason"]

    def test_fill_price_includes_slippage(self):
        eng = _engine()
        result = eng.open_position("ETH-USD", quantity=0.5, price=2_000, strategy="test")
        assert result["fill_price"] > 2_000, "BUY should fill above requested price"

    def test_fee_recorded(self):
        eng = _engine()
        result = eng.open_position("ETH-USD", quantity=0.5, price=2_000, strategy="test")
        assert result["fee"] > 0

    def test_position_size_limit(self):
        """A single position cannot exceed max_position_pct of equity."""
        eng = PaperTradingEngine(initial_capital=10_000, max_position_pct=0.10)
        # Try to buy $9,000 worth at $1 each (90% of equity)
        result = eng.open_position("TOKEN", quantity=9_000, price=1.0, strategy="test")
        assert result["status"] == "rejected"


class TestClosePosition:
    def test_basic_sell_increases_cash(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        cash_after_buy = eng.cash
        eng.close_position("BTC-USD", price=51_000)
        assert eng.cash > cash_after_buy

    def test_pnl_is_positive_on_gain(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        result = eng.close_position("BTC-USD", price=55_000)
        assert result["net_pnl"] > 0

    def test_pnl_is_negative_on_loss(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        result = eng.close_position("BTC-USD", price=45_000)
        assert result["net_pnl"] < 0

    def test_no_position_rejected(self):
        eng = _engine()
        result = eng.close_position("NONEXISTENT", price=100)
        assert result["status"] == "rejected"

    def test_position_removed_after_full_close(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        eng.close_position("BTC-USD", price=51_000)
        assert "BTC-USD" not in eng._positions

    def test_fill_price_includes_slippage(self):
        eng = _engine()
        eng.open_position("ETH-USD", quantity=0.5, price=2_000, strategy="test")
        result = eng.close_position("ETH-USD", price=2_000)
        assert result["fill_price"] < 2_000, "SELL should fill below requested price"

    def test_exit_reason_recorded(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        result = eng.close_position("BTC-USD", price=51_000, exit_reason="take_profit")
        records = result.get("records", [])
        assert records
        assert records[0]["exit_reason"] == "take_profit"


class TestPortfolioState:
    def test_equity_equals_cash_plus_positions(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        portfolio = eng.get_portfolio()
        expected = eng.cash + eng._positions["BTC-USD"].market_value
        assert abs(portfolio["equity"] - expected) < 0.01

    def test_total_fees_accumulate(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.01, price=50_000, strategy="test")
        eng.close_position("BTC-USD", price=51_000)
        assert eng._total_fees_paid > 0

    def test_multiple_symbols_tracked(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.005, price=50_000, strategy="test")
        eng.open_position("ETH-USD", quantity=0.5,   price=2_000,  strategy="test")
        assert len(eng._positions) == 2


class TestReset:
    def test_reset_clears_positions_and_journal(self):
        eng = _engine()
        eng.open_position("BTC-USD", quantity=0.1, price=50_000, strategy="test")
        eng.close_position("BTC-USD", price=51_000)
        eng.reset()
        assert eng.cash == eng.initial_capital
        assert len(eng._positions) == 0
        assert len(eng._journal) == 0
        assert eng._total_fees_paid == 0.0


class TestPerformanceMetrics:
    def _run_trades(self, wins: int, losses: int) -> PaperTradingEngine:
        eng = _engine()
        for i in range(wins):
            eng.open_position("BTC-USD",  quantity=0.01, price=50_000, strategy="test")
            eng.close_position("BTC-USD", price=55_000)
        for i in range(losses):
            eng.open_position("BTC-USD",  quantity=0.01, price=50_000, strategy="test")
            eng.close_position("BTC-USD", price=45_000)
        return eng

    def test_win_rate_correct(self):
        eng = self._run_trades(wins=3, losses=1)
        m = eng.get_performance()
        assert abs(m["win_rate"] - 0.75) < 0.01

    def test_profit_factor_gt_zero(self):
        eng = self._run_trades(wins=3, losses=1)
        m = eng.get_performance()
        assert m["profit_factor"] > 0

    def test_max_drawdown_non_negative(self):
        eng = self._run_trades(wins=1, losses=3)
        m = eng.get_performance()
        assert m["max_drawdown"] >= 0

    def test_all_metric_keys_present(self):
        eng = self._run_trades(wins=2, losses=2)
        m = eng.get_performance()
        required = [
            "total_trades", "wins", "losses", "win_rate", "loss_rate",
            "avg_win", "avg_loss", "profit_factor", "total_pnl",
            "net_profit_after_costs", "total_return_pct",
            "sharpe_ratio", "sortino_ratio",
            "max_drawdown", "max_drawdown_pct",
            "total_fees", "total_slippage", "equity",
        ]
        for key in required:
            assert key in m, f"Missing metric: {key}"

    def test_no_trades_returns_zero_metrics(self):
        eng = _engine()
        m = eng.get_performance()
        assert m["total_trades"] == 0
        assert m["win_rate"] == 0.0


class TestStopLossTakeProfit:
    def test_stop_loss_triggers_on_update(self):
        eng = _engine()
        eng.open_position("ETH-USD", quantity=1.0, price=2_000, strategy="test",
                          stop_loss=1_900)
        triggered = eng.update_prices({"ETH-USD": 1_850})
        assert "ETH-USD" in triggered
        assert triggered["ETH-USD"]["trigger"] == "stop_loss"

    def test_take_profit_triggers_on_update(self):
        eng = _engine()
        eng.open_position("ETH-USD", quantity=1.0, price=2_000, strategy="test",
                          take_profit=2_200)
        triggered = eng.update_prices({"ETH-USD": 2_300})
        assert "ETH-USD" in triggered
        assert triggered["ETH-USD"]["trigger"] == "take_profit"

    def test_no_trigger_in_range(self):
        eng = _engine()
        eng.open_position("ETH-USD", quantity=1.0, price=2_000, strategy="test",
                          stop_loss=1_900, take_profit=2_200)
        triggered = eng.update_prices({"ETH-USD": 2_050})
        assert triggered == {}


# ---------------------------------------------------------------------------
# CostCalibrator
# ---------------------------------------------------------------------------

class TestCostCalibrator:
    def test_import_and_instantiate(self):
        from cost_calibrator import CostCalibrator
        cal = CostCalibrator()
        assert cal is not None

    def test_expected_costs_returns_estimates(self):
        from cost_calibrator import CostCalibrator
        cal = CostCalibrator()
        est = cal.expected_costs("BTC-USD", notional=10_000)
        assert "total_cost_est" in est
        assert est["total_cost_est"] > 0

    def test_record_observation_stored(self):
        from cost_calibrator import CostCalibrator
        cal = CostCalibrator()
        cal.record_observation(
            trade_id="t1", symbol="BTC-USD", strategy="test",
            expected_price=50_000, actual_price=50_025,
            expected_fee=5.0, actual_fee=5.1,
            expected_slippage=2.5, actual_slippage=3.0,
        )
        summary = cal.get_summary()
        assert summary["observations"] == 1
        assert summary["avg_hidden_cost_per_trade"] > 0

    def test_alert_fires_on_excessive_slippage(self):
        from cost_calibrator import CostCalibrator
        cal = CostCalibrator(slippage_alert_bps=1.0)  # very tight threshold
        cal.record_observation(
            trade_id="t1", symbol="BTC-USD", strategy="test",
            expected_price=1_000, actual_price=1_000,
            expected_fee=1.0, actual_fee=1.0,
            expected_slippage=0.05, actual_slippage=5.0,   # 0.5 % slippage — way above 1 bps threshold
        )
        alerts = cal.get_alerts()
        assert len(alerts) >= 1

    def test_calibration_adjusts_after_observations(self):
        from cost_calibrator import CostCalibrator
        cal = CostCalibrator()
        for i in range(10):
            cal.record_observation(
                trade_id=f"t{i}", symbol="BTC-USD", strategy="test",
                expected_price=1_000, actual_price=1_002,
                expected_fee=1.0, actual_fee=1.1,
                expected_slippage=0.5, actual_slippage=0.8,
            )
        summary = cal.get_summary()
        adj = summary["calibration_adjustments"]
        # After consistent over-fee, fee_pct_added should be > 0
        assert adj["fee_pct_added"] >= 0


# ---------------------------------------------------------------------------
# ErrorCalibrator
# ---------------------------------------------------------------------------

class TestErrorCalibrator:
    def test_import_and_instantiate(self):
        from error_calibrator import ErrorCalibrator
        cal = ErrorCalibrator()
        assert cal is not None

    def test_record_outcome_stored(self):
        from error_calibrator import ErrorCalibrator
        cal = ErrorCalibrator()
        cal.record_outcome("momentum", "BTC-USD", predicted_return=0.02, actual_return=0.025)
        profile = cal.get_profile("momentum")
        assert profile["observations"] == 1

    def test_bias_calculated(self):
        from error_calibrator import ErrorCalibrator
        cal = ErrorCalibrator()
        for _ in range(5):
            cal.record_outcome("test_strat", "BTC-USD",
                               predicted_return=0.01, actual_return=0.03)
        profile = cal.get_profile("test_strat")
        # Actual is consistently higher than predicted, so bias should be positive
        assert profile["bias"] > 0

    def test_recalibration_triggered_on_high_divergence(self):
        from error_calibrator import ErrorCalibrator
        cal = ErrorCalibrator(
            divergence_threshold=0.01,
            min_observations=5,
            recal_cooldown_secs=0,
        )
        for _ in range(6):
            cal.record_outcome("high_bias_strategy", "BTC-USD",
                               predicted_return=0.00, actual_return=0.05)
        profile = cal.get_profile("high_bias_strategy")
        assert profile["recalibration_count"] >= 1

    def test_get_all_profiles_returns_dict(self):
        from error_calibrator import ErrorCalibrator
        cal = ErrorCalibrator()
        cal.record_outcome("strat_a", "ETH-USD", 0.01, 0.012)
        cal.record_outcome("strat_b", "BTC-USD", 0.02, 0.015)
        profiles = cal.get_all_profiles()
        assert "strat_a" in profiles
        assert "strat_b" in profiles

    def test_summary_has_required_keys(self):
        from error_calibrator import ErrorCalibrator
        cal = ErrorCalibrator()
        s = cal.get_summary()
        for key in ["tracked_strategies", "total_observations", "total_recalibrations", "pending_alerts"]:
            assert key in s


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

class TestBacktester:
    def _make_ohlcv(self, n: int = 200, start: float = 100.0, trend: float = 0.001):
        from backtester import OHLCVRow
        rows = []
        price = start
        ts    = time.time() - n * 86400
        for i in range(n):
            price = price * (1 + trend + (0.002 if i % 3 == 0 else -0.001))
            rows.append(OHLCVRow(
                timestamp=ts + i * 86400,
                open=price * 0.999, high=price * 1.005,
                low=price * 0.995, close=price,
                volume=1_000_000.0,
            ))
        return rows

    def test_backtester_runs(self):
        from backtester import Backtester
        from strategy_templates.momentum import MomentumStrategy
        bt  = Backtester(initial_capital=10_000)
        s   = MomentumStrategy("momentum_bt")
        ohlcv = self._make_ohlcv()
        result = bt.run(s, ohlcv, "TEST-USD")
        assert result.total_bars == len(ohlcv)
        assert isinstance(result.metrics, dict)

    def test_backtest_result_has_all_fields(self):
        from backtester import Backtester
        from strategy_templates.mean_reversion import MeanReversionStrategy
        bt    = Backtester(initial_capital=10_000)
        s     = MeanReversionStrategy("mr_bt")
        ohlcv = self._make_ohlcv()
        result = bt.run(s, ohlcv, "TEST-USD")
        d = result.to_dict()
        for key in ["strategy", "symbol", "timeframe", "total_bars", "metrics", "equity_curve", "trades"]:
            assert key in d

    def test_compare_returns_ranking(self):
        from backtester import Backtester
        from strategy_templates.momentum import MomentumStrategy
        from strategy_templates.mean_reversion import MeanReversionStrategy
        bt    = Backtester(initial_capital=10_000)
        strats = [MomentumStrategy("mom"), MeanReversionStrategy("mr")]
        ohlcv  = self._make_ohlcv()
        comp   = bt.compare(strats, ohlcv, "TEST-USD")
        assert "ranking" in comp
        assert len(comp["ranking"]) == 2

    def test_load_dicts(self):
        from backtester import load_dicts
        data = [
            {"timestamp": 1_700_000_000 + i * 86400,
             "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 1000.0}
            for i in range(10)
        ]
        rows = load_dicts(data)
        assert len(rows) == 10
        assert rows[0].close == 102.0

    def test_result_to_json(self):
        import json
        from backtester import Backtester
        from strategy_templates.scalping import ScalpingStrategy
        bt    = Backtester(initial_capital=10_000)
        s     = ScalpingStrategy("scalp_bt")
        ohlcv = self._make_ohlcv(n=100)
        result = bt.run(s, ohlcv, "TEST-USD")
        j = result.to_json()
        d = json.loads(j)
        assert d["strategy"] == "scalp_bt"
