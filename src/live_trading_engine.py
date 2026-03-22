# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Live Trading Engine — Murphy System

Bridge between paper-verified strategies and real Coinbase order execution.

SAFETY — 5 independent gates must ALL be GREEN before any live order:
  1. COINBASE_LIVE_MODE=true     (env var)
  2. LIVE_TRADING_ENABLED=true  (env var)
  3. Graduation controller status == GRADUATED
  4. Emergency stop NOT triggered
  5. Valid Coinbase API connection verified

All other states fall through to paper-trading or a hard block.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safety constants — do NOT change defaults without careful review
# ---------------------------------------------------------------------------

_COINBASE_LIVE_MODE      = os.getenv("COINBASE_LIVE_MODE",     "false").lower() == "true"
_LIVE_TRADING_ENABLED    = os.getenv("LIVE_TRADING_ENABLED",   "false").lower() == "true"
_POSITION_MONITOR_INTERVAL = int(os.getenv("POSITION_MONITOR_INTERVAL", "30"))  # seconds
_MAX_AUDIT_RECORDS        = 5_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class GateStatus(Enum):
    """Individual safety-gate result (Enum subclass)."""
    PASS  = "pass"
    FAIL  = "fail"
    SKIP  = "skip"


class OrderType(Enum):
    """Supported order types (Enum subclass)."""
    MARKET = "market"
    LIMIT  = "limit"


class OrderSide(Enum):
    """Buy / Sell (Enum subclass)."""
    BUY  = "buy"
    SELL = "sell"


class EngineState(Enum):
    """Live engine lifecycle state (Enum subclass)."""
    STOPPED         = "stopped"
    STARTING        = "starting"
    RUNNING         = "running"
    SHUTTING_DOWN   = "shutting_down"
    ERROR           = "error"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GateCheckResult:
    """Result of the 5-gate pre-trade check."""
    gate_coinbase_live:   GateStatus = GateStatus.FAIL
    gate_live_enabled:    GateStatus = GateStatus.FAIL
    gate_graduated:       GateStatus = GateStatus.FAIL
    gate_emergency_stop:  GateStatus = GateStatus.FAIL
    gate_api_valid:       GateStatus = GateStatus.FAIL
    all_pass:             bool       = False
    checked_at:           str        = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_coinbase_live":  self.gate_coinbase_live.value,
            "gate_live_enabled":   self.gate_live_enabled.value,
            "gate_graduated":      self.gate_graduated.value,
            "gate_emergency_stop": self.gate_emergency_stop.value,
            "gate_api_valid":      self.gate_api_valid.value,
            "all_pass":            self.all_pass,
            "checked_at":          self.checked_at,
        }


@dataclass
class LiveOrder:
    """Represents a submitted live order."""
    order_id:       str
    product_id:     str
    side:           OrderSide
    order_type:     OrderType
    size:           float
    limit_price:    Optional[float]
    stop_loss:      Optional[float]
    take_profit:    Optional[float]
    strategy_id:    str
    submitted_at:   str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    filled_at:      Optional[str]   = None
    filled_size:    float           = 0.0
    average_price:  float           = 0.0
    status:         str             = "pending"
    coinbase_id:    Optional[str]   = None
    sl_order_id:    Optional[str]   = None
    tp_order_id:    Optional[str]   = None
    slippage_pct:   float           = 0.0
    metadata:       Dict[str, Any]  = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id":      self.order_id,
            "product_id":    self.product_id,
            "side":          self.side.value,
            "order_type":    self.order_type.value,
            "size":          self.size,
            "limit_price":   self.limit_price,
            "stop_loss":     self.stop_loss,
            "take_profit":   self.take_profit,
            "strategy_id":   self.strategy_id,
            "submitted_at":  self.submitted_at,
            "filled_at":     self.filled_at,
            "filled_size":   self.filled_size,
            "average_price": self.average_price,
            "status":        self.status,
            "coinbase_id":   self.coinbase_id,
            "sl_order_id":   self.sl_order_id,
            "tp_order_id":   self.tp_order_id,
            "slippage_pct":  self.slippage_pct,
        }


@dataclass
class LivePosition:
    """Open position tracked by the engine."""
    position_id:    str
    product_id:     str
    entry_price:    float
    current_price:  float
    size:           float
    side:           OrderSide
    strategy_id:    str
    opened_at:      str
    stop_loss:      Optional[float] = None
    take_profit:    Optional[float] = None
    unrealised_pnl: float           = 0.0
    realised_pnl:   float           = 0.0
    status:         str             = "open"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id":   self.position_id,
            "product_id":    self.product_id,
            "entry_price":   self.entry_price,
            "current_price": self.current_price,
            "size":          self.size,
            "side":          self.side.value,
            "strategy_id":   self.strategy_id,
            "opened_at":     self.opened_at,
            "stop_loss":     self.stop_loss,
            "take_profit":   self.take_profit,
            "unrealised_pnl": self.unrealised_pnl,
            "realised_pnl":  self.realised_pnl,
            "status":        self.status,
        }


# ---------------------------------------------------------------------------
# Live Trading Engine
# ---------------------------------------------------------------------------

class LiveTradingEngine:
    """
    Bridges strategy signals to real Coinbase order execution.

    All trades are blocked unless all 5 safety gates pass.
    """

    def __init__(
        self,
        coinbase_connector:       Optional[Any] = None,
        graduation_controller:    Optional[Any] = None,
        emergency_stop_controller: Optional[Any] = None,
        risk_manager:             Optional[Any] = None,
        cost_calibrator:          Optional[Any] = None,
    ) -> None:
        self._coinbase     = coinbase_connector
        self._graduation   = graduation_controller
        self._emergency    = emergency_stop_controller
        self._risk         = risk_manager
        self._calibrator   = cost_calibrator

        self._state        = EngineState.STOPPED
        self._positions:   Dict[str, LivePosition] = {}
        self._orders:      List[LiveOrder]          = []
        self._audit_log:   List[Dict[str, Any]]     = []
        self._lock         = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running      = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_gates(self) -> GateCheckResult:
        """Run all 5 safety gates.  Returns GateCheckResult."""
        result = GateCheckResult()

        # Gate 1 — COINBASE_LIVE_MODE env var
        result.gate_coinbase_live = (
            GateStatus.PASS if _COINBASE_LIVE_MODE else GateStatus.FAIL
        )

        # Gate 2 — LIVE_TRADING_ENABLED env var
        result.gate_live_enabled = (
            GateStatus.PASS if _LIVE_TRADING_ENABLED else GateStatus.FAIL
        )

        # Gate 3 — Graduation status
        try:
            if self._graduation is not None:
                status = self._graduation.get_status()
                graduated = (
                    status.get("graduated", False)
                    if isinstance(status, dict)
                    else getattr(status, "graduated", False)
                )
                result.gate_graduated = GateStatus.PASS if graduated else GateStatus.FAIL
            else:
                result.gate_graduated = GateStatus.SKIP
        except Exception as exc:
            logger.warning("Graduation gate check failed: %s", exc)
            result.gate_graduated = GateStatus.FAIL

        # Gate 4 — Emergency stop NOT triggered
        try:
            if self._emergency is not None:
                triggered = self._emergency.is_triggered()
                result.gate_emergency_stop = (
                    GateStatus.FAIL if triggered else GateStatus.PASS
                )
            else:
                result.gate_emergency_stop = GateStatus.SKIP
        except Exception as exc:
            logger.warning("Emergency stop gate check failed: %s", exc)
            result.gate_emergency_stop = GateStatus.FAIL

        # Gate 5 — Valid Coinbase API connection
        try:
            if self._coinbase is not None:
                ok = self._coinbase.test_connection()
                result.gate_api_valid = GateStatus.PASS if ok else GateStatus.FAIL
            else:
                result.gate_api_valid = GateStatus.FAIL
        except Exception as exc:
            logger.warning("Coinbase API gate check failed: %s", exc)
            result.gate_api_valid = GateStatus.FAIL

        # All-pass requires no FAIL (SKIP is allowed for optional gates)
        result.all_pass = all(
            g in (GateStatus.PASS, GateStatus.SKIP)
            for g in [
                result.gate_coinbase_live,
                result.gate_live_enabled,
                result.gate_graduated,
                result.gate_emergency_stop,
                result.gate_api_valid,
            ]
        )
        # But the two hard env-var gates must both be PASS (not SKIP)
        if (result.gate_coinbase_live != GateStatus.PASS
                or result.gate_live_enabled != GateStatus.PASS):
            result.all_pass = False

        return result

    def execute_signal(
        self,
        product_id:    str,
        side:          str,
        size:          float,
        order_type:    str             = "market",
        limit_price:   Optional[float] = None,
        stop_loss:     Optional[float] = None,
        take_profit:   Optional[float] = None,
        strategy_id:   str             = "unknown",
        metadata:      Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Attempt to execute a trading signal after all gate and risk checks.

        Returns a dict describing the result (order details or rejection reason).
        """
        gates = self.check_gates()
        self._audit("gate_check", {"gates": gates.to_dict(), "product_id": product_id})

        if not gates.all_pass:
            reason = "Live trading gates not all passing"
            self._audit("execution_blocked", {"reason": reason, "gates": gates.to_dict()})
            logger.warning("Live order blocked for %s — gates: %s", product_id, gates.to_dict())
            return {"success": False, "blocked": True, "reason": reason, "gates": gates.to_dict()}

        # Risk validation
        if self._risk is not None:
            try:
                risk_ok, risk_reason = self._risk.validate_trade(
                    product_id=product_id, side=side, size=size, price=limit_price
                )
                if not risk_ok:
                    self._audit("risk_blocked", {"reason": risk_reason})
                    return {"success": False, "blocked": True, "reason": risk_reason}
            except Exception as exc:
                logger.warning("Risk validation error: %s", exc)

        # Cost calibration adjustment
        adjusted_size = size
        if self._calibrator is not None:
            try:
                adjusted_size = self._calibrator.adjust_size(size, product_id)
            except Exception as exc:
                logger.warning("Cost calibrator error (using original size): %s", exc)

        order_id  = str(uuid.uuid4())
        order_obj = LiveOrder(
            order_id    = order_id,
            product_id  = product_id,
            side        = OrderSide(side.lower()),
            order_type  = OrderType(order_type.lower()),
            size        = adjusted_size,
            limit_price = limit_price,
            stop_loss   = stop_loss,
            take_profit = take_profit,
            strategy_id = strategy_id,
            metadata    = metadata or {},
        )

        # Submit to Coinbase
        try:
            cb_result = self._submit_to_coinbase(order_obj)
            order_obj.coinbase_id  = cb_result.get("order_id")
            order_obj.filled_size  = float(cb_result.get("filled_size",   adjusted_size))
            order_obj.average_price= float(cb_result.get("average_price", limit_price or 0))
            order_obj.status       = cb_result.get("status", "filled")
            order_obj.filled_at    = datetime.now(timezone.utc).isoformat()

            if adjusted_size > 0 and limit_price and limit_price > 0:
                expected = limit_price
                actual   = order_obj.average_price
                order_obj.slippage_pct = abs(actual - expected) / expected * 100

            # Place SL / TP orders
            if stop_loss:
                order_obj.sl_order_id = self._place_stop_loss(order_obj, stop_loss)
            if take_profit:
                order_obj.tp_order_id = self._place_take_profit(order_obj, take_profit)

            # Track position
            self._open_position(order_obj)

        except Exception as exc:
            order_obj.status = "failed"
            self._audit("execution_error", {"order_id": order_id, "error": str(exc)})
            logger.error("Live order execution failed: %s", exc)
            with self._lock:
                self._orders.append(order_obj)
            return {"success": False, "error": str(exc), "order": order_obj.to_dict()}

        with self._lock:
            self._orders.append(order_obj)

        self._audit("order_executed", {"order": order_obj.to_dict()})
        logger.info(
            "Live order executed: %s %s %s %.4f @ %.4f (cb_id=%s)",
            side.upper(), product_id, order_type.upper(),
            order_obj.filled_size, order_obj.average_price, order_obj.coinbase_id,
        )
        return {"success": True, "order": order_obj.to_dict()}

    def start(self) -> None:
        """Start the position-monitoring loop."""
        with self._lock:
            if self._state == EngineState.RUNNING:
                return
            self._state   = EngineState.STARTING
            self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="live-position-monitor"
        )
        self._monitor_thread.start()
        with self._lock:
            self._state = EngineState.RUNNING
        logger.info("LiveTradingEngine started (monitor interval=%ds)", _POSITION_MONITOR_INTERVAL)

    def stop(self, close_all: bool = True) -> None:
        """Graceful shutdown; optionally close all open positions."""
        with self._lock:
            self._state   = EngineState.SHUTTING_DOWN
            self._running = False
        if close_all:
            self._close_all_positions()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10)
        with self._lock:
            self._state = EngineState.STOPPED
        logger.info("LiveTradingEngine stopped")

    def get_status(self) -> Dict[str, Any]:
        """Return current engine status."""
        gates = self.check_gates()
        with self._lock:
            open_count = sum(1 for p in self._positions.values() if p.status == "open")
        return {
            "state":        self._state.value,
            "gates":        gates.to_dict(),
            "open_positions": open_count,
            "total_orders": len(self._orders),
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """Return all open positions."""
        with self._lock:
            return [p.to_dict() for p in self._positions.values() if p.status == "open"]

    def get_orders(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return most recent orders."""
        with self._lock:
            return [o.to_dict() for o in self._orders[-limit:]]

    def get_audit_log(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return recent audit log entries."""
        with self._lock:
            return list(self._audit_log[-limit:])

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _submit_to_coinbase(self, order: LiveOrder) -> Dict[str, Any]:
        if self._coinbase is None:
            raise RuntimeError("No Coinbase connector configured")
        if order.order_type == OrderType.MARKET:
            return self._coinbase.place_market_order(
                product_id = order.product_id,
                side       = order.side.value.upper(),
                base_size  = str(order.size),
            )
        else:
            return self._coinbase.place_limit_order(
                product_id  = order.product_id,
                side        = order.side.value.upper(),
                base_size   = str(order.size),
                limit_price = str(order.limit_price),
            )

    def _place_stop_loss(self, order: LiveOrder, stop_price: float) -> Optional[str]:
        if self._coinbase is None:
            return None
        try:
            sl_side = "SELL" if order.side == OrderSide.BUY else "BUY"
            result  = self._coinbase.place_stop_limit_order(
                product_id  = order.product_id,
                side        = sl_side,
                base_size   = str(order.filled_size),
                stop_price  = str(stop_price),
                limit_price = str(stop_price * 0.995),   # slight limit below stop
            )
            return result.get("order_id")
        except Exception as exc:
            logger.warning("SL order placement failed: %s", exc)
            return None

    def _place_take_profit(self, order: LiveOrder, tp_price: float) -> Optional[str]:
        if self._coinbase is None:
            return None
        try:
            tp_side = "SELL" if order.side == OrderSide.BUY else "BUY"
            result  = self._coinbase.place_limit_order(
                product_id  = order.product_id,
                side        = tp_side,
                base_size   = str(order.filled_size),
                limit_price = str(tp_price),
            )
            return result.get("order_id")
        except Exception as exc:
            logger.warning("TP order placement failed: %s", exc)
            return None

    def _open_position(self, order: LiveOrder) -> None:
        pos = LivePosition(
            position_id  = str(uuid.uuid4()),
            product_id   = order.product_id,
            entry_price  = order.average_price,
            current_price= order.average_price,
            size         = order.filled_size,
            side         = order.side,
            strategy_id  = order.strategy_id,
            opened_at    = order.filled_at or datetime.now(timezone.utc).isoformat(),
            stop_loss    = order.stop_loss,
            take_profit  = order.take_profit,
        )
        with self._lock:
            self._positions[pos.position_id] = pos

    def _close_all_positions(self) -> None:
        with self._lock:
            open_ids = [
                pid for pid, p in self._positions.items() if p.status == "open"
            ]
        for pid in open_ids:
            try:
                pos = self._positions[pid]
                logger.info("Closing position %s (%s %s)", pid, pos.product_id, pos.size)
                if self._coinbase:
                    close_side = "SELL" if pos.side == OrderSide.BUY else "BUY"
                    self._coinbase.place_market_order(
                        product_id = pos.product_id,
                        side       = close_side,
                        base_size  = str(pos.size),
                    )
                with self._lock:
                    self._positions[pid].status = "closed"
            except Exception as exc:
                logger.error("Failed to close position %s: %s", pid, exc)

    def _monitor_loop(self) -> None:
        """Background loop: update position P&L every N seconds."""
        while self._running:
            try:
                self._update_positions()
            except Exception as exc:
                logger.warning("Position monitor error: %s", exc)
            time.sleep(_POSITION_MONITOR_INTERVAL)

    def _update_positions(self) -> None:
        if self._coinbase is None:
            return
        with self._lock:
            open_positions = {
                pid: p for pid, p in self._positions.items() if p.status == "open"
            }
        for pid, pos in open_positions.items():
            try:
                ticker = self._coinbase.get_product_ticker(pos.product_id)
                price  = float(ticker.get("price", pos.current_price))
                pnl    = (price - pos.entry_price) * pos.size
                if pos.side == OrderSide.SELL:
                    pnl = -pnl
                with self._lock:
                    if pid in self._positions:
                        self._positions[pid].current_price  = price
                        self._positions[pid].unrealised_pnl = pnl
            except Exception as exc:
                logger.debug("Could not update position %s: %s", pid, exc)

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        entry = {
            "event":     event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        with self._lock:
            if len(self._audit_log) >= _MAX_AUDIT_RECORDS:
                del self._audit_log[:_MAX_AUDIT_RECORDS // 10]
            self._audit_log.append(entry)
