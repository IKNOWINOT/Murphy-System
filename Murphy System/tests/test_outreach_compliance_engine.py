"""
Tests for Outreach Compliance Engine (SSE-COMPL-002).

Covers:
  - can_contact: 30-day cooldown, opt-out, DNC, daily cap, TCPA blocked hours
  - record_contact / record_opt_out / record_response (opt-out detection)
  - add_to_dnc / mark_as_customer / is_customer
  - check_regulatory_compliance: CAN-SPAM, TCPA, GDPR, CASL
  - get_compliance_report
  - Input validation guards
  - Thread-safety

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import os
import threading

import pytest


from self_selling_engine._outreach_compliance import (
    ComplianceDecision,
    ContactRecord,
    OutreachComplianceEngine,
    OutreachCompliancePolicy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return OutreachComplianceEngine()


@pytest.fixture
def engine_low_cap():
    """Engine with daily cap of 1 per channel for rate-limit testing."""
    policy = OutreachCompliancePolicy(
        max_contacts_per_day={"email": 1, "sms": 1, "phone": 1, "linkedin": 1, "push": 1},
        min_days_between_contacts=30,
    )
    return OutreachComplianceEngine(policy=policy)


# ---------------------------------------------------------------------------
# OutreachCompliancePolicy
# ---------------------------------------------------------------------------

class TestOutreachCompliancePolicy:
    def test_defaults(self):
        p = OutreachCompliancePolicy()
        assert p.min_days_between_contacts == 30
        assert p.honor_opt_out is True
        assert p.customer_recontact_allowed is True

    def test_to_dict_keys(self):
        p = OutreachCompliancePolicy()
        d = p.to_dict()
        assert "min_days_between_contacts" in d
        assert "honor_opt_out" in d
        assert "required_opt_out_language" in d


# ---------------------------------------------------------------------------
# can_contact — basic allow
# ---------------------------------------------------------------------------

class TestCanContactAllow:
    def test_fresh_prospect_allowed(self, engine):
        allowed, reason = engine.can_contact("prospect-001", "email")
        assert allowed is True
        assert reason == "allowed"

    def test_sms_allowed_when_no_history(self, engine):
        """SMS is subject to TCPA blocked hours (0-8 and 21-24 UTC).
        We test both that the prospect is not blocked for non-time reasons,
        and that time-restriction is the only thing that could block them.
        """
        allowed, reason = engine.can_contact("prospect-002", "sms")
        # Either allowed (daytime) or only blocked by TCPA hours
        if not allowed:
            assert reason == "tcpa_blocked_hours", \
                f"Expected TCPA hours block or allow, got: {reason}"

    def test_linkedin_allowed(self, engine):
        allowed, _ = engine.can_contact("prospect-003", "linkedin")
        assert allowed is True


# ---------------------------------------------------------------------------
# can_contact — cooldown
# ---------------------------------------------------------------------------

class TestCooldown:
    def test_blocked_immediately_after_contact(self, engine):
        engine.record_contact("cooldown-001", "email", "msg1")
        allowed, reason = engine.can_contact("cooldown-001", "email")
        assert allowed is False
        assert "cooldown" in reason

    def test_customer_uses_shorter_cooldown(self, engine):
        engine.mark_as_customer("customer-001")
        engine.record_contact("customer-001", "email")
        allowed, reason = engine.can_contact("customer-001", "email")
        assert allowed is False
        assert "cooldown" in reason


# ---------------------------------------------------------------------------
# can_contact — opt-out suppression
# ---------------------------------------------------------------------------

class TestOptOut:
    def test_blocked_after_opt_out(self, engine):
        engine.record_opt_out("opt-001", "requested via reply")
        allowed, reason = engine.can_contact("opt-001", "email")
        assert allowed is False
        assert reason == "opt_out_suppressed"

    def test_opt_out_all_channels(self, engine):
        engine.record_opt_out("opt-002")
        for ch in ("email", "sms", "phone", "linkedin"):
            allowed, _ = engine.can_contact("opt-002", ch)
            assert allowed is False


# ---------------------------------------------------------------------------
# can_contact — DNC
# ---------------------------------------------------------------------------

class TestDNC:
    def test_blocked_after_dnc_add(self, engine):
        engine.add_to_dnc("dnc-001")
        allowed, reason = engine.can_contact("dnc-001", "phone")
        assert allowed is False
        assert reason == "dnc_registry"

    def test_dnc_capacity_exceeded(self):
        from self_selling_engine._outreach_compliance import _MAX_DNC
        e = OutreachComplianceEngine()
        for i in range(_MAX_DNC):
            e.add_to_dnc(f"prospect-{i:07d}")
        with pytest.raises(ValueError):
            e.add_to_dnc("overflow-prospect")


# ---------------------------------------------------------------------------
# can_contact — daily rate cap
# ---------------------------------------------------------------------------

class TestDailyCap:
    def test_blocked_at_cap(self, engine_low_cap):
        engine_low_cap.record_contact("cap-001", "email")
        # First call is allowed, second should be blocked by rate limit
        # (different prospect so cooldown doesn't apply)
        allowed, reason = engine_low_cap.can_contact("cap-002", "email")
        assert allowed is False
        assert "daily_cap" in reason


# ---------------------------------------------------------------------------
# record_response — opt-out detection
# ---------------------------------------------------------------------------

class TestRecordResponse:
    @pytest.mark.parametrize("reply", [
        "unsubscribe",
        "STOP",
        "Remove me from your list",
        "Do not contact me",
        "opt out please",
        "not interested, stop emailing",
        "take me off this list",
    ])
    def test_detects_opt_out_keywords(self, engine, reply):
        detected = engine.record_response("reply-001", reply)
        assert detected is True

    def test_normal_reply_not_detected(self, engine):
        detected = engine.record_response("reply-002", "Thanks for reaching out!")
        assert detected is False

    def test_auto_suppresses_on_opt_out(self, engine):
        engine.record_response("reply-003", "unsubscribe please")
        allowed, reason = engine.can_contact("reply-003", "email")
        assert allowed is False

    def test_capped_reply_text(self, engine):
        # Should not raise even with very long text
        long_reply = "stop " * 20_000
        engine.record_response("reply-004", long_reply)


# ---------------------------------------------------------------------------
# Customer exceptions
# ---------------------------------------------------------------------------

class TestCustomerExceptions:
    def test_is_customer_false_by_default(self, engine):
        assert engine.is_customer("not-a-customer") is False

    def test_mark_as_customer(self, engine):
        engine.mark_as_customer("cust-001")
        assert engine.is_customer("cust-001") is True


# ---------------------------------------------------------------------------
# Regulatory compliance
# ---------------------------------------------------------------------------

class TestRegulatoryCompliance:
    def test_email_us_has_can_spam(self, engine):
        regs = engine.check_regulatory_compliance("email", "US")
        assert "CAN-SPAM" in regs

    def test_email_eu_has_gdpr(self, engine):
        regs = engine.check_regulatory_compliance("email", "DE")
        assert "GDPR" in regs

    def test_email_canada_has_casl(self, engine):
        regs = engine.check_regulatory_compliance("email", "CA")
        assert "CASL" in regs

    def test_phone_has_tcpa(self, engine):
        regs = engine.check_regulatory_compliance("phone", "US")
        assert "TCPA" in regs

    def test_phone_has_dnc(self, engine):
        regs = engine.check_regulatory_compliance("phone", "US")
        assert "DNC_REGISTRY" in regs

    def test_sms_has_tcpa(self, engine):
        regs = engine.check_regulatory_compliance("sms", "US")
        assert "TCPA" in regs


# ---------------------------------------------------------------------------
# Compliance report
# ---------------------------------------------------------------------------

class TestComplianceReport:
    def test_report_keys(self, engine):
        report = engine.get_compliance_report()
        assert "total_prospects_contacted" in report
        assert "opt_out_count" in report
        assert "violations_prevented" in report
        assert "policy" in report

    def test_violations_counted(self, engine):
        # Trigger a few violations
        engine.record_opt_out("viol-001")
        engine.can_contact("viol-001", "email")
        engine.can_contact("viol-001", "sms")
        report = engine.get_compliance_report()
        assert report["violations_prevented"] >= 2

    def test_opt_out_count_increments(self, engine):
        engine.record_opt_out("count-001")
        engine.record_opt_out("count-002")
        report = engine.get_compliance_report()
        assert report["opt_out_count"] == 2


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_invalid_prospect_id_raises(self, engine):
        with pytest.raises(ValueError):
            engine.can_contact("bad prospect id with spaces!", "email")

    def test_invalid_channel_raises(self, engine):
        with pytest.raises(ValueError):
            engine.can_contact("valid-id", "fax")

    def test_empty_prospect_id_raises(self, engine):
        with pytest.raises(ValueError):
            engine.can_contact("", "email")


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_can_contact(self, engine):
        errors = []

        def check():
            try:
                engine.can_contact("ts-prospect", "email")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_opt_out(self, engine):
        errors = []

        def opt_out(i):
            try:
                engine.record_opt_out(f"ts-prospect-{i:05d}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=opt_out, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
