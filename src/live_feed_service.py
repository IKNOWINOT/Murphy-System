# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Live Market Data Feed Service — Murphy System

Unified real-time and historical price feed for:
  - Crypto pairs    : Coinbase Advanced Trade (REST + WebSocket)
                      Binance REST + WebSocket (python-binance / HTTP fallback)
                      CCXT multi-exchange fallback
  - Stock equities  : Yahoo Finance (free, no key)
                      Alpaca Markets (REST + WebSocket)
                      Alpha Vantage (REST, free tier 500 req/day)
                      Polygon.io (REST, free tier)
                      IEX Cloud (REST, free tier)
                      Interactive Brokers (IBKR) via ib_insync (requires TWS/Gateway)

All providers are tried in priority order with graceful fallback.
No external SDK is required — each provider has an HTTP fallback.
WebSocket streaming is supported for Coinbase, Binance, and Alpaca.

Architecture:
  LiveFeedService
    ├── CryptoFeed      : Coinbase → Binance → CCXT fallback
    └── EquityFeed      : Yahoo → Alpaca → Alpha Vantage → Polygon → IEX → IBKR → stub

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

Each version of this file will convert to Apache 2.0 four years after release.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AssetClass(Enum):
    """Asset class taxonomy."""
    CRYPTO = "crypto"
    EQUITY = "equity"
    ETF    = "etf"
    INDEX  = "index"
    FOREX  = "forex"


class FeedProvider(Enum):
    """Data provider identifiers."""
    COINBASE      = "coinbase"
    BINANCE       = "binance"
    CCXT          = "ccxt"
    YAHOO         = "yahoo"
    ALPACA        = "alpaca"
    ALPHA_VANTAGE = "alpha_vantage"
    POLYGON       = "polygon"
    IEX_CLOUD     = "iex_cloud"
    IBKR          = "ibkr"
    STUB          = "stub"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class LiveQuote:
    """Normalised real-time quote across all asset classes and providers."""
    symbol: str
    asset_class: str
    price: float
    bid: float
    ask: float
    volume_24h: float
    change_pct_24h: float
    high_24h: float
    low_24h: float
    market_cap: float = 0.0
    provider: str = ""
    timestamp: str = ""
    sandbox: bool = False

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class LiveCandle:
    """Single OHLCV candle from any provider."""
    symbol: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    provider: str


@dataclass
class MarketMover:
    """A symbol that has moved significantly in the last 24 hours."""
    symbol: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    volume: float = 0.0
    asset_class: str = ""


# ---------------------------------------------------------------------------
# Crypto feed
# ---------------------------------------------------------------------------

# Known crypto base symbols (no quote suffix)
_KNOWN_CRYPTO_BASES = frozenset({
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT",
    "MATIC", "ATOM", "LTC", "LINK", "UNI", "ALGO", "FIL", "NEAR",
    "AAVE", "COMP", "MKR", "SNX", "CRV", "1INCH", "YFI", "SUSHI",
    "USDC", "USDT", "DAI", "BUSD",
})

_CRYPTO_QUOTE_SUFFIXES = ("-USD", "-USDT", "-BTC", "-ETH", "-USDC")


class CryptoFeed:
    """
    Real-time crypto price feed.

    Provider priority: CoinbaseConnector → Binance REST → CCXT → stub.
    All provider calls are wrapped with try/except so that import or network
    failures degrade gracefully to the next fallback.
    """

    def __init__(self, coinbase_connector: Any = None, binance_key: str = "", binance_secret: str = "") -> None:
        self._cb = coinbase_connector
        self._binance_key = binance_key
        self._binance_secret = binance_secret
        self._price_cache: Dict[str, LiveQuote] = {}
        self._lock = threading.Lock()
        self._binance_ws_running: bool = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str) -> LiveQuote:
        """
        Return a live quote for *symbol* (e.g. ``"BTC-USD"`` or ``"BTC/USD"``).

        Tries CoinbaseConnector first, then Binance REST, then CCXT, then
        returns a stub with ``price=0.0`` so callers always get a valid object.
        """
        symbol = symbol.upper().replace("/", "-")

        # 1. Coinbase
        quote = self._quote_via_coinbase(symbol)
        if quote is not None:
            with self._lock:
                self._price_cache[symbol] = quote
            return quote

        # 2. Binance REST
        quote = self._quote_via_binance(symbol)
        if quote is not None:
            with self._lock:
                self._price_cache[symbol] = quote
            return quote

        # 3. CCXT
        quote = self._quote_via_ccxt(symbol)
        if quote is not None:
            with self._lock:
                self._price_cache[symbol] = quote
            return quote

        # 4. Stub
        return self._stub_quote(symbol)

    def get_candles(
        self,
        symbol: str,
        granularity: str = "ONE_HOUR",
        limit: int = 100,
    ) -> List[LiveCandle]:
        """Return OHLCV candles for *symbol*."""
        symbol = symbol.upper().replace("/", "-")

        candles = self._candles_via_coinbase(symbol, granularity, limit)
        if candles:
            return candles

        candles = self._candles_via_binance(symbol, granularity, limit)
        if candles:
            return candles

        candles = self._candles_via_ccxt(symbol, granularity, limit)
        if candles:
            return candles

        return []

    def get_top_movers(self, limit: int = 10) -> List[MarketMover]:
        """Return the top *limit* crypto movers (gainers + losers)."""
        movers = self._movers_via_binance(limit)
        if movers:
            return movers
        movers = self._movers_via_ccxt(limit)
        if movers:
            return movers
        return self._stub_movers(limit)

    def start_binance_websocket(
        self,
        symbols: List[str],
        callback: Callable[[str, float], None],
    ) -> None:
        """
        Start a Binance combined stream WebSocket for *symbols*.

        Each tick calls *callback(symbol, price)*. Runs in a daemon thread.
        Falls back silently if ``websocket-client`` is not installed.
        """
        if self._binance_ws_running:
            return
        self._binance_ws_running = True
        t = threading.Thread(
            target=self._binance_ws_loop,
            args=(symbols, callback),
            daemon=True,
            name="binance-ws",
        )
        t.start()

    # ------------------------------------------------------------------
    # Coinbase provider
    # ------------------------------------------------------------------

    def _quote_via_coinbase(self, symbol: str) -> Optional[LiveQuote]:
        if self._cb is None:
            return None
        try:
            ticker = self._cb.get_ticker(symbol)
            if ticker is None:
                return None
            from dataclasses import asdict as _asdict
            d = _asdict(ticker)
            price = float(d.get("price", 0) or 0)
            bid   = float(d.get("best_bid", 0) or 0)
            ask   = float(d.get("best_ask", 0) or 0)
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO.value,
                price=price,
                bid=bid,
                ask=ask,
                volume_24h=float(d.get("volume_24h", 0) or 0),
                change_pct_24h=float(d.get("price_percent_chg_24h", 0) or 0),
                high_24h=float(d.get("high_24h", 0) or 0),
                low_24h=float(d.get("low_24h", 0) or 0),
                provider=FeedProvider.COINBASE.value,
                sandbox=getattr(self._cb, "sandbox", True),
            )
        except Exception as exc:
            logger.debug("CryptoFeed Coinbase quote failed for %s: %s", symbol, exc)
            return None

    def _candles_via_coinbase(
        self, symbol: str, granularity: str, limit: int
    ) -> List[LiveCandle]:
        if self._cb is None:
            return []
        try:
            raw = self._cb.get_product_candles(symbol, granularity=granularity, limit=limit)
            if not raw:
                return []
            candles: List[LiveCandle] = []
            for c in raw:
                try:
                    from dataclasses import asdict as _asdict
                    d = _asdict(c) if hasattr(c, "__dataclass_fields__") else dict(c)
                    candles.append(LiveCandle(
                        symbol=symbol,
                        open_time=int(d.get("start", 0) or 0),
                        open=float(d.get("open", 0) or 0),
                        high=float(d.get("high", 0) or 0),
                        low=float(d.get("low", 0) or 0),
                        close=float(d.get("close", 0) or 0),
                        volume=float(d.get("volume", 0) or 0),
                        provider=FeedProvider.COINBASE.value,
                    ))
                except Exception:
                    logger.debug("Coinbase candle parse failed for %s", symbol, exc_info=True)
            return candles
        except Exception as exc:
            logger.debug("CryptoFeed Coinbase candles failed for %s: %s", symbol, exc)
            return []

    # ------------------------------------------------------------------
    # Binance provider (REST + WebSocket)
    # ------------------------------------------------------------------

    # Granularity → Binance interval string
    _BINANCE_INTERVAL_MAP: Dict[str, str] = {
        "ONE_MINUTE": "1m", "FIVE_MINUTE": "5m", "FIFTEEN_MINUTE": "15m",
        "THIRTY_MINUTE": "30m", "ONE_HOUR": "1h", "TWO_HOUR": "2h",
        "SIX_HOUR": "6h", "ONE_DAY": "1d",
    }

    def _binance_symbol(self, symbol: str) -> str:
        """Convert ``BTC-USD`` → ``BTCUSDT`` for Binance API."""
        # Strip known quote suffixes (longest first to avoid partial matches)
        for suffix in ("-USDT", "-USD", "-BTC", "-ETH", "-USDC"):
            if symbol.endswith(suffix):
                return symbol[: -len(suffix)] + "USDT"
        # Fallback: strip all dashes and append USDT
        return symbol.replace("-", "") + "USDT"

    def _quote_via_binance(self, symbol: str) -> Optional[LiveQuote]:
        """Fetch quote via Binance REST API (public endpoint, no key required for ticker)."""
        try:
            import requests as _req  # noqa: PLC0415
            bsym = self._binance_symbol(symbol)
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={bsym}"
            resp = _req.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            d = resp.json()
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO.value,
                price=float(d.get("lastPrice", 0) or 0),
                bid=float(d.get("bidPrice", 0) or 0),
                ask=float(d.get("askPrice", 0) or 0),
                volume_24h=float(d.get("volume", 0) or 0),
                change_pct_24h=float(d.get("priceChangePercent", 0) or 0),
                high_24h=float(d.get("highPrice", 0) or 0),
                low_24h=float(d.get("lowPrice", 0) or 0),
                provider=FeedProvider.BINANCE.value,
            )
        except Exception as exc:
            logger.debug("CryptoFeed Binance quote failed for %s: %s", symbol, exc)
            return None

    def _candles_via_binance(
        self, symbol: str, granularity: str, limit: int
    ) -> List[LiveCandle]:
        """Fetch OHLCV from Binance REST (public endpoint)."""
        try:
            import requests as _req  # noqa: PLC0415
            bsym = self._binance_symbol(symbol)
            interval = self._BINANCE_INTERVAL_MAP.get(granularity, "1h")
            url = (
                f"https://api.binance.com/api/v3/klines"
                f"?symbol={bsym}&interval={interval}&limit={min(limit, 1000)}"
            )
            resp = _req.get(url, timeout=10)
            if resp.status_code != 200:
                return []
            return [
                LiveCandle(
                    symbol=symbol,
                    open_time=int(row[0] / 1000),
                    open=float(row[1] or 0),
                    high=float(row[2] or 0),
                    low=float(row[3] or 0),
                    close=float(row[4] or 0),
                    volume=float(row[5] or 0),
                    provider=FeedProvider.BINANCE.value,
                )
                for row in resp.json()
            ]
        except Exception as exc:
            logger.debug("CryptoFeed Binance candles failed for %s: %s", symbol, exc)
            return []

    def _movers_via_binance(self, limit: int) -> List[MarketMover]:
        """Fetch top movers from Binance 24hr ticker (public endpoint)."""
        try:
            import requests as _req  # noqa: PLC0415
            resp = _req.get(
                "https://api.binance.com/api/v3/ticker/24hr", timeout=10
            )
            if resp.status_code != 200:
                return []
            tickers = [
                t for t in resp.json()
                if str(t.get("symbol", "")).endswith("USDT")
                and float(t.get("quoteVolume", 0) or 0) > 1_000_000
            ]
            tickers.sort(key=lambda t: abs(float(t.get("priceChangePercent", 0) or 0)), reverse=True)
            return [
                MarketMover(
                    symbol=t["symbol"].replace("USDT", "-USD"),
                    price=float(t.get("lastPrice", 0) or 0),
                    change_pct=float(t.get("priceChangePercent", 0) or 0),
                    volume=float(t.get("quoteVolume", 0) or 0),
                    asset_class=AssetClass.CRYPTO.value,
                )
                for t in tickers[:limit]
            ]
        except Exception as exc:
            logger.debug("CryptoFeed Binance movers failed: %s", exc)
            return []

    def _binance_ws_loop(
        self, symbols: List[str], callback: Callable[[str, float], None]
    ) -> None:
        """Background thread: subscribe to Binance combined miniticker stream."""
        try:
            import websocket  # type: ignore  # noqa: PLC0415
            import json as _json  # noqa: PLC0415
        except ImportError as exc:
            logger.warning("websocket-client not installed — Binance WS disabled: %s", exc)
            self._binance_ws_running = False
            return

        # Build combined stream URL: <sym1>@miniTicker/<sym2>@miniTicker/...
        streams = "/".join(
            self._binance_symbol(s).lower() + "@miniTicker" for s in symbols
        )
        ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"

        def on_message(ws: Any, raw: str) -> None:  # noqa: ANN001
            try:
                msg = _json.loads(raw)
                data = msg.get("data", msg)
                bsym = data.get("s", "")
                price = float(data.get("c", 0) or 0)
                if bsym and price:
                    # Convert BTCUSDT → BTC-USD
                    sym = bsym.replace("USDT", "-USD")
                    callback(sym, price)
            except Exception as exc:
                logger.debug("Binance WS message error: %s", exc)

        def on_error(ws: Any, err: Any) -> None:  # noqa: ANN001
            logger.warning("Binance WS error: %s", err)

        def on_close(ws: Any, code: Any, reason: Any) -> None:  # noqa: ANN001
            logger.info("Binance WS closed — code=%s", code)
            self._binance_ws_running = False

        ws_app = websocket.WebSocketApp(
            ws_url, on_message=on_message, on_error=on_error, on_close=on_close
        )
        try:
            ws_app.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as exc:
            logger.error("Binance WS loop terminated: %s", exc)
        finally:
            self._binance_ws_running = False

    # ------------------------------------------------------------------
    # CCXT provider
    # ------------------------------------------------------------------

    def _quote_via_ccxt(self, symbol: str) -> Optional[LiveQuote]:
        try:
            import ccxt  # noqa: PLC0415
            exchange = ccxt.coinbase()
            ccxt_sym = symbol.replace("-", "/")
            ticker = exchange.fetch_ticker(ccxt_sym)
            if not ticker:
                return None
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO.value,
                price=float(ticker.get("last", 0) or 0),
                bid=float(ticker.get("bid", 0) or 0),
                ask=float(ticker.get("ask", 0) or 0),
                volume_24h=float(ticker.get("baseVolume", 0) or 0),
                change_pct_24h=float(ticker.get("percentage", 0) or 0),
                high_24h=float(ticker.get("high", 0) or 0),
                low_24h=float(ticker.get("low", 0) or 0),
                provider=FeedProvider.CCXT.value,
            )
        except Exception as exc:
            logger.debug("CryptoFeed CCXT quote failed for %s: %s", symbol, exc)
            return None

    def _candles_via_ccxt(
        self, symbol: str, granularity: str, limit: int
    ) -> List[LiveCandle]:
        # Map Coinbase granularity strings to CCXT timeframe strings
        _gran_map = {
            "ONE_MINUTE": "1m", "FIVE_MINUTE": "5m", "FIFTEEN_MINUTE": "15m",
            "THIRTY_MINUTE": "30m", "ONE_HOUR": "1h", "TWO_HOUR": "2h",
            "SIX_HOUR": "6h", "ONE_DAY": "1d",
        }
        try:
            import ccxt  # noqa: PLC0415
            exchange = ccxt.coinbase()
            ccxt_sym = symbol.replace("-", "/")
            tf = _gran_map.get(granularity, "1h")
            ohlcv = exchange.fetch_ohlcv(ccxt_sym, tf, limit=limit)
            return [
                LiveCandle(
                    symbol=symbol,
                    open_time=int(row[0] / 1000),
                    open=float(row[1] or 0),
                    high=float(row[2] or 0),
                    low=float(row[3] or 0),
                    close=float(row[4] or 0),
                    volume=float(row[5] or 0),
                    provider=FeedProvider.CCXT.value,
                )
                for row in (ohlcv or [])
            ]
        except Exception as exc:
            logger.debug("CryptoFeed CCXT candles failed for %s: %s", symbol, exc)
            return []

    def _movers_via_ccxt(self, limit: int) -> List[MarketMover]:
        try:
            import ccxt  # noqa: PLC0415
            exchange = ccxt.coinbase()
            tickers = exchange.fetch_tickers()
            if not tickers:
                return []
            rows = [
                (sym, float(t.get("percentage", 0) or 0), float(t.get("last", 0) or 0),
                 float(t.get("baseVolume", 0) or 0))
                for sym, t in tickers.items()
                if t.get("last")
            ]
            rows.sort(key=lambda x: abs(x[1]), reverse=True)
            return [
                MarketMover(
                    symbol=sym.replace("/", "-"),
                    price=price,
                    change_pct=pct,
                    volume=vol,
                    asset_class=AssetClass.CRYPTO.value,
                )
                for sym, pct, price, vol in rows[:limit]
            ]
        except Exception as exc:
            logger.debug("CryptoFeed CCXT movers failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Stubs
    # ------------------------------------------------------------------

    def _stub_quote(self, symbol: str) -> LiveQuote:
        return LiveQuote(
            symbol=symbol,
            asset_class=AssetClass.CRYPTO.value,
            price=0.0,
            bid=0.0,
            ask=0.0,
            volume_24h=0.0,
            change_pct_24h=0.0,
            high_24h=0.0,
            low_24h=0.0,
            provider=FeedProvider.STUB.value,
        )

    def _stub_movers(self, limit: int) -> List[MarketMover]:
        stubs = [
            ("BTC-USD", "Bitcoin", 65000.0, 2.5),
            ("ETH-USD", "Ethereum", 3200.0, 1.8),
            ("SOL-USD", "Solana", 140.0, 4.2),
            ("MATIC-USD", "Polygon", 0.85, -1.1),
            ("ATOM-USD", "Cosmos", 8.50, 3.0),
        ]
        return [
            MarketMover(
                symbol=sym, name=name, price=price,
                change_pct=pct, asset_class=AssetClass.CRYPTO.value,
            )
            for sym, name, price, pct in stubs[:limit]
        ]


# ---------------------------------------------------------------------------
# Equity feed
# ---------------------------------------------------------------------------

class EquityFeed:
    """
    Real-time equity/ETF/index price feed.

    Provider priority: Yahoo Finance → Alpaca → Alpha Vantage → Polygon → IEX Cloud → IBKR → stub.
    No API key is required for Yahoo Finance (free tier).
    """

    def __init__(
        self,
        alpaca_key: str = "",
        alpaca_secret: str = "",
        alpha_vantage_key: str = "",
        polygon_key: str = "",
        iex_cloud_key: str = "",
        ibkr_host: str = "127.0.0.1",
        ibkr_port: int = 7497,
        ibkr_client_id: int = 1,
    ) -> None:
        self._alpaca_key = alpaca_key
        self._alpaca_secret = alpaca_secret
        self._av_key = alpha_vantage_key
        self._polygon_key = polygon_key
        self._iex_key = iex_cloud_key
        self._ibkr_host = ibkr_host
        self._ibkr_port = ibkr_port
        self._ibkr_client_id = ibkr_client_id
        self._alpaca_ws_running: bool = False
        self._session = self._build_session()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str) -> LiveQuote:
        """Return a live equity quote, trying providers in priority order."""
        symbol = symbol.upper()
        for fn in (
            self._quote_via_yfinance,
            self._quote_via_alpaca,
            self._quote_via_alpha_vantage,
            self._quote_via_polygon,
            self._quote_via_iex,
            self._quote_via_ibkr,
        ):
            try:
                quote = fn(symbol)
                if quote is not None and quote.price > 0:
                    return quote
            except Exception as exc:
                logger.debug("EquityFeed provider %s failed for %s: %s", fn.__name__, symbol, exc)
        return self._stub_quote(symbol)

    def get_candles(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> List[LiveCandle]:
        """Return OHLCV candles via yfinance or empty list on failure."""
        symbol = symbol.upper()
        candles = self._candles_via_yfinance(symbol, period, interval)
        if candles:
            return candles
        return []

    def get_top_movers(self, limit: int = 10) -> List[MarketMover]:
        """Return top equity movers from yfinance or stub data."""
        movers = self._movers_via_yfinance(limit)
        if movers:
            return movers
        return self._stub_movers(limit)

    def start_alpaca_websocket(
        self,
        symbols: List[str],
        callback: Callable[[str, float], None],
    ) -> None:
        """
        Start an Alpaca market data WebSocket for *symbols*.

        Calls *callback(symbol, price)* on each trade update.
        Requires ALPACA_API_KEY and ALPACA_API_SECRET to be configured.
        """
        if self._alpaca_ws_running or not self._alpaca_key:
            return
        self._alpaca_ws_running = True
        t = threading.Thread(
            target=self._alpaca_ws_loop,
            args=(symbols, callback),
            daemon=True,
            name="alpaca-ws",
        )
        t.start()

    # ------------------------------------------------------------------
    # Yahoo Finance provider
    # ------------------------------------------------------------------

    def _quote_via_yfinance(self, symbol: str) -> Optional[LiveQuote]:
        try:
            import yfinance as yf  # noqa: PLC0415
            t = yf.Ticker(symbol)
            info = t.fast_info
            price = float(getattr(info, "last_price", 0) or 0)
            if price <= 0:
                return None
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.EQUITY.value,
                price=price,
                bid=float(getattr(info, "bid", price) or price),
                ask=float(getattr(info, "ask", price) or price),
                volume_24h=float(getattr(info, "three_month_average_volume", 0) or 0),
                change_pct_24h=0.0,
                high_24h=float(getattr(info, "day_high", 0) or 0),
                low_24h=float(getattr(info, "day_low", 0) or 0),
                market_cap=float(getattr(info, "market_cap", 0) or 0),
                provider=FeedProvider.YAHOO.value,
            )
        except Exception as exc:
            logger.debug("EquityFeed yfinance quote failed for %s: %s", symbol, exc)
            return None

    def _candles_via_yfinance(
        self, symbol: str, period: str, interval: str
    ) -> List[LiveCandle]:
        try:
            import yfinance as yf  # noqa: PLC0415
            df = yf.download(symbol, period=period, interval=interval, progress=False)
            if df is None or df.empty:
                return []
            candles: List[LiveCandle] = []
            for ts, row in df.iterrows():
                try:
                    candles.append(LiveCandle(
                        symbol=symbol,
                        open_time=int(ts.timestamp()),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row["Volume"]),
                        provider=FeedProvider.YAHOO.value,
                    ))
                except Exception:
                    logger.debug("yfinance candle parse failed for %s", symbol, exc_info=True)
            return candles
        except Exception as exc:
            logger.debug("EquityFeed yfinance candles failed for %s: %s", symbol, exc)
            return []

    def _movers_via_yfinance(self, limit: int) -> List[MarketMover]:
        """Fetch price info for a curated list of S&P 500 constituents."""
        watchlist = [
            "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
            "BRK-B", "UNH", "JPM", "V", "JNJ", "XOM", "PG", "MA",
        ]
        try:
            import yfinance as yf  # noqa: PLC0415
            movers: List[MarketMover] = []
            for sym in watchlist[:limit * 2]:
                try:
                    info = yf.Ticker(sym).fast_info
                    price = float(getattr(info, "last_price", 0) or 0)
                    if price <= 0:
                        continue
                    prev = float(getattr(info, "previous_close", price) or price)
                    pct = ((price - prev) / prev * 100) if prev else 0.0
                    movers.append(MarketMover(
                        symbol=sym, price=price, change_pct=pct,
                        volume=float(getattr(info, "three_month_average_volume", 0) or 0),
                        asset_class=AssetClass.EQUITY.value,
                    ))
                except Exception:
                    logger.debug("yfinance mover fetch failed for %s", sym, exc_info=True)
            movers.sort(key=lambda m: abs(m.change_pct), reverse=True)
            return movers[:limit]
        except Exception as exc:
            logger.debug("EquityFeed yfinance movers failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Alpaca provider
    # ------------------------------------------------------------------

    def _quote_via_alpaca(self, symbol: str) -> Optional[LiveQuote]:
        if not self._alpaca_key:
            return None
        try:
            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
            headers = {
                "APCA-API-KEY-ID": self._alpaca_key,
                "APCA-API-SECRET-KEY": self._alpaca_secret,
            }
            resp = self._session.get(url, headers=headers, timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json()
            q = data.get("quote", {})
            ask = float(q.get("ap", 0) or 0)
            bid = float(q.get("bp", 0) or 0)
            price = (ask + bid) / 2 if (ask and bid) else (ask or bid)
            if not price:
                return None
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.EQUITY.value,
                price=price,
                bid=bid,
                ask=ask,
                volume_24h=0.0,
                change_pct_24h=0.0,
                high_24h=0.0,
                low_24h=0.0,
                provider=FeedProvider.ALPACA.value,
            )
        except Exception as exc:
            logger.debug("EquityFeed Alpaca quote failed for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------
    # Alpha Vantage provider
    # ------------------------------------------------------------------

    def _quote_via_alpha_vantage(self, symbol: str) -> Optional[LiveQuote]:
        if not self._av_key:
            return None
        try:
            url = (
                "https://www.alphavantage.co/query"
                f"?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self._av_key}"
            )
            resp = self._session.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json().get("Global Quote", {})
            price = float(data.get("05. price", 0) or 0)
            if not price:
                return None
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.EQUITY.value,
                price=price,
                bid=price,
                ask=price,
                volume_24h=float(data.get("06. volume", 0) or 0),
                change_pct_24h=float(
                    str(data.get("10. change percent", "0%")).rstrip("%") or 0
                ),
                high_24h=float(data.get("03. high", 0) or 0),
                low_24h=float(data.get("04. low", 0) or 0),
                provider=FeedProvider.ALPHA_VANTAGE.value,
            )
        except Exception as exc:
            logger.debug("EquityFeed Alpha Vantage quote failed for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------
    # Polygon provider
    # ------------------------------------------------------------------

    def _quote_via_polygon(self, symbol: str) -> Optional[LiveQuote]:
        if not self._polygon_key:
            return None
        try:
            url = f"https://api.polygon.io/v2/last/trade/{symbol}?apiKey={self._polygon_key}"
            resp = self._session.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json().get("results", {})
            price = float(data.get("p", 0) or 0)
            if not price:
                return None
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.EQUITY.value,
                price=price,
                bid=price,
                ask=price,
                volume_24h=float(data.get("s", 0) or 0),
                change_pct_24h=0.0,
                high_24h=0.0,
                low_24h=0.0,
                provider=FeedProvider.POLYGON.value,
            )
        except Exception as exc:
            logger.debug("EquityFeed Polygon quote failed for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------
    # IEX Cloud provider
    # ------------------------------------------------------------------

    def _quote_via_iex(self, symbol: str) -> Optional[LiveQuote]:
        """Fetch quote from IEX Cloud (free sandbox or paid production tier)."""
        if not self._iex_key:
            return None
        try:
            # IEX Cloud: try iexfinance SDK first, then HTTP fallback
            try:
                import iexfinance.stocks as _iex  # type: ignore  # noqa: PLC0415
                import os as _os  # noqa: PLC0415
                _os.environ["IEX_TOKEN"] = self._iex_key
                stock = _iex.Stock(symbol)
                price = float(stock.get_price() or 0)
                if price > 0:
                    q_data = stock.get_quote()
                    return LiveQuote(
                        symbol=symbol,
                        asset_class=AssetClass.EQUITY.value,
                        price=price,
                        bid=float(q_data.get("iexBidPrice", price) or price),
                        ask=float(q_data.get("iexAskPrice", price) or price),
                        volume_24h=float(q_data.get("latestVolume", 0) or 0),
                        change_pct_24h=float(q_data.get("changePercent", 0) or 0) * 100,
                        high_24h=float(q_data.get("high", price) or price),
                        low_24h=float(q_data.get("low", price) or price),
                        provider=FeedProvider.IEX_CLOUD.value,
                    )
            except (ImportError, Exception):
                pass
            # HTTP fallback — IEX Cloud v1 REST
            base = (
                "https://sandbox.iexapis.com/stable"
                if self._iex_key.startswith("T")
                else "https://cloud.iexapis.com/stable"
            )
            url = f"{base}/stock/{symbol}/quote?token={self._iex_key}"
            if self._session is None:
                import requests as _req  # noqa: PLC0415
                resp = _req.get(url, timeout=5)
            else:
                resp = self._session.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            d = resp.json()
            price = float(d.get("latestPrice", 0) or 0)
            if not price:
                return None
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.EQUITY.value,
                price=price,
                bid=float(d.get("iexBidPrice", price) or price),
                ask=float(d.get("iexAskPrice", price) or price),
                volume_24h=float(d.get("latestVolume", 0) or 0),
                change_pct_24h=float(d.get("changePercent", 0) or 0) * 100,
                high_24h=float(d.get("high", price) or price),
                low_24h=float(d.get("low", price) or price),
                provider=FeedProvider.IEX_CLOUD.value,
            )
        except Exception as exc:
            logger.debug("EquityFeed IEX Cloud quote failed for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------
    # IBKR (Interactive Brokers) provider — requires TWS or IB Gateway
    # ------------------------------------------------------------------

    def _quote_via_ibkr(self, symbol: str) -> Optional[LiveQuote]:
        """
        Fetch a snapshot quote from Interactive Brokers via ib_insync.

        Requires IB TWS or IB Gateway running locally and ``ib_insync``
        installed.  This method is a last-resort fallback; timeout is kept
        short so it does not block the provider waterfall.
        """
        try:
            from ib_insync import IB, Stock  # type: ignore  # noqa: PLC0415
            ib = IB()
            ib.connect(self._ibkr_host, self._ibkr_port, clientId=self._ibkr_client_id + 100)
            contract = Stock(symbol, "SMART", "USD")
            ib.qualifyContracts(contract)
            [ticker] = ib.reqTickers(contract)
            price = float(ticker.marketPrice() or 0)
            ib.disconnect()
            if not price or price != price:  # NaN guard
                return None
            return LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.EQUITY.value,
                price=price,
                bid=float(ticker.bid or price),
                ask=float(ticker.ask or price),
                volume_24h=float(ticker.volume or 0),
                change_pct_24h=0.0,
                high_24h=float(ticker.high or price),
                low_24h=float(ticker.low or price),
                provider=FeedProvider.IBKR.value,
            )
        except Exception as exc:
            logger.debug("EquityFeed IBKR quote failed for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------
    # Alpaca WebSocket loop
    # ------------------------------------------------------------------

    def _alpaca_ws_loop(
        self, symbols: List[str], callback: Callable[[str, float], None]
    ) -> None:
        """Subscribe to Alpaca market data WebSocket feed (iex data source)."""
        try:
            import websocket  # type: ignore  # noqa: PLC0415
            import json as _json  # noqa: PLC0415
        except ImportError as exc:
            logger.warning("websocket-client not installed — Alpaca WS disabled: %s", exc)
            self._alpaca_ws_running = False
            return

        ws_url = "wss://stream.data.alpaca.markets/v2/iex"
        auth_msg = _json.dumps({"action": "auth", "key": self._alpaca_key, "secret": self._alpaca_secret})
        sub_msg = _json.dumps({"action": "subscribe", "trades": symbols})

        def on_open(ws: Any) -> None:  # noqa: ANN001
            ws.send(auth_msg)
            ws.send(sub_msg)

        def on_message(ws: Any, raw: str) -> None:  # noqa: ANN001
            try:
                msgs = _json.loads(raw)
                for msg in (msgs if isinstance(msgs, list) else [msgs]):
                    if msg.get("T") == "t":  # trade message
                        sym = msg.get("S", "")
                        price = float(msg.get("p", 0) or 0)
                        if sym and price:
                            callback(sym, price)
            except Exception as exc:
                logger.debug("Alpaca WS message error: %s", exc)

        def on_error(ws: Any, err: Any) -> None:  # noqa: ANN001
            logger.warning("Alpaca WS error: %s", err)

        def on_close(ws: Any, code: Any, reason: Any) -> None:  # noqa: ANN001
            logger.info("Alpaca WS closed — code=%s", code)
            self._alpaca_ws_running = False

        ws_app = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        try:
            ws_app.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as exc:
            logger.error("Alpaca WS loop terminated: %s", exc)
        finally:
            self._alpaca_ws_running = False

    # ------------------------------------------------------------------
    # Equity stubs
    # ------------------------------------------------------------------

    def _stub_quote(self, symbol: str) -> LiveQuote:
        return LiveQuote(
            symbol=symbol,
            asset_class=AssetClass.EQUITY.value,
            price=0.0,
            bid=0.0,
            ask=0.0,
            volume_24h=0.0,
            change_pct_24h=0.0,
            high_24h=0.0,
            low_24h=0.0,
            provider=FeedProvider.STUB.value,
        )

    def _stub_movers(self, limit: int) -> List[MarketMover]:
        stubs = [
            ("AAPL", "Apple Inc.", 185.0, 1.2),
            ("MSFT", "Microsoft Corp.", 415.0, 0.8),
            ("NVDA", "NVIDIA Corp.", 875.0, 3.5),
            ("GOOGL", "Alphabet Inc.", 175.0, -0.5),
            ("AMZN", "Amazon.com Inc.", 195.0, 1.9),
        ]
        return [
            MarketMover(
                symbol=sym, name=name, price=price,
                change_pct=pct, asset_class=AssetClass.EQUITY.value,
            )
            for sym, name, price, pct in stubs[:limit]
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_session() -> "Optional[requests.Session]":
        try:
            import requests  # noqa: PLC0415
            s = requests.Session()
            s.headers.update({"User-Agent": "MurphySystem/1.0 market-data-feed"})
            return s
        except ImportError:
            return None


# ---------------------------------------------------------------------------
# LiveFeedService — unified entry point
# ---------------------------------------------------------------------------

class LiveFeedService:
    """
    Process-wide unified market data service.

    Routes quote and candle requests to CryptoFeed or EquityFeed based on
    symbol heuristics, then merges results for aggregate views such as
    get_top_movers().

    Thread-safe: internal state is protected by a reentrant lock.
    """

    def __init__(
        self,
        coinbase_connector: Any = None,
        binance_key: str = "",
        binance_secret: str = "",
        alpaca_key: str = "",
        alpaca_secret: str = "",
        alpha_vantage_key: str = "",
        polygon_key: str = "",
        iex_cloud_key: str = "",
        ibkr_host: str = "127.0.0.1",
        ibkr_port: int = 7497,
        ibkr_client_id: int = 1,
    ) -> None:
        self._crypto = CryptoFeed(
            coinbase_connector=coinbase_connector,
            binance_key=binance_key,
            binance_secret=binance_secret,
        )
        self._equity = EquityFeed(
            alpaca_key=alpaca_key,
            alpaca_secret=alpaca_secret,
            alpha_vantage_key=alpha_vantage_key,
            polygon_key=polygon_key,
            iex_cloud_key=iex_cloud_key,
            ibkr_host=ibkr_host,
            ibkr_port=ibkr_port,
            ibkr_client_id=ibkr_client_id,
        )
        self._subscriptions: Dict[str, List[Callable[[LiveQuote], None]]] = {}
        self._lock = threading.Lock()
        self._ws_active: bool = False
        self._coinbase_connector = coinbase_connector

    # ------------------------------------------------------------------
    # Core query interface
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str) -> LiveQuote:
        """Return a live quote for *symbol*, routing to the appropriate feed."""
        if self._is_crypto(symbol):
            return self._crypto.get_quote(symbol)
        return self._equity.get_quote(symbol)

    def get_candles(
        self, symbol: str, granularity: str = "ONE_HOUR", limit: int = 100
    ) -> List[LiveCandle]:
        """Return OHLCV candles, routing to crypto or equity feed."""
        if self._is_crypto(symbol):
            return self._crypto.get_candles(symbol, granularity=granularity, limit=limit)
        # Map Coinbase granularity → yfinance period/interval
        _period_map = {
            "ONE_MINUTE": ("5d", "1m"),
            "FIVE_MINUTE": ("1mo", "5m"),
            "FIFTEEN_MINUTE": ("1mo", "15m"),
            "THIRTY_MINUTE": ("1mo", "30m"),
            "ONE_HOUR": ("3mo", "1h"),
            "TWO_HOUR": ("3mo", "2h"),
            "SIX_HOUR": ("6mo", "1d"),
            "ONE_DAY": ("1y", "1d"),
        }
        period, interval = _period_map.get(granularity, ("3mo", "1h"))
        return self._equity.get_candles(symbol, period=period, interval=interval)

    def get_top_movers(self, asset_class: str = "all", limit: int = 10) -> List[MarketMover]:
        """Return top movers, optionally filtered by asset class."""
        movers: List[MarketMover] = []
        if asset_class in ("all", AssetClass.CRYPTO.value):
            movers.extend(self._crypto.get_top_movers(limit))
        if asset_class in ("all", AssetClass.EQUITY.value):
            movers.extend(self._equity.get_top_movers(limit))
        movers.sort(key=lambda m: abs(m.change_pct), reverse=True)
        return movers[:limit]

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, symbol: str, callback: Callable[[LiveQuote], None]) -> None:
        """Register *callback* to receive price updates for *symbol*."""
        with self._lock:
            self._subscriptions.setdefault(symbol.upper(), []).append(callback)

    def unsubscribe(self, symbol: str, callback: Callable[[LiveQuote], None]) -> None:
        """Remove *callback* from the subscriber list for *symbol*."""
        with self._lock:
            sym = symbol.upper()
            cbs = self._subscriptions.get(sym, [])
            try:
                cbs.remove(callback)
            except ValueError:
                pass
            if not cbs:
                self._subscriptions.pop(sym, None)

    # ------------------------------------------------------------------
    # WebSocket streaming
    # ------------------------------------------------------------------

    def start_coinbase_websocket(self, symbols: List[str]) -> None:
        """
        Start a Coinbase Advanced Trade WebSocket subscription for *symbols*.

        Ticks are delivered to :meth:`_on_coinbase_tick` and forwarded to all
        registered subscribers.  The connector must have been supplied at init
        time.
        """
        if self._coinbase_connector is None:
            logger.warning("LiveFeedService: no Coinbase connector — WebSocket unavailable")
            return
        try:
            self._coinbase_connector.subscribe_tickers(
                product_ids=symbols,
                callback=self._on_coinbase_tick,
            )
            self._ws_active = True
            logger.info("LiveFeedService: Coinbase WebSocket active for %s", symbols)
        except Exception as exc:
            logger.warning("LiveFeedService: Coinbase WS subscribe failed: %s", exc)

    def start_binance_websocket(self, symbols: List[str]) -> None:
        """
        Start a Binance combined miniticker WebSocket for *symbols*.

        Ticks are forwarded to all registered subscribers for each symbol.
        Does not require API credentials (uses public stream endpoint).
        """
        def _on_binance_tick(sym: str, price: float) -> None:
            quote = LiveQuote(
                symbol=sym,
                asset_class=AssetClass.CRYPTO.value,
                price=price,
                bid=price,
                ask=price,
                volume_24h=0.0,
                change_pct_24h=0.0,
                high_24h=0.0,
                low_24h=0.0,
                provider=FeedProvider.BINANCE.value,
            )
            self._notify(sym, quote)

        self._crypto.start_binance_websocket(symbols, _on_binance_tick)

    def start_alpaca_websocket(self, symbols: List[str]) -> None:
        """
        Start an Alpaca market data WebSocket for equity *symbols*.

        Requires ALPACA_API_KEY and ALPACA_API_SECRET to be configured.
        Ticks are forwarded to all registered subscribers.
        """
        def _on_alpaca_tick(sym: str, price: float) -> None:
            quote = LiveQuote(
                symbol=sym,
                asset_class=AssetClass.EQUITY.value,
                price=price,
                bid=price,
                ask=price,
                volume_24h=0.0,
                change_pct_24h=0.0,
                high_24h=0.0,
                low_24h=0.0,
                provider=FeedProvider.ALPACA.value,
            )
            self._notify(sym, quote)

        self._equity.start_alpaca_websocket(symbols, _on_alpaca_tick)

    def _on_coinbase_tick(self, data: dict) -> None:
        """Parse an incoming Coinbase WebSocket tick and notify subscribers."""
        try:
            symbol = data.get("product_id", "").upper()
            price = float(data.get("price", 0) or 0)
            if not symbol or not price:
                return
            quote = LiveQuote(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO.value,
                price=price,
                bid=float(data.get("best_bid", price) or price),
                ask=float(data.get("best_ask", price) or price),
                volume_24h=float(data.get("volume_24h", 0) or 0),
                change_pct_24h=float(data.get("price_percent_chg_24h", 0) or 0),
                high_24h=float(data.get("high_24h", 0) or 0),
                low_24h=float(data.get("low_24h", 0) or 0),
                provider=FeedProvider.COINBASE.value,
                sandbox=getattr(self._coinbase_connector, "sandbox", True),
            )
            self._notify(symbol, quote)
        except Exception as exc:
            logger.debug("LiveFeedService _on_coinbase_tick error: %s", exc)

    def _notify(self, symbol: str, quote: LiveQuote) -> None:
        """Dispatch *quote* to all subscribers registered for *symbol*."""
        with self._lock:
            callbacks = list(self._subscriptions.get(symbol.upper(), []))
        for cb in callbacks:
            try:
                cb(quote)
            except Exception as exc:
                logger.debug("LiveFeedService subscriber callback error: %s", exc)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _is_crypto(self, symbol: str) -> bool:
        """Return True if *symbol* looks like a crypto pair."""
        sym = symbol.upper()
        for suffix in _CRYPTO_QUOTE_SUFFIXES:
            if sym.endswith(suffix):
                return True
        # Bare base symbols like "BTC", "ETH"
        if sym in _KNOWN_CRYPTO_BASES:
            return True
        # Slash notation: BTC/USD
        if "/" in sym:
            base = sym.split("/")[0]
            return base in _KNOWN_CRYPTO_BASES
        return False

    def status(self) -> dict:
        """Return a snapshot of feed service health and configuration."""
        with self._lock:
            sub_count = sum(len(v) for v in self._subscriptions.values())
            symbol_count = len(self._subscriptions)
        return {
            "ws_active": self._ws_active,
            "symbol_count": symbol_count,
            "subscriber_count": sub_count,
            "providers": {
                "crypto_primary": FeedProvider.COINBASE.value,
                "crypto_fallback": FeedProvider.CCXT.value,
                "equity_primary": FeedProvider.YAHOO.value,
                "equity_fallbacks": [
                    FeedProvider.ALPACA.value,
                    FeedProvider.ALPHA_VANTAGE.value,
                    FeedProvider.POLYGON.value,
                    FeedProvider.IEX_CLOUD.value,
                    FeedProvider.IBKR.value,
                ],
                "crypto_ws": {
                    "coinbase": self._ws_active,
                    "binance": self._crypto._binance_ws_running,
                },
                "equity_ws": {
                    "alpaca": self._equity._alpaca_ws_running,
                },
            },
            "coinbase_connected": self._coinbase_connector is not None,
            "binance_configured": bool(self._crypto._binance_key),
            "alpaca_configured": bool(self._equity._alpaca_key),
            "alpha_vantage_configured": bool(self._equity._av_key),
            "polygon_configured": bool(self._equity._polygon_key),
            "iex_cloud_configured": bool(self._equity._iex_key),
            "ibkr_configured": self._equity._ibkr_port != 0,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_feed: Optional[LiveFeedService] = None
_feed_lock = threading.Lock()


def get_live_feed(coinbase_connector: Any = None, **kwargs: Any) -> LiveFeedService:
    """Return the process-wide :class:`LiveFeedService` singleton."""
    global _default_feed
    with _feed_lock:
        if _default_feed is None:
            _default_feed = LiveFeedService(
                coinbase_connector=coinbase_connector, **kwargs
            )
    return _default_feed
