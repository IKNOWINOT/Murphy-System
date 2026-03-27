# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Orchestrator — Murphy System

Master controller that ties together:
  - Market data feeds
  - Strategy execution
  - Signal aggregation with confidence-weighted conflict resolution
  - Paper / live routing
  - Portfolio state persistence
  - Health monitoring for all subsystems
  - Emergency stop and graduation checks

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_LOOP_INTERVAL  = int(os.getenv("ORCHESTRATOR_INTERVAL", "60"))   # seconds
_STATE_FILE             = os.getenv("ORCHESTRATOR_STATE_FILE", "/tmp/orchestrator_state.json")
_MAX_SIGNAL_HISTORY     = 10_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TradingMode(Enum):
    """Active trading mode (Enum subclass)."""
    PAPER  = "paper"
    LIVE   = "live"


class OrchestratorState(Enum):
    """Orchestrator lifecycle state (Enum subclass)."""
    STOPPED      = "stopped"
    STARTING     = "starting"
    RUNNING      = "running"
    PAUSED       = "paused"
    SHUTTING_DOWN= "shutting_down"
    ERROR        = "error"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AggregatedSignal:
    """Result of multi-strategy signal aggregation."""
    product_id:       str
    action:           str             # buy | sell | hold
    confidence:       float           # 0.0 → 1.0 (weighted average)
    contributing_strategies: List[str] = field(default_factory=list)
    conflict:         bool             = False
    timestamp:        str             = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata:         Dict[str, Any]  = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id":     self.product_id,
            "action":         self.action,
            "confidence":     self.confidence,
            "contributing":   self.contributing_strategies,
            "conflict":       self.conflict,
            "timestamp":      self.timestamp,
        }


@dataclass
class SubsystemHealth:
    """Health snapshot for one subsystem."""
    name:    str
    healthy: bool
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "healthy": self.healthy, "message": self.message}


# ---------------------------------------------------------------------------
# Trading Orchestrator
# ---------------------------------------------------------------------------

class TradingOrchestrator:
    """
    Master controller for Murphy's automated trading system.

    Usage::

        orch = TradingOrchestrator(mode=TradingMode.PAPER, ...)
        orch.start()           # starts the main loop in a daemon thread
        orch.stop()            # graceful shutdown
    """

    def __init__(
        self,
        mode:                  TradingMode                 = TradingMode.PAPER,
        strategies:            Optional[List[Any]]         = None,
        market_data_feed:      Optional[Any]               = None,
        paper_engine:          Optional[Any]               = None,
        live_engine:           Optional[Any]               = None,
        risk_manager:          Optional[Any]               = None,
        graduation_controller: Optional[Any]               = None,
        emergency_stop:        Optional[Any]               = None,
        profit_sweeper:        Optional[Any]               = None,
        loop_interval:         int                         = _DEFAULT_LOOP_INTERVAL,
        state_file:            str                         = _STATE_FILE,
    ) -> None:
        self._mode          = mode
        self._strategies    = strategies or []
        self._market_data   = market_data_feed
        self._paper_engine  = paper_engine
        self._live_engine   = live_engine
        self._risk          = risk_manager
        self._graduation    = graduation_controller
        self._emergency     = emergency_stop
        self._sweeper       = profit_sweeper
        self._loop_interval = loop_interval
        self._state_file    = state_file

        self._state         = OrchestratorState.STOPPED
        self._portfolio: Dict[str, Any] = {
            "total_value_usd": 0.0,
            "available_cash":  0.0,
            "positions":       {},
            "daily_pnl":       0.0,
            "total_pnl":       0.0,
            "updated_at":      None,
        }
        self._signal_history: List[AggregatedSignal] = []
        self._trade_history:  List[Dict[str, Any]]   = []
        self._health:         List[SubsystemHealth]  = []
        self._loop_count      = 0
        self._lock            = threading.Lock()
        self._stop_event      = threading.Event()
        self._main_thread:    Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the orchestrator main loop in a background thread."""
        with self._lock:
            if self._state == OrchestratorState.RUNNING:
                logger.warning("Orchestrator already running")
                return
            self._state = OrchestratorState.STARTING
            self._stop_event.clear()

        self._restore_state()

        self._main_thread = threading.Thread(
            target=self._main_loop, daemon=True, name="trading-orchestrator"
        )
        self._main_thread.start()

        if self._live_engine and self._mode == TradingMode.LIVE:
            self._live_engine.start()

        with self._lock:
            self._state = OrchestratorState.RUNNING
        logger.info("TradingOrchestrator started in %s mode", self._mode.value.upper())

    def stop(self) -> None:
        """Graceful shutdown."""
        with self._lock:
            self._state = OrchestratorState.SHUTTING_DOWN
        self._stop_event.set()
        if self._main_thread and self._main_thread.is_alive():
            self._main_thread.join(timeout=30)
        if self._live_engine:
            self._live_engine.stop(close_all=True)
        self._persist_state()
        with self._lock:
            self._state = OrchestratorState.STOPPED
        logger.info("TradingOrchestrator stopped")

    def switch_mode(self, new_mode: TradingMode) -> Dict[str, Any]:
        """
        Switch between PAPER and LIVE modes.

        LIVE requires the live engine's gate check to pass.
        """
        if new_mode == TradingMode.LIVE:
            if self._live_engine is None:
                return {"success": False, "reason": "LiveTradingEngine not configured"}
            gate_result = self._live_engine.check_gates()
            if not gate_result.all_pass:
                return {
                    "success": False,
                    "reason":  "Live trading gates not all passing",
                    "gates":   gate_result.to_dict(),
                }

        with self._lock:
            old_mode    = self._mode
            self._mode  = new_mode
        logger.info("Trading mode switched %s → %s", old_mode.value, new_mode.value)
        return {"success": True, "old_mode": old_mode.value, "new_mode": new_mode.value}

    # ------------------------------------------------------------------
    # Status / data access
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return full orchestrator status."""
        with self._lock:
            state = self._state.value
            mode  = self._mode.value
            loop  = self._loop_count

        health = self.check_health()
        return {
            "state":       state,
            "mode":        mode,
            "loop_count":  loop,
            "health":      [h.to_dict() for h in health],
            "portfolio":   self.get_portfolio(),
            "updated_at":  datetime.now(timezone.utc).isoformat(),
        }

    def get_portfolio(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._portfolio)

    def get_portfolio_history(self) -> List[Dict[str, Any]]:
        """Placeholder — returns current snapshot only (extend with DB)."""
        return [{"timestamp": datetime.now(timezone.utc).isoformat(), **self._portfolio}]

    def get_signal_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._signal_history[-limit:]]

    def get_trade_history(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._trade_history[-limit:])

    def get_todays_trades(self) -> List[Dict[str, Any]]:
        today = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            return [t for t in self._trade_history if t.get("timestamp", "").startswith(today)]

    def check_health(self) -> List[SubsystemHealth]:
        """Check all subsystem health."""
        health: List[SubsystemHealth] = []

        # Market data feed
        try:
            if self._market_data:
                ok = self._market_data.is_healthy() if hasattr(self._market_data, "is_healthy") else True
                health.append(SubsystemHealth("market_data", ok))
            else:
                health.append(SubsystemHealth("market_data", False, "not configured"))
        except Exception as exc:
            health.append(SubsystemHealth("market_data", False, str(exc)))

        # Strategies
        strategy_names = [getattr(s, "strategy_id", str(i)) for i, s in enumerate(self._strategies)]
        health.append(SubsystemHealth(
            "strategies",
            len(self._strategies) > 0,
            f"{len(self._strategies)} loaded: {strategy_names[:5]}",
        ))

        # Risk manager
        health.append(SubsystemHealth(
            "risk_manager", self._risk is not None,
            "configured" if self._risk else "not configured",
        ))

        # Graduation controller
        try:
            if self._graduation:
                status = self._graduation.get_status()
                graduated = status.get("graduated", False) if isinstance(status, dict) else False
                health.append(SubsystemHealth("graduation", True, f"graduated={graduated}"))
            else:
                health.append(SubsystemHealth("graduation", False, "not configured"))
        except Exception as exc:
            health.append(SubsystemHealth("graduation", False, str(exc)))

        # Emergency stop
        try:
            if self._emergency:
                triggered = self._emergency.is_triggered()
                health.append(SubsystemHealth(
                    "emergency_stop", not triggered,
                    "triggered" if triggered else "armed/safe",
                ))
            else:
                health.append(SubsystemHealth("emergency_stop", False, "not configured"))
        except Exception as exc:
            health.append(SubsystemHealth("emergency_stop", False, str(exc)))

        with self._lock:
            self._health = health
        return health

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _main_loop(self) -> None:
        logger.info("Orchestrator main loop starting")
        while not self._stop_event.is_set():
            loop_start = time.monotonic()
            try:
                self._run_one_cycle()
            except Exception as exc:
                logger.error("Orchestrator cycle error: %s", exc, exc_info=True)

            elapsed  = time.monotonic() - loop_start
            sleep_for = max(0, self._loop_interval - elapsed)
            self._stop_event.wait(timeout=sleep_for)
        logger.info("Orchestrator main loop exited")

    def _run_one_cycle(self) -> None:
        with self._lock:
            self._loop_count += 1
            mode = self._mode

        # 1 — Fetch market data
        market_data = self._fetch_market_data()

        # 2 — Run strategies
        raw_signals = self._run_strategies(market_data)

        # 3 — Aggregate signals
        aggregated  = self._aggregate_signals(raw_signals)

        # 4 — Check risk manager
        validated   = self._validate_signals(aggregated)

        # 5 — Execute trades
        for signal in validated:
            self._route_signal(signal, mode)

        # 6 — Update portfolio
        self._refresh_portfolio()

        # 7 — Emergency stop check
        self._check_emergency()

        # 8 — Graduation check
        self._check_graduation()

        # 9 — Log
        logger.debug(
            "Cycle %d complete — mode=%s signals=%d validated=%d",
            self._loop_count, mode.value, len(raw_signals), len(validated),
        )

        # 10 — Persist state periodically (every 10 cycles)
        if self._loop_count % 10 == 0:
            self._persist_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_market_data(self) -> Dict[str, Any]:
        if self._market_data is None:
            return {}
        try:
            return self._market_data.get_latest() if hasattr(self._market_data, "get_latest") else {}
        except Exception as exc:
            logger.warning("Market data fetch error: %s", exc)
            return {}

    def _run_strategies(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        for strategy in self._strategies:
            try:
                raw = strategy.generate_signal(market_data=market_data)
                if raw is not None:
                    if hasattr(raw, "to_dict"):
                        signals.append(raw.to_dict())
                    elif isinstance(raw, dict):
                        signals.append(raw)
            except Exception as exc:
                sid = getattr(strategy, "strategy_id", "?")
                logger.warning("Strategy %s error: %s", sid, exc)
        return signals

    def _aggregate_signals(
        self, raw_signals: List[Dict[str, Any]]
    ) -> List[AggregatedSignal]:
        """Confidence-weighted voting; conflict if buy vs sell both present."""
        if not raw_signals:
            return []

        # Group by product_id
        by_product: Dict[str, List[Dict[str, Any]]] = {}
        for sig in raw_signals:
            pid = sig.get("pair") or sig.get("product_id", "UNKNOWN")
            by_product.setdefault(pid, []).append(sig)

        aggregated: List[AggregatedSignal] = []
        for pid, sigs in by_product.items():
            buy_conf  = sum(s.get("confidence", 0.5) for s in sigs if s.get("action") == "buy")
            sell_conf = sum(s.get("confidence", 0.5) for s in sigs if s.get("action") == "sell")
            total     = buy_conf + sell_conf

            if total == 0:
                continue

            conflict = buy_conf > 0 and sell_conf > 0

            if buy_conf >= sell_conf:
                action    = "buy"
                confidence= buy_conf / total
            else:
                action    = "sell"
                confidence= sell_conf / total

            agg = AggregatedSignal(
                product_id               = pid,
                action                   = action,
                confidence               = round(confidence, 4),
                contributing_strategies  = [s.get("strategy_id", "?") for s in sigs],
                conflict                 = conflict,
            )
            aggregated.append(agg)
            with self._lock:
                if len(self._signal_history) >= _MAX_SIGNAL_HISTORY:
                    del self._signal_history[:_MAX_SIGNAL_HISTORY // 10]
                self._signal_history.append(agg)

        return aggregated

    def _validate_signals(
        self, signals: List[AggregatedSignal]
    ) -> List[AggregatedSignal]:
        if self._risk is None:
            return signals
        validated = []
        for sig in signals:
            try:
                ok, _reason = self._risk.validate_trade(
                    product_id = sig.product_id,
                    side       = sig.action,
                    size       = 0,     # size determined at execution
                    price      = None,
                )
                if ok:
                    validated.append(sig)
            except Exception:
                validated.append(sig)   # pass through on risk-manager error
        return validated

    def _route_signal(self, signal: AggregatedSignal, mode: TradingMode) -> None:
        """Route to paper or live engine based on current mode."""
        # Minimum confidence threshold
        if signal.confidence < 0.6:
            return

        trade_data = {
            "product_id": signal.product_id,
            "side":       signal.action,
            "strategy_id": ",".join(signal.contributing_strategies),
            "confidence": signal.confidence,
            "timestamp":  signal.timestamp,
        }

        try:
            if mode == TradingMode.LIVE and self._live_engine:
                result = self._live_engine.execute_signal(
                    product_id  = signal.product_id,
                    side        = signal.action,
                    size        = 0,        # let risk manager size it
                    strategy_id = ",".join(signal.contributing_strategies),
                )
                trade_data["result"]  = result
                trade_data["engine"]  = "live"
            elif self._paper_engine:
                result = self._paper_engine.execute_signal(
                    product_id  = signal.product_id,
                    side        = signal.action,
                    size        = 0,
                    strategy_id = ",".join(signal.contributing_strategies),
                ) if hasattr(self._paper_engine, "execute_signal") else {}
                trade_data["result"]  = result
                trade_data["engine"]  = "paper"
            else:
                return

            with self._lock:
                self._trade_history.append(trade_data)
        except Exception as exc:
            logger.warning("Signal routing error: %s", exc)

    def _refresh_portfolio(self) -> None:
        """Update portfolio state from active engine."""
        try:
            if self._mode == TradingMode.LIVE and self._live_engine:
                positions = self._live_engine.get_positions()
                with self._lock:
                    self._portfolio["positions"] = {
                        p["position_id"]: p for p in positions
                    }
                    self._portfolio["updated_at"] = datetime.now(timezone.utc).isoformat()
            elif self._paper_engine and hasattr(self._paper_engine, "get_portfolio"):
                paper_port = self._paper_engine.get_portfolio()
                with self._lock:
                    self._portfolio.update(paper_port)
                    self._portfolio["updated_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            logger.debug("Portfolio refresh error: %s", exc)

    def _check_emergency(self) -> None:
        if self._emergency is None:
            return
        try:
            if self._emergency.is_triggered():
                logger.critical("EMERGENCY STOP triggered — halting orchestrator")
                self._stop_event.set()
                with self._lock:
                    self._state = OrchestratorState.ERROR
        except Exception as exc:
            logger.warning("Emergency stop check error: %s", exc)

    def _check_graduation(self) -> None:
        if self._graduation is None:
            return
        try:
            status = self._graduation.get_status()
            graduated = (
                status.get("graduated", False)
                if isinstance(status, dict)
                else getattr(status, "graduated", False)
            )
            if graduated and self._mode == TradingMode.PAPER:
                logger.info(
                    "Graduation check: system has graduated from paper trading. "
                    "Set LIVE_TRADING_ENABLED=true and call switch_mode(LIVE) to activate live trading."
                )
        except Exception as exc:
            logger.debug("Graduation check error: %s", exc)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _persist_state(self) -> None:
        try:
            state_data = {
                "mode":        self._mode.value,
                "loop_count":  self._loop_count,
                "portfolio":   self._portfolio,
                "saved_at":    datetime.now(timezone.utc).isoformat(),
            }
            Path(self._state_file).write_text(json.dumps(state_data, indent=2))
        except Exception as exc:
            logger.debug("State persistence error: %s", exc)

    def _restore_state(self) -> None:
        try:
            if Path(self._state_file).is_file():
                data = json.loads(Path(self._state_file).read_text())
                with self._lock:
                    self._loop_count = data.get("loop_count", 0)
                    self._portfolio.update(data.get("portfolio", {}))
                logger.info("Restored orchestrator state from %s", self._state_file)
        except Exception as exc:
            logger.debug("State restore error (will start fresh): %s", exc)
