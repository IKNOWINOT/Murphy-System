"""
Comprehensive tests for OutreachComplianceGovernor
(murphy_system/src/self_selling_engine/_compliance.py).

Covers:
  - 30-day cooldown enforcement for non-customers
  - Customer exemption from 30-day cooldown
  - Permanent opt-out suppression across all channels
  - Opt-out keyword detection in prospect replies
  - Per-channel daily rate limiting (email, sms, linkedin)
  - record_contact() cooldown tracking
  - is_customer() and mark_as_customer() behaviour
  - clear_opt_out() human-override path (with audit trail)
  - detect_opt_out_in_reply() regex coverage
  - ComplianceDecision.to_dict() shape
  - ContactRecord dataclass defaults
  - Thread-safety: concurrent check_contact_allowed + record_contact
  - Audit log is populated for every decision (allow and block)
  - Input validation (bad prospect_id, bad channel)
  - Integration: MurphySelfSellingEngine respects compliance governor

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
import os
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from self_selling_engine._compliance import (
    ComplianceDecision,
    ContactRecord,
    DecisionStatus,
    OutreachComplianceGovernor,
    _DEFAULT_DAILY_LIMITS,
    _COOLDOWN_DAYS_NON_CUSTOMER,
)
from self_selling_engine._engine import MurphySelfSellingEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_governor(**kwargs) -> OutreachComplianceGovernor:
    """Return a fresh governor with optional constructor overrides."""
    return OutreachComplianceGovernor(**kwargs)


def _past_iso(days: int) -> str:
    """Return an ISO-8601 UTC string *days* in the past."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# ContactRecord dataclass
# ---------------------------------------------------------------------------

class TestContactRecord(unittest.TestCase):

    def test_defaults(self):
        r = ContactRecord(prospect_id="p1", channel="email")
        self.assertEqual(r.prospect_id, "p1")
        self.assertEqual(r.channel, "email")
        self.assertIsNone(r.last_contacted_at)
        self.assertFalse(r.opt_out_status)
        self.assertIsNone(r.opt_out_reason)
        self.assertIsNone(r.opt_out_at)
        self.assertFalse(r.is_customer)
        self.assertEqual(r.contact_count, 0)
        self.assertIsNone(r.suppression_expires_at)


# ---------------------------------------------------------------------------
# ComplianceDecision dataclass
# ---------------------------------------------------------------------------

class TestComplianceDecision(unittest.TestCase):

    def test_to_dict_contains_required_keys(self):
        d = ComplianceDecision(
            allowed=True,
            status=DecisionStatus.ALLOWED.value,
            reason="ok",
            prospect_id="p1",
            channel="email",
        )
        result = d.to_dict()
        for key in ("allowed", "status", "reason", "prospect_id", "channel",
                    "cooldown_remaining_days", "checked_at"):
            self.assertIn(key, result)

    def test_to_dict_allowed_true(self):
        d = ComplianceDecision(
            allowed=True,
            status=DecisionStatus.ALLOWED.value,
            reason="ok",
            prospect_id="p1",
            channel="sms",
        )
        self.assertTrue(d.to_dict()["allowed"])

    def test_to_dict_allowed_false(self):
        d = ComplianceDecision(
            allowed=False,
            status=DecisionStatus.BLOCKED_OPT_OUT.value,
            reason="opted out",
            prospect_id="p2",
            channel="linkedin",
        )
        self.assertFalse(d.to_dict()["allowed"])


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation(unittest.TestCase):

    def setUp(self):
        self.gov = _make_governor()

    def test_invalid_prospect_id_raises(self):
        with self.assertRaises(ValueError):
            self.gov.check_contact_allowed("", "email")

    def test_invalid_prospect_id_special_chars_raises(self):
        with self.assertRaises(ValueError):
            self.gov.check_contact_allowed("p1; DROP TABLE", "email")

    def test_invalid_channel_raises(self):
        with self.assertRaises(ValueError):
            self.gov.check_contact_allowed("p1", "fax")

    def test_valid_channels_accepted(self):
        for ch in ("email", "sms", "linkedin"):
            d = self.gov.check_contact_allowed("p1", ch)
            self.assertTrue(d.allowed, f"Expected allowed for channel {ch}")

    def test_record_contact_invalid_channel_raises(self):
        with self.assertRaises(ValueError):
            self.gov.record_contact("p1", "carrier_pigeon")

    def test_record_opt_out_invalid_prospect_raises(self):
        with self.assertRaises(ValueError):
            self.gov.record_opt_out("!!bad!!", "test", "system")


# ---------------------------------------------------------------------------
# Opt-out suppression
# ---------------------------------------------------------------------------

class TestOptOutSuppression(unittest.TestCase):

    def setUp(self):
        self.gov = _make_governor()

    def test_opt_out_blocks_all_channels(self):
        self.gov.record_opt_out("p1", "unsubscribe request", "prospect_reply")
        for ch in ("email", "sms", "linkedin"):
            d = self.gov.check_contact_allowed("p1", ch)
            self.assertFalse(d.allowed, f"Should be blocked on {ch} after opt-out")
            self.assertEqual(d.status, DecisionStatus.BLOCKED_OPT_OUT.value)

    def test_opt_out_is_permanent_without_clear(self):
        self.gov.record_opt_out("p1", "stop", "prospect_reply")
        # Even after a long time, still blocked
        d = self.gov.check_contact_allowed("p1", "email")
        self.assertFalse(d.allowed)

    def test_clear_opt_out_re_enables_contact(self):
        self.gov.record_opt_out("p1", "stop", "prospect_reply")
        self.gov.clear_opt_out("p1", cleared_by="admin", audit_reason="re-optin confirmed")
        d = self.gov.check_contact_allowed("p1", "email")
        self.assertTrue(d.allowed)

    def test_clear_opt_out_creates_audit_entry(self):
        self.gov.record_opt_out("p1", "stop", "prospect_reply")
        self.gov.clear_opt_out("p1", cleared_by="admin", audit_reason="re-optin confirmed")
        log = self.gov.get_audit_log()
        clear_events = [e for e in log if e.get("event") == "OPT_OUT_CLEARED"]
        self.assertEqual(len(clear_events), 1)
        self.assertEqual(clear_events[0]["cleared_by"], "admin")

    def test_opt_out_creates_audit_entry(self):
        self.gov.record_opt_out("p1", "unsubscribe", "prospect_reply")
        log = self.gov.get_audit_log()
        opt_events = [e for e in log if e.get("event") == "OPT_OUT_RECORDED"]
        self.assertEqual(len(opt_events), 1)

    def test_opt_out_reason_capped(self):
        long_reason = "x" * 10_000
        self.gov.record_opt_out("p1", long_reason, "system")
        # Should not raise; reason is stored capped
        log = self.gov.get_audit_log()
        opt_events = [e for e in log if e.get("event") == "OPT_OUT_RECORDED"]
        stored_reason = opt_events[0]["reason"]
        self.assertLessEqual(len(stored_reason), 500)


# ---------------------------------------------------------------------------
# Opt-out keyword detection
# ---------------------------------------------------------------------------

class TestOptOutKeywordDetection(unittest.TestCase):

    def setUp(self):
        self.gov = _make_governor()

    def test_unsubscribe_detected(self):
        self.assertTrue(self.gov.detect_opt_out_in_reply("Please unsubscribe me"))

    def test_stop_detected(self):
        self.assertTrue(self.gov.detect_opt_out_in_reply("stop"))

    def test_remove_me_detected(self):
        self.assertTrue(self.gov.detect_opt_out_in_reply("Remove me from your list"))

    def test_do_not_contact_detected(self):
        self.assertTrue(self.gov.detect_opt_out_in_reply("Do not contact me again"))

    def test_opt_out_detected(self):
        self.assertTrue(self.gov.detect_opt_out_in_reply("I want to opt out"))

    def test_positive_reply_not_detected(self):
        self.assertFalse(self.gov.detect_opt_out_in_reply("Yes, I'm interested!"))

    def test_empty_string_not_detected(self):
        self.assertFalse(self.gov.detect_opt_out_in_reply(""))

    def test_non_string_not_detected(self):
        self.assertFalse(self.gov.detect_opt_out_in_reply(None))  # type: ignore

    def test_oversized_input_does_not_crash(self):
        huge = "A" * 1_000_000
        # Should not raise; capped before regex evaluation
        result = self.gov.detect_opt_out_in_reply(huge)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# 30-day cooldown (non-customers)
# ---------------------------------------------------------------------------

class TestCooldownNonCustomer(unittest.TestCase):

    def setUp(self):
        self.gov = _make_governor()

    def test_first_contact_allowed(self):
        d = self.gov.check_contact_allowed("p1", "email")
        self.assertTrue(d.allowed)

    def test_same_day_blocked_after_record(self):
        self.gov.check_contact_allowed("p1", "email")
        self.gov.record_contact("p1", "email")
        # Now try again on the same day — still in cooldown
        d = self.gov.check_contact_allowed("p1", "email")
        self.assertFalse(d.allowed)
        self.assertEqual(d.status, DecisionStatus.BLOCKED_COOLDOWN.value)

    def test_cooldown_remaining_days_populated(self):
        self.gov.check_contact_allowed("p1", "email")
        self.gov.record_contact("p1", "email")
        d = self.gov.check_contact_allowed("p1", "email")
        self.assertGreater(d.cooldown_remaining_days, 0)

    def test_after_cooldown_expires_allowed(self):
        gov = _make_governor(cooldown_days_non_customer=1)
        gov.record_contact("p1", "email")
        # Manually set last_contacted_at to 2 days ago
        with gov._lock:
            gov._contacts["p1"]["email"].last_contacted_at = _past_iso(2)
        d = gov.check_contact_allowed("p1", "email")
        self.assertTrue(d.allowed)

    def test_different_channels_tracked_independently(self):
        self.gov.record_contact("p1", "email")
        # LinkedIn not yet contacted — should be allowed
        d = self.gov.check_contact_allowed("p1", "linkedin")
        self.assertTrue(d.allowed)

    def test_cooldown_thirty_days(self):
        gov = _make_governor()
        gov.record_contact("p1", "email")
        with gov._lock:
            gov._contacts["p1"]["email"].last_contacted_at = _past_iso(15)
        d = gov.check_contact_allowed("p1", "email")
        self.assertFalse(d.allowed)


# ---------------------------------------------------------------------------
# Customer exemption
# ---------------------------------------------------------------------------

class TestCustomerExemption(unittest.TestCase):

    def setUp(self):
        self.gov = _make_governor(cooldown_days_customer=7)

    def test_customer_not_subject_to_30_day_cooldown(self):
        self.gov.mark_as_customer("p1")
        self.gov.record_contact("p1", "email")
        # Pretend 10 days have passed — for non-customer this would still block
        with self.gov._lock:
            self.gov._contacts["p1"]["email"].last_contacted_at = _past_iso(10)
        d = self.gov.check_contact_allowed("p1", "email")
        # Customer cooldown is 7 days; 10 days have passed → should be allowed
        self.assertTrue(d.allowed)

    def test_customer_subject_to_shorter_cooldown(self):
        self.gov.mark_as_customer("p1")
        self.gov.record_contact("p1", "email")
        # Only 3 days have passed (less than 7-day customer cooldown)
        with self.gov._lock:
            self.gov._contacts["p1"]["email"].last_contacted_at = _past_iso(3)
        d = self.gov.check_contact_allowed("p1", "email")
        self.assertFalse(d.allowed)

    def test_customer_still_respects_opt_out(self):
        self.gov.mark_as_customer("p1")
        self.gov.record_opt_out("p1", "stop", "prospect_reply")
        d = self.gov.check_contact_allowed("p1", "email")
        self.assertFalse(d.allowed)
        self.assertEqual(d.status, DecisionStatus.BLOCKED_OPT_OUT.value)

    def test_is_customer_returns_true_after_mark(self):
        self.gov.mark_as_customer("p1")
        self.assertTrue(self.gov.is_customer("p1"))

    def test_is_customer_returns_false_for_unknown(self):
        self.assertFalse(self.gov.is_customer("unknown_prospect"))


# ---------------------------------------------------------------------------
# Daily rate limits
# ---------------------------------------------------------------------------

class TestDailyRateLimits(unittest.TestCase):

    def test_email_rate_limit_blocks_after_cap(self):
        gov = _make_governor(daily_limits={"email": 2})
        gov.record_contact("p1", "email")
        gov.record_contact("p2", "email")
        # Third attempt on a fresh prospect should be rate-limited
        d = gov.check_contact_allowed("p3", "email")
        self.assertFalse(d.allowed)
        self.assertEqual(d.status, DecisionStatus.BLOCKED_RATE.value)

    def test_sms_rate_limit_blocks_after_cap(self):
        gov = _make_governor(daily_limits={"sms": 1})
        gov.record_contact("p1", "sms")
        d = gov.check_contact_allowed("p2", "sms")
        self.assertFalse(d.allowed)
        self.assertEqual(d.status, DecisionStatus.BLOCKED_RATE.value)

    def test_linkedin_rate_limit_blocks_after_cap(self):
        gov = _make_governor(daily_limits={"linkedin": 1})
        gov.record_contact("p1", "linkedin")
        d = gov.check_contact_allowed("p2", "linkedin")
        self.assertFalse(d.allowed)
        self.assertEqual(d.status, DecisionStatus.BLOCKED_RATE.value)

    def test_rate_limit_per_channel_independent(self):
        gov = _make_governor(daily_limits={"email": 1, "sms": 10})
        gov.record_contact("p1", "email")
        # Email is at cap, but SMS is not
        d_email = gov.check_contact_allowed("p2", "email")
        d_sms = gov.check_contact_allowed("p2", "sms")
        self.assertFalse(d_email.allowed)
        self.assertTrue(d_sms.allowed)

    def test_get_daily_counts_returns_today(self):
        gov = _make_governor()
        gov.record_contact("p1", "email")
        gov.record_contact("p2", "email")
        counts = gov.get_daily_counts()
        today = list(counts["email"].values())[0]
        self.assertEqual(today, 2)

    def test_default_daily_limits_are_configurable(self):
        gov = _make_governor(daily_limits={"email": 100})
        self.assertEqual(gov._daily_limits["email"], 100)
        # SMS falls back to default
        self.assertEqual(gov._daily_limits["sms"], _DEFAULT_DAILY_LIMITS["sms"])

    def test_zero_limit_blocks_all(self):
        gov = _make_governor(daily_limits={"email": 0})
        d = gov.check_contact_allowed("p1", "email")
        self.assertFalse(d.allowed)
        self.assertEqual(d.status, DecisionStatus.BLOCKED_RATE.value)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAuditLog(unittest.TestCase):

    def setUp(self):
        self.gov = _make_governor()

    def test_allow_decision_appended(self):
        self.gov.check_contact_allowed("p1", "email")
        log = self.gov.get_audit_log()
        self.assertGreater(len(log), 0)
        self.assertEqual(log[-1]["status"], DecisionStatus.ALLOWED.value)

    def test_block_decision_appended(self):
        self.gov.record_opt_out("p1", "stop", "prospect_reply")
        self.gov.check_contact_allowed("p1", "email")
        log = self.gov.get_audit_log()
        block_entries = [e for e in log if e.get("status") == DecisionStatus.BLOCKED_OPT_OUT.value]
        self.assertGreater(len(block_entries), 0)

    def test_audit_log_is_copy(self):
        self.gov.check_contact_allowed("p1", "email")
        log1 = self.gov.get_audit_log()
        log1.clear()
        log2 = self.gov.get_audit_log()
        self.assertGreater(len(log2), 0)


# ---------------------------------------------------------------------------
# Thread-safety
# ---------------------------------------------------------------------------

class TestThreadSafety(unittest.TestCase):

    def test_concurrent_check_and_record(self):
        gov = _make_governor()
        errors = []

        def worker(pid: str):
            try:
                for ch in ("email", "sms", "linkedin"):
                    gov.check_contact_allowed(pid, ch)
                    gov.record_contact(pid, ch)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(f"p{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")

    def test_concurrent_opt_out_and_check(self):
        gov = _make_governor()
        results = []

        def opt_out_worker():
            gov.record_opt_out("px", "stop", "test")

        def check_worker():
            d = gov.check_contact_allowed("px", "email")
            results.append(d.allowed)

        threads = (
            [threading.Thread(target=opt_out_worker) for _ in range(5)]
            + [threading.Thread(target=check_worker) for _ in range(10)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all opt-outs run, the prospect must be blocked
        d = gov.check_contact_allowed("px", "email")
        self.assertFalse(d.allowed)


# ---------------------------------------------------------------------------
# Integration: MurphySelfSellingEngine respects compliance governor
# ---------------------------------------------------------------------------

class TestEngineComplianceIntegration(unittest.TestCase):
    """The self-selling engine must skip outreach for blocked prospects."""

    def _make_engine_with_single_prospect(self, prospect_id: str):
        """Return an engine that discovers exactly one prospect."""
        from self_selling_engine._engine import ProspectProfile

        profile = ProspectProfile(
            prospect_id=prospect_id,
            company_name="Test Co",
            contact_name="Alice",
            contact_email="alice@test.com",
            business_type="restaurant",
            industry="food",
            estimated_revenue="under_1m",
            tools_detected=[],
            pain_points_inferred=[],
            automation_constraints=[],
            constraint_alert_rules=[],
        )

        engine = MurphySelfSellingEngine()
        # Patch _discover_prospects to return our single profile
        engine._discover_prospects = lambda: [profile]
        return engine, profile

    def test_engine_skips_opted_out_prospect(self):
        engine, profile = self._make_engine_with_single_prospect("px123")
        # Mark the prospect as opted out before the cycle
        engine.compliance_governor.record_opt_out(
            "px123", "unsubscribe", "prospect_reply"
        )

        send_calls = []
        engine.outreach.send = lambda msg: send_calls.append(msg)

        result = engine.run_selling_cycle()

        self.assertEqual(result.outreach_sent, 0)
        self.assertEqual(len(send_calls), 0)
        self.assertEqual(engine.metrics.emails_sent, 0)

    def test_engine_sends_to_compliant_prospect(self):
        engine, profile = self._make_engine_with_single_prospect("py456")
        send_calls = []
        engine.outreach.send = lambda msg: send_calls.append(msg)

        result = engine.run_selling_cycle()

        self.assertEqual(result.outreach_sent, 1)
        self.assertEqual(len(send_calls), 1)
        self.assertEqual(engine.metrics.emails_sent, 1)

    def test_engine_records_contact_after_send(self):
        engine, profile = self._make_engine_with_single_prospect("pz789")
        engine.outreach.send = lambda msg: None

        engine.run_selling_cycle()

        # After the cycle, prospect should be in cooldown
        d = engine.compliance_governor.check_contact_allowed("pz789", "email")
        self.assertFalse(d.allowed)
        self.assertEqual(d.status, DecisionStatus.BLOCKED_COOLDOWN.value)

    def test_engine_skips_rate_limited_channel(self):
        # Set email cap to 0 — nothing should be sent
        gov = _make_governor(daily_limits={"email": 0})
        engine, profile = self._make_engine_with_single_prospect("pq000")
        engine.compliance_governor = gov

        send_calls = []
        engine.outreach.send = lambda msg: send_calls.append(msg)

        result = engine.run_selling_cycle()

        self.assertEqual(result.outreach_sent, 0)
        self.assertEqual(len(send_calls), 0)

    def test_compliance_governor_injected_via_constructor(self):
        gov = OutreachComplianceGovernor(daily_limits={"email": 100})
        engine = MurphySelfSellingEngine(compliance_governor=gov)
        self.assertIs(engine.compliance_governor, gov)

    def test_default_compliance_governor_created_when_not_injected(self):
        engine = MurphySelfSellingEngine()
        self.assertIsInstance(engine.compliance_governor, OutreachComplianceGovernor)


if __name__ == "__main__":
    unittest.main()
