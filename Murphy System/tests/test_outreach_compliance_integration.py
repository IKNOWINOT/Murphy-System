"""Tests for outreach_compliance_integration.py (COMPL-002)."""

from __future__ import annotations

import sys
import os
import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from outreach_compliance_integration import (
    AuditRecord,
    BlockReason,
    OutreachComplianceGate,
    OutreachDecision,
    OutreachDecisionType,
    get_default_gate,
    _StubGovernor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_governor(**overrides) -> MagicMock:
    """Return a MagicMock governor that allows everything by default."""
    gov = MagicMock()
    gov.is_dnc.return_value = overrides.get("is_dnc", False)
    gov.is_in_cooldown.return_value = overrides.get("is_in_cooldown", False)
    gov.cooldown_remaining_seconds.return_value = overrides.get("cooldown_remaining_seconds", 0)
    gov.check_regulatory.return_value = overrides.get(
        "check_regulatory", {"allowed": True, "regulation": "", "reason": ""}
    )
    gov.record_contact.return_value = None
    gov.add_to_dnc.return_value = None
    gov.last_contacted_at.return_value = overrides.get("last_contacted_at", None)
    gov.consent_status.return_value = overrides.get("consent_status", "unknown")
    return gov


def _make_gate(governor: Any = None) -> OutreachComplianceGate:
    gov = governor if governor is not None else _make_governor()
    return OutreachComplianceGate(governor=gov)


# ---------------------------------------------------------------------------
# Tests: OutreachDecision
# ---------------------------------------------------------------------------

class TestOutreachDecision(unittest.TestCase):

    def test_allowed_property_true_for_allow(self):
        d = OutreachDecision(
            decision=OutreachDecisionType.ALLOW,
            contact_id="c1",
            contact_email="a@b.com",
            channel="email",
            outreach_type="cold",
        )
        self.assertTrue(d.allowed)

    def test_allowed_property_false_for_block(self):
        d = OutreachDecision(
            decision=OutreachDecisionType.BLOCK,
            contact_id="c1",
            contact_email="a@b.com",
            channel="email",
            outreach_type="cold",
            block_reason=BlockReason.DNC,
        )
        self.assertFalse(d.allowed)

    def test_to_dict_contains_required_keys(self):
        d = OutreachDecision(
            decision=OutreachDecisionType.ALLOW,
            contact_id="c1",
            contact_email="a@b.com",
            channel="sms",
            outreach_type="marketing",
        )
        result = d.to_dict()
        for key in ("decision", "contact_id", "contact_email", "channel", "outreach_type", "checked_at"):
            self.assertIn(key, result)


# ---------------------------------------------------------------------------
# Tests: check_and_record — ALLOW path
# ---------------------------------------------------------------------------

class TestCheckAndRecordAllow(unittest.TestCase):

    def test_allow_calls_record_contact(self):
        gov = _make_governor()
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertTrue(decision.allowed)
        gov.record_contact.assert_called_once_with("c1", "a@b.com", "email", "cold")

    def test_allow_records_audit_entry(self):
        gate = _make_gate()
        gate.check_and_record("c2", "b@c.com", "sms", "follow_up")
        log = gate.get_audit_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["decision"], "allow")
        self.assertEqual(log[0]["contact_id"], "c2")

    def test_allow_decision_has_no_block_reason(self):
        gate = _make_gate()
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertIsNone(decision.block_reason)

    def test_allow_returns_outreach_decision_instance(self):
        gate = _make_gate()
        result = gate.check_and_record("c1", "a@b.com", "linkedin", "prospecting")
        self.assertIsInstance(result, OutreachDecision)


# ---------------------------------------------------------------------------
# Tests: check_and_record — BLOCK paths
# ---------------------------------------------------------------------------

class TestCheckAndRecordBlockDNC(unittest.TestCase):

    def test_block_on_dnc(self):
        gov = _make_governor(is_dnc=True)
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.block_reason, BlockReason.DNC)

    def test_block_on_dnc_does_not_call_record_contact(self):
        gov = _make_governor(is_dnc=True)
        gate = _make_gate(gov)
        gate.check_and_record("c1", "a@b.com", "email", "cold")
        gov.record_contact.assert_not_called()

    def test_block_on_dnc_records_audit_as_block(self):
        gov = _make_governor(is_dnc=True)
        gate = _make_gate(gov)
        gate.check_and_record("c1", "a@b.com", "email", "cold")
        log = gate.get_audit_log()
        self.assertEqual(log[0]["decision"], "block")
        self.assertEqual(log[0]["block_reason"], "dnc")


class TestCheckAndRecordBlockCooldown(unittest.TestCase):

    def test_block_on_cooldown(self):
        gov = _make_governor(is_in_cooldown=True, cooldown_remaining_seconds=86400)
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.block_reason, BlockReason.COOLDOWN)

    def test_block_on_cooldown_does_not_call_record_contact(self):
        gov = _make_governor(is_in_cooldown=True, cooldown_remaining_seconds=3600)
        gate = _make_gate(gov)
        gate.check_and_record("c1", "a@b.com", "email", "cold")
        gov.record_contact.assert_not_called()

    def test_cooldown_message_contains_time_remaining(self):
        gov = _make_governor(is_in_cooldown=True, cooldown_remaining_seconds=172800)
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertIn("2d", decision.message)


class TestCheckAndRecordBlockRegulatory(unittest.TestCase):

    def test_block_on_regulatory(self):
        gov = _make_governor(
            check_regulatory={"allowed": False, "regulation": "GDPR", "reason": "no lawful basis"}
        )
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold",
                                         contact_region="EU")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.regulation_cited, "GDPR")

    def test_block_on_consent_uses_no_consent_reason(self):
        gov = _make_governor(
            check_regulatory={"allowed": False, "regulation": "GDPR",
                               "reason": "explicit consent required"}
        )
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertEqual(decision.block_reason, BlockReason.NO_CONSENT)

    def test_block_on_non_consent_regulatory_reason(self):
        gov = _make_governor(
            check_regulatory={"allowed": False, "regulation": "TCPA",
                               "reason": "time-of-day restriction"}
        )
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "sms", "cold")
        self.assertEqual(decision.block_reason, BlockReason.REGULATORY)


class TestCheckAndRecordFailClosed(unittest.TestCase):

    def test_governor_exception_blocks_outreach(self):
        gov = MagicMock()
        gov.is_dnc.side_effect = RuntimeError("DB unavailable")
        gate = _make_gate(gov)
        decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.block_reason, BlockReason.GOVERNOR_ERROR)

    def test_governor_exception_records_audit(self):
        gov = MagicMock()
        gov.is_dnc.side_effect = RuntimeError("DB unavailable")
        gate = _make_gate(gov)
        gate.check_and_record("c1", "a@b.com", "email", "cold")
        log = gate.get_audit_log()
        self.assertEqual(log[0]["decision"], "block")
        self.assertEqual(log[0]["block_reason"], "governor_error")


# ---------------------------------------------------------------------------
# Tests: process_reply — opt-out detection
# ---------------------------------------------------------------------------

class TestProcessReplyOptOut(unittest.TestCase):

    OPT_OUT_PHRASES = [
        "Please stop contacting me.",
        "Unsubscribe me from this list.",
        "Remove me immediately.",
        "Do not contact me again.",
        "Opt out please.",
        "Opt-out — remove my email.",
        "I don't want to hear from you anymore, leave me alone.",
        "No more emails please.",
        "Take me off your list.",
    ]

    def test_opt_out_keywords_detected(self):
        gate = _make_gate()
        for phrase in self.OPT_OUT_PHRASES:
            with self.subTest(phrase=phrase):
                result = gate.process_reply("c1", "a@b.com", phrase)
                self.assertTrue(result["opted_out"], f"Expected opt-out for: {phrase!r}")

    def test_opt_out_adds_to_dnc(self):
        gov = _make_governor()
        gate = _make_gate(gov)
        gate.process_reply("c1", "a@b.com", "Please stop emailing me.")
        gov.add_to_dnc.assert_called_once()
        call_args = gov.add_to_dnc.call_args
        self.assertEqual(call_args[0][0], "c1")
        self.assertEqual(call_args[0][1], "a@b.com")

    def test_opt_out_reason_contains_keyword(self):
        gate = _make_gate()
        result = gate.process_reply("c1", "a@b.com", "Please unsubscribe me.")
        self.assertIn("reason", result)
        self.assertEqual(result["opted_out"], True)

    def test_opt_out_dnc_failure_still_returns_opted_out(self):
        gov = _make_governor()
        gov.add_to_dnc.side_effect = RuntimeError("DB write failed")
        gate = _make_gate(gov)
        result = gate.process_reply("c1", "a@b.com", "Stop contacting me.")
        # Even if DNC write fails, the response should indicate opt-out was detected
        self.assertTrue(result["opted_out"])


# ---------------------------------------------------------------------------
# Tests: process_reply — positive replies do NOT trigger DNC
# ---------------------------------------------------------------------------

class TestProcessReplyPositive(unittest.TestCase):

    POSITIVE_PHRASES = [
        "I'm interested, tell me more!",
        "Sounds good, how much does it cost?",
        "Can we schedule a demo?",
        "Yes please, sign me up.",
        "I'd like to try the trial.",
    ]

    def test_positive_reply_does_not_trigger_dnc(self):
        gov = _make_governor()
        gate = _make_gate(gov)
        for phrase in self.POSITIVE_PHRASES:
            with self.subTest(phrase=phrase):
                gate.process_reply("c1", "a@b.com", phrase)
                gov.add_to_dnc.assert_not_called()

    def test_positive_reply_returns_positive_true(self):
        gate = _make_gate()
        result = gate.process_reply("c1", "a@b.com", "I'm interested, tell me more!")
        self.assertFalse(result["opted_out"])
        self.assertTrue(result["positive"])

    def test_neutral_reply_returns_positive_false(self):
        gate = _make_gate()
        result = gate.process_reply("c1", "a@b.com", "Who are you?")
        self.assertFalse(result["opted_out"])
        self.assertFalse(result["positive"])


# ---------------------------------------------------------------------------
# Tests: get_contact_status
# ---------------------------------------------------------------------------

class TestGetContactStatus(unittest.TestCase):

    def test_returns_correct_dnc_status(self):
        gov = _make_governor(is_dnc=True)
        gate = _make_gate(gov)
        status = gate.get_contact_status("c1", "a@b.com")
        self.assertTrue(status["is_dnc"])

    def test_returns_cooldown_remaining(self):
        gov = _make_governor(cooldown_remaining_seconds=3600)
        gate = _make_gate(gov)
        status = gate.get_contact_status("c1", "a@b.com")
        self.assertEqual(status["cooldown_remaining"], 3600)

    def test_returns_last_contacted(self):
        ts = "2026-02-01T12:00:00+00:00"
        gov = _make_governor(last_contacted_at=ts)
        gate = _make_gate(gov)
        status = gate.get_contact_status("c1", "a@b.com")
        self.assertEqual(status["last_contacted"], ts)

    def test_returns_consent_status(self):
        gov = _make_governor(consent_status="granted")
        gate = _make_gate(gov)
        status = gate.get_contact_status("c1", "a@b.com")
        self.assertEqual(status["consent_status"], "granted")

    def test_governor_failure_returns_fail_safe_status(self):
        gov = MagicMock()
        gov.is_dnc.side_effect = RuntimeError("DB unavailable")
        gate = _make_gate(gov)
        status = gate.get_contact_status("c1", "a@b.com")
        # Fail safe: treat as DNC
        self.assertTrue(status["is_dnc"])
        self.assertIn("error", status)

    def test_status_contains_contact_identifiers(self):
        gate = _make_gate()
        status = gate.get_contact_status("c-99", "z@example.com")
        self.assertEqual(status["contact_id"], "c-99")
        self.assertEqual(status["contact_email"], "z@example.com")


# ---------------------------------------------------------------------------
# Tests: Lazy governor creation
# ---------------------------------------------------------------------------

class TestLazyGovernorCreation(unittest.TestCase):

    def test_gate_created_without_governor(self):
        """Gate can be instantiated without providing a governor."""
        gate = OutreachComplianceGate()
        self.assertIsNone(gate._governor)

    def test_lazy_creation_uses_stub_when_module_missing(self):
        """When ContactComplianceGovernor cannot be imported, stub is used."""
        gate = OutreachComplianceGate()
        # Ensure the real module isn't importable in this context
        with patch.dict("sys.modules", {"contact_compliance_governor": None}):
            gov = gate._get_governor()
        # Should have fallen back to the stub
        self.assertIsInstance(gov, _StubGovernor)

    def test_lazy_creation_is_idempotent(self):
        """Calling _get_governor() multiple times returns the same instance."""
        gate = OutreachComplianceGate()
        with patch.dict("sys.modules", {"contact_compliance_governor": None}):
            gov1 = gate._get_governor()
            gov2 = gate._get_governor()
        self.assertIs(gov1, gov2)

    def test_provided_governor_is_used_directly(self):
        gov = _make_governor()
        gate = OutreachComplianceGate(governor=gov)
        returned = gate._get_governor()
        self.assertIs(returned, gov)


# ---------------------------------------------------------------------------
# Tests: Multiple channels for same contact tracked independently
# ---------------------------------------------------------------------------

class TestMultiChannelTracking(unittest.TestCase):

    def test_different_channels_each_recorded_separately(self):
        gov = _make_governor()
        gate = _make_gate(gov)

        gate.check_and_record("c1", "a@b.com", "email", "cold")
        gate.check_and_record("c1", "a@b.com", "sms", "cold")
        gate.check_and_record("c1", "a@b.com", "linkedin", "cold")

        # record_contact should have been called 3 times with different channels
        self.assertEqual(gov.record_contact.call_count, 3)
        called_channels = {call[0][2] for call in gov.record_contact.call_args_list}
        self.assertEqual(called_channels, {"email", "sms", "linkedin"})

    def test_email_cooldown_does_not_block_sms(self):
        """Cooldown on email channel should not block an SMS outreach."""
        def is_in_cooldown_side_effect(contact_id, contact_email, channel, is_existing_customer=False):
            return channel == "email"

        gov = _make_governor()
        gov.is_in_cooldown.side_effect = is_in_cooldown_side_effect
        gov.cooldown_remaining_seconds.return_value = 86400

        gate = _make_gate(gov)

        email_decision = gate.check_and_record("c1", "a@b.com", "email", "cold")
        sms_decision = gate.check_and_record("c1", "a@b.com", "sms", "cold")

        self.assertFalse(email_decision.allowed)
        self.assertTrue(sms_decision.allowed)


# ---------------------------------------------------------------------------
# Tests: Audit log accumulation
# ---------------------------------------------------------------------------

class TestAuditLog(unittest.TestCase):

    def test_audit_log_grows_with_each_check(self):
        gate = _make_gate()
        gate.check_and_record("c1", "a@b.com", "email", "cold")
        gate.check_and_record("c2", "b@c.com", "sms", "follow_up")
        self.assertEqual(len(gate.get_audit_log()), 2)

    def test_get_audit_log_returns_dicts(self):
        gate = _make_gate()
        gate.check_and_record("c1", "a@b.com", "email", "cold")
        log = gate.get_audit_log()
        self.assertIsInstance(log[0], dict)

    def test_audit_log_snapshot_is_independent_copy(self):
        gate = _make_gate()
        gate.check_and_record("c1", "a@b.com", "email", "cold")
        log1 = gate.get_audit_log()
        gate.check_and_record("c2", "b@c.com", "sms", "cold")
        # The first snapshot should not have grown
        self.assertEqual(len(log1), 1)


# ---------------------------------------------------------------------------
# Tests: Module-level default gate singleton
# ---------------------------------------------------------------------------

class TestDefaultGateSingleton(unittest.TestCase):

    def test_get_default_gate_returns_gate_instance(self):
        gate = get_default_gate()
        self.assertIsInstance(gate, OutreachComplianceGate)

    def test_get_default_gate_returns_same_instance(self):
        gate1 = get_default_gate()
        gate2 = get_default_gate()
        self.assertIs(gate1, gate2)


# ---------------------------------------------------------------------------
# Tests: StubGovernor defaults
# ---------------------------------------------------------------------------

class TestStubGovernor(unittest.TestCase):

    def test_stub_is_dnc_returns_false(self):
        stub = _StubGovernor()
        self.assertFalse(stub.is_dnc("c1", "a@b.com"))

    def test_stub_is_in_cooldown_returns_false(self):
        stub = _StubGovernor()
        self.assertFalse(stub.is_in_cooldown("c1", "a@b.com", "email"))

    def test_stub_check_regulatory_allows(self):
        stub = _StubGovernor()
        result = stub.check_regulatory("a@b.com", "email")
        self.assertTrue(result["allowed"])

    def test_stub_record_contact_is_no_op(self):
        stub = _StubGovernor()
        stub.record_contact("c1", "a@b.com", "email", "cold")  # should not raise

    def test_stub_add_to_dnc_is_no_op(self):
        stub = _StubGovernor()
        stub.add_to_dnc("c1", "a@b.com", "opt_out")  # should not raise


if __name__ == "__main__":
    unittest.main()
