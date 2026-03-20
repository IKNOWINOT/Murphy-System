# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Coinbase Advanced Trade API v3 Connector — Murphy System

Implements the full Coinbase Advanced Trade REST and WebSocket API with:
- HMAC-SHA256 authentication for API key credentials
- Sandbox / paper-trading mode via environment flag
- Rate-limit awareness with Retry-After back-off
- Unified order, product, and portfolio endpoints
- Real-time WebSocket subscription management for tickers, candles, and L2

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post

Each version of this file will convert to Apache 2.0 four years after release.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COINBASE_REST_PROD = "https://api.coinbase.com"
COINBASE_REST_SAND = "https://api-public.sandbox.exchange.coinbase.com"
COINBASE_WS_PROD   = "wss://advanced-trade-ws.coinbase.com"
COINBASE_WS_SAND   = "wss://advanced-trade-ws-sandbox.coinbase.com"

_MAX_ORDER_HISTORY = 10_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CoinbaseOrderSide(Enum):
    """Order direction (Enum subclass)."""
    BUY  = "BUY"
    SELL = "SELL"


class CoinbaseOrderType(Enum):
    """Order type (Enum subclass)."""
    MARKET_MARKET_IOC = "MARKET_MARKET_IOC"
    LIMIT_LIMIT_GTC   = "LIMIT_LIMIT_GTC"
    LIMIT_LIMIT_GTD   = "LIMIT_LIMIT_GTD"
    STOP_LIMIT_STOP_LIMIT_GTC = "STOP_LIMIT_STOP_LIMIT_GTC"


class CoinbaseOrderStatus(Enum):
    """Order lifecycle state (Enum subclass)."""
    PENDING   = "PENDING"
    OPEN      = "OPEN"
    FILLED    = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED   = "EXPIRED"
    FAILED    = "FAILED"


class CoinbaseConnectionStatus(Enum):
    """Connector lifecycle state (Enum subclass)."""
    DISCONNECTED  = "disconnected"
    CONNECTING    = "connecting"
    CONNECTED     = "connected"
    ERROR         = "error"
    SANDBOX       = "sandbox"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CoinbaseProduct:
    """Single tradable product / pair from the Coinbase catalogue."""
    product_id:       str
    base_currency:    str
    quote_currency:   str
    quote_min_size:   str
    quote_max_size:   str
    base_min_size:    str
    base_max_size:    str
    base_increment:   str
    quote_increment:  str
    price:            str = "0"
    price_percentage_change_24h: str = "0"
    volume_24h:       str = "0"
    status:           str = "online"


@dataclass
class CoinbaseOrder:
    """A submitted or historical Coinbase order."""
    order_id:           str
    client_order_id:    str
    product_id:         str
    side:               CoinbaseOrderSide
    order_type:         CoinbaseOrderType
    status:             CoinbaseOrderStatus
    created_time:       str
    base_size:          str = "0"
    limit_price:        str = "0"
    filled_size:        str = "0"
    average_filled_price: str = "0"
    fee:                str = "0"
    total_value_after_fees: str = "0"
    raw:                Dict[str, Any] = field(default_factory=dict)


@dataclass
class CoinbaseBalance:
    """Balance for a single currency in a Coinbase portfolio."""
    currency:          str
    available_balance: str
    hold:              str
    total:             str


@dataclass
class CoinbaseTicker:
    """Best-bid-ask snapshot for a product."""
    product_id: str
    bid:        str
    ask:        str
    bid_qty:    str
    ask_qty:    str
    time:       str


# ---------------------------------------------------------------------------
# Core connector
# ---------------------------------------------------------------------------

class CoinbaseConnector:
    """
    Coinbase Advanced Trade API v3 connector.

    Provides authenticated REST calls and optional WebSocket streaming.
    All network I/O uses the ``requests`` library loaded lazily so that the
    module remains importable in environments without network access.

    Parameters
    ----------
    api_key:     Coinbase API key name (CDP format or legacy key).
    api_secret:  Corresponding secret (HMAC-SHA256 signing).
    sandbox:     If True, routes to the sandbox endpoint.
    timeout:     HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key:    str = "",
        api_secret: str = "",
        sandbox:    bool = True,
        timeout:    int  = 10,
    ) -> None:
        self.api_key    = api_key or os.getenv("COINBASE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("COINBASE_API_SECRET", "")
        # Sandbox is ON by default. Only disable when COINBASE_LIVE_MODE=true is
        # explicitly set AND the caller has passed sandbox=False.
        live_mode = os.getenv("COINBASE_LIVE_MODE", "false").lower() == "true"
        self.sandbox    = sandbox or (not live_mode)
        self.timeout    = timeout

        self._base_url  = COINBASE_REST_SAND if self.sandbox else COINBASE_REST_PROD
        self._ws_url    = COINBASE_WS_SAND   if self.sandbox else COINBASE_WS_PROD

        self.status     = (
            CoinbaseConnectionStatus.SANDBOX
            if self.sandbox
            else CoinbaseConnectionStatus.DISCONNECTED
        )
        self._lock      = threading.Lock()
        self._order_history: List[CoinbaseOrder] = []

        # WebSocket state
        self._ws_thread:   Optional[threading.Thread] = None
        self._ws_running   = False
        self._ws_callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

        logger.info(
            "CoinbaseConnector initialised — sandbox=%s base_url=%s",
            self.sandbox, self._base_url,
        )

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Return signed headers for Coinbase Advanced Trade HMAC auth."""
        timestamp = str(int(time.time()))
        message   = timestamp + method.upper() + path + body
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "CB-ACCESS-KEY":       self.api_key,
            "CB-ACCESS-SIGN":      signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "Content-Type":        "application/json",
        }

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    def _request(
        self,
        method:  str,
        path:    str,
        params:  Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send an authenticated request and return the parsed JSON body."""
        try:
            import requests  # lazy import
        except ImportError as exc:
            logger.error("requests library not available: %s", exc)
            return {"error": "requests_unavailable", "detail": str(exc)}

        body    = json.dumps(payload) if payload else ""
        qs      = ("?" + urlencode(params)) if params else ""
        headers = self._sign_request(method, path + qs, body)
        url     = self._base_url + path + qs

        for attempt in range(3):
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=headers,
                    data=body or None,
                    timeout=self.timeout,
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                    logger.warning("Coinbase rate-limited; retrying in %ss", retry_after)
                    time.sleep(retry_after)
                    continue
                resp.raise_for_status()
                with self._lock:
                    self.status = CoinbaseConnectionStatus.CONNECTED
                return resp.json()
            except Exception as exc:
                logger.error("Coinbase request error (attempt %d): %s", attempt + 1, exc)
                if attempt == 2:
                    with self._lock:
                        self.status = CoinbaseConnectionStatus.ERROR
                    return {"error": type(exc).__name__, "detail": str(exc)}
                time.sleep(1.5 ** attempt)
        return {"error": "max_retries_exceeded"}

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    def list_products(
        self,
        product_type: str = "SPOT",
        limit:        int  = 250,
    ) -> List[CoinbaseProduct]:
        """Return a list of available spot products."""
        resp = self._request("GET", "/api/v3/brokerage/products", {"product_type": product_type, "limit": limit})
        products = []
        for p in resp.get("products", []):
            try:
                products.append(
                    CoinbaseProduct(
                        product_id      = p["product_id"],
                        base_currency   = p.get("base_currency_id", ""),
                        quote_currency  = p.get("quote_currency_id", ""),
                        quote_min_size  = p.get("quote_min_size", "0"),
                        quote_max_size  = p.get("quote_max_size", "0"),
                        base_min_size   = p.get("base_min_size", "0"),
                        base_max_size   = p.get("base_max_size", "0"),
                        base_increment  = p.get("base_increment", "0"),
                        quote_increment = p.get("quote_increment", "0"),
                        price           = p.get("price", "0"),
                        price_percentage_change_24h = p.get("price_percentage_change_24h", "0"),
                        volume_24h      = p.get("volume_24h", "0"),
                        status          = p.get("status", "online"),
                    )
                )
            except (KeyError, TypeError) as exc:
                logger.debug("Skipping malformed product entry: %s", exc)
        return products

    def get_best_bid_ask(self, product_ids: List[str]) -> List[CoinbaseTicker]:
        """Return best bid/ask for the given product IDs."""
        params = {"product_ids": ",".join(product_ids)}
        resp   = self._request("GET", "/api/v3/brokerage/best_bid_ask", params)
        tickers = []
        for entry in resp.get("pricebooks", []):
            bids = entry.get("bids", [{}])
            asks = entry.get("asks", [{}])
            tickers.append(
                CoinbaseTicker(
                    product_id = entry.get("product_id", ""),
                    bid        = bids[0].get("price", "0") if bids else "0",
                    ask        = asks[0].get("price", "0") if asks else "0",
                    bid_qty    = bids[0].get("size", "0")  if bids else "0",
                    ask_qty    = asks[0].get("size", "0")  if asks else "0",
                    time       = entry.get("time", ""),
                )
            )
        return tickers

    def get_candles(
        self,
        product_id:  str,
        start:       int,
        end:         int,
        granularity: str = "ONE_HOUR",
    ) -> List[Dict[str, Any]]:
        """Return OHLCV candles for *product_id* in the given time window."""
        resp = self._request(
            "GET",
            f"/api/v3/brokerage/products/{product_id}/candles",
            {"start": str(start), "end": str(end), "granularity": granularity},
        )
        return resp.get("candles", [])

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def create_market_order(
        self,
        product_id: str,
        side:       CoinbaseOrderSide,
        quote_size: Optional[str] = None,
        base_size:  Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a market (IOC) order. Provide *quote_size* to buy a dollar
        amount or *base_size* to buy/sell a specific coin quantity."""
        client_order_id = str(uuid.uuid4())
        order_config: Dict[str, Any] = {}
        if quote_size:
            order_config["quote_size"] = quote_size
        if base_size:
            order_config["base_size"] = base_size
        payload = {
            "client_order_id": client_order_id,
            "product_id":      product_id,
            "side":            side.value,
            "order_configuration": {"market_market_ioc": order_config},
        }
        resp = self._request("POST", "/api/v3/brokerage/orders", payload=payload)
        self._record_order(resp, product_id, side, CoinbaseOrderType.MARKET_MARKET_IOC, client_order_id)
        return resp

    def create_limit_order(
        self,
        product_id:  str,
        side:        CoinbaseOrderSide,
        base_size:   str,
        limit_price: str,
        post_only:   bool = False,
    ) -> Dict[str, Any]:
        """Submit a GTC limit order."""
        client_order_id = str(uuid.uuid4())
        payload = {
            "client_order_id": client_order_id,
            "product_id":      product_id,
            "side":            side.value,
            "order_configuration": {
                "limit_limit_gtc": {
                    "base_size":   base_size,
                    "limit_price": limit_price,
                    "post_only":   post_only,
                }
            },
        }
        resp = self._request("POST", "/api/v3/brokerage/orders", payload=payload)
        self._record_order(resp, product_id, side, CoinbaseOrderType.LIMIT_LIMIT_GTC, client_order_id)
        return resp

    def create_stop_limit_order(
        self,
        product_id:  str,
        side:        CoinbaseOrderSide,
        base_size:   str,
        limit_price: str,
        stop_price:  str,
    ) -> Dict[str, Any]:
        """Submit a stop-limit GTC order for risk-managed exits."""
        client_order_id = str(uuid.uuid4())
        payload = {
            "client_order_id": client_order_id,
            "product_id":      product_id,
            "side":            side.value,
            "order_configuration": {
                "stop_limit_stop_limit_gtc": {
                    "base_size":   base_size,
                    "limit_price": limit_price,
                    "stop_price":  stop_price,
                    "stop_direction": (
                        "STOP_DIRECTION_STOP_DOWN"
                        if side == CoinbaseOrderSide.SELL
                        else "STOP_DIRECTION_STOP_UP"
                    ),
                }
            },
        }
        resp = self._request("POST", "/api/v3/brokerage/orders", payload=payload)
        self._record_order(resp, product_id, side, CoinbaseOrderType.STOP_LIMIT_STOP_LIMIT_GTC, client_order_id)
        return resp

    def cancel_orders(self, order_ids: List[str]) -> Dict[str, Any]:
        """Cancel one or more open orders by ID."""
        payload = {"order_ids": order_ids}
        return self._request("POST", "/api/v3/brokerage/orders/batch_cancel", payload=payload)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Fetch a single order by its server-assigned ID."""
        return self._request("GET", f"/api/v3/brokerage/orders/historical/{order_id}")

    def list_orders(
        self,
        product_id: Optional[str] = None,
        status:     Optional[str] = None,
        limit:      int = 100,
    ) -> List[Dict[str, Any]]:
        """List historical orders, optionally filtered by product or status."""
        params: Dict[str, Any] = {"limit": limit}
        if product_id:
            params["product_id"] = product_id
        if status:
            params["order_status"] = status
        resp = self._request("GET", "/api/v3/brokerage/orders/historical/batch", params)
        return resp.get("orders", [])

    # ------------------------------------------------------------------
    # Portfolio / balances
    # ------------------------------------------------------------------

    def get_portfolios(self) -> List[Dict[str, Any]]:
        """List all portfolios in the account."""
        resp = self._request("GET", "/api/v3/brokerage/portfolios")
        return resp.get("portfolios", [])

    def get_portfolio_breakdown(self, portfolio_uuid: str) -> Dict[str, Any]:
        """Detailed breakdown of positions and balances for a portfolio."""
        return self._request("GET", f"/api/v3/brokerage/portfolios/{portfolio_uuid}")

    def get_balances(self) -> List[CoinbaseBalance]:
        """Return spot account balances across all currencies."""
        resp = self._request("GET", "/api/v3/brokerage/accounts")
        balances = []
        for acct in resp.get("accounts", []):
            av = acct.get("available_balance", {})
            hd = acct.get("hold", {})
            currency = av.get("currency", acct.get("currency", ""))
            total_val = str(
                float(av.get("value", "0")) + float(hd.get("value", "0"))
            )
            balances.append(
                CoinbaseBalance(
                    currency          = currency,
                    available_balance = av.get("value", "0"),
                    hold              = hd.get("value", "0"),
                    total             = total_val,
                )
            )
        return balances

    # ------------------------------------------------------------------
    # WebSocket streaming
    # ------------------------------------------------------------------

    def subscribe(
        self,
        channel:     str,
        product_ids: List[str],
        callback:    Callable[[Dict[str, Any]], None],
    ) -> None:
        """Register *callback* for *channel* messages and start the WS thread if needed."""
        key = f"{channel}::{','.join(sorted(product_ids))}"
        with self._lock:
            self._ws_callbacks.setdefault(key, []).append(callback)
        if not self._ws_running:
            self._start_ws(channel, product_ids)

    def _start_ws(self, channel: str, product_ids: List[str]) -> None:
        """Start the background WebSocket listener thread."""
        self._ws_running = True
        self._ws_thread  = threading.Thread(
            target=self._ws_loop,
            args=(channel, product_ids),
            daemon=True,
            name="coinbase-ws",
        )
        self._ws_thread.start()

    def _ws_loop(self, channel: str, product_ids: List[str]) -> None:
        """Internal WebSocket event loop (runs in daemon thread)."""
        try:
            import websocket  # type: ignore  # lazy import
        except ImportError as exc:
            logger.warning("websocket-client not installed — WS streaming disabled: %s", exc)
            self._ws_running = False
            return

        ws_url = self._ws_url
        timestamp = str(int(time.time()))
        message   = timestamp + "subscribe" + ",".join(product_ids)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        subscribe_msg = json.dumps({
            "type":        "subscribe",
            "product_ids": product_ids,
            "channel":     channel,
            "api_key":     self.api_key,
            "timestamp":   timestamp,
            "signature":   signature,
        })

        def on_message(ws: Any, raw: str) -> None:  # noqa: ANN001
            try:
                data = json.loads(raw)
                for callbacks in self._ws_callbacks.values():
                    for cb in callbacks:
                        try:
                            cb(data)
                        except Exception as exc:
                            logger.debug("WS callback error: %s", exc)
            except Exception as exc:
                logger.debug("WS message parse error: %s", exc)

        def on_error(ws: Any, err: Any) -> None:  # noqa: ANN001
            logger.error("Coinbase WS error: %s", err)
            with self._lock:
                self.status = CoinbaseConnectionStatus.ERROR

        def on_close(ws: Any, code: Any, reason: Any) -> None:  # noqa: ANN001
            logger.info("Coinbase WS closed — code=%s reason=%s", code, reason)
            self._ws_running = False

        def on_open(ws: Any) -> None:  # noqa: ANN001
            ws.send(subscribe_msg)
            logger.info("Coinbase WS subscribed — channel=%s products=%s", channel, product_ids)

        ws_app = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )
        try:
            ws_app.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as exc:
            logger.error("Coinbase WS loop terminated: %s", exc)
        finally:
            self._ws_running = False

    def close(self) -> None:
        """Stop WebSocket streaming and mark connector as disconnected."""
        self._ws_running = False
        with self._lock:
            self.status = CoinbaseConnectionStatus.DISCONNECTED
        logger.info("CoinbaseConnector closed")

    def __enter__(self) -> "CoinbaseConnector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _record_order(
        self,
        resp:             Dict[str, Any],
        product_id:       str,
        side:             CoinbaseOrderSide,
        order_type:       CoinbaseOrderType,
        client_order_id:  str,
    ) -> None:
        """Persist an order response into the local history ring buffer."""
        success_resp = resp.get("success_response", {})
        order_id = success_resp.get("order_id", resp.get("order_id", "unknown"))
        order = CoinbaseOrder(
            order_id        = order_id,
            client_order_id = client_order_id,
            product_id      = product_id,
            side            = side,
            order_type      = order_type,
            status          = CoinbaseOrderStatus.PENDING,
            created_time    = datetime.now(timezone.utc).isoformat(),
            raw             = resp,
        )
        with self._lock:
            try:
                from thread_safe_operations import capped_append
            except ImportError:
                def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
                    """Fallback bounded append (CWE-770)."""
                    if len(target_list) >= max_size:
                        del target_list[: max_size // 10]
                    target_list.append(item)
            capped_append(self._order_history, order, _MAX_ORDER_HISTORY)

    def get_order_history(self) -> List[CoinbaseOrder]:
        """Return a snapshot of the local order ring buffer."""
        with self._lock:
            return list(self._order_history)

    # ------------------------------------------------------------------
    # Convenience aliases matching the interface contract
    # ------------------------------------------------------------------

    def get_accounts(self) -> List[Dict[str, Any]]:
        """List all Coinbase brokerage accounts."""
        resp = self._request("GET", "/api/v3/brokerage/accounts")
        return resp.get("accounts", [])

    def get_ticker(self, product_id: str) -> Optional[CoinbaseTicker]:
        """Get the current best bid/ask for a single product."""
        tickers = self.get_best_bid_ask([product_id])
        return tickers[0] if tickers else None

    def place_market_order(
        self,
        product_id: str,
        side: str,
        size: str,
    ) -> Dict[str, Any]:
        """Place a market order. *side* is 'BUY' or 'SELL'; *size* is base size."""
        order_side = CoinbaseOrderSide(side.upper())
        return self.create_market_order(product_id, order_side, base_size=size)

    def place_limit_order(
        self,
        product_id: str,
        side: str,
        size: str,
        price: str,
    ) -> Dict[str, Any]:
        """Place a GTC limit order."""
        order_side = CoinbaseOrderSide(side.upper())
        return self.create_limit_order(product_id, order_side, base_size=size, limit_price=price)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel a single open order by ID."""
        return self.cancel_orders([order_id])

    def get_product_candles(
        self,
        product_id:  str,
        start:       int,
        end:         int,
        granularity: str = "ONE_HOUR",
    ) -> List[Dict[str, Any]]:
        """Return OHLCV candles (alias for get_candles)."""
        return self.get_candles(product_id, start, end, granularity)

    def health_check(self) -> Dict[str, Any]:
        """Lightweight connectivity test — fetches the server time."""
        t0   = time.monotonic()
        resp = self._request("GET", "/api/v3/brokerage/time")
        ms   = int((time.monotonic() - t0) * 1000)
        ok   = "iso" in resp or "epochSeconds" in resp
        return {
            "connected":  ok,
            "sandbox":    self.sandbox,
            "latency_ms": ms,
            "status":     self.status.value,
            "server_time": resp.get("iso", resp.get("epochSeconds")),
        }
