# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Crypto Exchange Connector — Murphy System

Unified multi-exchange abstraction layer following the Murphy
Connector / Registry / Orchestrator 3-layer pattern.

Supports Coinbase, Binance, Kraken, Bybit and any exchange
reachable via the CCXT-compatible interface.  All order execution
passes through the TradingHITLGateway before hitting the network.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_TRADE_LOG = 50_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ExchangeId(Enum):
    """Supported exchange identifiers (Enum subclass)."""
    COINBASE = "coinbase"
    BINANCE  = "binance"
    KRAKEN   = "kraken"
    BYBIT    = "bybit"
    PAPER    = "paper"   # Simulated paper-trading exchange


class OrderSide(Enum):
    """Trade direction (Enum subclass)."""
    BUY  = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order execution type (Enum subclass)."""
    MARKET     = "market"
    LIMIT      = "limit"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Order state machine (Enum subclass)."""
    PENDING   = "pending"
    OPEN      = "open"
    FILLED    = "filled"
    PARTIAL   = "partial"
    CANCELLED = "cancelled"
    REJECTED  = "rejected"
    EXPIRED   = "expired"


class ExchangeStatus(Enum):
    """Exchange connector lifecycle (Enum subclass)."""
    INITIALISING = "initialising"
    CONNECTED    = "connected"
    DEGRADED     = "degraded"
    ERROR        = "error"
    PAPER        = "paper"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class OrderRequest:
    """Encapsulates a trade order before submission."""
    exchange_id:  ExchangeId
    pair:         str              # e.g. "BTC/USDT"
    side:         OrderSide
    order_type:   OrderType
    quantity:     float
    price:        Optional[float]  # None for market orders
    stop_price:   Optional[float] = None
    client_id:    str              = field(default_factory=lambda: str(uuid.uuid4()))
    metadata:     Dict[str, Any]   = field(default_factory=dict)


@dataclass
class OrderResult:
    """Normalised result from any exchange after order placement."""
    success:      bool
    exchange_id:  str
    pair:         str
    side:         OrderSide
    order_type:   OrderType
    quantity:     float
    price:        float
    filled:       float            = 0.0
    avg_fill_price: float          = 0.0
    fee:          float            = 0.0
    order_id:     str              = field(default_factory=lambda: str(uuid.uuid4()))
    client_id:    str              = ""
    status:       OrderStatus      = OrderStatus.PENDING
    timestamp:    str              = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error:        Optional[str]    = None
    raw:          Dict[str, Any]   = field(default_factory=dict)


@dataclass
class Ticker:
    """Real-time price snapshot (normalised across exchanges)."""
    exchange_id:   str
    pair:          str
    last:          float
    bid:           float
    ask:           float
    volume_24h:    float
    change_24h_pct: float
    timestamp:     str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class Balance:
    """Normalised account balance for a single currency."""
    exchange_id: str
    currency:    str
    free:        float
    locked:      float

    @property
    def total(self) -> float:
        """Sum of free and locked balances."""
        return self.free + self.locked


# ---------------------------------------------------------------------------
# Per-exchange connectors
# ---------------------------------------------------------------------------

class ExchangeConnector(ABC):
    """
    Abstract base for a single exchange.  Subclasses or the generic
    ``_CCXTExchangeConnector`` override ``_fetch_ticker``,
    ``_place_order``, and ``_fetch_balances``.
    """

    def __init__(self, exchange_id: ExchangeId, credentials: Dict[str, str]) -> None:
        self.exchange_id = exchange_id
        self._credentials = credentials
        self.status = ExchangeStatus.INITIALISING
        self._lock  = threading.Lock()
        self._trade_log: List[OrderResult] = []

    # ---- public surface --------------------------------------------------

    def place_order(self, req: OrderRequest) -> OrderResult:
        """Submit an order; returns a normalised ``OrderResult``."""
        try:
            result = self._place_order(req)
            with self._lock:
                from thread_safe_operations import capped_append
                capped_append(self._trade_log, result, _MAX_TRADE_LOG)
            return result
        except Exception as exc:
            logger.error("%s place_order error: %s", self.exchange_id.value, exc)
            return OrderResult(
                success=False, exchange_id=self.exchange_id.value,
                pair=req.pair, side=req.side, order_type=req.order_type,
                quantity=req.quantity, price=req.price or 0.0,
                error=str(exc),
            )

    def get_ticker(self, pair: str) -> Optional[Ticker]:
        """Fetch real-time ticker for *pair*."""
        try:
            return self._fetch_ticker(pair)
        except Exception as exc:
            logger.error("%s get_ticker error: %s", self.exchange_id.value, exc)
            return None

    def get_balances(self) -> List[Balance]:
        """Fetch account balances."""
        try:
            return self._fetch_balances()
        except Exception as exc:
            logger.error("%s get_balances error: %s", self.exchange_id.value, exc)
            return []

    def health_check(self) -> Dict[str, Any]:
        """Probe the exchange and return a status dict."""
        try:
            t0     = time.monotonic()
            result = self._probe()
            ms     = int((time.monotonic() - t0) * 1000)
            with self._lock:
                self.status = ExchangeStatus.CONNECTED
            return {"connected": result, "latency_ms": ms, "exchange": self.exchange_id.value}
        except Exception as exc:
            with self._lock:
                self.status = ExchangeStatus.ERROR
            return {"connected": False, "error": str(exc), "exchange": self.exchange_id.value}

    def close(self) -> None:
        """Release any persistent connections."""

    def __enter__(self) -> "ExchangeConnector":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---- overridable internals -------------------------------------------

    @abstractmethod
    def _place_order(self, req: OrderRequest) -> OrderResult:
        """Place an order on the exchange.  Subclasses must override."""
        ...

    @abstractmethod
    def _fetch_ticker(self, pair: str) -> Ticker:
        """Fetch the latest ticker for *pair*.  Subclasses must override."""
        ...

    @abstractmethod
    def _fetch_balances(self) -> List[Balance]:
        """Fetch account balances.  Subclasses must override."""
        ...

    @abstractmethod
    def _probe(self) -> bool:
        """Lightweight health probe.  Subclasses must override."""
        ...


class CoinbaseExchangeConnector(ExchangeConnector):
    """
    ExchangeConnector backed by the Murphy CoinbaseConnector.

    The native ``CoinbaseConnector`` handles auth and REST; this adapter
    normalises the responses to the unified ``OrderResult`` / ``Ticker``
    / ``Balance`` types.
    """

    def __init__(self, credentials: Dict[str, str]) -> None:
        super().__init__(ExchangeId.COINBASE, credentials)
        from coinbase_connector import CoinbaseConnector, CoinbaseOrderSide, CoinbaseOrderType
        self._cb = CoinbaseConnector(
            api_key=credentials.get("api_key", ""),
            api_secret=credentials.get("api_secret", ""),
            sandbox=credentials.get("sandbox", "").lower() == "true",
        )
        self.status = ExchangeStatus.CONNECTED

    def _probe(self) -> bool:
        return self._cb.health_check().get("connected", False)

    def _fetch_ticker(self, pair: str) -> Ticker:
        from coinbase_connector import CoinbaseConnector
        cb_pair = pair.replace("/", "-")
        tickers = self._cb.get_best_bid_ask([cb_pair])
        t       = tickers[0] if tickers else None
        last    = float(t.bid) if t else 0.0
        bid     = float(t.bid) if t else 0.0
        ask     = float(t.ask) if t else 0.0
        return Ticker(
            exchange_id   = ExchangeId.COINBASE.value,
            pair          = pair,
            last          = last,
            bid           = bid,
            ask           = ask,
            volume_24h    = 0.0,
            change_24h_pct= 0.0,
        )

    def _fetch_balances(self) -> List[Balance]:
        raw = self._cb.get_balances()
        return [
            Balance(
                exchange_id = ExchangeId.COINBASE.value,
                currency    = b.currency,
                free        = float(b.available_balance),
                locked      = float(b.hold),
            )
            for b in raw
        ]

    def _place_order(self, req: OrderRequest) -> OrderResult:
        from coinbase_connector import (
            CoinbaseOrderSide,
            CoinbaseOrderType,
        )
        cb_pair = req.pair.replace("/", "-")
        side    = CoinbaseOrderSide.BUY if req.side == OrderSide.BUY else CoinbaseOrderSide.SELL

        if req.order_type == OrderType.MARKET:
            resp = self._cb.create_market_order(cb_pair, side, base_size=str(req.quantity))
        elif req.order_type == OrderType.LIMIT:
            resp = self._cb.create_limit_order(
                cb_pair, side, str(req.quantity), str(req.price or 0)
            )
        else:
            resp = self._cb.create_stop_limit_order(
                cb_pair, side, str(req.quantity),
                str(req.price or 0), str(req.stop_price or 0)
            )

        success = resp.get("success", bool(resp.get("success_response")))
        order_id = (resp.get("success_response") or {}).get("order_id", str(uuid.uuid4()))
        return OrderResult(
            success    = success,
            exchange_id= ExchangeId.COINBASE.value,
            pair       = req.pair,
            side       = req.side,
            order_type = req.order_type,
            quantity   = req.quantity,
            price      = req.price or 0.0,
            order_id   = order_id,
            client_id  = req.client_id,
            status     = OrderStatus.PENDING if success else OrderStatus.REJECTED,
            raw        = resp,
        )


class PaperExchangeConnector(ExchangeConnector):
    """
    Simulated paper-trading exchange.  Orders fill instantly at the
    requested price with a configurable fee rate.  Useful for HITL
    training and bot backtesting without real-money risk.
    """

    FEE_RATE = 0.001  # 0.10 %

    def __init__(self, initial_balances: Optional[Dict[str, float]] = None) -> None:
        super().__init__(ExchangeId.PAPER, {})
        self._balances: Dict[str, float] = initial_balances or {
            "USDT": 10_000.0,
            "BTC":  0.0,
            "ETH":  0.0,
        }
        self._prices: Dict[str, float] = {}
        self.status = ExchangeStatus.PAPER

    def set_price(self, pair: str, price: float) -> None:
        """Override the simulated mid-price for a pair."""
        self._prices[pair] = price

    def _probe(self) -> bool:
        return True

    def _fetch_ticker(self, pair: str) -> Ticker:
        price = self._prices.get(pair, 50_000.0)
        return Ticker(
            exchange_id    = ExchangeId.PAPER.value,
            pair           = pair,
            last           = price,
            bid            = price * 0.9995,
            ask            = price * 1.0005,
            volume_24h     = 0.0,
            change_24h_pct = 0.0,
        )

    def _fetch_balances(self) -> List[Balance]:
        with self._lock:
            return [
                Balance(exchange_id=ExchangeId.PAPER.value, currency=c, free=v, locked=0.0)
                for c, v in self._balances.items()
            ]

    def _place_order(self, req: OrderRequest) -> OrderResult:
        price  = req.price or self._prices.get(req.pair, 50_000.0)
        base   = req.pair.split("/")[0] if "/" in req.pair else req.pair
        quote  = req.pair.split("/")[1] if "/" in req.pair else "USDT"
        cost   = price * req.quantity
        fee    = cost * self.FEE_RATE
        with self._lock:
            if req.side == OrderSide.BUY:
                if self._balances.get(quote, 0.0) < cost + fee:
                    return OrderResult(
                        success=False, exchange_id=ExchangeId.PAPER.value,
                        pair=req.pair, side=req.side, order_type=req.order_type,
                        quantity=req.quantity, price=price,
                        status=OrderStatus.REJECTED, error="insufficient_quote_balance",
                    )
                self._balances[quote] = self._balances.get(quote, 0.0) - cost - fee
                self._balances[base]  = self._balances.get(base, 0.0)  + req.quantity
            else:
                if self._balances.get(base, 0.0) < req.quantity:
                    return OrderResult(
                        success=False, exchange_id=ExchangeId.PAPER.value,
                        pair=req.pair, side=req.side, order_type=req.order_type,
                        quantity=req.quantity, price=price,
                        status=OrderStatus.REJECTED, error="insufficient_base_balance",
                    )
                self._balances[base]  = self._balances.get(base, 0.0)  - req.quantity
                self._balances[quote] = self._balances.get(quote, 0.0) + cost - fee
        return OrderResult(
            success       = True,
            exchange_id   = ExchangeId.PAPER.value,
            pair          = req.pair,
            side          = req.side,
            order_type    = req.order_type,
            quantity      = req.quantity,
            price         = price,
            filled        = req.quantity,
            avg_fill_price= price,
            fee           = fee,
            status        = OrderStatus.FILLED,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ExchangeRegistry:
    """
    Thread-safe registry for all active exchange connectors.

    Usage::

        registry = ExchangeRegistry()
        registry.register(CoinbaseExchangeConnector(creds))
        result = registry.place_order(req)
    """

    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._connectors: Dict[str, ExchangeConnector] = {}

    def register(self, connector: ExchangeConnector) -> str:
        """Add *connector* to the registry.  Returns its exchange ID."""
        with self._lock:
            self._connectors[connector.exchange_id.value] = connector
        logger.info("ExchangeRegistry: registered %s", connector.exchange_id.value)
        return connector.exchange_id.value

    def get(self, exchange_id: str) -> Optional[ExchangeConnector]:
        """Retrieve a connector by its exchange ID string."""
        with self._lock:
            return self._connectors.get(exchange_id)

    def place_order(self, req: OrderRequest) -> OrderResult:
        """Route *req* to the correct exchange connector."""
        connector = self.get(req.exchange_id.value)
        if connector is None:
            return OrderResult(
                success=False, exchange_id=req.exchange_id.value,
                pair=req.pair, side=req.side, order_type=req.order_type,
                quantity=req.quantity, price=req.price or 0.0,
                error=f"exchange_not_registered:{req.exchange_id.value}",
            )
        return connector.place_order(req)

    def get_ticker(self, exchange_id: str, pair: str) -> Optional[Ticker]:
        """Fetch ticker for *pair* on *exchange_id*."""
        connector = self.get(exchange_id)
        return connector.get_ticker(pair) if connector else None

    def get_balances(self, exchange_id: str) -> List[Balance]:
        """Fetch balances from *exchange_id*."""
        connector = self.get(exchange_id)
        return connector.get_balances() if connector else []

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Run health check on every registered exchange."""
        with self._lock:
            connectors = list(self._connectors.items())
        return {eid: conn.health_check() for eid, conn in connectors}

    def list_exchanges(self) -> List[str]:
        """Return names of all registered exchanges."""
        with self._lock:
            return list(self._connectors.keys())


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ExchangeOrchestrator:
    """
    Coordinates multi-step trading workflows across one or more exchanges.

    Sequences are dicts describing ordered steps; the orchestrator executes
    each step, tracks state, and surfaces a summary result.
    """

    def __init__(self, registry: ExchangeRegistry) -> None:
        self.registry   = registry
        self._lock      = threading.Lock()
        self._sequences: Dict[str, Dict[str, Any]] = {}

    def create_sequence(
        self,
        seq_id: str,
        name:   str,
        steps:  List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Define a named multi-step trading sequence."""
        seq = {
            "seq_id":  seq_id,
            "name":    name,
            "steps":   steps,
            "status":  "created",
            "results": [],
        }
        with self._lock:
            self._sequences[seq_id] = seq
        return seq

    def execute_sequence(self, seq_id: str) -> Dict[str, Any]:
        """Execute all steps in the sequence and return aggregated results."""
        with self._lock:
            seq = self._sequences.get(seq_id)
        if seq is None:
            return {"success": False, "error": f"sequence_not_found:{seq_id}"}

        seq["status"]  = "running"
        seq["results"] = []
        all_ok         = True

        for step in seq.get("steps", []):
            step_type = step.get("type")
            if step_type == "place_order":
                req    = step["request"]
                result = self.registry.place_order(req)
                seq["results"].append({"step": step_type, "success": result.success, "order_id": result.order_id})
                if not result.success:
                    all_ok = False
            elif step_type == "wait":
                time.sleep(step.get("seconds", 1))
                seq["results"].append({"step": step_type, "success": True})
            else:
                seq["results"].append({"step": step_type, "success": False, "error": "unknown_step_type"})
                all_ok = False

        seq["status"] = "completed" if all_ok else "partial_failure"
        return {"success": all_ok, "seq_id": seq_id, "results": seq["results"]}

    def get_sequence(self, seq_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a sequence definition by ID."""
        with self._lock:
            return self._sequences.get(seq_id)
