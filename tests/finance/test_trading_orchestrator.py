"""
Tests for Trading Orchestrator — Murphy System

Covers:
- Mode switching (paper / live)
- Signal aggregation and conflict resolution
- Confidence-weighted voting
- Main loop cycle
- Health checking
- State persistence
"""

import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trading_orchestrator import (
    TradingOrchestrator,
    TradingMode,
    OrchestratorState,
    AggregatedSignal,
)


class TestModeSwitching(unittest.TestCase):

    def test_default_mode_is_paper(self):
        orch = TradingOrchestrator()
        self.assertEqual(orch._mode, TradingMode.PAPER)

    def test_switch_to_paper_always_succeeds(self):
        orch   = TradingOrchestrator(mode=TradingMode.PAPER)
        result = orch.switch_mode(TradingMode.PAPER)
        self.assertTrue(result["success"])

    def test_switch_to_live_without_live_engine_fails(self):
        orch   = TradingOrchestrator()
        result = orch.switch_mode(TradingMode.LIVE)
        self.assertFalse(result["success"])

    def test_switch_to_live_fails_when_gates_fail(self):
        mock_live = MagicMock()
        mock_gate = MagicMock()
        mock_gate.all_pass = False
        mock_gate.to_dict.return_value = {}
        mock_live.check_gates.return_value = mock_gate
        orch   = TradingOrchestrator(live_engine=mock_live)
        result = orch.switch_mode(TradingMode.LIVE)
        self.assertFalse(result["success"])

    def test_switch_to_live_succeeds_when_gates_pass(self):
        mock_live = MagicMock()
        mock_gate = MagicMock()
        mock_gate.all_pass = True
        mock_live.check_gates.return_value = mock_gate
        orch   = TradingOrchestrator(live_engine=mock_live)
        result = orch.switch_mode(TradingMode.LIVE)
        self.assertTrue(result["success"])
        self.assertEqual(orch._mode, TradingMode.LIVE)

    def test_mode_reflected_in_status(self):
        orch   = TradingOrchestrator(mode=TradingMode.PAPER)
        status = orch.get_status()
        self.assertEqual(status["mode"], "paper")


class TestSignalAggregation(unittest.TestCase):

    def setUp(self):
        self.orch = TradingOrchestrator()

    def _sig(self, sid, action, conf, pid="BTC-USD"):
        return {"strategy_id": sid, "pair": pid, "action": action, "confidence": conf}

    def test_unanimous_buy_gives_buy(self):
        agg = self.orch._aggregate_signals([self._sig("s1","buy",0.8), self._sig("s2","buy",0.7)])
        self.assertEqual(agg[0].action, "buy")

    def test_unanimous_sell_gives_sell(self):
        agg = self.orch._aggregate_signals([self._sig("s1","sell",0.9), self._sig("s2","sell",0.6)])
        self.assertEqual(agg[0].action, "sell")

    def test_conflict_detected(self):
        agg = self.orch._aggregate_signals([self._sig("s1","buy",0.7), self._sig("s2","sell",0.7)])
        self.assertTrue(agg[0].conflict)

    def test_confidence_weighted_voting(self):
        signals = [
            self._sig("s1","sell",0.3),
            self._sig("s2","sell",0.3),
            self._sig("s3","buy", 0.9),
        ]
        agg = self.orch._aggregate_signals(signals)
        self.assertEqual(agg[0].action, "buy")

    def test_empty_signals_returns_empty(self):
        self.assertEqual(self.orch._aggregate_signals([]), [])

    def test_multiple_products_aggregated_separately(self):
        signals = [self._sig("s1","buy",0.8,"BTC-USD"), self._sig("s2","sell",0.8,"ETH-USD")]
        agg     = self.orch._aggregate_signals(signals)
        self.assertEqual(len(agg), 2)

    def test_contributing_strategies_listed(self):
        agg = self.orch._aggregate_signals([
            self._sig("momentum","buy",0.8),
            self._sig("breakout","buy",0.7),
        ])
        self.assertIn("momentum", agg[0].contributing_strategies)
        self.assertIn("breakout", agg[0].contributing_strategies)

    def test_aggregated_signal_to_dict_keys(self):
        agg = self.orch._aggregate_signals([self._sig("s1","buy",0.8)])
        d   = agg[0].to_dict()
        for key in ("product_id","action","confidence","contributing"):
            self.assertIn(key, d)


class TestStrategyExecution(unittest.TestCase):

    def test_strategy_signals_collected(self):
        mock_s = MagicMock()
        mock_s.strategy_id = "test"
        mock_s.generate_signal.return_value = {"strategy_id":"test","pair":"BTC-USD","action":"buy","confidence":0.75}
        orch    = TradingOrchestrator(strategies=[mock_s])
        signals = orch._run_strategies({})
        self.assertEqual(len(signals), 1)

    def test_broken_strategy_handled_gracefully(self):
        mock_s = MagicMock()
        mock_s.generate_signal.side_effect = RuntimeError("crash")
        orch    = TradingOrchestrator(strategies=[mock_s])
        signals = orch._run_strategies({})
        self.assertEqual(signals, [])


class TestHealthCheck(unittest.TestCase):

    def test_health_check_returns_non_empty_list(self):
        orch   = TradingOrchestrator()
        health = orch.check_health()
        self.assertGreater(len(health), 0)

    def test_health_items_have_required_keys(self):
        for item in TradingOrchestrator().check_health():
            d = item.to_dict()
            self.assertIn("name", d)
            self.assertIn("healthy", d)

    def test_unconfigured_market_data_unhealthy(self):
        health = TradingOrchestrator(market_data_feed=None).check_health()
        mdf    = next((h for h in health if h.name=="market_data"), None)
        self.assertFalse(mdf.healthy)

    def test_unconfigured_risk_manager_unhealthy(self):
        health = TradingOrchestrator(risk_manager=None).check_health()
        rm     = next((h for h in health if h.name=="risk_manager"), None)
        self.assertFalse(rm.healthy)


class TestPortfolioAndTrades(unittest.TestCase):

    def test_get_portfolio_keys(self):
        p = TradingOrchestrator().get_portfolio()
        self.assertIn("total_value_usd", p)

    def test_trade_history_is_list(self):
        self.assertIsInstance(TradingOrchestrator().get_trade_history(), list)

    def test_todays_trades_is_list(self):
        self.assertIsInstance(TradingOrchestrator().get_todays_trades(), list)

    def test_signal_history_is_list(self):
        self.assertIsInstance(TradingOrchestrator().get_signal_history(), list)


class TestStatePersistence(unittest.TestCase):

    def test_persist_and_restore(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            state_file = tf.name
        try:
            orch = TradingOrchestrator(state_file=state_file)
            orch._loop_count = 42
            orch._portfolio["total_value_usd"] = 99_999.0
            orch._persist_state()
            orch2 = TradingOrchestrator(state_file=state_file)
            orch2._restore_state()
            self.assertEqual(orch2._loop_count, 42)
        finally:
            os.unlink(state_file)


class TestOrchestratorLifecycle(unittest.TestCase):

    def test_start_and_stop(self):
        orch = TradingOrchestrator(loop_interval=1000)
        orch.start()
        self.assertEqual(orch.get_status()["state"], OrchestratorState.RUNNING.value)
        orch.stop()
        self.assertEqual(orch.get_status()["state"], OrchestratorState.STOPPED.value)


if __name__ == "__main__":
    unittest.main()
