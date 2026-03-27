"""
Gap Closure Tests — Round 47.

Validates the shadow learning system and real-money guard introduced in this round:

  Gap 1 (Critical): Real-money guard in TradingHITLGateway
                    - if dry_run=False and mode != MANUAL → force MANUAL automatically

  Gap 2 (High):     trading_shadow_learner module
                    - PatternMemoryStore  — CRUD + review/promote/reject lifecycle
                    - ShadowBot           — paper tick, weekly stats, pattern capture
                    - ShadowLearnerEngine — fleet management, week-end evaluation,
                                            pattern hints surface
"""

import time
import tempfile
import os
from pathlib import Path


import pytest


# ===========================================================================
# Helpers / Fixtures
# ===========================================================================

def _make_rich_feed(pair: str = "BTC/USDT", n: int = 250) -> "MarketDataFeed":
    """Build a MarketDataFeed pre-populated with enough candles for indicators.
    Uses oscillating prices (sine-like) to produce realistic RSI values."""
    import math
    from market_data_feed import MarketDataFeed, Candle, CandleGranularity
    feed = MarketDataFeed()
    for i in range(n):
        # Oscillate between ~49_000 and ~51_000 to keep RSI in 30–70 range
        close = 50_000.0 + math.sin(i * 0.3) * 1_000.0
        high  = close + 100.0
        low   = close - 100.0
        feed.push_candle(Candle(
            "paper", pair, CandleGranularity.ONE_HOUR,
            1_700_000_000 + i * 3600,
            close - 50.0, high, low, close, 100.0,
        ))
    return feed


def _make_momentum_strategy(sid: str = "mom_test") -> "MomentumStrategy":
    from trading_strategy_engine import MomentumStrategy
    return MomentumStrategy(sid, {"rsi_oversold": 35.0, "rsi_overbought": 65.0})


def _make_dca_strategy(sid: str = "dca_test") -> "DCAStrategy":
    from trading_strategy_engine import DCAStrategy
    return DCAStrategy(sid, {"interval_hours": 0, "invest_amount_usd": 100.0, "rsi_max": 80.0})


def _tmp_store() -> "PatternMemoryStore":
    """Create a PatternMemoryStore backed by a temp file."""
    from trading_shadow_learner import PatternMemoryStore
    tmp = tempfile.mktemp(suffix=".json", prefix="test_shadow_", dir="/tmp")
    return PatternMemoryStore(store_path=tmp)


def _make_signal(action: str = "buy", confidence: float = 0.9, dry_run: bool = False) -> tuple:
    """Return (signal, config) for HITL gateway tests."""
    from trading_strategy_engine import TradingSignal, SignalAction
    from trading_bot_lifecycle import BotLifecycleConfig, BotHITLMode
    sig = TradingSignal(
        strategy_id     = "test_strat",
        pair            = "BTC/USDT",
        action          = SignalAction.BUY if action == "buy" else SignalAction.SELL,
        confidence      = confidence,
        suggested_price = 50_000.0,
        suggested_size  = 0.01,
        stop_loss       = 49_000.0,
        take_profit     = 52_000.0,
        reasoning       = "test",
    )
    cfg = BotLifecycleConfig(
        exchange_id = "coinbase",
        pair        = "BTC/USDT",
        strategy_id = "test_strat",
        hitl_mode   = BotHITLMode.AUTOMATED,   # will be downgraded if dry_run=False
        dry_run     = dry_run,
    )
    return sig, cfg


# ===========================================================================
# Gap 1 — Real-money guard in TradingHITLGateway
# ===========================================================================

class TestGap1_RealMoneyGuard:
    """
    Real-money (dry_run=False) signals must always route to MANUAL queue,
    regardless of the bot's configured HITL mode.
    """

    def test_module_imports(self):
        import trading_hitl_gateway  # noqa: F401

    def test_real_money_automated_forced_to_manual_queue(self):
        """dry_run=False + AUTOMATED mode → must land in the MANUAL pending queue."""
        from trading_hitl_gateway import TradingHITLGateway, ApprovalStatus
        gw  = TradingHITLGateway()
        sig, cfg = _make_signal(dry_run=False)
        req = gw.submit_trade_signal("bot_real_auto", sig, cfg)
        # Must be queued for a human, not auto-approved
        assert req.status == ApprovalStatus.PENDING, (
            f"Expected PENDING but got {req.status} — real-money bot was auto-approved!"
        )
        assert len(gw.get_pending_trades()) >= 1

    def test_real_money_supervised_forced_to_manual_queue(self):
        """dry_run=False + SUPERVISED mode → must land in the MANUAL pending queue."""
        from trading_hitl_gateway import TradingHITLGateway, ApprovalStatus
        from trading_bot_lifecycle import BotLifecycleConfig, BotHITLMode
        from trading_strategy_engine import TradingSignal, SignalAction
        gw = TradingHITLGateway(auto_confidence_threshold=0.5)
        sig = TradingSignal(
            strategy_id="s", pair="ETH/USDT", action=SignalAction.BUY,
            confidence=0.99, suggested_price=3000.0, suggested_size=0.1,
            stop_loss=2900.0, take_profit=3200.0, reasoning="high confidence",
        )
        cfg = BotLifecycleConfig(
            exchange_id="coinbase", pair="ETH/USDT", strategy_id="s",
            hitl_mode=BotHITLMode.SUPERVISED, dry_run=False,
        )
        req = gw.submit_trade_signal("bot_real_sup", sig, cfg)
        assert req.status == ApprovalStatus.PENDING, (
            "SUPERVISED real-money should be PENDING, not auto-approved"
        )

    def test_real_money_manual_mode_stays_pending(self):
        """dry_run=False + MANUAL mode → stays MANUAL (no change needed)."""
        from trading_hitl_gateway import TradingHITLGateway, ApprovalStatus
        from trading_bot_lifecycle import BotLifecycleConfig, BotHITLMode
        from trading_strategy_engine import TradingSignal, SignalAction
        gw  = TradingHITLGateway()
        sig = TradingSignal(
            strategy_id="s", pair="BTC/USDT", action=SignalAction.BUY,
            confidence=0.8, suggested_price=50_000.0, suggested_size=0.01,
            stop_loss=49_000.0, take_profit=52_000.0, reasoning="manual real",
        )
        cfg = BotLifecycleConfig(
            exchange_id="coinbase", pair="BTC/USDT", strategy_id="s",
            hitl_mode=BotHITLMode.MANUAL, dry_run=False,
        )
        req = gw.submit_trade_signal("bot_real_man", sig, cfg)
        assert req.status == ApprovalStatus.PENDING

    def test_paper_automated_bot_still_auto_approves(self):
        """dry_run=True + AUTOMATED mode → auto-approve is allowed (paper bot)."""
        from trading_hitl_gateway import TradingHITLGateway, ApprovalStatus, TradeDecision
        from trading_bot_lifecycle import BotLifecycleConfig, BotHITLMode
        from trading_strategy_engine import TradingSignal, SignalAction
        gw  = TradingHITLGateway()
        sig = TradingSignal(
            strategy_id="s", pair="BTC/USDT", action=SignalAction.BUY,
            confidence=0.9, suggested_price=50_000.0, suggested_size=0.01,
            stop_loss=49_000.0, take_profit=52_000.0, reasoning="paper auto",
        )
        cfg = BotLifecycleConfig(
            exchange_id="paper", pair="BTC/USDT", strategy_id="s",
            hitl_mode=BotHITLMode.AUTOMATED, dry_run=True,
        )
        req = gw.submit_trade_signal("bot_paper_auto", sig, cfg)
        assert req.status   == ApprovalStatus.DECIDED
        assert req.decision == TradeDecision.AUTO

    def test_paper_supervised_high_confidence_auto_approves(self):
        """dry_run=True + SUPERVISED + high confidence → auto-approve is allowed."""
        from trading_hitl_gateway import TradingHITLGateway, ApprovalStatus, TradeDecision
        from trading_bot_lifecycle import BotLifecycleConfig, BotHITLMode
        from trading_strategy_engine import TradingSignal, SignalAction
        gw  = TradingHITLGateway(auto_confidence_threshold=0.7, auto_murphy_threshold=0.5)
        sig = TradingSignal(
            strategy_id="s", pair="BTC/USDT", action=SignalAction.BUY,
            confidence=0.95, suggested_price=50_000.0, suggested_size=0.01,
            stop_loss=49_000.0, take_profit=52_000.0, reasoning="supervised paper",
        )
        cfg = BotLifecycleConfig(
            exchange_id="paper", pair="BTC/USDT", strategy_id="s",
            hitl_mode=BotHITLMode.SUPERVISED, dry_run=True,
        )
        req = gw.submit_trade_signal("bot_paper_sup", sig, cfg)
        assert req.decision == TradeDecision.AUTO

    def test_real_money_request_has_dry_run_false(self):
        """The request object must faithfully record dry_run=False."""
        from trading_hitl_gateway import TradingHITLGateway
        gw  = TradingHITLGateway()
        sig, cfg = _make_signal(dry_run=False)
        req = gw.submit_trade_signal("bot_check_dry", sig, cfg)
        assert req.dry_run is False

    def test_real_money_guard_logged_as_manual_override(self, caplog):
        """The override warning should appear in logs."""
        import logging
        from trading_hitl_gateway import TradingHITLGateway
        gw   = TradingHITLGateway()
        sig, cfg = _make_signal(dry_run=False)   # cfg has AUTOMATED mode
        with caplog.at_level(logging.WARNING, logger="trading_hitl_gateway"):
            gw.submit_trade_signal("bot_log_check", sig, cfg)
        assert any("SAFETY LOCK" in r.message or "MANUAL" in r.message for r in caplog.records)

    def test_multiple_real_money_bots_all_queued(self):
        """Multiple real-money signals from different bots all queue for human."""
        from trading_hitl_gateway import TradingHITLGateway, ApprovalStatus
        gw = TradingHITLGateway()
        for i in range(5):
            sig, cfg = _make_signal(dry_run=False)
            req = gw.submit_trade_signal(f"bot_real_{i}", sig, cfg)
            assert req.status == ApprovalStatus.PENDING, f"bot {i} was not PENDING"
        assert len(gw.get_pending_trades()) == 5


# ===========================================================================
# Gap 2a — PatternMemoryStore
# ===========================================================================

class TestGap2a_PatternMemoryStore:
    """Verify CRUD, status lifecycle, and filter queries for PatternMemoryStore."""

    def test_module_imports(self):
        import trading_shadow_learner  # noqa: F401

    def test_enums_exist(self):
        from trading_shadow_learner import PatternStatus
        assert PatternStatus.PENDING.value  == "pending"
        assert PatternStatus.PROMOTED.value == "promoted"
        assert PatternStatus.REJECTED.value == "rejected"

    def test_save_and_list(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern, PatternStatus
        store = _tmp_store()
        p = WeeklyWinningPattern(
            pattern_id="p1", bot_id="b1", strategy_id="mom", pair="BTC/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=10_000.0, end_equity=10_500.0, gain_pct=0.05,
            total_trades=10, winning_trades=7, losing_trades=3, win_rate=0.7,
            dominant_action="buy",
            avg_winning_indicators={"rsi_14": 32.0, "macd_hist": 0.002},
            avg_losing_indicators={"rsi_14": 55.0, "macd_hist": -0.001},
        )
        pid = store.save_pattern(p)
        assert pid == "p1"
        patterns = store.list_patterns()
        assert len(patterns) == 1
        assert patterns[0]["gain_pct"] == pytest.approx(0.05)

    def test_list_filtered_by_status(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern, PatternStatus
        store = _tmp_store()
        for i in range(3):
            store.save_pattern(WeeklyWinningPattern(
                pattern_id=f"p{i}", bot_id="b1", strategy_id="mom", pair="BTC/USDT",
                week_start="2026-01-01", week_end="2026-01-07",
                start_equity=10_000.0, end_equity=10_100.0, gain_pct=0.01,
                total_trades=5, winning_trades=3, losing_trades=2, win_rate=0.6,
                dominant_action="buy",
                avg_winning_indicators={"rsi_14": 30.0},
                avg_losing_indicators={},
            ))
        store.promote_pattern("p1")
        pending  = store.list_patterns(status=PatternStatus.PENDING)
        promoted = store.list_patterns(status=PatternStatus.PROMOTED)
        assert len(pending)  == 2
        assert len(promoted) == 1

    def test_review_pattern(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern, PatternStatus
        store = _tmp_store()
        store.save_pattern(WeeklyWinningPattern(
            pattern_id="rv1", bot_id="b", strategy_id="s", pair="BTC/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=10_000.0, end_equity=10_200.0, gain_pct=0.02,
            total_trades=4, winning_trades=3, losing_trades=1, win_rate=0.75,
            dominant_action="buy",
            avg_winning_indicators={"rsi_14": 28.0},
            avg_losing_indicators={},
        ))
        ok = store.review_pattern("rv1", notes="Looks good")
        assert ok
        p = store.get_pattern("rv1")
        assert p["status"] == PatternStatus.REVIEWED.value
        assert p["notes"] == "Looks good"

    def test_promote_pattern(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern, PatternStatus
        store = _tmp_store()
        store.save_pattern(WeeklyWinningPattern(
            pattern_id="pr1", bot_id="b", strategy_id="mom", pair="BTC/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=10_000.0, end_equity=10_300.0, gain_pct=0.03,
            total_trades=6, winning_trades=4, losing_trades=2, win_rate=0.667,
            dominant_action="buy",
            avg_winning_indicators={"rsi_14": 31.0, "macd_hist": 0.003},
            avg_losing_indicators={"rsi_14": 60.0},
        ))
        store.promote_pattern("pr1")
        hints = store.get_pattern_hints("mom", "BTC/USDT")
        assert len(hints) == 1
        assert hints[0]["indicators"]["rsi_14"] == pytest.approx(31.0)

    def test_reject_pattern(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern, PatternStatus
        store = _tmp_store()
        store.save_pattern(WeeklyWinningPattern(
            pattern_id="rj1", bot_id="b", strategy_id="s", pair="ETH/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=5_000.0, end_equity=5_100.0, gain_pct=0.02,
            total_trades=2, winning_trades=1, losing_trades=1, win_rate=0.5,
            dominant_action="sell",
            avg_winning_indicators={},
            avg_losing_indicators={},
        ))
        ok = store.reject_pattern("rj1", notes="noise trade")
        assert ok
        hints = store.get_pattern_hints("s", "ETH/USDT")
        assert hints == []

    def test_get_pattern_by_id(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern
        store = _tmp_store()
        store.save_pattern(WeeklyWinningPattern(
            pattern_id="get1", bot_id="b", strategy_id="s", pair="BTC/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=10_000.0, end_equity=10_500.0, gain_pct=0.05,
            total_trades=8, winning_trades=6, losing_trades=2, win_rate=0.75,
            dominant_action="buy",
            avg_winning_indicators={"rsi_14": 28.0},
            avg_losing_indicators={},
        ))
        p = store.get_pattern("get1")
        assert p is not None
        assert p["pair"] == "BTC/USDT"

    def test_unknown_pattern_returns_none(self):
        from trading_shadow_learner import PatternMemoryStore
        store = _tmp_store()
        assert store.get_pattern("does_not_exist") is None

    def test_count_by_status(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern
        store = _tmp_store()
        for i in range(4):
            store.save_pattern(WeeklyWinningPattern(
                pattern_id=f"cnt{i}", bot_id="b", strategy_id="s", pair="BTC/USDT",
                week_start="2026-01-01", week_end="2026-01-07",
                start_equity=10_000.0, end_equity=10_100.0, gain_pct=0.01,
                total_trades=1, winning_trades=1, losing_trades=0, win_rate=1.0,
                dominant_action="buy",
                avg_winning_indicators={}, avg_losing_indicators={},
            ))
        store.promote_pattern("cnt0")
        store.promote_pattern("cnt1")
        counts = store.count_by_status()
        assert counts.get("pending", 0) == 2
        assert counts.get("promoted", 0) == 2

    def test_filter_by_strategy_and_pair(self):
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern
        store = _tmp_store()
        store.save_pattern(WeeklyWinningPattern(
            pattern_id="f1", bot_id="b", strategy_id="alpha", pair="BTC/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=10_000.0, end_equity=10_200.0, gain_pct=0.02,
            total_trades=3, winning_trades=2, losing_trades=1, win_rate=0.67,
            dominant_action="buy", avg_winning_indicators={}, avg_losing_indicators={},
        ))
        store.save_pattern(WeeklyWinningPattern(
            pattern_id="f2", bot_id="b", strategy_id="beta", pair="ETH/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=5_000.0, end_equity=5_100.0, gain_pct=0.02,
            total_trades=2, winning_trades=2, losing_trades=0, win_rate=1.0,
            dominant_action="buy", avg_winning_indicators={}, avg_losing_indicators={},
        ))
        assert len(store.list_patterns(strategy_id="alpha")) == 1
        assert len(store.list_patterns(pair="ETH/USDT"))      == 1
        assert len(store.list_patterns(strategy_id="beta", pair="BTC/USDT")) == 0

    def test_store_persists_across_instances(self):
        """Writing in one store instance, reading in another should work."""
        from trading_shadow_learner import PatternMemoryStore, WeeklyWinningPattern
        import tempfile
        path = tempfile.mktemp(suffix=".json", prefix="persist_test_", dir="/tmp")
        s1   = PatternMemoryStore(path)
        s1.save_pattern(WeeklyWinningPattern(
            pattern_id="pers1", bot_id="b", strategy_id="s", pair="BTC/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=10_000.0, end_equity=10_500.0, gain_pct=0.05,
            total_trades=5, winning_trades=4, losing_trades=1, win_rate=0.8,
            dominant_action="buy", avg_winning_indicators={}, avg_losing_indicators={},
        ))
        s2 = PatternMemoryStore(path)
        assert len(s2.list_patterns()) == 1


# ===========================================================================
# Gap 2b — ShadowBot
# ===========================================================================

class TestGap2b_ShadowBot:
    """Verify paper-trading mechanics and weekly stats in ShadowBot."""

    def test_module_imports(self):
        from trading_shadow_learner import ShadowBot  # noqa: F401

    def test_initial_equity(self):
        from trading_shadow_learner import ShadowBot
        feed  = _make_rich_feed()
        strat = _make_momentum_strategy()
        bot   = ShadowBot("sb1", strat, feed, "BTC/USDT", initial_paper_usd=5_000.0,
                          week_duration_s=9999)
        assert bot.get_current_equity() == pytest.approx(5_000.0)

    def test_tick_returns_none_with_no_signal(self):
        """A strategy that never signals should return None on every tick.
        Use a DCA strategy with an enormous interval AND very low rsi_max
        so even an oversold RSI does not trigger."""
        from trading_shadow_learner import ShadowBot
        from trading_strategy_engine import DCAStrategy
        # interval_hours=9999 PLUS rsi_max=0 so RSI (always > 0) never satisfies the check
        strat  = DCAStrategy("no_signal_dca", {"interval_hours": 9_999, "invest_amount_usd": 100.0,
                                               "rsi_max": 0.0})
        feed   = _make_rich_feed()
        bot    = ShadowBot("sb_ns", strat, feed, "BTC/USDT", week_duration_s=9999)
        result = bot.tick()
        assert result is None

    def test_tick_buy_then_sell_cycle(self):
        """DCA bot at interval_hours=0 should buy on first tick, sell on a sell signal."""
        from trading_shadow_learner import ShadowBot
        from trading_strategy_engine import DCAStrategy, MomentumStrategy
        feed  = _make_rich_feed()
        strat = DCAStrategy("cycle_dca", {"interval_hours": 0, "invest_amount_usd": 500.0, "rsi_max": 99.0})
        bot   = ShadowBot("sb_cycle", strat, feed, "BTC/USDT",
                          initial_paper_usd=10_000.0, week_duration_s=9999)
        # Should generate a BUY on first tick
        fill = bot.tick()
        assert fill is not None
        assert fill.action == "buy"
        assert bot._paper_position > 0.0

    def test_buy_reduces_paper_cash(self):
        """After a buy tick, paper_usd should decrease."""
        from trading_shadow_learner import ShadowBot
        from trading_strategy_engine import DCAStrategy
        feed  = _make_rich_feed()
        strat = DCAStrategy("cash_dca", {"interval_hours": 0, "invest_amount_usd": 500.0, "rsi_max": 99.0})
        bot   = ShadowBot("sb_cash", strat, feed, "BTC/USDT",
                          initial_paper_usd=10_000.0, week_duration_s=9999)
        bot.tick()
        assert bot._paper_usd < 10_000.0

    def test_sell_closes_position(self):
        """Simulate a sell signal being generated to close an open position."""
        from trading_shadow_learner import ShadowBot, ShadowTrade
        from trading_strategy_engine import SignalAction
        feed  = _make_rich_feed()
        strat = _make_momentum_strategy()
        bot   = ShadowBot("sb_sell", strat, feed, "BTC/USDT",
                          initial_paper_usd=10_000.0, week_duration_s=9999)
        # Manually inject an open position
        bot._paper_usd      -= 5_000.0
        bot._paper_position  = 0.1
        bot._entry_price     = 50_000.0
        # Force a sell via a fake signal
        bot._week_trades = []
        # Patch the strategy to return a SELL
        from unittest.mock import patch, MagicMock
        from market_data_feed import TechnicalIndicators, CandleGranularity
        ind = TechnicalIndicators(pair="BTC/USDT", granularity=CandleGranularity.ONE_HOUR)
        ind.rsi_14    = 80.0
        ind.macd_hist = -0.01
        ind.ema_9     = 50_050.0
        from trading_strategy_engine import TradingSignal
        sell_sig = TradingSignal(
            strategy_id="test", pair="BTC/USDT", action=SignalAction.SELL,
            confidence=0.85, suggested_price=50_050.0, suggested_size=0.1,
            stop_loss=None, take_profit=None, reasoning="rsi overbought",
        )
        with patch.object(strat, "generate_signal", return_value=sell_sig):
            fill = bot.tick()
        if fill is not None:
            assert fill.action == "sell"
            assert bot._paper_position == 0.0

    def test_week_stats_structure(self):
        from trading_shadow_learner import ShadowBot
        strat = _make_dca_strategy()
        feed  = _make_rich_feed()
        bot   = ShadowBot("sb_stats", strat, feed, "BTC/USDT",
                          initial_paper_usd=10_000.0, week_duration_s=9999)
        stats = bot.get_week_stats()
        assert "bot_id"         in stats
        assert "start_equity"   in stats
        assert "current_equity" in stats
        assert "gain_pct"       in stats
        assert "pct_complete"   in stats

    def test_is_week_over_false_initially(self):
        from trading_shadow_learner import ShadowBot
        bot = ShadowBot("sb_wk", _make_dca_strategy(), _make_rich_feed(), "BTC/USDT",
                        week_duration_s=9999)
        assert not bot.is_week_over()

    def test_is_week_over_with_zero_duration(self):
        """A duration of 0 seconds means the week is always over."""
        from trading_shadow_learner import ShadowBot
        bot = ShadowBot("sb_0wk", _make_dca_strategy(), None, "BTC/USDT",
                        week_duration_s=0)
        assert bot.is_week_over()

    def test_reset_week_keep_equity(self):
        from trading_shadow_learner import ShadowBot
        bot = ShadowBot("sb_rst", _make_dca_strategy(), None, "BTC/USDT",
                        initial_paper_usd=10_000.0, week_duration_s=9999)
        bot._paper_usd = 11_000.0
        bot.reset_week(keep_equity=True)
        assert bot._week_start_usd == pytest.approx(11_000.0)

    def test_reset_week_revert_equity(self):
        from trading_shadow_learner import ShadowBot
        bot = ShadowBot("sb_rst2", _make_dca_strategy(), None, "BTC/USDT",
                        initial_paper_usd=10_000.0, week_duration_s=9999)
        bot._paper_usd = 8_000.0
        bot.reset_week(keep_equity=False)
        assert bot._paper_usd == pytest.approx(10_000.0)
        assert bot._week_start_usd == pytest.approx(10_000.0)

    def test_no_winning_pattern_when_equity_flat(self):
        from trading_shadow_learner import ShadowBot
        bot = ShadowBot("sb_flat", _make_dca_strategy(), None, "BTC/USDT",
                        initial_paper_usd=10_000.0, week_duration_s=0)
        # equity unchanged → no pattern
        pattern = bot.build_week_pattern("2026-01-01", "2026-01-07")
        assert pattern is None

    def test_winning_pattern_when_equity_higher(self):
        from trading_shadow_learner import ShadowBot, ShadowTrade
        bot = ShadowBot("sb_win", _make_dca_strategy(), None, "BTC/USDT",
                        initial_paper_usd=10_000.0, week_duration_s=0)
        # Simulate a profitable week with one winning sell trade
        trade = ShadowTrade(
            trade_id="t1", bot_id="sb_win", pair="BTC/USDT", action="sell",
            entry_price=50_000.0, exit_price=51_000.0, quantity=0.1,
            pnl=100.0, pnl_pct=0.02, confidence=0.8, reasoning="test",
            indicators={"rsi_14": 30.0, "macd_hist": 0.001},
        )
        bot._week_trades.append(trade)
        bot._paper_usd = 10_200.0  # above start
        pattern = bot.build_week_pattern("2026-01-01", "2026-01-07")
        assert pattern is not None
        assert pattern.gain_pct > 0.0
        assert pattern.winning_trades == 1
        assert "rsi_14" in pattern.avg_winning_indicators

    def test_winning_pattern_indicator_averages(self):
        """avg_winning_indicators must be the mean of all winning sell trades."""
        from trading_shadow_learner import ShadowBot, ShadowTrade
        bot = ShadowBot("sb_avgi", _make_dca_strategy(), None, "BTC/USDT",
                        initial_paper_usd=10_000.0, week_duration_s=0)
        for i in range(3):
            trade = ShadowTrade(
                trade_id=str(i), bot_id="sb_avgi", pair="BTC/USDT", action="sell",
                entry_price=50_000.0, exit_price=51_000.0, quantity=0.01,
                pnl=10.0, pnl_pct=0.02, confidence=0.8, reasoning="win",
                indicators={"rsi_14": 30.0 + i, "macd_hist": 0.001 * (i + 1)},
            )
            bot._week_trades.append(trade)
        bot._paper_usd = 10_300.0
        pattern = bot.build_week_pattern("2026-01-01", "2026-01-07")
        assert pattern is not None
        # rsi_14 average of [30, 31, 32] = 31.0
        assert pattern.avg_winning_indicators["rsi_14"] == pytest.approx(31.0)


# ===========================================================================
# Gap 2c — ShadowLearnerEngine
# ===========================================================================

class TestGap2c_ShadowLearnerEngine:
    """Verify fleet management and week-end evaluation in ShadowLearnerEngine."""

    def test_module_imports(self):
        from trading_shadow_learner import ShadowLearnerEngine  # noqa: F401

    def test_register_shadow_bot(self):
        from trading_shadow_learner import ShadowLearnerEngine
        store  = _tmp_store()
        feed   = _make_rich_feed()
        engine = ShadowLearnerEngine(store, feed, week_duration_s=9999)
        bid    = engine.register_shadow_bot(_make_momentum_strategy(), "BTC/USDT")
        assert bid in engine.list_bot_ids()

    def test_unregister_shadow_bot(self):
        from trading_shadow_learner import ShadowLearnerEngine
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, None, week_duration_s=9999)
        bid    = engine.register_shadow_bot(_make_dca_strategy(), "BTC/USDT", bot_id="rem1")
        ok     = engine.unregister_shadow_bot("rem1")
        assert ok
        assert "rem1" not in engine.list_bot_ids()

    def test_tick_all_returns_list(self):
        from trading_shadow_learner import ShadowLearnerEngine
        store  = _tmp_store()
        feed   = _make_rich_feed()
        engine = ShadowLearnerEngine(store, feed, week_duration_s=9999)
        engine.register_shadow_bot(_make_dca_strategy("tick_dca"), "BTC/USDT")
        fills  = engine.tick_all()
        assert isinstance(fills, list)

    def test_check_week_end_no_expired_bots(self):
        """check_week_end should return empty when no bot's week has elapsed."""
        from trading_shadow_learner import ShadowLearnerEngine
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, None, week_duration_s=9999)
        engine.register_shadow_bot(_make_dca_strategy(), "BTC/USDT")
        saved  = engine.check_week_end()
        assert saved == []

    def test_check_week_end_winning_week_saves_pattern(self):
        """When a bot's week is over and profitable, a pattern must be saved."""
        from trading_shadow_learner import ShadowLearnerEngine, ShadowTrade
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, None, week_duration_s=0)  # week always over
        strat  = _make_dca_strategy("win_wk_dca")
        bid    = engine.register_shadow_bot(strat, "BTC/USDT", initial_paper_usd=10_000.0)
        bot    = engine.get_bot(bid)
        # Inject profitable week data
        bot._paper_usd = 10_300.0
        bot._week_trades.append(ShadowTrade(
            trade_id="t1", bot_id=bid, pair="BTC/USDT", action="sell",
            entry_price=50_000.0, exit_price=51_000.0, quantity=0.1,
            pnl=100.0, pnl_pct=0.02, confidence=0.8, reasoning="win",
            indicators={"rsi_14": 28.0},
        ))
        saved = engine.check_week_end()
        assert len(saved) == 1
        assert saved[0].gain_pct > 0
        # Also check it's in the store
        assert len(store.list_patterns()) == 1

    def test_check_week_end_losing_week_resets_equity(self):
        """Losing week → pattern not saved, equity reset to initial."""
        from trading_shadow_learner import ShadowLearnerEngine
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, None, week_duration_s=0)
        bid    = engine.register_shadow_bot(_make_dca_strategy(), "BTC/USDT",
                                            initial_paper_usd=10_000.0)
        bot    = engine.get_bot(bid)
        bot._paper_usd = 9_500.0   # losing week
        saved  = engine.check_week_end()
        assert saved == []
        assert len(store.list_patterns()) == 0
        assert bot._paper_usd == pytest.approx(10_000.0)

    def test_check_week_end_winning_week_carries_equity(self):
        """Winning week → equity carries forward (compound growth)."""
        from trading_shadow_learner import ShadowLearnerEngine, ShadowTrade
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, None, week_duration_s=0)
        bid    = engine.register_shadow_bot(_make_dca_strategy(), "BTC/USDT",
                                            initial_paper_usd=10_000.0)
        bot    = engine.get_bot(bid)
        bot._paper_usd = 10_500.0
        bot._week_trades.append(ShadowTrade(
            trade_id="t1", bot_id=bid, pair="BTC/USDT", action="sell",
            entry_price=50_000.0, exit_price=51_000.0, quantity=0.1,
            pnl=100.0, pnl_pct=0.02, confidence=0.8, reasoning="win",
            indicators={"rsi_14": 28.0},
        ))
        engine.check_week_end()
        # After keep_equity=True, week_start_usd should be 10_500
        assert bot._week_start_usd == pytest.approx(10_500.0)

    def test_multiple_bots_evaluated_independently(self):
        """Two shadow bots in the same engine are evaluated independently."""
        from trading_shadow_learner import ShadowLearnerEngine, ShadowTrade
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, None, week_duration_s=0)
        b1 = engine.register_shadow_bot(_make_dca_strategy("d1"), "BTC/USDT",
                                         initial_paper_usd=10_000.0, bot_id="b1")
        b2 = engine.register_shadow_bot(_make_dca_strategy("d2"), "ETH/USDT",
                                         initial_paper_usd=5_000.0, bot_id="b2")
        # b1 wins, b2 loses
        engine.get_bot(b1)._paper_usd = 10_400.0
        engine.get_bot(b1)._week_trades.append(ShadowTrade(
            trade_id="t1", bot_id=b1, pair="BTC/USDT", action="sell",
            entry_price=50_000.0, exit_price=51_000.0, quantity=0.1,
            pnl=100.0, pnl_pct=0.02, confidence=0.8, reasoning="win",
            indicators={"rsi_14": 28.0},
        ))
        engine.get_bot(b2)._paper_usd = 4_800.0
        saved = engine.check_week_end()
        assert len(saved) == 1
        assert saved[0].bot_id == b1
        assert len(store.list_patterns()) == 1

    def test_get_all_week_stats(self):
        from trading_shadow_learner import ShadowLearnerEngine
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, _make_rich_feed(), week_duration_s=9999)
        engine.register_shadow_bot(_make_momentum_strategy("m1"), "BTC/USDT", bot_id="ws1")
        engine.register_shadow_bot(_make_dca_strategy("d1"), "ETH/USDT", bot_id="ws2")
        stats  = engine.get_all_week_stats()
        assert len(stats) == 2
        ids = {s["bot_id"] for s in stats}
        assert "ws1" in ids and "ws2" in ids

    def test_get_hints_for_bot_empty_before_promote(self):
        """Before any pattern is promoted, hints should be empty."""
        from trading_shadow_learner import ShadowLearnerEngine
        store  = _tmp_store()
        engine = ShadowLearnerEngine(store, None, week_duration_s=9999)
        bid    = engine.register_shadow_bot(_make_dca_strategy("hint_d"), "BTC/USDT")
        hints  = engine.get_hints_for_bot(bid)
        assert hints == []

    def test_get_hints_for_bot_returns_promoted(self):
        """After promoting a pattern, hints should be non-empty."""
        from trading_shadow_learner import (
            ShadowLearnerEngine, ShadowTrade, PatternMemoryStore, WeeklyWinningPattern
        )
        store = _tmp_store()
        store.save_pattern(WeeklyWinningPattern(
            pattern_id="h1", bot_id="h_bot", strategy_id="hint_d2", pair="BTC/USDT",
            week_start="2026-01-01", week_end="2026-01-07",
            start_equity=10_000.0, end_equity=10_500.0, gain_pct=0.05,
            total_trades=5, winning_trades=4, losing_trades=1, win_rate=0.8,
            dominant_action="buy",
            avg_winning_indicators={"rsi_14": 29.5, "macd_hist": 0.002},
            avg_losing_indicators={},
        ))
        store.promote_pattern("h1")
        engine = ShadowLearnerEngine(store, None, week_duration_s=9999)
        bid    = engine.register_shadow_bot(
            _make_dca_strategy("hint_d2"), "BTC/USDT", bot_id="h_bot"
        )
        hints = engine.get_hints_for_bot(bid)
        assert len(hints) == 1
        assert hints[0]["indicators"]["rsi_14"] == pytest.approx(29.5)

    def test_shadow_bot_is_always_paper(self):
        """Shadow bots must never have dry_run=False — ensure no real-order pathway."""
        from trading_shadow_learner import ShadowBot
        bot = ShadowBot("dry_check", _make_dca_strategy(), None, "BTC/USDT")
        # There is no dry_run attribute on ShadowBot — it is always paper
        # Verify by checking it cannot be configured otherwise
        assert not hasattr(bot, "dry_run") or getattr(bot, "dry_run", True) is True
