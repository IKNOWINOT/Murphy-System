# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Bot Lifecycle Manager — Murphy System

Manages the creation, supervision, and termination of strategy-driven
trading bots with built-in Human-in-the-Loop (HITL) approval gates.

Bot lifecycle state machine:
    CREATED → RUNNING → PAUSED → STOPPED / ERROR

All bots start in MANUAL mode (every trade requires human approval).
Graduation to SUPERVISED or AUTOMATED is driven by the HITLGraduationEngine
based on win-rate, consecutive fills, and drawdown history.

Designed to work alongside the existing TradingBotEngine (reverse-inference,
paper simulation) while adding strategy-agnostic HITL orchestration.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_BOT_EVENTS = 5_000


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BotLifecycleStatus(Enum):
    """Trading bot lifecycle state (Enum subclass)."""
    CREATED  = "created"
    RUNNING  = "running"
    PAUSED   = "paused"
    STOPPED  = "stopped"
    ERROR    = "error"


class BotHITLMode(Enum):
    """HITL oversight level for a bot (Enum subclass)."""
    MANUAL      = "manual"      # Every trade requires human approval
    SUPERVISED  = "supervised"  # Auto-executes low-confidence signals only
    AUTOMATED   = "automated"   # Full automation; emergency stop always available


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BotLifecycleConfig:
    """Immutable configuration for a managed trading bot."""
    exchange_id:       str
    pair:              str
    strategy_id:       str
    tick_interval_s:   int       = 60
    hitl_mode:         BotHITLMode = BotHITLMode.MANUAL
    max_open_trades:   int       = 3
    stake_amount_usd:  float     = 500.0
    stop_loss_pct:     float     = 0.03
    take_profit_pct:   float     = 0.05
    dry_run:           bool      = True    # Safe default: paper trade


@dataclass
class BotEvent:
    """A single lifecycle or trade event log entry."""
    event_id:   str
    bot_id:     str
    event_type: str    # tick | signal | order_submitted | fill | error | status_change
    message:    str
    data:       Dict[str, Any] = field(default_factory=dict)
    timestamp:  str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class BotPerformanceStats:
    """Running performance counters for a managed bot."""
    bot_id:            str
    total_trades:      int    = 0
    winning_trades:    int    = 0
    losing_trades:     int    = 0
    total_pnl_usd:     float  = 0.0
    win_rate:          float  = 0.0
    avg_trade_pnl_usd: float  = 0.0
    max_drawdown:      float  = 0.0
    last_updated:      str    = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Managed bot
# ---------------------------------------------------------------------------

class ManagedBot:
    """
    A single strategy-driven bot instance with HITL lifecycle management.

    On each tick the bot:
      1. Fetches fresh indicators from the MarketDataFeed.
      2. Calls strategy.generate_signal().
      3. Passes signals to the TradingHITLGateway for approval routing.
      4. Records outcomes to update HITL graduation scoring.
    """

    def __init__(
        self,
        bot_id:       str,
        config:       BotLifecycleConfig,
        strategy:     Any,    # BaseStrategy
        exchange_reg: Any,    # ExchangeRegistry
        hitl_gateway: Any,    # TradingHITLGateway
        market_feed:  Any,    # MarketDataFeed
        risk_manager: Any,    # CryptoRiskManager
    ) -> None:
        self.bot_id      = bot_id
        self.config      = config
        self.strategy    = strategy
        self._exchange   = exchange_reg
        self._hitl       = hitl_gateway
        self._feed       = market_feed
        self._risk       = risk_manager
        self.status      = BotLifecycleStatus.CREATED
        self.hitl_mode   = config.hitl_mode
        self._lock       = threading.Lock()
        self._stop_evt   = threading.Event()
        self._thread:     Optional[threading.Thread] = None
        self._stats      = BotPerformanceStats(bot_id=bot_id)
        self._events:     List[BotEvent] = []
        self._position    = 0.0
        self._entry_price = 0.0

    # ---- lifecycle -------------------------------------------------------

    def start(self) -> bool:
        with self._lock:
            if self.status == BotLifecycleStatus.RUNNING:
                return True
            self.status = BotLifecycleStatus.RUNNING
            self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._tick_loop,
            name=f"mbot-{self.bot_id[:8]}",
            daemon=True,
        )
        self._thread.start()
        self._log_event("status_change", "started", {"mode": self.hitl_mode.value})
        return True

    def pause(self) -> bool:
        with self._lock:
            if self.status != BotLifecycleStatus.RUNNING:
                return False
            self.status = BotLifecycleStatus.PAUSED
        self._log_event("status_change", "paused")
        return True

    def resume(self) -> bool:
        with self._lock:
            if self.status != BotLifecycleStatus.PAUSED:
                return False
        return self.start()

    def stop(self) -> bool:
        self._stop_evt.set()
        with self._lock:
            self.status = BotLifecycleStatus.STOPPED
        if self._thread:
            self._thread.join(timeout=15)
        self._log_event("status_change", "stopped")
        return True

    # ---- tick loop -------------------------------------------------------

    def _tick_loop(self) -> None:
        while not self._stop_evt.is_set():
            with self._lock:
                if self.status != BotLifecycleStatus.RUNNING:
                    break
            try:
                self._tick()
            except Exception as exc:
                logger.error("ManagedBot %s tick error: %s", self.bot_id, exc)
                self._log_event("error", str(exc))
                with self._lock:
                    self.status = BotLifecycleStatus.ERROR
                break
            self._stop_evt.wait(timeout=self.config.tick_interval_s)

    def _tick(self) -> None:
        from market_data_feed import CandleGranularity
        from trading_strategy_engine import SignalAction

        indicators = None
        if self._feed is not None:
            indicators = self._feed.get_indicators(
                self.config.exchange_id,
                self.config.pair,
                CandleGranularity.ONE_HOUR,
            )
        if indicators is None:
            return

        signal = self.strategy.generate_signal(self.config.pair, self._feed, indicators)
        self._log_event("signal", signal.action.value, {
            "action":     signal.action.value,
            "confidence": signal.confidence,
            "reasoning":  signal.reasoning,
        })

        if signal.action in (SignalAction.NO_SIGNAL, SignalAction.HOLD):
            return

        # Risk gate
        if self._risk is not None:
            size = signal.suggested_size or (self.config.stake_amount_usd / (indicators.ema_9 or 1))
            if not self._risk.pre_trade_check(self.bot_id, self.config.pair, signal.action.value, size):
                self._log_event("risk_blocked", "pre_trade_check failed")
                return

        # HITL gate
        if self._hitl is not None:
            self._hitl.submit_trade_signal(self.bot_id, signal, self.config)

    # ---- performance tracking -------------------------------------------

    def record_fill(self, side: str, price: float, quantity: float, fee: float) -> None:
        with self._lock:
            if side == "buy":
                self._position    += quantity
                self._entry_price  = price
            else:
                pnl = (price - self._entry_price) * quantity - fee
                self._stats.total_pnl_usd  += pnl
                self._stats.total_trades   += 1
                if pnl > 0:
                    self._stats.winning_trades += 1
                else:
                    self._stats.losing_trades  += 1
                self._stats.win_rate = (
                    self._stats.winning_trades / (self._stats.total_trades or 1)
                )
                self._stats.avg_trade_pnl_usd = (
                    self._stats.total_pnl_usd / (self._stats.total_trades or 1)
                )
                self._position = 0.0
            self._stats.last_updated = datetime.now(timezone.utc).isoformat()
        self._log_event("fill", f"side={side} price={price} qty={quantity}")

    def get_stats(self) -> BotPerformanceStats:
        with self._lock:
            return BotPerformanceStats(**self._stats.__dict__)

    def get_events(self, limit: int = 100) -> List[BotEvent]:
        with self._lock:
            return list(self._events[-limit:])

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "bot_id":      self.bot_id,
                "exchange":    self.config.exchange_id,
                "pair":        self.config.pair,
                "strategy":    self.config.strategy_id,
                "status":      self.status.value,
                "hitl_mode":   self.hitl_mode.value,
                "position":    self._position,
                "entry_price": self._entry_price,
                "dry_run":     self.config.dry_run,
                "stats":       self._stats.__dict__,
            }

    # ---- helpers --------------------------------------------------------

    def _log_event(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        event = BotEvent(
            event_id   = str(uuid.uuid4()),
            bot_id     = self.bot_id,
            event_type = event_type,
            message    = message,
            data       = data or {},
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
            capped_append(self._events, event, _MAX_BOT_EVENTS)


# ---------------------------------------------------------------------------
# Lifecycle manager
# ---------------------------------------------------------------------------

class BotLifecycleManager:
    """
    Central registry and controller for all ManagedBot instances.

    Provides create / start / pause / resume / stop / delete operations,
    an emergency stop for all bots, and a live dashboard summary.
    """

    def __init__(
        self,
        exchange_registry: Any,
        strategy_registry: Any,
        hitl_gateway:      Any,
        market_feed:       Any,
        risk_manager:      Any,
    ) -> None:
        self._exchange   = exchange_registry
        self._strategies = strategy_registry
        self._hitl       = hitl_gateway
        self._feed       = market_feed
        self._risk       = risk_manager
        self._lock       = threading.Lock()
        self._bots:       Dict[str, ManagedBot] = {}

    def create_bot(self, config: BotLifecycleConfig) -> str:
        """Create and register a new ManagedBot. Returns bot_id."""
        strategy = self._strategies.get(config.strategy_id) if self._strategies else None
        if strategy is None:
            raise ValueError(f"Strategy '{config.strategy_id}' not found in registry")
        bot_id = str(uuid.uuid4())
        bot = ManagedBot(
            bot_id       = bot_id,
            config       = config,
            strategy     = strategy,
            exchange_reg = self._exchange,
            hitl_gateway = self._hitl,
            market_feed  = self._feed,
            risk_manager = self._risk,
        )
        with self._lock:
            self._bots[bot_id] = bot
        logger.info(
            "BotLifecycleManager: created %s pair=%s strategy=%s mode=%s",
            bot_id, config.pair, config.strategy_id, config.hitl_mode.value,
        )
        return bot_id

    def start_bot(self, bot_id: str) -> bool:
        bot = self._get(bot_id)
        return bot.start() if bot else False

    def pause_bot(self, bot_id: str) -> bool:
        bot = self._get(bot_id)
        return bot.pause() if bot else False

    def resume_bot(self, bot_id: str) -> bool:
        bot = self._get(bot_id)
        return bot.resume() if bot else False

    def stop_bot(self, bot_id: str) -> bool:
        bot = self._get(bot_id)
        return bot.stop() if bot else False

    def delete_bot(self, bot_id: str) -> bool:
        bot = self._get(bot_id)
        if bot is None:
            return False
        bot.stop()
        with self._lock:
            del self._bots[bot_id]
        return True

    def set_hitl_mode(self, bot_id: str, mode: BotHITLMode) -> bool:
        """Promote or demote a bot's HITL oversight level."""
        bot = self._get(bot_id)
        if bot is None:
            return False
        with bot._lock:
            bot.hitl_mode = mode
        logger.info("BotLifecycleManager: %s mode → %s", bot_id, mode.value)
        return True

    def emergency_stop_all(self) -> int:
        """Stop every running bot immediately.  Returns count stopped."""
        with self._lock:
            bot_ids = list(self._bots.keys())
        count = 0
        for bid in bot_ids:
            bot = self._get(bid)
            if bot and bot.status == BotLifecycleStatus.RUNNING:
                bot.stop()
                count += 1
        logger.warning("BotLifecycleManager: EMERGENCY STOP — halted %d bots", count)
        return count

    def get_dashboard(self) -> Dict[str, Any]:
        """Return a live summary of all bots for the trading dashboard."""
        with self._lock:
            bots = list(self._bots.values())
        summaries = [b.to_dict() for b in bots]
        running = sum(1 for b in bots if b.status == BotLifecycleStatus.RUNNING)
        total_pnl = sum(b.get_stats().total_pnl_usd for b in bots)
        return {
            "total_bots":    len(bots),
            "running":       running,
            "paused":        sum(1 for b in bots if b.status == BotLifecycleStatus.PAUSED),
            "stopped":       sum(1 for b in bots if b.status == BotLifecycleStatus.STOPPED),
            "total_pnl_usd": total_pnl,
            "bots":          summaries,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }

    def list_bot_ids(self) -> List[str]:
        """Return IDs of all registered bots."""
        with self._lock:
            return list(self._bots.keys())

    def _get(self, bot_id: str) -> Optional[ManagedBot]:
        with self._lock:
            return self._bots.get(bot_id)
