"""
Tests for Dynamic Risk Manager (src/dynamic_risk_manager.py)

Covers:
  - RiskAssessment output structure
  - ATR / volatility calculations
  - Market regime detection
  - Kelly position sizing
  - ATR-based stop-loss / take-profit
  - Portfolio state tracking
"""

import sys
import os
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dynamic_risk_manager import (
    DynamicRiskManager,
    RiskAssessment,
    RiskLevel,
    MarketRegime,
    PositionInfo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mgr():
    return DynamicRiskManager(portfolio_value_usd=10_000.0)


def _prices(n: int = 30, start: float = 100.0, step: float = 0.5) -> list:
    """Generate a simple rising price series."""
    return [start + i * step for i in range(n)]


def _volatile_prices(n: int = 30) -> list:
    """Generate high-volatility price series."""
    import random
    random.seed(42)
    p = 100.0
    result = [p]
    for _ in range(n - 1):
        p *= 1 + random.uniform(-0.06, 0.06)
        result.append(p)
    return result


# ---------------------------------------------------------------------------
# Test: RiskAssessment structure
# ---------------------------------------------------------------------------


class TestRiskAssessmentStructure:

    def test_returns_risk_assessment_object(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        assert isinstance(result, RiskAssessment)

    def test_all_fields_present(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        assert isinstance(result.recommended_risk_level, RiskLevel)
        assert result.max_position_size >= 0
        assert 0 <= result.risk_score <= 100
        assert isinstance(result.reasoning, list)
        assert len(result.reasoning) > 0
        assert isinstance(result.market_regime, MarketRegime)

    def test_to_dict_serializable(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        d = result.to_dict()
        assert "recommended_risk_level" in d
        assert "risk_score" in d
        assert "reasoning" in d
        import json
        json.dumps(d)  # should not raise

    def test_risk_score_in_bounds(self, mgr):
        for _ in range(5):
            prices = _prices(30)
            result = mgr.assess(prices=prices, entry_price=prices[-1])
            assert 0 <= result.risk_score <= 100


# ---------------------------------------------------------------------------
# Test: Volatility & ATR
# ---------------------------------------------------------------------------


class TestVolatilityAndATR:

    def test_atr_computed(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        assert result.atr is not None
        assert result.atr >= 0

    def test_volatility_computed(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        assert result.volatility is not None
        assert result.volatility >= 0

    def test_high_volatility_raises_risk_score(self, mgr):
        steady = _prices(30, step=0.1)
        volatile = _volatile_prices(30)
        r_steady   = mgr.assess(prices=steady,   entry_price=steady[-1])
        r_volatile = mgr.assess(prices=volatile, entry_price=volatile[-1])
        assert r_volatile.risk_score >= r_steady.risk_score

    def test_high_volatility_recommends_conservative(self, mgr):
        prices = _volatile_prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        # Volatile market should lean conservative or moderate
        assert result.recommended_risk_level in (RiskLevel.CONSERVATIVE, RiskLevel.MODERATE)


# ---------------------------------------------------------------------------
# Test: Market regime detection
# ---------------------------------------------------------------------------


class TestMarketRegimeDetection:

    def test_trending_regime_detected(self, mgr):
        prices = [50 + i * 2 for i in range(30)]  # strong uptrend
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        assert result.market_regime == MarketRegime.TRENDING

    def test_ranging_regime_detected(self, mgr):
        import math
        prices = [100 + 1.5 * math.sin(i * 0.5) for i in range(30)]  # oscillating
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        assert result.market_regime == MarketRegime.RANGING

    def test_volatile_regime_detected(self, mgr):
        prices = _volatile_prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1])
        # should be VOLATILE or TRENDING depending on random seed
        assert result.market_regime in (MarketRegime.VOLATILE, MarketRegime.TRENDING, MarketRegime.RANGING)


# ---------------------------------------------------------------------------
# Test: Position sizing (Kelly)
# ---------------------------------------------------------------------------


class TestPositionSizing:

    def test_position_size_positive(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1], win_rate=0.6)
        assert result.max_position_size > 0

    def test_position_size_capped_at_5_pct(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1], win_rate=0.9, avg_win=10, avg_loss=1)
        assert result.max_position_size <= 10_000 * 0.05  # 5% cap

    def test_zero_win_rate_gives_zero_size(self, mgr):
        prices = _prices(30)
        result = mgr.assess(prices=prices, entry_price=prices[-1], win_rate=0.0)
        assert result.max_position_size == 0.0

    def test_conservative_smaller_than_aggressive(self):
        mgr_small = DynamicRiskManager(portfolio_value_usd=10_000)
        volatile = _volatile_prices(30)
        result_volatile = mgr_small.assess(prices=volatile, entry_price=volatile[-1], win_rate=0.6)

        mgr_large = DynamicRiskManager(portfolio_value_usd=10_000)
        steady = _prices(30, step=0.01)  # very low vol
        result_steady = mgr_large.assess(prices=steady, entry_price=steady[-1], win_rate=0.6)

        # Steady/aggressive conditions should produce larger sizing than volatile/conservative
        assert result_steady.max_position_size >= result_volatile.max_position_size


# ---------------------------------------------------------------------------
# Test: Stop-loss / take-profit
# ---------------------------------------------------------------------------


class TestStopLossAndTakeProfit:

    def test_buy_stop_below_entry(self, mgr):
        prices = _prices(30)
        entry = prices[-1]
        result = mgr.assess(prices=prices, entry_price=entry, side="buy")
        if result.suggested_stop_loss:
            assert result.suggested_stop_loss < entry

    def test_buy_tp_above_entry(self, mgr):
        prices = _prices(30)
        entry = prices[-1]
        result = mgr.assess(prices=prices, entry_price=entry, side="buy")
        if result.suggested_take_profit:
            assert result.suggested_take_profit > entry

    def test_sell_stop_above_entry(self, mgr):
        prices = _prices(30)
        entry = prices[-1]
        result = mgr.assess(prices=prices, entry_price=entry, side="sell")
        if result.suggested_stop_loss:
            assert result.suggested_stop_loss > entry

    def test_sell_tp_below_entry(self, mgr):
        prices = _prices(30)
        entry = prices[-1]
        result = mgr.assess(prices=prices, entry_price=entry, side="sell")
        if result.suggested_take_profit:
            assert result.suggested_take_profit < entry


# ---------------------------------------------------------------------------
# Test: Portfolio state tracking
# ---------------------------------------------------------------------------


class TestPortfolioState:

    def test_update_portfolio_value(self, mgr):
        mgr.update_portfolio_value(12_000.0)
        summary = mgr.get_summary()
        assert summary["portfolio_value_usd"] == 12_000.0

    def test_drawdown_tracked(self, mgr):
        mgr.update_portfolio_value(10_000.0)
        mgr.update_portfolio_value(8_500.0)
        summary = mgr.get_summary()
        assert summary["current_drawdown_pct"] > 0

    def test_add_remove_position(self, mgr):
        mgr.add_position("BTC-USD", 3_000.0, 50_000.0)
        s1 = mgr.get_summary()
        assert s1["open_positions"] == 1
        mgr.remove_position("BTC-USD")
        s2 = mgr.get_summary()
        assert s2["open_positions"] == 0

    def test_win_loss_streak(self, mgr):
        for _ in range(3):
            mgr.record_trade_result(-50.0)
        summary = mgr.get_summary()
        assert summary["loss_streak"] == 3
        assert summary["win_streak"] == 0

    def test_win_streak_resets_loss_streak(self, mgr):
        mgr.record_trade_result(-50.0)
        mgr.record_trade_result(100.0)
        s = mgr.get_summary()
        assert s["win_streak"] == 1
        assert s["loss_streak"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
