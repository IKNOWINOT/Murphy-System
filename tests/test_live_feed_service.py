# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for Live Market Data Feed Service (src/live_feed_service.py).

All tests are mock-based and do NOT require real API keys or network access.
"""

from __future__ import annotations

import os
import sys
import threading
import types
import unittest
from dataclasses import asdict
from unittest.mock import MagicMock, patch

# Ensure src is on the path for direct imports
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_coinbase(price: float = 50000.0, sandbox: bool = True):
    """Return a MagicMock that looks like CoinbaseConnector."""
    cb = MagicMock()
    cb.sandbox = sandbox
    from live_feed_service import LiveQuote, AssetClass, FeedProvider

    ticker = MagicMock()
    ticker.price = price
    ticker.best_bid = price - 10
    ticker.best_ask = price + 10
    ticker.volume_24h = 1234567.0
    ticker.price_percent_chg_24h = 2.5
    ticker.high_24h = price + 500
    ticker.low_24h = price - 500
    cb.get_ticker.return_value = ticker
    cb.get_product_candles.return_value = []
    return cb


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestAssetClassEnum(unittest.TestCase):
    """AssetClass enum values."""

    def test_crypto_value(self):
        from live_feed_service import AssetClass
        self.assertEqual(AssetClass.CRYPTO.value, "crypto")

    def test_equity_value(self):
        from live_feed_service import AssetClass
        self.assertEqual(AssetClass.EQUITY.value, "equity")

    def test_etf_value(self):
        from live_feed_service import AssetClass
        self.assertEqual(AssetClass.ETF.value, "etf")

    def test_index_value(self):
        from live_feed_service import AssetClass
        self.assertEqual(AssetClass.INDEX.value, "index")

    def test_forex_value(self):
        from live_feed_service import AssetClass
        self.assertEqual(AssetClass.FOREX.value, "forex")


class TestFeedProviderEnum(unittest.TestCase):
    """FeedProvider enum values."""

    def test_coinbase_value(self):
        from live_feed_service import FeedProvider
        self.assertEqual(FeedProvider.COINBASE.value, "coinbase")

    def test_yahoo_value(self):
        from live_feed_service import FeedProvider
        self.assertEqual(FeedProvider.YAHOO.value, "yahoo")

    def test_stub_value(self):
        from live_feed_service import FeedProvider
        self.assertEqual(FeedProvider.STUB.value, "stub")

    def test_all_providers_present(self):
        from live_feed_service import FeedProvider
        names = {p.value for p in FeedProvider}
        expected = {"coinbase", "ccxt", "yahoo", "alpaca", "alpha_vantage", "polygon", "stub"}
        self.assertEqual(names, expected)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestLiveQuoteDataclass(unittest.TestCase):
    """LiveQuote dataclass construction and defaults."""

    def test_basic_creation(self):
        from live_feed_service import LiveQuote
        q = LiveQuote(
            symbol="BTC-USD", asset_class="crypto",
            price=50000.0, bid=49990.0, ask=50010.0,
            volume_24h=1e6, change_pct_24h=2.5,
            high_24h=51000.0, low_24h=49000.0,
        )
        self.assertEqual(q.symbol, "BTC-USD")
        self.assertEqual(q.price, 50000.0)

    def test_timestamp_auto_populated(self):
        from live_feed_service import LiveQuote
        q = LiveQuote(
            symbol="ETH-USD", asset_class="crypto",
            price=3000.0, bid=2999.0, ask=3001.0,
            volume_24h=0.0, change_pct_24h=0.0,
            high_24h=0.0, low_24h=0.0,
        )
        self.assertTrue(q.timestamp, "timestamp should be auto-set")

    def test_market_cap_default(self):
        from live_feed_service import LiveQuote
        q = LiveQuote(
            symbol="SOL-USD", asset_class="crypto",
            price=100.0, bid=99.9, ask=100.1,
            volume_24h=0.0, change_pct_24h=0.0,
            high_24h=0.0, low_24h=0.0,
        )
        self.assertEqual(q.market_cap, 0.0)

    def test_sandbox_default_false(self):
        from live_feed_service import LiveQuote
        q = LiveQuote(
            symbol="BTC-USD", asset_class="crypto",
            price=1.0, bid=0.9, ask=1.1,
            volume_24h=0.0, change_pct_24h=0.0,
            high_24h=0.0, low_24h=0.0,
        )
        self.assertFalse(q.sandbox)

    def test_asdict_serialisable(self):
        from live_feed_service import LiveQuote
        q = LiveQuote(
            symbol="AAPL", asset_class="equity",
            price=185.0, bid=184.9, ask=185.1,
            volume_24h=1e7, change_pct_24h=-0.5,
            high_24h=186.0, low_24h=184.0,
        )
        d = asdict(q)
        self.assertIn("symbol", d)
        self.assertIn("price", d)


class TestLiveCandleDataclass(unittest.TestCase):
    """LiveCandle dataclass."""

    def test_basic_creation(self):
        from live_feed_service import LiveCandle
        c = LiveCandle(
            symbol="BTC-USD", open_time=1700000000,
            open=50000.0, high=51000.0, low=49000.0,
            close=50500.0, volume=1234.5, provider="coinbase",
        )
        self.assertEqual(c.close, 50500.0)
        self.assertEqual(c.provider, "coinbase")


class TestMarketMoverDataclass(unittest.TestCase):
    """MarketMover dataclass defaults."""

    def test_defaults(self):
        from live_feed_service import MarketMover
        m = MarketMover(symbol="NVDA")
        self.assertEqual(m.name, "")
        self.assertEqual(m.price, 0.0)
        self.assertEqual(m.change_pct, 0.0)
        self.assertEqual(m.volume, 0.0)
        self.assertEqual(m.asset_class, "")


# ---------------------------------------------------------------------------
# _is_crypto tests
# ---------------------------------------------------------------------------

class TestIsCrypto(unittest.TestCase):
    """LiveFeedService._is_crypto() classification logic."""

    def setUp(self):
        from live_feed_service import LiveFeedService
        self.feed = LiveFeedService()

    def test_btc_usd_is_crypto(self):
        self.assertTrue(self.feed._is_crypto("BTC-USD"))

    def test_eth_usd_is_crypto(self):
        self.assertTrue(self.feed._is_crypto("ETH-USD"))

    def test_sol_usdt_is_crypto(self):
        self.assertTrue(self.feed._is_crypto("SOL-USDT"))

    def test_matic_btc_is_crypto(self):
        self.assertTrue(self.feed._is_crypto("MATIC-BTC"))

    def test_bare_btc_is_crypto(self):
        self.assertTrue(self.feed._is_crypto("BTC"))

    def test_slash_notation_is_crypto(self):
        self.assertTrue(self.feed._is_crypto("BTC/USD"))

    def test_aapl_is_not_crypto(self):
        self.assertFalse(self.feed._is_crypto("AAPL"))

    def test_msft_is_not_crypto(self):
        self.assertFalse(self.feed._is_crypto("MSFT"))

    def test_spy_is_not_crypto(self):
        self.assertFalse(self.feed._is_crypto("SPY"))


# ---------------------------------------------------------------------------
# CryptoFeed tests
# ---------------------------------------------------------------------------

class TestCryptoFeedWithCoinbase(unittest.TestCase):
    """CryptoFeed using a mocked CoinbaseConnector."""

    def _make_feed(self, price=50000.0):
        from live_feed_service import CryptoFeed
        cb = _make_mock_coinbase(price)
        # get_ticker returns a plain dataclass-like object; patch asdict
        return CryptoFeed(coinbase_connector=cb), cb

    def test_get_quote_returns_live_quote(self):
        from live_feed_service import LiveQuote
        feed, cb = self._make_feed()
        # Mock asdict to return a dict representation
        with patch("live_feed_service.CryptoFeed._quote_via_coinbase") as mock_qvc:
            from live_feed_service import LiveQuote, FeedProvider, AssetClass
            mock_qvc.return_value = LiveQuote(
                symbol="BTC-USD", asset_class=AssetClass.CRYPTO.value,
                price=50000.0, bid=49990.0, ask=50010.0,
                volume_24h=1234567.0, change_pct_24h=2.5,
                high_24h=50500.0, low_24h=49500.0,
                provider=FeedProvider.COINBASE.value,
            )
            quote = feed.get_quote("BTC-USD")
        self.assertIsInstance(quote, LiveQuote)
        self.assertEqual(quote.price, 50000.0)
        self.assertEqual(quote.provider, "coinbase")

    def test_get_quote_normalises_slash_notation(self):
        from live_feed_service import CryptoFeed, LiveQuote, AssetClass, FeedProvider
        feed = CryptoFeed()
        with patch.object(feed, "_quote_via_coinbase", return_value=None), \
             patch.object(feed, "_quote_via_ccxt", return_value=None):
            quote = feed.get_quote("BTC/USD")
        self.assertEqual(quote.symbol, "BTC-USD")

    def test_get_quote_falls_back_to_stub_on_failure(self):
        from live_feed_service import CryptoFeed, FeedProvider
        feed = CryptoFeed()
        with patch.object(feed, "_quote_via_coinbase", return_value=None), \
             patch.object(feed, "_quote_via_ccxt", return_value=None):
            quote = feed.get_quote("XRP-USD")
        self.assertEqual(quote.provider, FeedProvider.STUB.value)
        self.assertEqual(quote.price, 0.0)

    def test_get_candles_returns_list(self):
        from live_feed_service import CryptoFeed
        feed = CryptoFeed()
        with patch.object(feed, "_candles_via_coinbase", return_value=[]), \
             patch.object(feed, "_candles_via_ccxt", return_value=[]):
            candles = feed.get_candles("BTC-USD")
        self.assertIsInstance(candles, list)

    def test_get_top_movers_returns_list(self):
        from live_feed_service import CryptoFeed
        feed = CryptoFeed()
        with patch.object(feed, "_movers_via_ccxt", return_value=[]):
            movers = feed.get_top_movers()
        self.assertIsInstance(movers, list)

    def test_stub_movers_length(self):
        from live_feed_service import CryptoFeed
        feed = CryptoFeed()
        movers = feed._stub_movers(3)
        self.assertEqual(len(movers), 3)


# ---------------------------------------------------------------------------
# EquityFeed tests
# ---------------------------------------------------------------------------

class TestEquityFeedYFinance(unittest.TestCase):
    """EquityFeed with mocked yfinance."""

    def _mock_yfinance_ticker(self, price=185.0):
        mock_yf = MagicMock()
        fast_info = MagicMock()
        fast_info.last_price = price
        fast_info.bid = price - 0.1
        fast_info.ask = price + 0.1
        fast_info.three_month_average_volume = 1e7
        fast_info.day_high = price + 2
        fast_info.day_low = price - 2
        fast_info.market_cap = 2.8e12
        mock_ticker = MagicMock()
        mock_ticker.fast_info = fast_info
        mock_yf.Ticker.return_value = mock_ticker
        return mock_yf

    def test_get_quote_via_yfinance(self):
        from live_feed_service import EquityFeed, FeedProvider
        feed = EquityFeed()
        mock_yf = self._mock_yfinance_ticker(185.0)
        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            quote = feed._quote_via_yfinance("AAPL")
        self.assertIsNotNone(quote)
        self.assertEqual(quote.price, 185.0)
        self.assertEqual(quote.provider, FeedProvider.YAHOO.value)

    def test_get_quote_falls_back_to_stub(self):
        from live_feed_service import EquityFeed, FeedProvider
        feed = EquityFeed()
        with patch.object(feed, "_quote_via_yfinance", return_value=None), \
             patch.object(feed, "_quote_via_alpaca", return_value=None), \
             patch.object(feed, "_quote_via_alpha_vantage", return_value=None), \
             patch.object(feed, "_quote_via_polygon", return_value=None):
            quote = feed.get_quote("FAKE")
        self.assertEqual(quote.provider, FeedProvider.STUB.value)
        self.assertEqual(quote.price, 0.0)

    def test_get_top_movers_stub_fallback(self):
        from live_feed_service import EquityFeed
        feed = EquityFeed()
        with patch.object(feed, "_movers_via_yfinance", return_value=[]):
            movers = feed.get_top_movers(3)
        self.assertIsInstance(movers, list)

    def test_alpaca_skipped_without_key(self):
        from live_feed_service import EquityFeed
        feed = EquityFeed()
        result = feed._quote_via_alpaca("MSFT")
        self.assertIsNone(result)

    def test_alpha_vantage_skipped_without_key(self):
        from live_feed_service import EquityFeed
        feed = EquityFeed()
        result = feed._quote_via_alpha_vantage("MSFT")
        self.assertIsNone(result)

    def test_polygon_skipped_without_key(self):
        from live_feed_service import EquityFeed
        feed = EquityFeed()
        result = feed._quote_via_polygon("MSFT")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# LiveFeedService routing
# ---------------------------------------------------------------------------

class TestLiveFeedServiceRouting(unittest.TestCase):
    """get_quote routes to the correct sub-feed."""

    def test_crypto_symbol_routed_to_crypto_feed(self):
        from live_feed_service import LiveFeedService, LiveQuote, AssetClass, FeedProvider
        feed = LiveFeedService()
        stub = LiveQuote(
            symbol="BTC-USD", asset_class=AssetClass.CRYPTO.value,
            price=50000.0, bid=49990.0, ask=50010.0,
            volume_24h=0.0, change_pct_24h=0.0,
            high_24h=0.0, low_24h=0.0,
            provider=FeedProvider.STUB.value,
        )
        with patch.object(feed._crypto, "get_quote", return_value=stub) as mock_cq, \
             patch.object(feed._equity, "get_quote") as mock_eq:
            result = feed.get_quote("BTC-USD")
        mock_cq.assert_called_once_with("BTC-USD")
        mock_eq.assert_not_called()
        self.assertEqual(result.asset_class, AssetClass.CRYPTO.value)

    def test_equity_symbol_routed_to_equity_feed(self):
        from live_feed_service import LiveFeedService, LiveQuote, AssetClass, FeedProvider
        feed = LiveFeedService()
        stub = LiveQuote(
            symbol="AAPL", asset_class=AssetClass.EQUITY.value,
            price=185.0, bid=184.9, ask=185.1,
            volume_24h=0.0, change_pct_24h=0.0,
            high_24h=0.0, low_24h=0.0,
            provider=FeedProvider.STUB.value,
        )
        with patch.object(feed._equity, "get_quote", return_value=stub) as mock_eq, \
             patch.object(feed._crypto, "get_quote") as mock_cq:
            result = feed.get_quote("AAPL")
        mock_eq.assert_called_once_with("AAPL")
        mock_cq.assert_not_called()
        self.assertEqual(result.asset_class, AssetClass.EQUITY.value)


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------

class TestSubscriptionManagement(unittest.TestCase):
    """subscribe() and unsubscribe() callback registration."""

    def test_subscribe_registers_callback(self):
        from live_feed_service import LiveFeedService
        feed = LiveFeedService()
        cb = MagicMock()
        feed.subscribe("BTC-USD", cb)
        self.assertIn("BTC-USD", feed._subscriptions)
        self.assertIn(cb, feed._subscriptions["BTC-USD"])

    def test_unsubscribe_removes_callback(self):
        from live_feed_service import LiveFeedService
        feed = LiveFeedService()
        cb = MagicMock()
        feed.subscribe("ETH-USD", cb)
        feed.unsubscribe("ETH-USD", cb)
        self.assertNotIn("ETH-USD", feed._subscriptions)

    def test_unsubscribe_nonexistent_is_safe(self):
        from live_feed_service import LiveFeedService
        feed = LiveFeedService()
        cb = MagicMock()
        # Should not raise
        feed.unsubscribe("FAKE-USD", cb)

    def test_notify_calls_subscriber(self):
        from live_feed_service import LiveFeedService, LiveQuote, AssetClass, FeedProvider
        feed = LiveFeedService()
        received = []
        def cb(q):
            received.append(q)
        feed.subscribe("BTC-USD", cb)
        q = LiveQuote(
            symbol="BTC-USD", asset_class=AssetClass.CRYPTO.value,
            price=60000.0, bid=59990.0, ask=60010.0,
            volume_24h=0.0, change_pct_24h=0.0,
            high_24h=0.0, low_24h=0.0,
            provider=FeedProvider.COINBASE.value,
        )
        feed._notify("BTC-USD", q)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].price, 60000.0)


# ---------------------------------------------------------------------------
# status() tests
# ---------------------------------------------------------------------------

class TestFeedServiceStatus(unittest.TestCase):
    """status() returns expected shape."""

    def test_status_keys_present(self):
        from live_feed_service import LiveFeedService
        feed = LiveFeedService()
        s = feed.status()
        expected_keys = {
            "ws_active", "symbol_count", "subscriber_count",
            "providers", "coinbase_connected",
            "alpaca_configured", "alpha_vantage_configured", "polygon_configured",
        }
        self.assertTrue(expected_keys.issubset(set(s.keys())))

    def test_ws_active_initially_false(self):
        from live_feed_service import LiveFeedService
        feed = LiveFeedService()
        self.assertFalse(feed.status()["ws_active"])

    def test_coinbase_connected_false_without_connector(self):
        from live_feed_service import LiveFeedService
        feed = LiveFeedService()
        self.assertFalse(feed.status()["coinbase_connected"])

    def test_coinbase_connected_true_with_connector(self):
        from live_feed_service import LiveFeedService
        feed = LiveFeedService(coinbase_connector=MagicMock())
        self.assertTrue(feed.status()["coinbase_connected"])


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------

class TestSingleton(unittest.TestCase):
    """get_live_feed() returns the same instance."""

    def test_singleton_same_instance(self):
        import live_feed_service as lfs
        # Reset for test isolation
        with lfs._feed_lock:
            lfs._default_feed = None
        feed1 = lfs.get_live_feed()
        feed2 = lfs.get_live_feed()
        self.assertIs(feed1, feed2)
        # Cleanup
        with lfs._feed_lock:
            lfs._default_feed = None

    def test_singleton_returns_live_feed_service(self):
        import live_feed_service as lfs
        from live_feed_service import LiveFeedService
        with lfs._feed_lock:
            lfs._default_feed = None
        feed = lfs.get_live_feed()
        self.assertIsInstance(feed, LiveFeedService)
        with lfs._feed_lock:
            lfs._default_feed = None


# ---------------------------------------------------------------------------
# get_top_movers
# ---------------------------------------------------------------------------

class TestGetTopMovers(unittest.TestCase):
    """get_top_movers() merges and limits results."""

    def test_movers_returns_list_of_market_movers(self):
        from live_feed_service import LiveFeedService, MarketMover
        feed = LiveFeedService()
        with patch.object(feed._crypto, "get_top_movers", return_value=[
            MarketMover(symbol="BTC-USD", price=50000.0, change_pct=5.0, asset_class="crypto"),
        ]):
            with patch.object(feed._equity, "get_top_movers", return_value=[
                MarketMover(symbol="NVDA", price=875.0, change_pct=-3.0, asset_class="equity"),
            ]):
                movers = feed.get_top_movers(asset_class="all", limit=10)
        self.assertIsInstance(movers, list)
        syms = [m.symbol for m in movers]
        self.assertIn("BTC-USD", syms)
        self.assertIn("NVDA", syms)

    def test_movers_sorted_by_abs_change(self):
        from live_feed_service import LiveFeedService, MarketMover
        feed = LiveFeedService()
        with patch.object(feed._crypto, "get_top_movers", return_value=[
            MarketMover(symbol="A", change_pct=1.0),
            MarketMover(symbol="B", change_pct=10.0),
        ]):
            with patch.object(feed._equity, "get_top_movers", return_value=[]):
                movers = feed.get_top_movers(asset_class="all")
        self.assertEqual(movers[0].symbol, "B")

    def test_movers_crypto_only(self):
        from live_feed_service import LiveFeedService, MarketMover
        feed = LiveFeedService()
        with patch.object(feed._crypto, "get_top_movers", return_value=[
            MarketMover(symbol="ETH-USD", change_pct=3.0, asset_class="crypto"),
        ]) as mock_cm:
            with patch.object(feed._equity, "get_top_movers") as mock_em:
                feed.get_top_movers(asset_class="crypto")
        mock_cm.assert_called_once()
        mock_em.assert_not_called()


if __name__ == "__main__":
    unittest.main()
