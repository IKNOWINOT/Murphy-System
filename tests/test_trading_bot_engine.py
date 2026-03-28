"""
Tests for Trading Bot Engine — Internal-Only Trading System with Reverse Inference.

Covers:
- Market data ingestion
- Reverse inference corporate takeover detection
- Multiple trading strategies
- Paper trading P&L tracking
- Risk management (position sizing, stop-loss)
- Portfolio tracking
- Safety controls (live trading disabled, profitability proof)
- AI optimization feedback loop
- Account integration hooks (verify disabled by default)
"""

import unittest
import time
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trading_bot_engine import (
    LIVE_TRADING_ENABLED,
    AssetClass,
    Signal,
    MarketRegime,
    PositionSizingMethod,
    TradingMode,
    MarketData,
    TradeOrder,
    Position,
    TaxLot,
    MarketDataIngestion,
    ReverseInferenceEngine,
    TradingStrategyEngine,
    PaperTradingSimulator,
    RiskManager,
    PortfolioTracker,
    BrokerageAdapter,
    CoinbaseAdapter,
    TradingGateway,
    AIOptimizationLayer,
    TradingBotEngine,
)


def _make_market_data(
    symbol="ACME",
    price=50.0,
    volume=1000000,
    total_assets=1_000_000_000,
    total_liabilities=400_000_000,
    shares_outstanding=10_000_000,
    cash_position=200_000_000,
    revenue_history=None,
    asset_class=AssetClass.STOCK,
    market_cap=500_000_000,
):
    return MarketData(
        symbol=symbol,
        asset_class=asset_class,
        price=price,
        volume=volume,
        timestamp=time.time(),
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        shares_outstanding=shares_outstanding,
        cash_position=cash_position,
        revenue_history=revenue_history or [100, 110, 120, 130],
        market_cap=market_cap,
    )


# =============================================================================
# Market Data Ingestion Tests
# =============================================================================


class TestMarketDataIngestion(unittest.TestCase):
    def setUp(self):
        self.ingestion = MarketDataIngestion()

    def test_ingest_single(self):
        data = _make_market_data()
        result = self.ingestion.ingest(data)
        self.assertEqual(result["status"], "ingested")
        self.assertEqual(result["symbol"], "ACME")

    def test_get_latest(self):
        data = _make_market_data(price=55.0)
        self.ingestion.ingest(data)
        latest = self.ingestion.get_latest("ACME")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["price"], 55.0)

    def test_get_latest_missing(self):
        result = self.ingestion.get_latest("MISSING")
        self.assertIsNone(result)

    def test_get_history(self):
        for i in range(5):
            self.ingestion.ingest(_make_market_data(price=50.0 + i))
        history = self.ingestion.get_history("ACME")
        self.assertEqual(len(history), 5)

    def test_get_symbols(self):
        self.ingestion.ingest(_make_market_data(symbol="AAPL"))
        self.ingestion.ingest(_make_market_data(symbol="GOOG"))
        symbols = self.ingestion.get_symbols()
        self.assertIn("AAPL", symbols)
        self.assertIn("GOOG", symbols)

    def test_multiple_asset_classes(self):
        self.ingestion.ingest(_make_market_data(symbol="BTC", asset_class=AssetClass.CRYPTO))
        self.ingestion.ingest(_make_market_data(symbol="AAPL", asset_class=AssetClass.STOCK))
        self.ingestion.ingest(_make_market_data(symbol="SPY_CALL", asset_class=AssetClass.OPTION))
        self.assertEqual(len(self.ingestion.get_symbols()), 3)

    def test_history_limit(self):
        for i in range(20):
            self.ingestion.ingest(_make_market_data(price=50.0 + i))
        history = self.ingestion.get_history("ACME", limit=5)
        self.assertEqual(len(history), 5)


# =============================================================================
# Reverse Inference Engine Tests
# =============================================================================


class TestReverseInferenceEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ReverseInferenceEngine(margin=0.20)

    def test_intrinsic_value_calculation(self):
        data = _make_market_data(total_assets=1_000_000_000, total_liabilities=400_000_000, shares_outstanding=10_000_000)
        iv = self.engine.calculate_intrinsic_value(data)
        self.assertAlmostEqual(iv, 60.0, places=2)

    def test_is_takeover_candidate_true(self):
        # Intrinsic = 60, threshold = 60 * 0.8 = 48, price = 40 < 48
        data = _make_market_data(price=40.0)
        self.assertTrue(self.engine.is_takeover_candidate(data))

    def test_is_takeover_candidate_false(self):
        # Intrinsic = 60, threshold = 48, price = 55 > 48
        data = _make_market_data(price=55.0)
        self.assertFalse(self.engine.is_takeover_candidate(data))

    def test_score_candidate_is_candidate(self):
        data = _make_market_data(price=40.0)
        result = self.engine.score_candidate(data)
        self.assertTrue(result["is_candidate"])
        self.assertGreater(result["composite_score"], 0.0)

    def test_score_candidate_not_candidate(self):
        data = _make_market_data(price=70.0)
        result = self.engine.score_candidate(data)
        self.assertFalse(result["is_candidate"])

    def test_score_components(self):
        data = _make_market_data(price=40.0)
        result = self.engine.score_candidate(data)
        self.assertIn("discount_to_book_value", result)
        self.assertIn("asset_quality_score", result)
        self.assertIn("debt_ratio", result)
        self.assertIn("cash_score", result)
        self.assertIn("revenue_trend", result)

    def test_zero_shares_outstanding(self):
        data = _make_market_data(shares_outstanding=0)
        iv = self.engine.calculate_intrinsic_value(data)
        self.assertEqual(iv, 0.0)
        self.assertFalse(self.engine.is_takeover_candidate(data))

    def test_get_candidates(self):
        data = _make_market_data(price=40.0, symbol="TARGET")
        self.engine.score_candidate(data)
        candidates = self.engine.get_candidates()
        self.assertIn("TARGET", candidates)

    def test_clear_candidates(self):
        data = _make_market_data(price=40.0)
        self.engine.score_candidate(data)
        self.engine.clear_candidates()
        self.assertEqual(len(self.engine.get_candidates()), 0)

    def test_revenue_trend_positive(self):
        data = _make_market_data(price=40.0, revenue_history=[100, 120, 140, 160])
        result = self.engine.score_candidate(data)
        self.assertGreater(result["revenue_trend"], 0.5)

    def test_revenue_trend_negative(self):
        data = _make_market_data(price=40.0, revenue_history=[160, 140, 120, 100])
        result = self.engine.score_candidate(data)
        self.assertLess(result["revenue_trend"], 0.5)


# =============================================================================
# Trading Strategy Tests
# =============================================================================


class TestTradingStrategyEngine(unittest.TestCase):
    def setUp(self):
        self.engine = TradingStrategyEngine()

    def test_mean_reversion_buy(self):
        prices = [100] * 20 + [80]
        result = self.engine.mean_reversion(prices, 80.0)
        self.assertEqual(result["signal"], "buy")

    def test_mean_reversion_sell(self):
        prices = [100] * 20 + [120]
        result = self.engine.mean_reversion(prices, 120.0)
        self.assertEqual(result["signal"], "sell")

    def test_mean_reversion_hold(self):
        prices = [100] * 20
        result = self.engine.mean_reversion(prices, 100.0)
        self.assertEqual(result["signal"], "hold")

    def test_momentum_buy(self):
        prices = [100 + i * 2 for i in range(15)]
        result = self.engine.momentum(prices)
        self.assertEqual(result["signal"], "buy")

    def test_momentum_sell(self):
        prices = [100 - i * 2 for i in range(15)]
        result = self.engine.momentum(prices)
        self.assertEqual(result["signal"], "sell")

    def test_pairs_trading_signal(self):
        prices_a = [100] * 10 + [130]
        prices_b = [100] * 10 + [100]
        result = self.engine.pairs_trading(prices_a, prices_b)
        self.assertIn(result["signal"], ["buy", "sell", "hold"])

    def test_value_investing_buy(self):
        # PB ratio < 0.8 -> buy
        data = _make_market_data(price=30.0)  # book value per share = 60
        result = self.engine.value_investing(data)
        self.assertEqual(result["signal"], "buy")

    def test_value_investing_sell(self):
        # PB ratio > 2.0 -> sell
        data = _make_market_data(price=200.0)
        result = self.engine.value_investing(data)
        self.assertEqual(result["signal"], "sell")

    def test_reverse_inference_takeover_buy(self):
        data = _make_market_data(price=40.0)
        result = self.engine.reverse_inference_takeover(data)
        self.assertEqual(result["signal"], "buy")

    def test_reverse_inference_takeover_hold(self):
        data = _make_market_data(price=70.0)
        result = self.engine.reverse_inference_takeover(data)
        self.assertEqual(result["signal"], "hold")

    def test_get_all_signals(self):
        data = _make_market_data(price=50.0)
        prices = [48 + i for i in range(10)]
        signals = self.engine.get_all_signals(data, prices)
        self.assertGreaterEqual(len(signals), 3)

    def test_update_weights(self):
        self.engine.update_weights("momentum", 1.5)
        weights = self.engine.get_weights()
        self.assertEqual(weights["momentum"], 1.5)

    def test_insufficient_data_mean_reversion(self):
        result = self.engine.mean_reversion([100], 100)
        self.assertEqual(result["signal"], "hold")

    def test_insufficient_data_momentum(self):
        result = self.engine.momentum([100])
        self.assertEqual(result["signal"], "hold")


# =============================================================================
# Paper Trading Simulator Tests
# =============================================================================


class TestPaperTradingSimulator(unittest.TestCase):
    def setUp(self):
        self.sim = PaperTradingSimulator(initial_capital=100000.0)

    def test_submit_buy_order(self):
        result = self.sim.submit_order("ACME", "buy", 100, 50.0, "momentum", 0.8)
        self.assertEqual(result["status"], "filled")
        self.assertEqual(self.sim.capital, 95000.0)

    def test_submit_sell_order(self):
        self.sim.submit_order("ACME", "buy", 100, 50.0, "momentum", 0.8)
        result = self.sim.submit_order("ACME", "sell", 100, 55.0, "momentum", 0.8)
        self.assertEqual(result["status"], "filled")

    def test_insufficient_capital(self):
        result = self.sim.submit_order("ACME", "buy", 10000, 50.0, "momentum", 0.8)
        self.assertEqual(result["status"], "rejected")

    def test_performance_metrics_empty(self):
        metrics = self.sim.get_performance_metrics()
        self.assertEqual(metrics["total_trades"], 0)

    def test_performance_metrics_with_trades(self):
        self.sim.submit_order("ACME", "buy", 100, 50.0, "momentum", 0.8)
        self.sim.submit_order("ACME", "sell", 100, 55.0, "momentum", 0.8)
        metrics = self.sim.get_performance_metrics()
        self.assertEqual(metrics["total_trades"], 1)
        self.assertEqual(metrics["wins"], 1)

    def test_systematic_profitability_not_proven(self):
        self.assertFalse(self.sim.systematic_profitability_proven())

    def test_systematic_profitability_proven(self):
        for i in range(3):
            self.sim.record_monthly_return(f"2024-0{i+1}", 100000, 105000)
        self.assertTrue(self.sim.systematic_profitability_proven())

    def test_systematic_profitability_mixed(self):
        self.sim.record_monthly_return("2024-01", 100000, 105000)
        self.sim.record_monthly_return("2024-02", 105000, 100000)  # loss
        self.sim.record_monthly_return("2024-03", 100000, 106000)
        self.assertFalse(self.sim.systematic_profitability_proven())

    def test_trade_log(self):
        self.sim.submit_order("ACME", "buy", 10, 50.0, "test", 0.5)
        log = self.sim.get_trade_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["symbol"], "ACME")

    def test_equity_curve(self):
        self.sim.submit_order("ACME", "buy", 10, 50.0, "test", 0.5)
        curve = self.sim.get_equity_curve()
        self.assertEqual(len(curve), 2)
        self.assertEqual(curve[0], 100000.0)


# =============================================================================
# Risk Management Tests
# =============================================================================


class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager()

    def test_kelly_criterion_positive(self):
        fraction = self.rm.kelly_criterion(0.6, 2.0, 1.0)
        self.assertGreater(fraction, 0.0)
        self.assertLessEqual(fraction, 0.05)

    def test_kelly_criterion_zero_loss(self):
        fraction = self.rm.kelly_criterion(0.6, 2.0, 0.0)
        self.assertEqual(fraction, 0.0)

    def test_fixed_fractional(self):
        size = self.rm.fixed_fractional(100000, 0.01)
        self.assertEqual(size, 1000.0)

    def test_equal_weight(self):
        size = self.rm.equal_weight(100000, 20)
        self.assertEqual(size, 100000 * 0.05)

    def test_check_stop_loss_triggered(self):
        result = self.rm.check_stop_loss(100, 90, 0.05)
        self.assertTrue(result["triggered"])

    def test_check_stop_loss_not_triggered(self):
        result = self.rm.check_stop_loss(100, 97, 0.05)
        self.assertFalse(result["triggered"])

    def test_check_take_profit_triggered(self):
        result = self.rm.check_take_profit(100, 115, 0.10)
        self.assertTrue(result["triggered"])

    def test_check_take_profit_not_triggered(self):
        result = self.rm.check_take_profit(100, 105, 0.10)
        self.assertFalse(result["triggered"])

    def test_emergency_stop(self):
        result = self.rm.emergency_stop()
        self.assertEqual(result["status"], "emergency_stop_activated")
        self.assertTrue(self.rm.is_emergency_stopped())

    def test_reset_emergency_stop(self):
        self.rm.emergency_stop()
        self.rm.reset_emergency_stop()
        self.assertFalse(self.rm.is_emergency_stopped())

    def test_position_limit_allowed(self):
        result = self.rm.check_position_limit(4000, 100000)
        self.assertTrue(result["allowed"])

    def test_position_limit_exceeded(self):
        result = self.rm.check_position_limit(10000, 100000)
        self.assertFalse(result["allowed"])

    def test_portfolio_exposure(self):
        result = self.rm.check_portfolio_exposure(70000, 100000)
        self.assertTrue(result["allowed"])

    def test_portfolio_exposure_exceeded(self):
        result = self.rm.check_portfolio_exposure(90000, 100000)
        self.assertFalse(result["allowed"])

    def test_position_sizing_kelly(self):
        result = self.rm.calculate_position_size(
            PositionSizingMethod.KELLY, 100000, win_rate=0.6, avg_win=2.0, avg_loss=1.0
        )
        self.assertEqual(result["method"], "kelly")
        self.assertGreater(result["position_size"], 0)

    def test_daily_loss_recording(self):
        self.rm.record_daily_pnl(-500)
        result = self.rm.check_daily_loss_limit(100000)
        self.assertFalse(result["breached"])  # -500 < 2000 limit


# =============================================================================
# Portfolio Tracker Tests
# =============================================================================


class TestPortfolioTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = PortfolioTracker(initial_capital=100000.0)

    def test_open_position(self):
        result = self.tracker.open_position("ACME", 100, 50.0, "test")
        self.assertEqual(result["status"], "opened")
        self.assertEqual(self.tracker.cash, 95000.0)

    def test_close_position(self):
        self.tracker.open_position("ACME", 100, 50.0, "test")
        result = self.tracker.close_position("ACME", 55.0)
        self.assertEqual(result["status"], "closed")
        self.assertEqual(result["realized_pnl"], 500.0)

    def test_close_nonexistent(self):
        result = self.tracker.close_position("MISSING", 50.0)
        self.assertEqual(result["status"], "error")

    def test_portfolio_summary(self):
        self.tracker.open_position("ACME", 100, 50.0, "test")
        summary = self.tracker.get_portfolio_summary()
        self.assertEqual(summary["num_positions"], 1)
        self.assertIn("ACME", summary["allocation"])

    def test_update_price(self):
        self.tracker.open_position("ACME", 100, 50.0, "test")
        updated = self.tracker.update_price("ACME", 55.0)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["current_price"], 55.0)
        self.assertAlmostEqual(updated["unrealized_pnl"], 500.0)

    def test_tax_lots(self):
        self.tracker.open_position("ACME", 100, 50.0, "test")
        lots = self.tracker.get_tax_lots("ACME")
        self.assertEqual(len(lots), 1)

    def test_rebalance_check(self):
        self.tracker.open_position("ACME", 100, 50.0, "test")
        result = self.tracker.check_rebalance({"ACME": 0.20})
        self.assertIn("rebalance_needed", result)

    def test_partial_close(self):
        self.tracker.open_position("ACME", 100, 50.0, "test")
        self.tracker.close_position("ACME", 55.0, quantity=50)
        pos = self.tracker.get_position("ACME")
        self.assertIsNotNone(pos)
        self.assertEqual(pos["quantity"], 50)

    def test_insufficient_cash(self):
        result = self.tracker.open_position("ACME", 100000, 50.0, "test")
        self.assertEqual(result["status"], "rejected")


# =============================================================================
# Safety Controls Tests
# =============================================================================


class TestSafetyControls(unittest.TestCase):
    def test_live_trading_disabled(self):
        self.assertFalse(LIVE_TRADING_ENABLED)

    def test_gateway_paper_mode_default(self):
        sim = PaperTradingSimulator()
        gw = TradingGateway(sim)
        self.assertEqual(gw.get_mode(), "paper")

    def test_gateway_go_live_blocked(self):
        sim = PaperTradingSimulator()
        gw = TradingGateway(sim)
        result = gw.attempt_go_live()
        self.assertEqual(result["status"], "blocked")

    def test_profitability_proof_required(self):
        sim = PaperTradingSimulator()
        gw = TradingGateway(sim)
        result = gw.require_profitability_proof()
        self.assertFalse(result["profitability_proven"])

    def test_emergency_stop_blocks_trades(self):
        engine = TradingBotEngine()
        engine.emergency_stop()
        result = engine.execute_trade("ACME", "buy", 10, 50, "test", 0.5)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "emergency_stop_active")

    def test_audit_trail(self):
        engine = TradingBotEngine()
        engine.ingest_market_data(_make_market_data())
        trail = engine.get_audit_trail()
        self.assertGreater(len(trail), 0)

    def test_max_position_default(self):
        rm = RiskManager()
        self.assertEqual(rm.max_position_pct, 0.05)

    def test_max_daily_loss_default(self):
        rm = RiskManager()
        self.assertEqual(rm.max_daily_loss_pct, 0.02)


# =============================================================================
# Account Integration Hooks Tests
# =============================================================================


class TestAccountIntegrationHooks(unittest.TestCase):
    def test_brokerage_disabled_by_default(self):
        adapter = BrokerageAdapter("td_ameritrade")
        self.assertFalse(adapter.enabled)

    def test_brokerage_connect_disabled(self):
        adapter = BrokerageAdapter("interactive_brokers")
        result = adapter.connect()
        self.assertEqual(result["status"], "disabled")

    def test_brokerage_submit_disabled(self):
        adapter = BrokerageAdapter("alpaca")
        result = adapter.submit_order("ACME", "buy", 10, 50.0)
        self.assertEqual(result["status"], "disabled")

    def test_coinbase_disabled_by_default(self):
        adapter = CoinbaseAdapter()
        self.assertFalse(adapter.enabled)

    def test_coinbase_connect_disabled(self):
        adapter = CoinbaseAdapter()
        result = adapter.connect()
        self.assertEqual(result["status"], "disabled")

    def test_coinbase_submit_disabled(self):
        adapter = CoinbaseAdapter()
        result = adapter.submit_order("BTC-USD", "buy", 0.1, 50000.0)
        self.assertEqual(result["status"], "disabled")

    def test_gateway_registers_brokerage(self):
        sim = PaperTradingSimulator()
        gw = TradingGateway(sim)
        adapter = BrokerageAdapter("alpaca")
        result = gw.register_brokerage(adapter)
        self.assertEqual(result["status"], "registered")

    def test_gateway_registers_coinbase(self):
        sim = PaperTradingSimulator()
        gw = TradingGateway(sim)
        adapter = CoinbaseAdapter()
        result = gw.register_coinbase(adapter)
        self.assertEqual(result["status"], "registered")

    def test_gateway_routes_to_paper(self):
        sim = PaperTradingSimulator(initial_capital=100000)
        gw = TradingGateway(sim)
        result = gw.submit_order("ACME", "buy", 10, 50.0, "test", 0.5)
        self.assertEqual(result["status"], "filled")

    def test_gateway_audit_log(self):
        sim = PaperTradingSimulator()
        gw = TradingGateway(sim)
        gw.attempt_go_live()
        log = gw.get_audit_log()
        self.assertGreater(len(log), 0)


# =============================================================================
# AI Optimization Layer Tests
# =============================================================================


class TestAIOptimizationLayer(unittest.TestCase):
    def setUp(self):
        self.ai = AIOptimizationLayer(learning_rate=0.01)

    def test_record_outcome(self):
        result = self.ai.record_outcome("momentum", 0.05)
        self.assertEqual(result["strategy"], "momentum")
        self.assertEqual(result["total_trades"], 1)

    def test_detect_bull_regime(self):
        prices = [100 + i * 2 for i in range(25)]
        result = self.ai.detect_market_regime(prices)
        self.assertEqual(result["regime"], "bull")

    def test_detect_bear_regime(self):
        prices = [100 - i * 2 for i in range(25)]
        result = self.ai.detect_market_regime(prices)
        self.assertEqual(result["regime"], "bear")

    def test_detect_sideways(self):
        prices = [100.0] * 25
        result = self.ai.detect_market_regime(prices)
        self.assertEqual(result["regime"], "sideways")

    def test_optimize_weights(self):
        strategy_engine = TradingStrategyEngine()
        for _ in range(5):
            self.ai.record_outcome("momentum", 0.05)
            self.ai.record_outcome("mean_reversion", -0.02)
        result = self.ai.optimize_weights(strategy_engine)
        self.assertIn("momentum", result["adjustments"])

    def test_feature_importance(self):
        features = self.ai.get_feature_importance()
        self.assertIn("price", features)
        self.assertIn("volume", features)

    def test_update_feature_importance(self):
        result = self.ai.update_feature_importance("price", 0.3)
        self.assertEqual(result["importance"], 0.3)

    def test_strategy_performance(self):
        self.ai.record_outcome("momentum", 0.05)
        self.ai.record_outcome("momentum", 0.03)
        perf = self.ai.get_strategy_performance()
        self.assertIn("momentum", perf)
        self.assertEqual(perf["momentum"]["trades"], 2)

    def test_strategy_rotation_recommendation(self):
        self.ai.record_outcome("momentum", 0.05)
        self.ai.record_outcome("mean_reversion", 0.01)
        result = self.ai.recommend_strategy_rotation()
        self.assertEqual(result["best_strategy"], "momentum")

    def test_insufficient_data_rotation(self):
        result = self.ai.recommend_strategy_rotation()
        self.assertEqual(result["recommendation"], "insufficient_data")


# =============================================================================
# Full Integration / Orchestrator Tests
# =============================================================================


class TestTradingBotEngine(unittest.TestCase):
    def setUp(self):
        self.engine = TradingBotEngine(initial_capital=100000.0)

    def test_ingest_and_analyze(self):
        data = _make_market_data(price=40.0)
        self.engine.ingest_market_data(data)
        result = self.engine.analyze_takeover(data)
        self.assertTrue(result["is_candidate"])

    def test_generate_signals(self):
        data = _make_market_data(price=50.0)
        prices = [48 + i for i in range(10)]
        signals = self.engine.generate_signals(data, prices)
        self.assertGreater(len(signals), 0)

    def test_execute_paper_trade(self):
        result = self.engine.execute_trade("ACME", "buy", 10, 50.0, "test", 0.8)
        self.assertEqual(result["status"], "filled")

    def test_status(self):
        status = self.engine.get_status()
        self.assertFalse(status["live_trading_enabled"])
        self.assertEqual(status["mode"], "paper")

    def test_position_size_limit_enforced(self):
        # 10000 shares * 50 = 500000 > 5% of 100000
        result = self.engine.execute_trade("ACME", "buy", 10000, 50.0, "test", 0.8)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "position_size_limit_exceeded")


if __name__ == "__main__":
    unittest.main()
