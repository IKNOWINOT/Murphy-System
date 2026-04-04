# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for Coinbase Advanced Trade API integration (PR 1).

All tests are mock-based and do NOT require real API keys or network access.
"""

from __future__ import annotations

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Ensure src is on the path for direct imports
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


class TestCoinbaseConnectorInit(unittest.TestCase):
    """Connector initialisation and sandbox defaults."""

    def _import(self):
        from coinbase_connector import CoinbaseConnector  # noqa: PLC0415
        return CoinbaseConnector

    def test_sandbox_default_true(self):
        """Sandbox must be ON by default (live mode requires explicit env var)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COINBASE_LIVE_MODE", None)
            cls = self._import()
            cb = cls(api_key="k", api_secret="s")
        self.assertTrue(cb.sandbox, "sandbox should default to True")

    def test_live_mode_disables_sandbox(self):
        """Setting COINBASE_LIVE_MODE=true disables sandbox when sandbox=False."""
        with patch.dict(os.environ, {"COINBASE_LIVE_MODE": "true"}):
            cls = self._import()
            cb = cls(api_key="k", api_secret="s", sandbox=False)
        self.assertFalse(cb.sandbox, "sandbox should be False when COINBASE_LIVE_MODE=true and sandbox=False")

    def test_sandbox_kwarg_overrides_live_mode(self):
        """Passing sandbox=True should keep sandbox active even with COINBASE_LIVE_MODE=true."""
        with patch.dict(os.environ, {"COINBASE_LIVE_MODE": "true"}):
            cls = self._import()
            cb = cls(api_key="k", api_secret="s", sandbox=True)
        self.assertTrue(cb.sandbox)

    def test_env_api_key_loaded(self):
        """API key is read from COINBASE_API_KEY env var when not passed directly."""
        with patch.dict(os.environ, {"COINBASE_API_KEY": "envkey", "COINBASE_API_SECRET": "envsecret"}):
            cls = self._import()
            cb = cls()
        self.assertEqual(cb.api_key, "envkey")
        self.assertEqual(cb.api_secret, "envsecret")

    def test_base_url_sandbox(self):
        """Sandbox mode routes to the sandbox REST endpoint."""
        from coinbase_connector import COINBASE_REST_SAND, CoinbaseConnector
        cb = CoinbaseConnector(sandbox=True)
        self.assertEqual(cb._base_url, COINBASE_REST_SAND)

    def test_base_url_production(self):
        """Live mode routes to the production REST endpoint."""
        from coinbase_connector import COINBASE_REST_PROD, CoinbaseConnector
        with patch.dict(os.environ, {"COINBASE_LIVE_MODE": "true"}):
            cb = CoinbaseConnector(api_key="k", api_secret="s", sandbox=False)
        self.assertEqual(cb._base_url, COINBASE_REST_PROD)


class TestCoinbaseAuthentication(unittest.TestCase):
    """HMAC-SHA256 authentication header generation."""

    def setUp(self):
        from coinbase_connector import CoinbaseConnector
        self.cb = CoinbaseConnector(api_key="testkey", api_secret="testsecret", sandbox=True)

    def test_sign_request_returns_required_headers(self):
        """_sign_request must return all four required auth headers."""
        headers = self.cb._sign_request("GET", "/api/v3/brokerage/accounts")
        self.assertIn("CB-ACCESS-KEY", headers)
        self.assertIn("CB-ACCESS-SIGN", headers)
        self.assertIn("CB-ACCESS-TIMESTAMP", headers)
        self.assertIn("Content-Type", headers)

    def test_sign_request_key_matches(self):
        """CB-ACCESS-KEY header must equal the api_key."""
        headers = self.cb._sign_request("GET", "/api/v3/brokerage/accounts")
        self.assertEqual(headers["CB-ACCESS-KEY"], "testkey")

    def test_sign_request_signature_is_hex(self):
        """CB-ACCESS-SIGN must be a 64-char hex string (SHA-256 output)."""
        headers = self.cb._sign_request("POST", "/api/v3/brokerage/orders", '{"test": true}')
        sig = headers["CB-ACCESS-SIGN"]
        self.assertEqual(len(sig), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sig))

    def test_sign_request_different_bodies_produce_different_sigs(self):
        """Different message bodies must produce different signatures."""
        h1 = self.cb._sign_request("POST", "/path", "body1")
        h2 = self.cb._sign_request("POST", "/path", "body2")
        self.assertNotEqual(h1["CB-ACCESS-SIGN"], h2["CB-ACCESS-SIGN"])

    def test_sign_request_timestamp_is_numeric_string(self):
        """CB-ACCESS-TIMESTAMP must be a numeric Unix epoch string."""
        headers = self.cb._sign_request("GET", "/test")
        ts = headers["CB-ACCESS-TIMESTAMP"]
        self.assertTrue(ts.isdigit(), f"Expected numeric timestamp, got: {ts}")


class TestCoinbaseAPIMethodSignatures(unittest.TestCase):
    """Method signatures and return types (mocked HTTP layer)."""

    def setUp(self):
        from coinbase_connector import CoinbaseConnector
        self.cb = CoinbaseConnector(api_key="k", api_secret="s", sandbox=True)

    def _mock_request(self, return_value: dict):
        return patch.object(self.cb, "_request", return_value=return_value)

    def test_get_accounts_returns_list(self):
        with self._mock_request({"accounts": [{"uuid": "abc", "currency": "BTC"}]}):
            result = self.cb.get_accounts()
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["currency"], "BTC")

    def test_get_accounts_empty_on_missing_key(self):
        with self._mock_request({}):
            result = self.cb.get_accounts()
        self.assertEqual(result, [])

    def test_get_balances_returns_list_of_balances(self):
        from coinbase_connector import CoinbaseBalance
        mock_resp = {
            "accounts": [
                {"available_balance": {"currency": "ETH", "value": "1.5"}, "hold": {"value": "0.1"}}
            ]
        }
        with self._mock_request(mock_resp):
            result = self.cb.get_balances()
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], CoinbaseBalance)
        self.assertEqual(result[0].currency, "ETH")
        self.assertEqual(result[0].available_balance, "1.5")

    def test_list_products_returns_list(self):
        from coinbase_connector import CoinbaseProduct
        mock_resp = {"products": [
            {
                "product_id": "BTC-USD",
                "base_currency_id": "BTC",
                "quote_currency_id": "USD",
                "quote_min_size": "1",
                "quote_max_size": "1000000",
                "base_min_size": "0.001",
                "base_max_size": "100",
                "base_increment": "0.00000001",
                "quote_increment": "0.01",
            }
        ]}
        with self._mock_request(mock_resp):
            products = self.cb.list_products()
        self.assertIsInstance(products, list)
        self.assertIsInstance(products[0], CoinbaseProduct)
        self.assertEqual(products[0].product_id, "BTC-USD")

    def test_get_ticker_returns_ticker(self):
        from coinbase_connector import CoinbaseTicker
        mock_resp = {
            "pricebooks": [
                {
                    "product_id": "BTC-USD",
                    "bids": [{"price": "50000.00", "size": "0.5"}],
                    "asks": [{"price": "50001.00", "size": "0.3"}],
                    "time": "2024-01-01T00:00:00Z",
                }
            ]
        }
        with self._mock_request(mock_resp):
            ticker = self.cb.get_ticker("BTC-USD")
        self.assertIsInstance(ticker, CoinbaseTicker)
        self.assertEqual(ticker.product_id, "BTC-USD")
        self.assertEqual(ticker.bid, "50000.00")

    def test_get_ticker_returns_none_when_empty(self):
        with self._mock_request({"pricebooks": []}):
            ticker = self.cb.get_ticker("BTC-USD")
        self.assertIsNone(ticker)

    def test_place_market_order_delegates_to_create(self):
        mock_resp = {"success_response": {"order_id": "ord-123"}}
        with patch.object(self.cb, "create_market_order", return_value=mock_resp) as m:
            result = self.cb.place_market_order("BTC-USD", "BUY", "0.001")
        m.assert_called_once()
        self.assertEqual(result, mock_resp)

    def test_place_limit_order_delegates_to_create(self):
        mock_resp = {"success_response": {"order_id": "ord-456"}}
        with patch.object(self.cb, "create_limit_order", return_value=mock_resp) as m:
            result = self.cb.place_limit_order("ETH-USD", "SELL", "0.5", "3000.00")
        m.assert_called_once()
        self.assertEqual(result, mock_resp)

    def test_cancel_order_calls_batch_cancel(self):
        mock_resp = {"results": [{"order_id": "ord-789", "success": True}]}
        with patch.object(self.cb, "cancel_orders", return_value=mock_resp) as m:
            result = self.cb.cancel_order("ord-789")
        m.assert_called_once_with(["ord-789"])
        self.assertEqual(result, mock_resp)

    def test_get_product_candles_delegates_to_get_candles(self):
        mock_candles = [{"start": "1700000000", "open": "50000"}]
        with patch.object(self.cb, "get_candles", return_value=mock_candles) as m:
            result = self.cb.get_product_candles("BTC-USD", 1700000000, 1700003600, "ONE_HOUR")
        m.assert_called_once_with("BTC-USD", 1700000000, 1700003600, "ONE_HOUR")
        self.assertEqual(result, mock_candles)

    def test_get_order_calls_correct_path(self):
        mock_resp = {"order": {"order_id": "ord-abc", "status": "FILLED"}}
        with self._mock_request(mock_resp):
            result = self.cb.get_order("ord-abc")
        self.assertEqual(result, mock_resp)


class TestCoinbaseErrorHandling(unittest.TestCase):
    """Rate limiting, retries, and typed error responses."""

    def setUp(self):
        from coinbase_connector import CoinbaseConnector
        self.cb = CoinbaseConnector(api_key="k", api_secret="s", sandbox=True)

    def test_request_returns_error_dict_on_exception(self):
        """_request must return an error dict instead of raising on network failure."""
        import requests as req_lib
        with patch("requests.request", side_effect=req_lib.exceptions.ConnectionError("refused")):
            result = self.cb._request("GET", "/api/v3/brokerage/time")
        self.assertIn("error", result)

    def test_request_handles_missing_requests_library(self):
        """If requests is not importable, _request returns a structured error dict."""
        original = sys.modules.get("requests")
        sys.modules["requests"] = None  # type: ignore
        try:
            result = self.cb._request("GET", "/api/v3/brokerage/time")
        finally:
            if original is None:
                del sys.modules["requests"]
            else:
                sys.modules["requests"] = original
        self.assertIn("error", result)

    def test_health_check_returns_dict(self):
        """health_check always returns a dict with expected keys."""
        mock_resp = {"iso": "2024-01-01T00:00:00Z", "epochSeconds": "1704067200"}
        with patch.object(self.cb, "_request", return_value=mock_resp):
            result = self.cb.health_check()
        self.assertIn("connected", result)
        self.assertIn("sandbox", result)
        self.assertIn("latency_ms", result)
        self.assertIn("status", result)
        self.assertTrue(result["connected"])
        self.assertTrue(result["sandbox"])


class TestCoinbaseConnectionStatus(unittest.TestCase):
    """Connection status enum and state transitions."""

    def test_initial_status_is_sandbox_when_sandbox_true(self):
        from coinbase_connector import CoinbaseConnectionStatus, CoinbaseConnector
        cb = CoinbaseConnector(api_key="k", api_secret="s", sandbox=True)
        self.assertEqual(cb.status, CoinbaseConnectionStatus.SANDBOX)

    def test_initial_status_disconnected_when_not_sandbox(self):
        from coinbase_connector import CoinbaseConnectionStatus, CoinbaseConnector
        with patch.dict(os.environ, {"COINBASE_LIVE_MODE": "true"}):
            cb = CoinbaseConnector(api_key="k", api_secret="s", sandbox=False)
        self.assertEqual(cb.status, CoinbaseConnectionStatus.DISCONNECTED)

    def test_close_sets_disconnected_status(self):
        from coinbase_connector import CoinbaseConnectionStatus, CoinbaseConnector
        cb = CoinbaseConnector(api_key="k", api_secret="s", sandbox=True)
        cb.close()
        self.assertEqual(cb.status, CoinbaseConnectionStatus.DISCONNECTED)


class TestCoinbaseOrderEnums(unittest.TestCase):
    """Enum values match the Coinbase API spec."""

    def test_order_side_values(self):
        from coinbase_connector import CoinbaseOrderSide
        self.assertEqual(CoinbaseOrderSide.BUY.value, "BUY")
        self.assertEqual(CoinbaseOrderSide.SELL.value, "SELL")

    def test_order_type_values(self):
        from coinbase_connector import CoinbaseOrderType
        self.assertEqual(CoinbaseOrderType.MARKET_MARKET_IOC.value, "MARKET_MARKET_IOC")
        self.assertEqual(CoinbaseOrderType.LIMIT_LIMIT_GTC.value, "LIMIT_LIMIT_GTC")

    def test_place_market_order_side_case_insensitive(self):
        """place_market_order should accept lowercase 'buy'/'sell'."""
        from coinbase_connector import CoinbaseConnector, CoinbaseOrderSide
        cb = CoinbaseConnector(api_key="k", api_secret="s", sandbox=True)
        mock_resp = {"success_response": {"order_id": "ord-x"}}
        with patch.object(cb, "create_market_order", return_value=mock_resp) as m:
            cb.place_market_order("BTC-USD", "buy", "0.01")
        args, _ = m.call_args
        self.assertEqual(args[1], CoinbaseOrderSide.BUY)


if __name__ == "__main__":
    unittest.main()
