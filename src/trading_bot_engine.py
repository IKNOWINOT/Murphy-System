"""
TRADING BOT ENGINE — Internal-Only Trading System with Reverse Inference

WARNING: LIVE TRADING IS DISABLED BY DEFAULT.
Live trading requires regulatory compliance review before activation.
Trading is ONLY enabled after systematic profitability is proven in paper-trading mode.
This module is for INTERNAL USE ONLY — not a public trading platform.

WARNING: Before enabling live trading, ensure compliance with:
- SEC regulations (if trading US securities)
- FINRA rules (if applicable)
- Local financial regulations
- Anti-money laundering (AML) requirements
- Know Your Customer (KYC) requirements

Components:
1. Market data ingestion (stocks, crypto, options)
2. Reverse inference engine (corporate takeover detection)
3. Trading strategy engine (mean_reversion, momentum, pairs, value, reverse_inference)
4. Paper trading simulator with P&L tracking
5. Risk management (Kelly criterion, stop-loss, position limits)
6. Portfolio tracker (positions, P&L, tax lots)
7. Trading account integration hooks (DISABLED by default)
8. AI optimization layer (strategy parameter tuning)
"""

import json
import logging
import math
import statistics
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append, capped_append_paired
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)
    def capped_append_paired(*lists_and_items: Any, max_size: int = 10_000) -> None:
        """Fallback bounded paired append (CWE-770)."""
        pairs = list(zip(lists_and_items[::2], lists_and_items[1::2]))
        if not pairs:
            return
        ref_list = pairs[0][0]
        if len(ref_list) >= max_size:
            trim = max_size // 10
            for lst, _ in pairs:
                del lst[:trim]
        for lst, item in pairs:
            lst.append(item)

logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY: LIVE TRADING IS DISABLED BY DEFAULT
# WARNING: Do NOT change this without regulatory compliance review.
# =============================================================================
LIVE_TRADING_ENABLED = False


class AssetClass(Enum):
    """Asset class (Enum subclass)."""
    STOCK = "stock"
    CRYPTO = "crypto"
    OPTION = "option"


class Signal(Enum):
    """Signal (Enum subclass)."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class MarketRegime(Enum):
    """Market regime (Enum subclass)."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"


class PositionSizingMethod(Enum):
    """Position sizing method (Enum subclass)."""
    KELLY = "kelly"
    FIXED_FRACTIONAL = "fixed_fractional"
    EQUAL_WEIGHT = "equal_weight"


class TradingMode(Enum):
    """Trading mode (Enum subclass)."""
    PAPER = "paper"
    LIVE = "live"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class MarketData:
    """Market data."""
    symbol: str
    asset_class: AssetClass
    price: float
    volume: float
    timestamp: float
    bid: float = 0.0
    ask: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open_price: float = 0.0
    book_value: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    market_cap: float = 0.0
    shares_outstanding: float = 0.0
    cash_position: float = 0.0
    revenue_history: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp,
            "bid": self.bid,
            "ask": self.ask,
            "high": self.high,
            "low": self.low,
            "open_price": self.open_price,
            "book_value": self.book_value,
            "total_assets": self.total_assets,
            "total_liabilities": self.total_liabilities,
            "market_cap": self.market_cap,
            "shares_outstanding": self.shares_outstanding,
            "cash_position": self.cash_position,
            "revenue_history": self.revenue_history,
        }


@dataclass
class TradeOrder:
    """Trade order."""
    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    price: float
    timestamp: float
    strategy: str
    confidence: float
    mode: TradingMode = TradingMode.PAPER
    filled: bool = False
    fill_price: float = 0.0
    fill_timestamp: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "confidence": self.confidence,
            "mode": self.mode.value,
            "filled": self.filled,
            "fill_price": self.fill_price,
            "fill_timestamp": self.fill_timestamp,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }


@dataclass
class Position:
    """Position."""
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    opened_at: float
    strategy: str
    stop_loss: float = 0.0
    take_profit: float = 0.0
    realized_pnl: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_entry_price) * self.quantity

    @property
    def market_value(self) -> float:
        return self.current_price * self.quantity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "market_value": self.market_value,
            "opened_at": self.opened_at,
            "strategy": self.strategy,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
        }


@dataclass
class TaxLot:
    """Tax lot."""
    lot_id: str
    symbol: str
    quantity: float
    purchase_price: float
    purchase_date: float
    sale_price: float = 0.0
    sale_date: float = 0.0
    realized_gain: float = 0.0
    is_closed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_id": self.lot_id,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "purchase_price": self.purchase_price,
            "purchase_date": self.purchase_date,
            "sale_price": self.sale_price,
            "sale_date": self.sale_date,
            "realized_gain": self.realized_gain,
            "is_closed": self.is_closed,
        }


# =============================================================================
# Market Data Ingestion
# =============================================================================

class MarketDataIngestion:
    """Ingest price, volume, order book, and fundamental data."""

    def __init__(self):
        self._lock = threading.RLock()
        self._data_store: Dict[str, List[MarketData]] = {}
        self._latest: Dict[str, MarketData] = {}

    def ingest(self, data: MarketData) -> Dict[str, Any]:
        with self._lock:
            if data.symbol not in self._data_store:
                self._data_store[data.symbol] = []
            self._data_store[data.symbol].append(data)
            self._latest[data.symbol] = data
            return {"status": "ingested", "symbol": data.symbol, "price": data.price}

    def get_latest(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            md = self._latest.get(symbol)
            return md.to_dict() if md else None

    def get_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            history = self._data_store.get(symbol, [])
            return [d.to_dict() for d in history[-limit:]]

    def get_symbols(self) -> List[str]:
        with self._lock:
            return list(self._latest.keys())


# =============================================================================
# Reverse Inference Engine — Corporate Takeover Detection
# =============================================================================

class ReverseInferenceEngine:
    """
    Detect when a company's stock price drops below intrinsic value.

    Key insight: if stock_price < (total_assets - total_liabilities) /
    shares_outstanding * (1 - margin), the company is a takeover candidate.
    """

    def __init__(self, margin: float = 0.20):
        self._margin = margin
        self._lock = threading.RLock()
        self._candidates: Dict[str, Dict[str, Any]] = {}

    def calculate_intrinsic_value(self, data: MarketData) -> float:
        if data.shares_outstanding <= 0:
            return 0.0
        return (data.total_assets - data.total_liabilities) / data.shares_outstanding

    def is_takeover_candidate(self, data: MarketData) -> bool:
        intrinsic = self.calculate_intrinsic_value(data)
        if intrinsic <= 0:
            return False
        threshold = intrinsic * (1 - self._margin)
        return data.price < threshold

    def score_candidate(self, data: MarketData) -> Dict[str, Any]:
        """Score a takeover candidate on multiple dimensions."""
        intrinsic = self.calculate_intrinsic_value(data)
        if intrinsic <= 0 or data.shares_outstanding <= 0:
            return {"symbol": data.symbol, "is_candidate": False, "score": 0.0}

        discount = (intrinsic - data.price) / intrinsic if intrinsic > 0 else 0.0
        discount = max(0.0, min(1.0, discount))

        debt_ratio = (
            data.total_liabilities / data.total_assets
            if data.total_assets > 0
            else 1.0
        )
        asset_quality = max(0.0, 1.0 - debt_ratio)

        cash_score = 0.0
        if data.total_assets > 0:
            cash_score = min(1.0, data.cash_position / data.total_assets)

        revenue_trend = 0.5
        if len(data.revenue_history) >= 2:
            diffs = [
                data.revenue_history[i] - data.revenue_history[i - 1]
                for i in range(1, len(data.revenue_history))
            ]
            avg_diff = sum(diffs) / (len(diffs) or 1)
            base = abs(data.revenue_history[0]) if data.revenue_history[0] != 0 else 1.0
            trend = avg_diff / base
            revenue_trend = max(0.0, min(1.0, 0.5 + trend))

        composite = (
            discount * 0.30
            + asset_quality * 0.25
            + (1.0 - debt_ratio) * 0.15
            + cash_score * 0.15
            + revenue_trend * 0.15
        )
        composite = max(0.0, min(1.0, composite))

        is_candidate = self.is_takeover_candidate(data)

        result = {
            "symbol": data.symbol,
            "is_candidate": is_candidate,
            "intrinsic_value": round(intrinsic, 4),
            "current_price": data.price,
            "discount_to_book_value": round(discount, 4),
            "asset_quality_score": round(asset_quality, 4),
            "debt_ratio": round(debt_ratio, 4),
            "cash_score": round(cash_score, 4),
            "revenue_trend": round(revenue_trend, 4),
            "composite_score": round(composite, 4),
            "margin": self._margin,
        }

        if is_candidate:
            with self._lock:
                self._candidates[data.symbol] = result

        return result

    def get_candidates(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._candidates)

    def clear_candidates(self) -> None:
        with self._lock:
            self._candidates.clear()


# =============================================================================
# Trading Strategy Engine
# =============================================================================

class TradingStrategyEngine:
    """Produces BUY/SELL/HOLD signals with confidence scores."""

    def __init__(self):
        self._lock = threading.RLock()
        self._reverse_engine = ReverseInferenceEngine()
        self._strategy_weights: Dict[str, float] = {
            "mean_reversion": 1.0,
            "momentum": 1.0,
            "pairs_trading": 1.0,
            "value_investing": 1.0,
            "reverse_inference_takeover": 1.0,
        }

    def mean_reversion(self, prices: List[float], current: float) -> Dict[str, Any]:
        if len(prices) < 2:
            return {"signal": Signal.HOLD.value, "confidence": 0.0, "strategy": "mean_reversion"}
        mean = statistics.mean(prices)
        std = statistics.stdev(prices) if len(prices) > 1 else 1.0
        if std == 0:
            std = 1.0
        z_score = (current - mean) / std
        if z_score < -1.5:
            confidence = min(1.0, abs(z_score) / 3.0)
            return {"signal": Signal.BUY.value, "confidence": round(confidence, 4), "strategy": "mean_reversion", "z_score": round(z_score, 4)}
        elif z_score > 1.5:
            confidence = min(1.0, abs(z_score) / 3.0)
            return {"signal": Signal.SELL.value, "confidence": round(confidence, 4), "strategy": "mean_reversion", "z_score": round(z_score, 4)}
        return {"signal": Signal.HOLD.value, "confidence": round(1.0 - abs(z_score) / 3.0, 4), "strategy": "mean_reversion", "z_score": round(z_score, 4)}

    def momentum(self, prices: List[float], lookback: int = 10) -> Dict[str, Any]:
        if len(prices) < 2:
            return {"signal": Signal.HOLD.value, "confidence": 0.0, "strategy": "momentum"}
        recent = prices[-min(lookback, len(prices)):]
        returns = [(recent[i] - recent[i - 1]) / recent[i - 1] for i in range(1, len(recent)) if recent[i - 1] != 0]
        if not returns:
            return {"signal": Signal.HOLD.value, "confidence": 0.0, "strategy": "momentum"}
        avg_return = statistics.mean(returns)
        confidence = min(1.0, abs(avg_return) * 20)
        if avg_return > 0.01:
            return {"signal": Signal.BUY.value, "confidence": round(confidence, 4), "strategy": "momentum", "avg_return": round(avg_return, 6)}
        elif avg_return < -0.01:
            return {"signal": Signal.SELL.value, "confidence": round(confidence, 4), "strategy": "momentum", "avg_return": round(avg_return, 6)}
        return {"signal": Signal.HOLD.value, "confidence": round(1.0 - confidence, 4), "strategy": "momentum", "avg_return": round(avg_return, 6)}

    def pairs_trading(self, prices_a: List[float], prices_b: List[float]) -> Dict[str, Any]:
        if len(prices_a) < 2 or len(prices_b) < 2:
            return {"signal": Signal.HOLD.value, "confidence": 0.0, "strategy": "pairs_trading"}
        min_len = min(len(prices_a), len(prices_b))
        ratios = [prices_a[i] / prices_b[i] for i in range(min_len) if prices_b[i] != 0]
        if len(ratios) < 2:
            return {"signal": Signal.HOLD.value, "confidence": 0.0, "strategy": "pairs_trading"}
        mean_ratio = statistics.mean(ratios)
        std_ratio = statistics.stdev(ratios) if len(ratios) > 1 else 1.0
        if std_ratio == 0:
            std_ratio = 1.0
        current_ratio = ratios[-1]
        z = (current_ratio - mean_ratio) / std_ratio
        if z > 1.5:
            return {"signal": Signal.SELL.value, "confidence": round(min(1.0, abs(z) / 3.0), 4), "strategy": "pairs_trading", "z_score": round(z, 4)}
        elif z < -1.5:
            return {"signal": Signal.BUY.value, "confidence": round(min(1.0, abs(z) / 3.0), 4), "strategy": "pairs_trading", "z_score": round(z, 4)}
        return {"signal": Signal.HOLD.value, "confidence": round(1.0 - abs(z) / 3.0, 4), "strategy": "pairs_trading", "z_score": round(z, 4)}

    def value_investing(self, data: MarketData) -> Dict[str, Any]:
        if data.shares_outstanding <= 0 or data.total_assets <= 0:
            return {"signal": Signal.HOLD.value, "confidence": 0.0, "strategy": "value_investing"}
        book_value_per_share = (data.total_assets - data.total_liabilities) / data.shares_outstanding
        if book_value_per_share <= 0:
            return {"signal": Signal.HOLD.value, "confidence": 0.0, "strategy": "value_investing"}
        pb_ratio = data.price / book_value_per_share if book_value_per_share != 0 else 999
        if pb_ratio < 0.8:
            confidence = min(1.0, (1.0 - pb_ratio) * 1.5)
            return {"signal": Signal.BUY.value, "confidence": round(confidence, 4), "strategy": "value_investing", "pb_ratio": round(pb_ratio, 4)}
        elif pb_ratio > 2.0:
            confidence = min(1.0, (pb_ratio - 1.0) / 3.0)
            return {"signal": Signal.SELL.value, "confidence": round(confidence, 4), "strategy": "value_investing", "pb_ratio": round(pb_ratio, 4)}
        return {"signal": Signal.HOLD.value, "confidence": 0.5, "strategy": "value_investing", "pb_ratio": round(pb_ratio, 4)}

    def reverse_inference_takeover(self, data: MarketData) -> Dict[str, Any]:
        result = self._reverse_engine.score_candidate(data)
        if result["is_candidate"]:
            return {
                "signal": Signal.BUY.value,
                "confidence": round(result["composite_score"], 4),
                "strategy": "reverse_inference_takeover",
                "takeover_score": result,
            }
        return {
            "signal": Signal.HOLD.value,
            "confidence": 0.0,
            "strategy": "reverse_inference_takeover",
            "takeover_score": result,
        }

    def get_all_signals(self, data: MarketData, price_history: List[float]) -> List[Dict[str, Any]]:
        signals = []
        signals.append(self.mean_reversion(price_history, data.price))
        signals.append(self.momentum(price_history))
        signals.append(self.value_investing(data))
        signals.append(self.reverse_inference_takeover(data))
        return signals

    def update_weights(self, strategy: str, weight: float) -> None:
        with self._lock:
            if strategy in self._strategy_weights:
                self._strategy_weights[strategy] = max(0.0, min(2.0, weight))

    def get_weights(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._strategy_weights)


# =============================================================================
# Risk Management
# =============================================================================

class RiskManager:
    """Position sizing, stop-loss, and portfolio risk controls."""

    def __init__(
        self,
        max_position_pct: float = 0.05,
        max_daily_loss_pct: float = 0.02,
        max_portfolio_exposure: float = 0.80,
        max_correlation: float = 0.70,
    ):
        self._lock = threading.RLock()
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_portfolio_exposure = max_portfolio_exposure
        self.max_correlation = max_correlation
        self._daily_pnl: float = 0.0
        self._daily_reset_date: str = ""
        self._emergency_stop_active = False

    def kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        win_loss_ratio = avg_win / abs(avg_loss)
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        return max(0.0, min(self.max_position_pct, kelly))

    def fixed_fractional(self, portfolio_value: float, risk_per_trade: float = 0.01) -> float:
        return portfolio_value * min(risk_per_trade, self.max_position_pct)

    def equal_weight(self, portfolio_value: float, num_positions: int) -> float:
        if num_positions <= 0:
            return 0.0
        weight = 1.0 / num_positions
        capped = min(weight, self.max_position_pct)
        return portfolio_value * capped

    def calculate_position_size(
        self,
        method: PositionSizingMethod,
        portfolio_value: float,
        win_rate: float = 0.5,
        avg_win: float = 1.0,
        avg_loss: float = 1.0,
        num_positions: int = 10,
        risk_per_trade: float = 0.01,
    ) -> Dict[str, Any]:
        if method == PositionSizingMethod.KELLY:
            fraction = self.kelly_criterion(win_rate, avg_win, avg_loss)
            size = portfolio_value * fraction
        elif method == PositionSizingMethod.FIXED_FRACTIONAL:
            size = self.fixed_fractional(portfolio_value, risk_per_trade)
            fraction = risk_per_trade
        else:
            size = self.equal_weight(portfolio_value, num_positions)
            fraction = 1.0 / num_positions if num_positions > 0 else 0.0
        return {
            "method": method.value,
            "position_size": round(size, 2),
            "fraction": round(fraction, 4),
            "max_position_pct": self.max_position_pct,
        }

    def check_stop_loss(self, entry_price: float, current_price: float, stop_loss_pct: float) -> Dict[str, Any]:
        if entry_price <= 0:
            return {"triggered": False, "loss_pct": 0.0}
        loss_pct = (entry_price - current_price) / entry_price
        triggered = loss_pct >= stop_loss_pct
        return {"triggered": triggered, "loss_pct": round(loss_pct, 4), "stop_loss_pct": stop_loss_pct}

    def check_take_profit(self, entry_price: float, current_price: float, take_profit_pct: float) -> Dict[str, Any]:
        if entry_price <= 0:
            return {"triggered": False, "gain_pct": 0.0}
        gain_pct = (current_price - entry_price) / entry_price
        triggered = gain_pct >= take_profit_pct
        return {"triggered": triggered, "gain_pct": round(gain_pct, 4), "take_profit_pct": take_profit_pct}

    def check_daily_loss_limit(self, portfolio_value: float) -> Dict[str, Any]:
        with self._lock:
            today = datetime.now(tz=None).strftime("%Y-%m-%d")
            if self._daily_reset_date != today:
                self._daily_pnl = 0.0
                self._daily_reset_date = today
            max_loss = portfolio_value * self.max_daily_loss_pct
            breached = abs(self._daily_pnl) >= max_loss and self._daily_pnl < 0
            return {
                "daily_pnl": round(self._daily_pnl, 2),
                "max_daily_loss": round(max_loss, 2),
                "breached": breached,
            }

    def record_daily_pnl(self, pnl: float) -> None:
        with self._lock:
            today = datetime.now(tz=None).strftime("%Y-%m-%d")
            if self._daily_reset_date != today:
                self._daily_pnl = 0.0
                self._daily_reset_date = today
            self._daily_pnl += pnl

    def emergency_stop(self) -> Dict[str, Any]:
        """Kill switch — marks emergency stop as active."""
        with self._lock:
            self._emergency_stop_active = True
            return {
                "status": "emergency_stop_activated",
                "timestamp": time.time(),
                "message": "All trading halted. Liquidate all positions.",
            }

    def is_emergency_stopped(self) -> bool:
        with self._lock:
            return self._emergency_stop_active

    def reset_emergency_stop(self) -> None:
        with self._lock:
            self._emergency_stop_active = False

    def check_position_limit(self, position_value: float, portfolio_value: float) -> Dict[str, Any]:
        if portfolio_value <= 0:
            return {"allowed": False, "reason": "invalid_portfolio_value"}
        pct = position_value / portfolio_value
        allowed = pct <= self.max_position_pct
        return {"allowed": allowed, "position_pct": round(pct, 4), "max_position_pct": self.max_position_pct}

    def check_portfolio_exposure(self, total_exposure: float, portfolio_value: float) -> Dict[str, Any]:
        if portfolio_value <= 0:
            return {"allowed": False, "exposure_pct": 0.0}
        pct = total_exposure / portfolio_value
        return {"allowed": pct <= self.max_portfolio_exposure, "exposure_pct": round(pct, 4), "max_exposure": self.max_portfolio_exposure}


# =============================================================================
# Paper Trading Simulator
# =============================================================================

class PaperTradingSimulator:
    """Simulate trades without real money. Track P&L and performance metrics."""

    def __init__(self, initial_capital: float = 100000.0, profitability_months: int = 3):
        self._lock = threading.RLock()
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.profitability_months_required = profitability_months
        self._orders: List[TradeOrder] = []
        self._filled_orders: List[TradeOrder] = []
        self._monthly_returns: List[Dict[str, Any]] = []
        self._trade_log: List[Dict[str, Any]] = []
        self._equity_curve: List[float] = [initial_capital]

    def submit_order(self, symbol: str, side: str, quantity: float, price: float,
                     strategy: str, confidence: float, stop_loss: float = 0.0,
                     take_profit: float = 0.0) -> Dict[str, Any]:
        with self._lock:
            order = TradeOrder(
                order_id=str(uuid.uuid4()),
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                timestamp=time.time(),
                strategy=strategy,
                confidence=confidence,
                mode=TradingMode.PAPER,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            capped_append(self._orders, order)
            return self._fill_order(order)

    def _fill_order(self, order: TradeOrder) -> Dict[str, Any]:
        order.filled = True
        order.fill_price = order.price
        order.fill_timestamp = time.time()
        cost = order.quantity * order.price

        if order.side == "buy":
            if cost > self.capital:
                order.filled = False
                return {"status": "rejected", "reason": "insufficient_capital", "order": order.to_dict()}
            self.capital -= cost
        elif order.side == "sell":
            self.capital += cost

        capped_append_paired(self._filled_orders, order, self._equity_curve, self.capital)

        log_entry = {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
            "capital_after": self.capital,
            "timestamp": order.fill_timestamp,
            "strategy": order.strategy,
        }
        capped_append(self._trade_log, log_entry)

        return {"status": "filled", "order": order.to_dict(), "capital": self.capital}

    def record_monthly_return(self, month: str, starting_capital: float, ending_capital: float) -> Dict[str, Any]:
        with self._lock:
            ret = (ending_capital - starting_capital) / starting_capital if starting_capital > 0 else 0.0
            entry = {
                "month": month,
                "starting_capital": starting_capital,
                "ending_capital": ending_capital,
                "return_pct": round(ret * 100, 4),
                "profitable": ret > 0,
            }
            capped_append(self._monthly_returns, entry)
            return entry

    def systematic_profitability_proven(self) -> bool:
        with self._lock:
            if len(self._monthly_returns) < self.profitability_months_required:
                return False
            recent = self._monthly_returns[-self.profitability_months_required:]
            return all(m["profitable"] for m in recent)

    def get_performance_metrics(self) -> Dict[str, Any]:
        with self._lock:
            if not self._filled_orders:
                return {
                    "total_trades": 0, "win_rate": 0.0, "total_return": 0.0,
                    "sharpe_ratio": 0.0, "max_drawdown": 0.0, "capital": self.capital,
                }

            wins = 0
            losses = 0
            trade_returns = []

            buys: Dict[str, List[TradeOrder]] = {}
            for o in self._filled_orders:
                if o.side == "buy":
                    buys.setdefault(o.symbol, []).append(o)
                elif o.side == "sell" and o.symbol in buys and buys[o.symbol]:
                    buy_order = buys[o.symbol].pop(0)
                    ret = (o.fill_price - buy_order.fill_price) / buy_order.fill_price
                    trade_returns.append(ret)
                    if ret > 0:
                        wins += 1
                    else:
                        losses += 1

            total_trades = wins + losses
            win_rate = wins / total_trades if total_trades > 0 else 0.0
            total_return = (self.capital - self.initial_capital) / self.initial_capital

            # Sharpe ratio (annualized, assuming daily returns)
            sharpe = 0.0
            if len(trade_returns) > 1:
                avg_r = statistics.mean(trade_returns)
                std_r = statistics.stdev(trade_returns)
                if std_r > 0:
                    sharpe = (avg_r / std_r) * math.sqrt(252)

            # Max drawdown
            max_drawdown = 0.0
            peak = self._equity_curve[0]
            for val in self._equity_curve:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak if peak > 0 else 0.0
                if dd > max_drawdown:
                    max_drawdown = dd

            return {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 4),
                "total_return": round(total_return, 4),
                "sharpe_ratio": round(sharpe, 4),
                "max_drawdown": round(max_drawdown, 4),
                "capital": round(self.capital, 2),
                "initial_capital": self.initial_capital,
            }

    def get_trade_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._trade_log)

    def get_equity_curve(self) -> List[float]:
        with self._lock:
            return list(self._equity_curve)


# =============================================================================
# Portfolio Tracker
# =============================================================================

class PortfolioTracker:
    """Track positions, P&L, allocation, and tax lots."""

    def __init__(self, initial_capital: float = 100000.0):
        self._lock = threading.RLock()
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self._positions: Dict[str, Position] = {}
        self._tax_lots: List[TaxLot] = []
        self._rebalance_threshold: float = 0.05

    def open_position(self, symbol: str, quantity: float, price: float,
                      strategy: str, stop_loss: float = 0.0,
                      take_profit: float = 0.0) -> Dict[str, Any]:
        with self._lock:
            cost = quantity * price
            if cost > self.cash:
                return {"status": "rejected", "reason": "insufficient_cash"}
            self.cash -= cost

            if symbol in self._positions:
                pos = self._positions[symbol]
                total_qty = pos.quantity + quantity
                pos.avg_entry_price = (
                    (pos.avg_entry_price * pos.quantity + price * quantity) / total_qty
                )
                pos.quantity = total_qty
            else:
                self._positions[symbol] = Position(
                    symbol=symbol, quantity=quantity, avg_entry_price=price,
                    current_price=price, opened_at=time.time(), strategy=strategy,
                    stop_loss=stop_loss, take_profit=take_profit,
                )

            lot = TaxLot(
                lot_id=str(uuid.uuid4()), symbol=symbol, quantity=quantity,
                purchase_price=price, purchase_date=time.time(),
            )
            capped_append(self._tax_lots, lot)
            return {"status": "opened", "symbol": symbol, "quantity": quantity, "price": price, "cash": self.cash}

    def close_position(self, symbol: str, price: float, quantity: Optional[float] = None) -> Dict[str, Any]:
        with self._lock:
            if symbol not in self._positions:
                return {"status": "error", "reason": "no_position"}
            pos = self._positions[symbol]
            close_qty = quantity if quantity is not None else pos.quantity
            close_qty = min(close_qty, pos.quantity)

            realized = (price - pos.avg_entry_price) * close_qty
            pos.realized_pnl += realized
            self.cash += close_qty * price
            pos.quantity -= close_qty

            # Close tax lots (FIFO)
            remaining = close_qty
            for lot in self._tax_lots:
                if lot.symbol == symbol and not lot.is_closed and remaining > 0:
                    lot_close = min(lot.quantity, remaining)
                    lot.sale_price = price
                    lot.sale_date = time.time()
                    lot.realized_gain = (price - lot.purchase_price) * lot_close
                    if lot_close >= lot.quantity:
                        lot.is_closed = True
                    else:
                        lot.quantity -= lot_close
                    remaining -= lot_close

            if pos.quantity <= 0:
                del self._positions[symbol]

            return {
                "status": "closed", "symbol": symbol, "quantity": close_qty,
                "price": price, "realized_pnl": round(realized, 2), "cash": self.cash,
            }

    def update_price(self, symbol: str, price: float) -> Optional[Dict[str, Any]]:
        with self._lock:
            if symbol not in self._positions:
                return None
            self._positions[symbol].current_price = price
            return self._positions[symbol].to_dict()

    def get_portfolio_summary(self) -> Dict[str, Any]:
        with self._lock:
            positions = {s: p.to_dict() for s, p in self._positions.items()}
            total_market_value = sum(p.market_value for p in self._positions.values())
            total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
            total_realized = sum(p.realized_pnl for p in self._positions.values())
            portfolio_value = self.cash + total_market_value

            allocation = {}
            for s, p in self._positions.items():
                allocation[s] = round(p.market_value / portfolio_value, 4) if portfolio_value > 0 else 0.0

            return {
                "cash": round(self.cash, 2),
                "positions": positions,
                "total_market_value": round(total_market_value, 2),
                "unrealized_pnl": round(total_unrealized, 2),
                "realized_pnl": round(total_realized, 2),
                "portfolio_value": round(portfolio_value, 2),
                "allocation": allocation,
                "num_positions": len(self._positions),
            }

    def check_rebalance(self, target_allocation: Dict[str, float]) -> Dict[str, Any]:
        with self._lock:
            summary = self.get_portfolio_summary()
            current = summary["allocation"]
            trades_needed = {}
            for symbol, target_pct in target_allocation.items():
                current_pct = current.get(symbol, 0.0)
                diff = target_pct - current_pct
                if abs(diff) > self._rebalance_threshold:
                    trades_needed[symbol] = round(diff, 4)
            return {
                "rebalance_needed": len(trades_needed) > 0,
                "trades_needed": trades_needed,
                "current_allocation": current,
                "target_allocation": target_allocation,
            }

    def get_tax_lots(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            lots = self._tax_lots
            if symbol:
                lots = [l for l in lots if l.symbol == symbol]
            return [l.to_dict() for l in lots]

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            pos = self._positions.get(symbol)
            return pos.to_dict() if pos else None


# =============================================================================
# Trading Account Integration Hooks (DISABLED BY DEFAULT)
# WARNING: Live trading requires regulatory compliance review.
# =============================================================================

class BrokerageAdapter:
    """
    Interface for brokerage accounts (TD Ameritrade, Interactive Brokers, Alpaca).
    WARNING: DISABLED by default. Requires regulatory compliance review.
    """

    def __init__(self, broker_name: str, api_key: str = "", api_secret: str = ""):
        self.broker_name = broker_name
        self.api_key = api_key
        self.api_secret = api_secret
        self.connected = False
        self.enabled = False  # DISABLED by default

    def connect(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "message": "Brokerage adapter is disabled. Regulatory compliance review required."}
        self.connected = True
        return {"status": "connected", "broker": self.broker_name}

    def submit_order(self, symbol: str, side: str, quantity: float, price: float) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "message": "Live trading disabled."}
        if not self.connected:
            return {"status": "error", "message": "Not connected."}
        return {
            "status": "submitted",
            "broker": self.broker_name,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "order_id": str(uuid.uuid4()),
        }

    def get_account_info(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled"}
        return {"broker": self.broker_name, "connected": self.connected}

    def to_dict(self) -> Dict[str, Any]:
        return {"broker_name": self.broker_name, "connected": self.connected, "enabled": self.enabled}


class CoinbaseAdapter:
    """
    Interface for Coinbase Pro API.
    WARNING: DISABLED by default. Requires regulatory compliance review.
    """

    def __init__(self, api_key: str = "", api_secret: str = "", passphrase: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.connected = False
        self.enabled = False  # DISABLED by default

    def connect(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "message": "Coinbase adapter is disabled. Regulatory compliance review required."}
        self.connected = True
        return {"status": "connected", "exchange": "coinbase"}

    def submit_order(self, symbol: str, side: str, quantity: float, price: float) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "message": "Live trading disabled."}
        return {
            "status": "submitted",
            "exchange": "coinbase",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "order_id": str(uuid.uuid4()),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {"exchange": "coinbase", "connected": self.connected, "enabled": self.enabled}


class TradingGateway:
    """
    Controls the switch from paper-trading to live.
    ONLY activates when systematic_profitability_proven() == True.

    WARNING: Live trading requires regulatory compliance review before activation.
    """

    def __init__(self, paper_simulator: PaperTradingSimulator):
        self._lock = threading.RLock()
        self.paper_simulator = paper_simulator
        self.mode = TradingMode.PAPER
        self._brokerage: Optional[BrokerageAdapter] = None
        self._coinbase: Optional[CoinbaseAdapter] = None
        self._audit_log: List[Dict[str, Any]] = []

    def register_brokerage(self, adapter: BrokerageAdapter) -> Dict[str, Any]:
        with self._lock:
            self._brokerage = adapter
            return {"status": "registered", "broker": adapter.broker_name}

    def register_coinbase(self, adapter: CoinbaseAdapter) -> Dict[str, Any]:
        with self._lock:
            self._coinbase = adapter
            return {"status": "registered", "exchange": "coinbase"}

    def require_profitability_proof(self) -> Dict[str, Any]:
        """Must pass before live trading can be considered."""
        proven = self.paper_simulator.systematic_profitability_proven()
        metrics = self.paper_simulator.get_performance_metrics()
        return {
            "profitability_proven": proven,
            "months_required": self.paper_simulator.profitability_months_required,
            "metrics": metrics,
            "can_enable_live": proven and not LIVE_TRADING_ENABLED is False,
        }

    def attempt_go_live(self) -> Dict[str, Any]:
        """
        Attempt to switch to live trading.
        WARNING: LIVE_TRADING_ENABLED must be True AND profitability must be proven.
        """
        with self._lock:
            if not LIVE_TRADING_ENABLED:
                entry = {
                    "action": "go_live_attempt",
                    "result": "blocked",
                    "reason": "LIVE_TRADING_ENABLED is False",
                    "timestamp": time.time(),
                }
                capped_append(self._audit_log, entry)
                return {"status": "blocked", "reason": "LIVE_TRADING_ENABLED is False (hardcoded safety)"}

            if not self.paper_simulator.systematic_profitability_proven():
                entry = {
                    "action": "go_live_attempt",
                    "result": "blocked",
                    "reason": "profitability_not_proven",
                    "timestamp": time.time(),
                }
                capped_append(self._audit_log, entry)
                return {"status": "blocked", "reason": "Systematic profitability not proven in paper trading."}

            self.mode = TradingMode.LIVE
            entry = {
                "action": "go_live_attempt",
                "result": "activated",
                "timestamp": time.time(),
            }
            capped_append(self._audit_log, entry)
            return {"status": "activated", "mode": "live"}

    def submit_order(self, symbol: str, side: str, quantity: float, price: float,
                     strategy: str, confidence: float) -> Dict[str, Any]:
        with self._lock:
            entry = {
                "action": "submit_order",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "strategy": strategy,
                "confidence": confidence,
                "mode": self.mode.value,
                "timestamp": time.time(),
            }
            capped_append(self._audit_log, entry)

            if self.mode == TradingMode.PAPER:
                return self.paper_simulator.submit_order(
                    symbol, side, quantity, price, strategy, confidence,
                )

            # Live mode — route to adapter
            if self._brokerage and self._brokerage.enabled:
                return self._brokerage.submit_order(symbol, side, quantity, price)
            elif self._coinbase and self._coinbase.enabled:
                return self._coinbase.submit_order(symbol, side, quantity, price)
            return {"status": "error", "reason": "no_live_adapter_enabled"}

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)

    def get_mode(self) -> str:
        return self.mode.value


# =============================================================================
# AI Optimization Layer
# =============================================================================

class AIOptimizationLayer:
    """
    Use execution outcomes to optimize strategy parameters.
    Tracks feature importance, adjusts signal weights, detects market regime.
    """

    def __init__(self, learning_rate: float = 0.01):
        self._lock = threading.RLock()
        self.learning_rate = learning_rate
        self._strategy_performance: Dict[str, List[float]] = {}
        self._feature_importance: Dict[str, float] = {
            "price": 0.2,
            "volume": 0.15,
            "book_value": 0.15,
            "momentum": 0.15,
            "mean_reversion": 0.1,
            "takeover_score": 0.15,
            "market_regime": 0.1,
        }
        self._regime_history: List[str] = []

    def record_outcome(self, strategy: str, return_pct: float) -> Dict[str, Any]:
        with self._lock:
            if strategy not in self._strategy_performance:
                self._strategy_performance[strategy] = []
            self._strategy_performance[strategy].append(return_pct)
            return {"strategy": strategy, "return_pct": return_pct, "total_trades": len(self._strategy_performance[strategy])}

    def detect_market_regime(self, prices: List[float], lookback: int = 20) -> Dict[str, Any]:
        if len(prices) < 3:
            regime = MarketRegime.SIDEWAYS
            return {"regime": regime.value, "confidence": 0.0}

        recent = prices[-min(lookback, len(prices)):]
        returns = [(recent[i] - recent[i - 1]) / recent[i - 1] for i in range(1, len(recent)) if recent[i - 1] != 0]

        if not returns:
            return {"regime": MarketRegime.SIDEWAYS.value, "confidence": 0.0}

        avg_return = statistics.mean(returns)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0

        if volatility > 0.03:
            regime = MarketRegime.VOLATILE
            confidence = min(1.0, volatility / 0.05)
        elif avg_return > 0.005:
            regime = MarketRegime.BULL
            confidence = min(1.0, avg_return / 0.02)
        elif avg_return < -0.005:
            regime = MarketRegime.BEAR
            confidence = min(1.0, abs(avg_return) / 0.02)
        else:
            regime = MarketRegime.SIDEWAYS
            confidence = 1.0 - min(1.0, abs(avg_return) / 0.005)

        with self._lock:
            capped_append(self._regime_history, regime.value)

        return {"regime": regime.value, "confidence": round(confidence, 4), "avg_return": round(avg_return, 6), "volatility": round(volatility, 6)}

    def optimize_weights(self, strategy_engine: TradingStrategyEngine) -> Dict[str, Any]:
        with self._lock:
            adjustments = {}
            for strategy, outcomes in self._strategy_performance.items():
                if len(outcomes) < 2:
                    continue
                avg = statistics.mean(outcomes)
                current_weight = strategy_engine.get_weights().get(strategy, 1.0)
                adjustment = self.learning_rate * avg
                new_weight = max(0.1, min(2.0, current_weight + adjustment))
                strategy_engine.update_weights(strategy, new_weight)
                adjustments[strategy] = {
                    "old_weight": round(current_weight, 4),
                    "new_weight": round(new_weight, 4),
                    "avg_return": round(avg, 6),
                    "trades": len(outcomes),
                }
            return {"adjustments": adjustments, "learning_rate": self.learning_rate}

    def get_feature_importance(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._feature_importance)

    def update_feature_importance(self, feature: str, importance: float) -> Dict[str, Any]:
        with self._lock:
            if feature in self._feature_importance:
                self._feature_importance[feature] = max(0.0, min(1.0, importance))
                return {"feature": feature, "importance": self._feature_importance[feature]}
            return {"error": f"Unknown feature: {feature}"}

    def get_strategy_performance(self) -> Dict[str, Any]:
        with self._lock:
            result = {}
            for strategy, outcomes in self._strategy_performance.items():
                if outcomes:
                    result[strategy] = {
                        "trades": len(outcomes),
                        "avg_return": round(statistics.mean(outcomes), 6),
                        "total_return": round(sum(outcomes), 6),
                        "best": round(max(outcomes), 6),
                        "worst": round(min(outcomes), 6),
                    }
            return result

    def recommend_strategy_rotation(self) -> Dict[str, Any]:
        with self._lock:
            if not self._strategy_performance:
                return {"recommendation": "insufficient_data"}
            best_strategy = None
            best_avg = float("-inf")
            for s, outcomes in self._strategy_performance.items():
                if outcomes:
                    avg = statistics.mean(outcomes)
                    if avg > best_avg:
                        best_avg = avg
                        best_strategy = s
            regime = self._regime_history[-1] if self._regime_history else "unknown"
            return {
                "best_strategy": best_strategy,
                "avg_return": round(best_avg, 6) if best_strategy else 0.0,
                "current_regime": regime,
                "recommendation": f"Increase allocation to {best_strategy}" if best_strategy else "insufficient_data",
            }


# =============================================================================
# Main Trading Bot Engine (Orchestrator)
# =============================================================================

class TradingBotEngine:
    """
    Orchestrates all trading components.

    WARNING: LIVE TRADING IS DISABLED BY DEFAULT.
    This system is for INTERNAL USE ONLY.
    Live trading requires regulatory compliance review before activation.
    """

    def __init__(self, initial_capital: float = 100000.0, profitability_months: int = 3):
        self._lock = threading.RLock()
        self.market_data = MarketDataIngestion()
        self.reverse_engine = ReverseInferenceEngine()
        self.strategy_engine = TradingStrategyEngine()
        self.risk_manager = RiskManager()
        self.paper_simulator = PaperTradingSimulator(initial_capital, profitability_months)
        self.portfolio = PortfolioTracker(initial_capital)
        self.gateway = TradingGateway(self.paper_simulator)
        self.ai_optimizer = AIOptimizationLayer()
        self._audit_trail: List[Dict[str, Any]] = []

    def ingest_market_data(self, data: MarketData) -> Dict[str, Any]:
        result = self.market_data.ingest(data)
        self._log_audit("ingest_market_data", {"symbol": data.symbol, "price": data.price})
        return result

    def analyze_takeover(self, data: MarketData) -> Dict[str, Any]:
        result = self.reverse_engine.score_candidate(data)
        self._log_audit("analyze_takeover", {"symbol": data.symbol, "is_candidate": result["is_candidate"]})
        return result

    def generate_signals(self, data: MarketData, price_history: List[float]) -> List[Dict[str, Any]]:
        signals = self.strategy_engine.get_all_signals(data, price_history)
        self._log_audit("generate_signals", {"symbol": data.symbol, "num_signals": len(signals)})
        return signals

    def execute_trade(self, symbol: str, side: str, quantity: float, price: float,
                      strategy: str, confidence: float) -> Dict[str, Any]:
        # Safety checks
        if self.risk_manager.is_emergency_stopped():
            return {"status": "blocked", "reason": "emergency_stop_active"}

        daily_check = self.risk_manager.check_daily_loss_limit(self.paper_simulator.capital)
        if daily_check["breached"]:
            return {"status": "blocked", "reason": "daily_loss_limit_breached"}

        position_value = quantity * price
        pos_check = self.risk_manager.check_position_limit(position_value, self.paper_simulator.capital)
        if not pos_check["allowed"]:
            return {"status": "blocked", "reason": "position_size_limit_exceeded", "details": pos_check}

        result = self.gateway.submit_order(symbol, side, quantity, price, strategy, confidence)
        self._log_audit("execute_trade", {"symbol": symbol, "side": side, "result": result.get("status")})
        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "live_trading_enabled": LIVE_TRADING_ENABLED,
            "mode": self.gateway.get_mode(),
            "emergency_stop": self.risk_manager.is_emergency_stopped(),
            "profitability_proven": self.paper_simulator.systematic_profitability_proven(),
            "performance": self.paper_simulator.get_performance_metrics(),
            "portfolio": self.portfolio.get_portfolio_summary(),
        }

    def emergency_stop(self) -> Dict[str, Any]:
        result = self.risk_manager.emergency_stop()
        self._log_audit("emergency_stop", result)
        return result

    def _log_audit(self, action: str, details: Dict[str, Any]) -> None:
        with self._lock:
            capped_append(self._audit_trail, {
                "action": action,
                "details": details,
                "timestamp": time.time(),
            })

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_trail)
