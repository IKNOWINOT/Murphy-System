"""
Tests for Live Trading Engine — Murphy System

Covers:
- 5-gate system (all gates must pass for live trading)
- Gate FAIL scenarios
- Order execution flow
- Stop-loss / take-profit placement
- Graceful shutdown
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from live_trading_engine import (
    LiveTradingEngine,
    GateStatus,
    GateCheckResult,
    OrderType,
    OrderSide,
    EngineState,
)


def _make_engine(
    coinbase_live: bool      = False,
    live_enabled:  bool      = False,
    graduated:     bool      = False,
    estop_trigger: bool      = False,
    api_valid:     bool      = True,
) -> LiveTradingEngine:
    """Build a LiveTradingEngine with mocked dependencies."""
    mock_coinbase = MagicMock()
    mock_coinbase.test_connection.return_value = api_valid
    mock_coinbase.place_market_order.return_value = {
        "order_id":     "cb-order-123",
        "filled_size":  "0.01",
        "average_price": "50000",
        "status":       "filled",
    }

    mock_graduation = MagicMock()
    mock_graduation.get_status.return_value = {"graduated": graduated}

    mock_emergency = MagicMock()
    mock_emergency.is_triggered.return_value = estop_trigger

    engine = LiveTradingEngine(
        coinbase_connector        = mock_coinbase,
        graduation_controller     = mock_graduation,
        emergency_stop_controller = mock_emergency,
    )

    # Patch env-var driven flags at module level
    import live_trading_engine as lte
    lte._COINBASE_LIVE_MODE   = coinbase_live
    lte._LIVE_TRADING_ENABLED = live_enabled

    return engine


class TestGateSystem(unittest.TestCase):
    """5-gate pre-trade safety check."""

    def test_all_gates_fail_by_default(self):
        engine = _make_engine()
        result = engine.check_gates()
        self.assertFalse(result.all_pass)

    def test_gate1_coinbase_live_required(self):
        engine = _make_engine(
            coinbase_live=False,
            live_enabled=True, graduated=True, estop_trigger=False, api_valid=True,
        )
        result = engine.check_gates()
        self.assertEqual(result.gate_coinbase_live, GateStatus.FAIL)
        self.assertFalse(result.all_pass)

    def test_gate2_live_trading_enabled_required(self):
        engine = _make_engine(
            coinbase_live=True,
            live_enabled=False, graduated=True, estop_trigger=False, api_valid=True,
        )
        result = engine.check_gates()
        self.assertEqual(result.gate_live_enabled, GateStatus.FAIL)
        self.assertFalse(result.all_pass)

    def test_gate3_graduation_required(self):
        engine = _make_engine(
            coinbase_live=True, live_enabled=True,
            graduated=False, estop_trigger=False, api_valid=True,
        )
        result = engine.check_gates()
        self.assertEqual(result.gate_graduated, GateStatus.FAIL)
        self.assertFalse(result.all_pass)

    def test_gate4_emergency_stop_must_be_clear(self):
        engine = _make_engine(
            coinbase_live=True, live_enabled=True, graduated=True,
            estop_trigger=True, api_valid=True,
        )
        result = engine.check_gates()
        self.assertEqual(result.gate_emergency_stop, GateStatus.FAIL)
        self.assertFalse(result.all_pass)

    def test_gate5_api_connection_required(self):
        engine = _make_engine(
            coinbase_live=True, live_enabled=True, graduated=True,
            estop_trigger=False, api_valid=False,
        )
        result = engine.check_gates()
        self.assertEqual(result.gate_api_valid, GateStatus.FAIL)
        self.assertFalse(result.all_pass)

    def test_all_gates_pass(self):
        engine = _make_engine(
            coinbase_live=True, live_enabled=True, graduated=True,
            estop_trigger=False, api_valid=True,
        )
        result = engine.check_gates()
        self.assertTrue(result.all_pass)

    def test_single_gate_failure_blocks_all(self):
        """Any one FAIL means all_pass is False."""
        for kwarg in [
            {"coinbase_live": False},
            {"live_enabled":  False},
            {"graduated":     False},
            {"estop_trigger": True},
            {"api_valid":     False},
        ]:
            defaults = dict(coinbase_live=True, live_enabled=True, graduated=True,
                            estop_trigger=False, api_valid=True)
            defaults.update(kwarg)
            engine = _make_engine(**defaults)
            result = engine.check_gates()
            self.assertFalse(result.all_pass, f"Expected all_pass=False when {kwarg}")

    def test_gate_check_result_to_dict(self):
        engine = _make_engine()
        d = engine.check_gates().to_dict()
        self.assertIn("all_pass", d)
        self.assertIn("gate_coinbase_live", d)
        self.assertIn("checked_at", d)


class TestExecutionBlocking(unittest.TestCase):
    """Orders are blocked when gates do not pass."""

    def test_blocked_when_gates_fail(self):
        engine = _make_engine()   # all gates fail
        result = engine.execute_signal(
            product_id="BTC-USD", side="buy", size=0.01,
        )
        self.assertFalse(result["success"])
        self.assertTrue(result["blocked"])

    def test_not_blocked_when_all_gates_pass(self):
        engine = _make_engine(
            coinbase_live=True, live_enabled=True, graduated=True,
            estop_trigger=False, api_valid=True,
        )
        result = engine.execute_signal(
            product_id="BTC-USD", side="buy", size=0.01,
        )
        self.assertTrue(result["success"])
        self.assertIn("order", result)


class TestOrderExecution(unittest.TestCase):
    """Order execution when all gates pass."""

    def setUp(self):
        self.engine = _make_engine(
            coinbase_live=True, live_enabled=True, graduated=True,
            estop_trigger=False, api_valid=True,
        )

    def test_market_order_returns_filled(self):
        result = self.engine.execute_signal(
            product_id = "BTC-USD",
            side       = "buy",
            size       = 0.01,
            order_type = "market",
        )
        self.assertTrue(result["success"])
        order = result["order"]
        self.assertEqual(order["status"], "filled")
        self.assertEqual(order["product_id"], "BTC-USD")

    def test_order_is_stored_in_history(self):
        self.engine.execute_signal(product_id="ETH-USD", side="sell", size=0.1)
        orders = self.engine.get_orders()
        self.assertGreaterEqual(len(orders), 1)

    def test_audit_log_is_populated(self):
        self.engine.execute_signal(product_id="SOL-USD", side="buy", size=1.0)
        log = self.engine.get_audit_log()
        self.assertTrue(len(log) > 0)
        events = [e["event"] for e in log]
        self.assertIn("gate_check", events)
        self.assertIn("order_executed", events)

    def test_slippage_calculated(self):
        result = self.engine.execute_signal(
            product_id  = "BTC-USD",
            side        = "buy",
            size        = 0.01,
            limit_price = 50000.0,
        )
        order = result["order"]
        # slippage_pct should be present (may be 0 if prices match)
        self.assertIn("slippage_pct", order)

    def test_stop_loss_placement_attempted(self):
        result = self.engine.execute_signal(
            product_id = "BTC-USD",
            side       = "buy",
            size       = 0.01,
            stop_loss  = 48000.0,
        )
        self.assertTrue(result["success"])
        # SL order method was called on coinbase
        self.engine._coinbase.place_stop_limit_order.assert_called_once()

    def test_take_profit_placement_attempted(self):
        result = self.engine.execute_signal(
            product_id  = "BTC-USD",
            side        = "buy",
            size        = 0.01,
            take_profit = 55000.0,
        )
        self.assertTrue(result["success"])
        self.engine._coinbase.place_limit_order.assert_called_once()


class TestEngineLifecycle(unittest.TestCase):
    """Start / stop lifecycle."""

    def test_start_changes_state_to_running(self):
        engine = _make_engine()
        engine.start()
        status = engine.get_status()
        self.assertEqual(status["state"], EngineState.RUNNING.value)
        engine.stop(close_all=False)

    def test_stop_changes_state_to_stopped(self):
        engine = _make_engine()
        engine.start()
        engine.stop(close_all=False)
        status = engine.get_status()
        self.assertEqual(status["state"], EngineState.STOPPED.value)

    def test_get_positions_returns_list(self):
        engine = _make_engine()
        positions = engine.get_positions()
        self.assertIsInstance(positions, list)


if __name__ == "__main__":
    unittest.main()
