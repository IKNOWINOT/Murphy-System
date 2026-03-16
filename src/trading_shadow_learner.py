# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Shadow Learner — Murphy System

Implements a parallel paper-trading "shadow" layer that runs every strategy
against live market prices without risking real money.  At the end of each
week, if a shadow bot's paper portfolio finished higher than it started, the
system records *what the bot did right* as a ``WeeklyWinningPattern``.

Captured patterns are stored in a human-reviewable JSON file.  A human (or
privileged admin) reviews and promotes patterns they want to influence future
strategy hints.  Promoted patterns are then surfaced as contextual hints
when the same strategy runs the following week.

Architecture
────────────

  Live market feed ──► ShadowBot (paper-only, always dry_run=True)
                           │ tick() on every market update
                           │ simulates fills via PaperExchangeConnector
                           │ records ShadowTrade for every fill
                           ▼
                   ShadowLearnerEngine
                           │ check_week_end() once per week (UTC Sunday → Monday)
                           │ if end_equity > start_equity  → winning week
                           ▼
                   WeeklyWinningPattern (saved to PatternMemoryStore)
                           │
                    human reviews  →  promote_pattern()
                           │
                    get_pattern_hints() → strategy hint injected next week

Key design decisions
────────────────────
- Shadow bots NEVER touch real money.  dry_run=True is hard-coded; there is
  no config path that can make a shadow bot place a real order.
- Real-money bots are always MANUAL — the TradingHITLGateway enforces this.
- Winning patterns are stored with ``reviewed=False`` until a human explicitly
  reviews them.  Only ``promoted=True`` patterns influence future hints.
- Weekly evaluation uses configurable ``week_duration_s`` (default 7 days) so
  that unit tests can use short durations without real clock dependency.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_SHADOW_TRADES  = 10_000
_DEFAULT_WEEK_SECS  = 7 * 24 * 3600   # one calendar week in seconds
_DEFAULT_PAPER_USD  = 10_000.0         # starting paper capital per shadow bot


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PatternStatus(Enum):
    """Review lifecycle of a captured pattern (Enum subclass)."""
    PENDING  = "pending"    # saved, not yet reviewed
    REVIEWED = "reviewed"   # human has looked at it
    PROMOTED = "promoted"   # approved to influence future hints
    REJECTED = "rejected"   # human decided it was noise


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ShadowTrade:
    """A single simulated paper trade executed by a shadow bot."""
    trade_id:       str
    bot_id:         str
    pair:           str
    action:         str              # "buy" | "sell"
    entry_price:    float
    exit_price:     float
    quantity:       float
    pnl:            float
    pnl_pct:        float
    confidence:     float
    reasoning:      str
    indicators:     Dict[str, float] = field(default_factory=dict)
    timestamp:      str              = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class WeeklyWinningPattern:
    """
    Captures what a shadow bot did right during a profitable week.

    Fields
    ------
    pattern_id:              Unique ID for this pattern record.
    bot_id:                  Shadow bot that produced the week.
    strategy_id:             Strategy identifier.
    pair:                    Trading pair (e.g. "BTC/USDT").
    week_start / week_end:   ISO-8601 timestamps of the window.
    start_equity:            Paper equity at week start.
    end_equity:              Paper equity at week end.
    gain_pct:                Percentage gain (end/start - 1).
    total_trades:            Total paper trades executed.
    winning_trades:          Trades that ended with positive PnL.
    win_rate:                winning / total.
    dominant_action:         Most frequent signal action.
    avg_winning_indicators:  Mean indicator values across winning trades.
    avg_losing_indicators:   Mean indicator values across losing trades.
    all_trades:              Full list of shadow trades for the week.
    status:                  Review lifecycle state.
    saved_at:                When the pattern was persisted.
    notes:                   Human annotation after review.
    """
    pattern_id:             str
    bot_id:                 str
    strategy_id:            str
    pair:                   str
    week_start:             str
    week_end:               str
    start_equity:           float
    end_equity:             float
    gain_pct:               float
    total_trades:           int
    winning_trades:         int
    losing_trades:          int
    win_rate:               float
    dominant_action:        str
    avg_winning_indicators: Dict[str, float]
    avg_losing_indicators:  Dict[str, float]
    all_trades:             List[ShadowTrade] = field(default_factory=list)
    status:                 PatternStatus     = PatternStatus.PENDING
    saved_at:               str               = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes:                  str               = ""


# ---------------------------------------------------------------------------
# Pattern memory store
# ---------------------------------------------------------------------------

class PatternMemoryStore:
    """
    Persists ``WeeklyWinningPattern`` records to a JSON file.

    Provides human-facing review operations (``review_pattern``,
    ``promote_pattern``, ``reject_pattern``) and a ``get_pattern_hints()``
    method used by strategy-level code to retrieve promoted patterns for
    a given (strategy_id, pair) combination.

    The store is thread-safe; all reads and writes are protected by an
    internal RLock.  The backing file is re-read on every ``load`` call so
    that multiple processes can share the same store file.
    """

    def __init__(self, store_path: str = "data/shadow_patterns.json") -> None:
        self._path  = Path(store_path)
        self._lock  = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write_all([])
        logger.info("PatternMemoryStore: store at %s", self._path)

    # ---- public surface --------------------------------------------------

    def save_pattern(self, pattern: WeeklyWinningPattern) -> str:
        """Persist *pattern* to the store.  Returns ``pattern_id``."""
        with self._lock:
            patterns = self._load_all()
            # Convert enum for serialisation
            data = asdict(pattern)
            data["status"] = pattern.status.value
            patterns.append(data)
            self._write_all(patterns)
        logger.info(
            "PatternMemoryStore: saved pattern %s (%s %s gain=%.2f%%)",
            pattern.pattern_id, pattern.strategy_id, pattern.pair,
            pattern.gain_pct * 100,
        )
        return pattern.pattern_id

    def list_patterns(
        self,
        status:      Optional[PatternStatus] = None,
        strategy_id: Optional[str] = None,
        pair:        Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return pattern dicts matching the given filters."""
        with self._lock:
            all_p = self._load_all()
        result = []
        for p in all_p:
            if status      and p.get("status")      != status.value:      continue
            if strategy_id and p.get("strategy_id") != strategy_id:       continue
            if pair        and p.get("pair")         != pair:              continue
            result.append(p)
        return result

    def get_pattern(self, pattern_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single pattern by ID."""
        with self._lock:
            for p in self._load_all():
                if p.get("pattern_id") == pattern_id:
                    return p
        return None

    def review_pattern(self, pattern_id: str, notes: str = "") -> bool:
        """Mark *pattern_id* as REVIEWED and optionally add notes."""
        return self._update_status(pattern_id, PatternStatus.REVIEWED, notes)

    def promote_pattern(self, pattern_id: str, notes: str = "") -> bool:
        """
        Promote *pattern_id* to PROMOTED status.

        Only promoted patterns are returned by ``get_pattern_hints()``.
        A human must explicitly call this -- promotion cannot happen automatically.
        """
        return self._update_status(pattern_id, PatternStatus.PROMOTED, notes)

    def reject_pattern(self, pattern_id: str, notes: str = "") -> bool:
        """Mark *pattern_id* as REJECTED (noise -- do not use as hint)."""
        return self._update_status(pattern_id, PatternStatus.REJECTED, notes)

    def get_pattern_hints(
        self, strategy_id: str, pair: str
    ) -> List[Dict[str, float]]:
        """
        Return a list of indicator hint dicts from promoted patterns for
        the given strategy and pair.

        Each dict contains ``avg_winning_indicators`` values that can be
        used as a soft bias in strategy signal generation.
        """
        promoted = self.list_patterns(PatternStatus.PROMOTED, strategy_id, pair)
        hints = []
        for p in promoted:
            indicators = p.get("avg_winning_indicators", {})
            if indicators:
                hints.append({
                    "pattern_id":    p.get("pattern_id"),
                    "week_start":    p.get("week_start"),
                    "gain_pct":      p.get("gain_pct"),
                    "win_rate":      p.get("win_rate"),
                    "indicators":    indicators,
                })
        return hints

    def count_by_status(self) -> Dict[str, int]:
        """Return a count of patterns grouped by status."""
        with self._lock:
            all_p = self._load_all()
        counts: Dict[str, int] = {}
        for p in all_p:
            s = p.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ---- internals -------------------------------------------------------

    def _load_all(self) -> List[Dict[str, Any]]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("PatternMemoryStore: load error — returning empty: %s", exc)
            return []

    def _write_all(self, patterns: List[Dict[str, Any]]) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(patterns, fh, indent=2, default=str)
        except OSError as exc:
            logger.error("PatternMemoryStore: write error: %s", exc)

    def _update_status(
        self, pattern_id: str, new_status: PatternStatus, notes: str
    ) -> bool:
        with self._lock:
            patterns = self._load_all()
            for p in patterns:
                if p.get("pattern_id") == pattern_id:
                    p["status"] = new_status.value
                    if notes:
                        p["notes"] = notes
                    self._write_all(patterns)
                    logger.info(
                        "PatternMemoryStore: %s → %s", pattern_id, new_status.value
                    )
                    return True
        return False


# ---------------------------------------------------------------------------
# Shadow bot
# ---------------------------------------------------------------------------

class ShadowBot:
    """
    A paper-only trading bot that shadows live market prices.

    The shadow bot NEVER places real orders.  All fills are simulated
    through the ``PaperExchangeConnector`` (``dry_run=True`` is hard-coded).

    On each ``tick()``:
      1. Fetches latest indicators from the MarketDataFeed.
      2. Calls ``strategy.generate_signal()``.
      3. If BUY signal and no open position → simulate buy at current EMA-9.
      4. If SELL / CLOSE_LONG signal and open position → simulate sell.
      5. Records the ``ShadowTrade`` with the indicator snapshot.
    """

    def __init__(
        self,
        bot_id:          str,
        strategy:        Any,      # BaseStrategy
        market_feed:     Any,      # MarketDataFeed
        pair:            str,
        exchange_id:     str       = "paper",
        initial_paper_usd: float   = _DEFAULT_PAPER_USD,
        week_duration_s: int       = _DEFAULT_WEEK_SECS,
    ) -> None:
        self.bot_id          = bot_id
        self.strategy        = strategy
        self._feed           = market_feed
        self.pair            = pair
        self.exchange_id     = exchange_id
        self._initial_usd    = initial_paper_usd
        self._week_duration  = week_duration_s

        self._lock            = threading.Lock()
        self._paper_usd:      float  = initial_paper_usd
        self._paper_position: float  = 0.0    # base currency held
        self._entry_price:    float  = 0.0
        self._week_start_ts:  float  = time.time()
        self._week_start_usd: float  = initial_paper_usd
        self._week_trades:    List[ShadowTrade] = []
        self._all_trades:     List[ShadowTrade] = []

    # ---- tick -----------------------------------------------------------

    def tick(self) -> Optional[ShadowTrade]:
        """
        Evaluate the strategy and simulate a fill if a signal is generated.

        Returns the ``ShadowTrade`` if a fill occurred, or ``None``.
        """
        from market_data_feed import CandleGranularity
        from trading_strategy_engine import SignalAction

        if self._feed is None:
            return None

        try:
            indicators = self._feed.get_indicators(
                self.exchange_id, self.pair, CandleGranularity.ONE_HOUR
            )
        except Exception as exc:
            logger.debug("ShadowBot %s indicator fetch error: %s", self.bot_id, exc)
            return None

        price = indicators.ema_9 or 0.0
        if price <= 0:
            return None

        signal = self.strategy.generate_signal(self.pair, self._feed, indicators)
        if signal.action in (SignalAction.NO_SIGNAL, SignalAction.HOLD):
            return None

        ind_snapshot = {
            "rsi_14":    indicators.rsi_14,
            "macd_hist": indicators.macd_hist,
            "ema_9":     indicators.ema_9,
            "ema_21":    indicators.ema_21,
            "vwap":      indicators.vwap,
            "bb_upper":  indicators.bb_upper,
            "bb_lower":  indicators.bb_lower,
            "atr_14":    indicators.atr_14,
        }
        # Remove None values
        ind_snapshot = {k: v for k, v in ind_snapshot.items() if v is not None}

        trade: Optional[ShadowTrade] = None
        fee_rate = 0.001  # 0.10 %

        with self._lock:
            if signal.action == SignalAction.BUY and self._paper_position == 0.0:
                size = signal.suggested_size or (self._paper_usd * 0.1 / price)
                cost = price * size * (1 + fee_rate)
                if cost <= self._paper_usd:
                    self._paper_usd      -= cost
                    self._paper_position  = size
                    self._entry_price     = price
                    trade = ShadowTrade(
                        trade_id    = str(uuid.uuid4()),
                        bot_id      = self.bot_id,
                        pair        = self.pair,
                        action      = "buy",
                        entry_price = price,
                        exit_price  = price,
                        quantity    = size,
                        pnl         = 0.0,
                        pnl_pct     = 0.0,
                        confidence  = signal.confidence,
                        reasoning   = signal.reasoning,
                        indicators  = ind_snapshot,
                    )

            elif signal.action in (SignalAction.SELL, SignalAction.CLOSE_LONG) and self._paper_position > 0.0:
                proceeds  = price * self._paper_position * (1 - fee_rate)
                pnl       = proceeds - self._entry_price * self._paper_position
                pnl_pct   = pnl / ((self._entry_price * self._paper_position) or 1)
                self._paper_usd      += proceeds
                trade = ShadowTrade(
                    trade_id    = str(uuid.uuid4()),
                    bot_id      = self.bot_id,
                    pair        = self.pair,
                    action      = "sell",
                    entry_price = self._entry_price,
                    exit_price  = price,
                    quantity    = self._paper_position,
                    pnl         = pnl,
                    pnl_pct     = pnl_pct,
                    confidence  = signal.confidence,
                    reasoning   = signal.reasoning,
                    indicators  = ind_snapshot,
                )
                self._paper_position = 0.0
                self._entry_price    = 0.0

            if trade is not None:
                try:
                    from thread_safe_operations import capped_append_paired
                except ImportError:
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
                capped_append_paired(
                    self._week_trades, trade,
                    self._all_trades, trade,
                    max_size=_MAX_SHADOW_TRADES,
                )

        return trade

    # ---- weekly evaluation ----------------------------------------------

    def is_week_over(self) -> bool:
        """Return True if the configured week duration has elapsed."""
        return (time.time() - self._week_start_ts) >= self._week_duration

    def build_week_pattern(self, week_start_iso: str, week_end_iso: str) -> Optional["WeeklyWinningPattern"]:
        """
        If this week was profitable, return a ``WeeklyWinningPattern``.

        Returns ``None`` if the paper portfolio did not grow (nothing to save).
        """
        with self._lock:
            # Include current open position at last known price
            current_equity = self._paper_usd
            if self._paper_position > 0.0 and self._entry_price > 0.0:
                current_equity += self._paper_position * self._entry_price

            if current_equity <= self._week_start_usd:
                return None  # not a winning week

            trades = list(self._week_trades)
            sells  = [t for t in trades if t.action == "sell"]
            wins   = [t for t in sells if t.pnl > 0]
            losses = [t for t in sells if t.pnl <= 0]
            total  = len(sells) or 1
            gain   = (current_equity - self._week_start_usd) / (self._week_start_usd or 1)

            # Dominant action
            actions: Dict[str, int] = {}
            for t in trades:
                actions[t.action] = actions.get(t.action, 0) + 1
            dominant = max(actions, key=lambda a: actions[a]) if actions else "buy"

            # Average indicator values for winning vs losing sell trades
            def avg_indicators(trade_list: List[ShadowTrade]) -> Dict[str, float]:
                if not trade_list:
                    return {}
                merged: Dict[str, List[float]] = {}
                for t in trade_list:
                    for k, v in t.indicators.items():
                        merged.setdefault(k, []).append(v)
                return {
                    k: sum(vs) / (len(vs) or 1)
                    for k, vs in merged.items()
                    if vs  # only include keys with at least one value
                }

            strategy_id = getattr(self.strategy, "strategy_id", "unknown")

            return WeeklyWinningPattern(
                pattern_id             = str(uuid.uuid4()),
                bot_id                 = self.bot_id,
                strategy_id            = strategy_id,
                pair                   = self.pair,
                week_start             = week_start_iso,
                week_end               = week_end_iso,
                start_equity           = self._week_start_usd,
                end_equity             = current_equity,
                gain_pct               = gain,
                total_trades           = len(sells),
                winning_trades         = len(wins),
                losing_trades          = len(losses),
                win_rate               = len(wins) / total,
                dominant_action        = dominant,
                avg_winning_indicators = avg_indicators(wins),
                avg_losing_indicators  = avg_indicators(losses),
                all_trades             = trades,
            )

    def reset_week(self, keep_equity: bool = True) -> None:
        """
        Prepare the shadow bot for the next week.

        If *keep_equity* is True (winning week), the paper capital accumulated
        this week carries forward.  If False (losing week), revert to the
        original starting capital so the bot can try again fresh.
        """
        with self._lock:
            if not keep_equity:
                self._paper_usd      = self._initial_usd
                self._paper_position = 0.0
                self._entry_price    = 0.0
            self._week_start_usd = (
                self._paper_usd
                + (self._paper_position * self._entry_price if self._paper_position > 0 else 0.0)
            )
            self._week_trades     = []
            self._week_start_ts   = time.time()
            logger.info(
                "ShadowBot %s: week reset — starting_equity=%.2f carry_forward=%s",
                self.bot_id, self._week_start_usd, keep_equity,
            )

    def get_current_equity(self) -> float:
        """Return current paper equity (cash + open position value)."""
        with self._lock:
            return self._equity_unlocked()

    def get_week_stats(self) -> Dict[str, Any]:
        """Return a summary of performance for the current week window."""
        with self._lock:
            equity  = self._equity_unlocked()
            sells   = [t for t in self._week_trades if t.action == "sell"]
            wins    = [t for t in sells if t.pnl > 0]
            gain    = (equity - self._week_start_usd) / (self._week_start_usd or 1)
            elapsed = time.time() - self._week_start_ts
            return {
                "bot_id":          self.bot_id,
                "pair":            self.pair,
                "strategy_id":     getattr(self.strategy, "strategy_id", "unknown"),
                "start_equity":    self._week_start_usd,
                "current_equity":  equity,
                "gain_pct":        gain,
                "total_sells":     len(sells),
                "wins":            len(wins),
                "win_rate":        len(wins) / (len(sells) or 1),
                "elapsed_s":       elapsed,
                "week_duration_s": self._week_duration,
                "pct_complete":    min(1.0, elapsed / (self._week_duration or 1)),
            }

    # ---- helpers --------------------------------------------------------

    def _equity_unlocked(self) -> float:
        """Compute equity without acquiring self._lock (caller must hold it)."""
        equity = self._paper_usd
        if self._paper_position > 0.0 and self._entry_price > 0.0:
            equity += self._paper_position * self._entry_price
        return equity


# ---------------------------------------------------------------------------
# Shadow learner engine
# ---------------------------------------------------------------------------

class ShadowLearnerEngine:
    """
    Manages a fleet of ``ShadowBot`` instances and orchestrates the
    weekly learning cycle.

    Usage
    -----
    ::
        store  = PatternMemoryStore("data/shadow_patterns.json")
        feed   = MarketDataFeed()
        engine = ShadowLearnerEngine(store, feed)

        bot_id = engine.register_shadow_bot(
            strategy=MomentumStrategy("mom1"),
            pair="BTC/USDT",
        )
        # Call engine.tick_all() on every market update
        # Call engine.check_week_end() periodically (e.g. daily cron job)

    Pattern promotion workflow
    --------------------------
    After ``check_week_end()`` saves winning patterns the user calls::

        store.review_pattern(pattern_id, notes="looks good")
        store.promote_pattern(pattern_id, notes="promoting for next week")

    Promoted patterns can then be retrieved for strategy hints::

        hints = store.get_pattern_hints("mom1", "BTC/USDT")
    """

    def __init__(
        self,
        pattern_store:   PatternMemoryStore,
        market_feed:     Any,   # MarketDataFeed
        week_duration_s: int   = _DEFAULT_WEEK_SECS,
    ) -> None:
        self._store       = pattern_store
        self._feed        = market_feed
        self._week_secs   = week_duration_s
        self._lock        = threading.Lock()
        self._bots:       Dict[str, ShadowBot] = {}

    # ---- bot management --------------------------------------------------

    def register_shadow_bot(
        self,
        strategy:          Any,
        pair:              str,
        exchange_id:       str   = "paper",
        initial_paper_usd: float = _DEFAULT_PAPER_USD,
        bot_id:            Optional[str] = None,
    ) -> str:
        """
        Register a new shadow bot.  Returns the assigned ``bot_id``.

        Shadow bots are always paper-only; ``dry_run=True`` cannot be
        changed.
        """
        bid  = bot_id or str(uuid.uuid4())
        bot  = ShadowBot(
            bot_id          = bid,
            strategy        = strategy,
            market_feed     = self._feed,
            pair            = pair,
            exchange_id     = exchange_id,
            initial_paper_usd = initial_paper_usd,
            week_duration_s = self._week_secs,
        )
        with self._lock:
            self._bots[bid] = bot
        logger.info(
            "ShadowLearnerEngine: registered shadow bot %s pair=%s strategy=%s",
            bid, pair, getattr(strategy, "strategy_id", "unknown"),
        )
        return bid

    def unregister_shadow_bot(self, bot_id: str) -> bool:
        """Remove a shadow bot from the engine."""
        with self._lock:
            removed = self._bots.pop(bot_id, None)
        return removed is not None

    def tick_all(self) -> List[ShadowTrade]:
        """
        Evaluate every shadow bot for the current market state.

        Returns all ``ShadowTrade`` fills generated this tick.
        Call this whenever new candle/price data arrives.
        """
        with self._lock:
            bots = list(self._bots.values())
        fills = []
        for bot in bots:
            try:
                fill = bot.tick()
                if fill is not None:
                    fills.append(fill)
            except Exception as exc:
                logger.error("ShadowLearnerEngine: bot %s tick error: %s", bot.bot_id, exc)
        return fills

    def check_week_end(self) -> List[WeeklyWinningPattern]:
        """
        Evaluate all shadow bots whose week window has elapsed.

        For each bot:
          - If ``end_equity > start_equity`` (profitable week):
              * Build a ``WeeklyWinningPattern`` and save to the store.
              * Reset with ``keep_equity=True`` (compound gains).
          - Otherwise:
              * Reset with ``keep_equity=False`` (revert to starting capital).

        Returns the list of new ``WeeklyWinningPattern`` instances saved
        this call.
        """
        with self._lock:
            bots = list(self._bots.values())

        now_iso   = datetime.now(timezone.utc).isoformat()
        saved:    List[WeeklyWinningPattern] = []

        for bot in bots:
            if not bot.is_week_over():
                continue
            week_start_iso = datetime.fromtimestamp(
                bot._week_start_ts, tz=timezone.utc
            ).isoformat()
            pattern = bot.build_week_pattern(week_start_iso, now_iso)
            if pattern is not None:
                self._store.save_pattern(pattern)
                saved.append(pattern)
                bot.reset_week(keep_equity=True)
                logger.info(
                    "ShadowLearnerEngine: winning week saved — bot=%s gain=%.2f%% "
                    "trades=%d win_rate=%.1f%%",
                    bot.bot_id, pattern.gain_pct * 100,
                    pattern.total_trades, pattern.win_rate * 100,
                )
            else:
                bot.reset_week(keep_equity=False)
                logger.info(
                    "ShadowLearnerEngine: losing week — bot=%s portfolio reset",
                    bot.bot_id,
                )

        return saved

    # ---- dashboard -------------------------------------------------------

    def get_all_week_stats(self) -> List[Dict[str, Any]]:
        """Return current-week performance stats for every shadow bot."""
        with self._lock:
            bots = list(self._bots.values())
        return [b.get_week_stats() for b in bots]

    def get_bot(self, bot_id: str) -> Optional[ShadowBot]:
        """Retrieve a shadow bot by ID."""
        with self._lock:
            return self._bots.get(bot_id)

    def list_bot_ids(self) -> List[str]:
        """Return all registered shadow bot IDs."""
        with self._lock:
            return list(self._bots.keys())

    # ---- pattern hints interface ----------------------------------------

    def get_hints_for_bot(self, bot_id: str) -> List[Dict[str, float]]:
        """
        Return promoted pattern hints for the strategy and pair of *bot_id*.

        Hints are average winning indicator values from past promoted weeks.
        Strategy code can use these as soft biases (e.g. tighten RSI threshold
        if promoted patterns had RSI near 32 at winning buy signals).
        """
        bot = self.get_bot(bot_id)
        if bot is None:
            return []
        strategy_id = getattr(bot.strategy, "strategy_id", "unknown")
        return self._store.get_pattern_hints(strategy_id, bot.pair)
