"""
Tests for Profit Sweep — Murphy System

Covers:
- Profit calculation logic
- Sweep amount with cash reserve
- Dry-run mode (no execution)
- Minimum threshold
- Business day detection
- Error handling (negative profit, retry logic)
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from profit_sweep import (
    ProfitCalculator,
    ProfitSweep,
    SweepStatus,
    SweepError,
    is_business_day,
)


class TestProfitCalculator(unittest.TestCase):
    """Unit tests for ProfitCalculator."""

    def setUp(self):
        self.calc = ProfitCalculator()

    def test_basic_calculation(self):
        result = self.calc.calculate(
            portfolio_value  = 11_000,
            starting_capital = 10_000,
            open_positions   = 200,
            pending_orders   = 50,
            cash_reserve_pct = 20.0,
        )
        self.assertEqual(result["gross_profit"], 1_000.0)
        # reserved_cash = 1000 * 0.20 = 200
        self.assertEqual(result["reserved_cash"], 200.0)
        # sweepable = 1000 - 200 - 50 - 200 = 550
        self.assertEqual(result["sweepable_profit"], 550.0)

    def test_no_profit(self):
        """Zero gross profit → zero sweepable."""
        result = self.calc.calculate(
            portfolio_value  = 10_000,
            starting_capital = 10_000,
            open_positions   = 0,
            pending_orders   = 0,
        )
        self.assertEqual(result["gross_profit"], 0.0)
        self.assertEqual(result["sweepable_profit"], 0.0)

    def test_negative_profit_raises(self):
        """Negative gross profit must raise SweepError (safety halt)."""
        with self.assertRaises(SweepError):
            self.calc.calculate(
                portfolio_value  = 9_000,
                starting_capital = 10_000,
                open_positions   = 0,
                pending_orders   = 0,
            )

    def test_sweepable_never_negative(self):
        """Sweepable profit is clamped at 0 even if reserves exceed gross profit."""
        result = self.calc.calculate(
            portfolio_value  = 10_100,
            starting_capital = 10_000,
            open_positions   = 150,  # exceeds gross profit
            pending_orders   = 0,
            cash_reserve_pct = 20.0,
        )
        self.assertGreaterEqual(result["sweepable_profit"], 0.0)

    def test_zero_reserve(self):
        """With 0% cash reserve the full gross profit (minus reserved positions) is swept."""
        result = self.calc.calculate(
            portfolio_value  = 11_000,
            starting_capital = 10_000,
            open_positions   = 0,
            pending_orders   = 0,
            cash_reserve_pct = 0.0,
        )
        self.assertEqual(result["sweepable_profit"], 1_000.0)


class TestDryRunMode(unittest.TestCase):
    """Ensure dry-run mode never executes orders."""

    def test_default_is_dry_run(self):
        """ProfitSweep must default to dry-run."""
        sweeper = ProfitSweep(starting_capital=10_000)
        self.assertFalse(sweeper._enabled)

    def test_dry_run_returns_dry_run_status(self):
        sweeper = ProfitSweep(starting_capital=10_000, enabled=False)
        record  = sweeper.run_sweep(portfolio_value=11_000)
        self.assertEqual(record.status, SweepStatus.DRY_RUN)
        self.assertTrue(record.dry_run)
        self.assertEqual(record.atom_purchased, 0.0)

    def test_dry_run_does_not_call_coinbase(self):
        mock_coinbase = MagicMock()
        sweeper = ProfitSweep(
            coinbase_connector = mock_coinbase,
            starting_capital   = 10_000,
            enabled            = False,
        )
        sweeper.run_sweep(portfolio_value=12_000)
        mock_coinbase.place_market_order.assert_not_called()
        mock_coinbase.stake_asset.assert_not_called()

    def test_dry_run_logged_in_history(self):
        sweeper = ProfitSweep(starting_capital=10_000, enabled=False)
        sweeper.run_sweep(portfolio_value=11_000)
        history = sweeper.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "dry_run")


class TestMinimumThreshold(unittest.TestCase):
    """Sweeps below MIN_SWEEP_AMOUNT are skipped."""

    def test_below_minimum_is_skipped(self):
        sweeper = ProfitSweep(
            starting_capital  = 10_000,
            enabled           = False,
            min_sweep_amount  = 50.0,
        )
        # portfolio_value = 10_005 → gross = 5 < 50 threshold
        record = sweeper.run_sweep(portfolio_value=10_005)
        self.assertEqual(record.status, SweepStatus.SKIPPED)

    def test_exactly_at_minimum_sweeps(self):
        sweeper = ProfitSweep(
            starting_capital  = 10_000,
            enabled           = False,
            min_sweep_amount  = 10.0,
            cash_reserve_pct  = 0.0,
        )
        # gross = 10 == min_sweep_amount → should run (not skipped)
        record = sweeper.run_sweep(portfolio_value=10_010)
        self.assertNotEqual(record.status, SweepStatus.SKIPPED)

    def test_skipped_stats_counted(self):
        sweeper = ProfitSweep(
            starting_capital = 10_000,
            enabled          = False,
            min_sweep_amount = 100.0,
        )
        sweeper.run_sweep(portfolio_value=10_005)
        stats = sweeper.get_stats()
        self.assertEqual(stats["total_skipped"], 1)


class TestBusinessDayDetection(unittest.TestCase):
    """is_business_day() helper tests."""

    def test_monday_is_business_day(self):
        monday = datetime(2026, 3, 23, tzinfo=timezone.utc)  # March 23 2026 is a Monday
        self.assertTrue(is_business_day(monday))

    def test_friday_is_business_day(self):
        friday = datetime(2026, 3, 20, tzinfo=timezone.utc)  # March 20 2026 is a Friday
        self.assertTrue(is_business_day(friday))

    def test_saturday_is_not_business_day(self):
        saturday = datetime(2026, 3, 21, tzinfo=timezone.utc)
        self.assertFalse(is_business_day(saturday))

    def test_sunday_is_not_business_day(self):
        sunday = datetime(2026, 3, 22, tzinfo=timezone.utc)
        self.assertFalse(is_business_day(sunday))


class TestSweepStats(unittest.TestCase):
    """Statistics accumulate correctly."""

    def test_initial_stats_are_zero(self):
        sweeper = ProfitSweep(starting_capital=10_000)
        stats   = sweeper.get_stats()
        self.assertEqual(stats["total_sweeps_executed"],  0)
        self.assertEqual(stats["total_usd_swept"],        0.0)
        self.assertEqual(stats["total_atom_accumulated"], 0.0)

    def test_dry_run_count_increments(self):
        sweeper = ProfitSweep(starting_capital=10_000, enabled=False)
        sweeper.run_sweep(portfolio_value=12_000)
        sweeper.run_sweep(portfolio_value=12_000)
        stats = sweeper.get_stats()
        self.assertEqual(stats["total_dry_runs"], 2)


class TestSweepNextInfo(unittest.TestCase):
    """get_next_sweep_info returns usable data."""

    def test_returns_dict_with_required_keys(self):
        sweeper = ProfitSweep(starting_capital=10_000)
        info    = sweeper.get_next_sweep_info()
        # Should have at least sweep_enabled key
        self.assertIn("sweep_enabled", info)

    def test_atom_balance_update(self):
        sweeper = ProfitSweep(starting_capital=10_000)
        sweeper.update_atom_balance(staked=5.123, apy=14.5)
        stats = sweeper.get_stats()
        self.assertAlmostEqual(stats["current_atom_staked"], 5.123, places=3)
        self.assertAlmostEqual(stats["atom_staking_apy"],    14.5,  places=1)


class TestLiveSweepRetries(unittest.TestCase):
    """ATOM purchase retries with exponential back-off on failures."""

    @patch("profit_sweep.time.sleep", return_value=None)
    def test_all_retries_fail_returns_failed_record(self, _mock_sleep):
        mock_coinbase = MagicMock()
        mock_coinbase.place_market_order.side_effect = RuntimeError("exchange down")

        sweeper = ProfitSweep(
            coinbase_connector = mock_coinbase,
            starting_capital   = 10_000,
            enabled            = True,
            min_sweep_amount   = 10.0,
            cash_reserve_pct   = 0.0,
        )
        record = sweeper.run_sweep(portfolio_value=10_100)
        self.assertEqual(record.status, SweepStatus.FAILED)
        self.assertFalse(record.dry_run)
        # Should have attempted 3 times
        self.assertEqual(mock_coinbase.place_market_order.call_count, 3)


if __name__ == "__main__":
    unittest.main()
