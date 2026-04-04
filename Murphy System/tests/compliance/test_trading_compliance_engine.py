# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for src/trading_compliance_engine.py

All tests are mock-based — no real API keys or external dependencies required.
"""
from __future__ import annotations

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

# Make sure src/ is on the path
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from trading_compliance_engine import (
    ComplianceCheck,
    ComplianceEngine,
    ComplianceReport,
    ComplianceStatus,
    CheckSeverity,
    DailyPaperResult,
    Jurisdiction,
    PaperTradingGraduationTracker,
    get_compliance_engine,
    get_graduation_tracker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_pass_kwargs() -> dict:
    """Keyword arguments that satisfy ALL compliance checks (requires env vars)."""
    return dict(
        jurisdiction="personal",
        kyc_acknowledged=True,
        regulations_acknowledged=True,
        paper_trading_days=10,
        paper_trading_profitable_days=8,
        paper_trading_win_rate=0.8,
        paper_trading_total_return_pct=5.0,
        override_paper_graduation=False,
    )


# ---------------------------------------------------------------------------
# ComplianceStatus + CheckSeverity enums
# ---------------------------------------------------------------------------

class TestComplianceEnums(unittest.TestCase):

    def test_status_values(self):
        self.assertEqual(ComplianceStatus.PASS.value, "pass")
        self.assertEqual(ComplianceStatus.FAIL.value, "fail")
        self.assertEqual(ComplianceStatus.PENDING.value, "pending")

    def test_severity_values(self):
        self.assertEqual(CheckSeverity.BLOCKER.value, "blocker")
        self.assertEqual(CheckSeverity.WARNING.value, "warning")
        self.assertEqual(CheckSeverity.INFO.value, "info")

    def test_jurisdiction_personal(self):
        self.assertEqual(Jurisdiction.PERSONAL.value, "personal")

    def test_all_jurisdictions_present(self):
        vals = {j.value for j in Jurisdiction}
        for expected in ("us", "eu", "uk", "au", "ca", "sg", "other", "personal"):
            self.assertIn(expected, vals)


# ---------------------------------------------------------------------------
# ComplianceCheck dataclass
# ---------------------------------------------------------------------------

class TestComplianceCheck(unittest.TestCase):

    def test_basic_creation(self):
        c = ComplianceCheck(
            check_id="test_check",
            name="Test",
            description="A test check",
            severity=CheckSeverity.BLOCKER,
            status=ComplianceStatus.PASS,
        )
        self.assertEqual(c.check_id, "test_check")
        self.assertEqual(c.status, ComplianceStatus.PASS)
        self.assertEqual(c.severity, CheckSeverity.BLOCKER)


# ---------------------------------------------------------------------------
# ComplianceReport dataclass
# ---------------------------------------------------------------------------

class TestComplianceReport(unittest.TestCase):

    def _make_report(self) -> ComplianceReport:
        checks = [
            ComplianceCheck("c1", "C1", "desc", CheckSeverity.BLOCKER, ComplianceStatus.FAIL),
            ComplianceCheck("c2", "C2", "desc", CheckSeverity.WARNING, ComplianceStatus.FAIL),
            ComplianceCheck("c3", "C3", "desc", CheckSeverity.INFO, ComplianceStatus.PASS),
        ]
        return ComplianceReport(
            report_id="rpt1",
            evaluated_at="2026-01-01T00:00:00+00:00",
            overall=ComplianceStatus.FAIL,
            checks=checks,
        )

    def test_blockers(self):
        r = self._make_report()
        self.assertEqual(len(r.blockers()), 1)
        self.assertEqual(r.blockers()[0].check_id, "c1")

    def test_warnings(self):
        r = self._make_report()
        self.assertEqual(len(r.warnings()), 1)

    def test_to_dict_keys(self):
        d = self._make_report().to_dict()
        for key in ("report_id", "evaluated_at", "overall", "live_mode_allowed", "checks", "summary"):
            self.assertIn(key, d)

    def test_to_dict_summary_counts(self):
        d = self._make_report().to_dict()
        self.assertEqual(d["summary"]["total"], 3)
        self.assertEqual(d["summary"]["failed_blockers"], 1)
        self.assertEqual(d["summary"]["failed_warnings"], 1)
        self.assertEqual(d["summary"]["passed"], 1)


# ---------------------------------------------------------------------------
# ComplianceEngine — individual check methods
# ---------------------------------------------------------------------------

class TestComplianceEngineChecks(unittest.TestCase):

    def setUp(self):
        self.engine = ComplianceEngine()

    def test_evaluate_returns_report(self):
        r = self.engine.evaluate()
        self.assertIsInstance(r, ComplianceReport)

    def test_evaluate_fails_without_env_vars(self):
        """Default env has no COINBASE keys → should fail."""
        with patch.dict(os.environ, {}, clear=True):
            r = self.engine.evaluate(jurisdiction="personal",
                                      kyc_acknowledged=True,
                                      regulations_acknowledged=True,
                                      paper_trading_days=10,
                                      paper_trading_profitable_days=8,
                                      paper_trading_win_rate=0.8,
                                      paper_trading_total_return_pct=5.0)
        self.assertEqual(r.overall, ComplianceStatus.FAIL)
        self.assertFalse(r.live_mode_allowed)

    def test_evaluate_passes_with_all_env_vars(self):
        env = {
            "COINBASE_API_KEY": "test_key",
            "COINBASE_API_SECRET": "test_secret",
            "COINBASE_LIVE_MODE": "true",
        }
        with patch.dict(os.environ, env):
            r = self.engine.evaluate(**_minimal_pass_kwargs())
        self.assertEqual(r.overall, ComplianceStatus.PASS)
        self.assertTrue(r.live_mode_allowed)

    def test_live_mode_flag_check_fails_when_not_set(self):
        with patch.dict(os.environ, {"COINBASE_LIVE_MODE": "false"}):
            checks = self.engine._check_live_mode_flag()
        self.assertEqual(checks.status, ComplianceStatus.FAIL)
        self.assertEqual(checks.severity, CheckSeverity.BLOCKER)

    def test_live_mode_flag_check_passes_when_set(self):
        with patch.dict(os.environ, {"COINBASE_LIVE_MODE": "true"}):
            checks = self.engine._check_live_mode_flag()
        self.assertEqual(checks.status, ComplianceStatus.PASS)

    def test_jurisdiction_check_fails_for_empty(self):
        check = self.engine._check_jurisdiction("")
        self.assertEqual(check.status, ComplianceStatus.FAIL)

    def test_jurisdiction_check_passes_for_personal(self):
        check = self.engine._check_jurisdiction("personal")
        self.assertEqual(check.status, ComplianceStatus.PASS)

    def test_jurisdiction_check_passes_for_us(self):
        check = self.engine._check_jurisdiction("us")
        self.assertEqual(check.status, ComplianceStatus.PASS)

    def test_regulations_check_fails_when_not_acknowledged(self):
        check = self.engine._check_regulations_acknowledged(False)
        self.assertEqual(check.status, ComplianceStatus.FAIL)
        self.assertEqual(check.severity, CheckSeverity.BLOCKER)

    def test_regulations_check_passes_when_acknowledged(self):
        check = self.engine._check_regulations_acknowledged(True)
        self.assertEqual(check.status, ComplianceStatus.PASS)

    def test_kyc_check_fails_when_not_acknowledged(self):
        check = self.engine._check_kyc_acknowledged(False)
        self.assertEqual(check.status, ComplianceStatus.FAIL)

    def test_kyc_check_passes_when_acknowledged(self):
        check = self.engine._check_kyc_acknowledged(True)
        self.assertEqual(check.status, ComplianceStatus.PASS)

    def test_paper_graduation_fails_insufficient_days(self):
        check = self.engine._check_paper_graduation(
            total_days=3, profitable_days=3, win_rate=1.0, total_return_pct=5.0
        )
        self.assertEqual(check.status, ComplianceStatus.FAIL)

    def test_paper_graduation_fails_insufficient_profitable_days(self):
        check = self.engine._check_paper_graduation(
            total_days=7, profitable_days=2, win_rate=0.3, total_return_pct=2.0
        )
        self.assertEqual(check.status, ComplianceStatus.FAIL)

    def test_paper_graduation_fails_insufficient_return(self):
        check = self.engine._check_paper_graduation(
            total_days=7, profitable_days=5, win_rate=0.71, total_return_pct=0.5
        )
        self.assertEqual(check.status, ComplianceStatus.FAIL)

    def test_paper_graduation_passes_at_threshold(self):
        check = self.engine._check_paper_graduation(
            total_days=7, profitable_days=5, win_rate=0.71, total_return_pct=1.0
        )
        self.assertEqual(check.status, ComplianceStatus.PASS)

    def test_paper_graduation_override_bypasses_check(self):
        check = self.engine._check_paper_graduation(
            total_days=0, profitable_days=0, win_rate=0.0, total_return_pct=0.0,
            override=True,
        )
        self.assertEqual(check.status, ComplianceStatus.PASS)

    def test_personal_use_notice_always_passes(self):
        check = self.engine._check_personal_use_notice()
        self.assertEqual(check.status, ComplianceStatus.PASS)
        self.assertEqual(check.severity, CheckSeverity.INFO)

    def test_last_report_stored_after_evaluate(self):
        self.engine.evaluate()
        self.assertIsNotNone(self.engine.last_report())

    def test_is_live_trading_allowed_false_before_evaluate(self):
        fresh_engine = ComplianceEngine()
        self.assertFalse(fresh_engine.is_live_trading_allowed())

    def test_is_live_trading_allowed_false_when_failing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.engine.evaluate()
        self.assertFalse(self.engine.is_live_trading_allowed())


# ---------------------------------------------------------------------------
# PaperTradingGraduationTracker
# ---------------------------------------------------------------------------

class TestPaperTradingGraduationTracker(unittest.TestCase):

    def _tracker(self) -> PaperTradingGraduationTracker:
        tmp = tempfile.mktemp(suffix=".json")
        return PaperTradingGraduationTracker(storage_path=tmp)

    def test_record_day_creates_result(self):
        t = self._tracker()
        r = t.record_day("2026-01-01", start_equity=10000, end_equity=10200, trades=5)
        self.assertIsInstance(r, DailyPaperResult)
        self.assertTrue(r.profitable)

    def test_record_day_unprofitable(self):
        t = self._tracker()
        r = t.record_day("2026-01-02", start_equity=10000, end_equity=9800)
        self.assertFalse(r.profitable)

    def test_summary_empty(self):
        t = self._tracker()
        s = t.summary()
        self.assertEqual(s["total_days"], 0)
        self.assertEqual(s["win_rate"], 0.0)

    def test_summary_after_records(self):
        t = self._tracker()
        t.record_day("2026-01-01", 10000, 10200)
        t.record_day("2026-01-02", 10200, 10300)
        t.record_day("2026-01-03", 10300, 10250)
        s = t.summary()
        self.assertEqual(s["total_days"], 3)
        self.assertEqual(s["profitable_days"], 2)
        self.assertAlmostEqual(s["win_rate"], 2 / 3, places=4)

    def test_total_return_calculated_correctly(self):
        t = self._tracker()
        t.record_day("2026-01-01", 10000, 11000)  # +10%
        s = t.summary()
        self.assertAlmostEqual(s["total_return_pct"], 10.0, places=2)

    def test_overwrite_same_date(self):
        t = self._tracker()
        t.record_day("2026-01-01", 10000, 10100)
        t.record_day("2026-01-01", 10000, 9900)  # overwrite same date
        results = t.all_results()
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].profitable)

    def test_meets_graduation_threshold_false_by_default(self):
        t = self._tracker()
        self.assertFalse(t.meets_graduation_threshold())

    def test_meets_graduation_threshold_true_when_criteria_met(self):
        t = self._tracker()
        for i in range(7):
            t.record_day(f"2026-01-{i+1:02d}", 10000 + i * 200, 10200 + i * 200)
        # All 7 profitable, return ~+14%
        self.assertTrue(t.meets_graduation_threshold())

    def test_persistence_round_trip(self):
        tmp = tempfile.mktemp(suffix=".json")
        t1 = PaperTradingGraduationTracker(storage_path=tmp)
        t1.record_day("2026-01-01", 10000, 10500)
        # Reload from same file
        t2 = PaperTradingGraduationTracker(storage_path=tmp)
        self.assertEqual(t2.summary()["total_days"], 1)
        self.assertAlmostEqual(t2.summary()["total_return_pct"], 5.0, places=2)

    def test_all_results_returns_list(self):
        t = self._tracker()
        self.assertIsInstance(t.all_results(), list)


# ---------------------------------------------------------------------------
# Singleton factories
# ---------------------------------------------------------------------------

class TestSingletons(unittest.TestCase):

    def test_get_compliance_engine_returns_engine(self):
        engine = get_compliance_engine()
        self.assertIsInstance(engine, ComplianceEngine)

    def test_get_compliance_engine_same_instance(self):
        e1 = get_compliance_engine()
        e2 = get_compliance_engine()
        self.assertIs(e1, e2)

    def test_get_graduation_tracker_returns_tracker(self):
        tmp = tempfile.mktemp(suffix=".json")
        t = get_graduation_tracker(storage_path=tmp)
        self.assertIsInstance(t, PaperTradingGraduationTracker)


# ---------------------------------------------------------------------------
# DailyPaperResult dataclass
# ---------------------------------------------------------------------------

class TestDailyPaperResult(unittest.TestCase):

    def test_profitable_auto_set(self):
        r = DailyPaperResult(date="2026-01-01", start_equity=10000, end_equity=10100, trades=3)
        self.assertTrue(r.profitable)

    def test_not_profitable_auto_set(self):
        r = DailyPaperResult(date="2026-01-01", start_equity=10000, end_equity=9999, trades=1)
        self.assertFalse(r.profitable)

    def test_break_even_not_profitable(self):
        r = DailyPaperResult(date="2026-01-01", start_equity=10000, end_equity=10000, trades=0)
        self.assertFalse(r.profitable)


if __name__ == "__main__":
    unittest.main()
