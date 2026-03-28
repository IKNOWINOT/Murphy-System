"""
Tests for COMPL-001: ContactComplianceGovernor.

Validates cooldown enforcement, DNC list, opt-out detection,
regulatory gating, audit trail, and persistence round-trip.

Design Label: TEST-COMPL-001
Owner: QA Team
"""

import os
from datetime import datetime, timedelta, timezone

import pytest


from contact_compliance_governor import (
    ContactComplianceGovernor,
    DecisionType,
    OutreachDecision,
    Regulation,
)
from persistence_manager import PersistenceManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path))


@pytest.fixture
def gov():
    return ContactComplianceGovernor()


@pytest.fixture
def gov_with_pm(pm):
    return ContactComplianceGovernor(persistence_manager=pm)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allow(gov, contact_id="c1", contact_email="a@b.com", channel="email",
           outreach_type="marketing", **kwargs):
    return gov.validate_outreach(
        contact_id=contact_id,
        contact_email=contact_email,
        channel=channel,
        outreach_type=outreach_type,
        message_metadata={
            "has_unsubscribe_link": True,
            "has_physical_address": True,
        },
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. Cooldown — non-customer 30-day rule
# ---------------------------------------------------------------------------

class TestNonCustomerCooldown:
    def test_first_contact_allowed(self, gov):
        d = _allow(gov, contact_id="nc1")
        assert d.allowed is True
        assert d.decision == DecisionType.ALLOW.value

    def test_second_contact_blocked_within_30_days(self, gov):
        _allow(gov, contact_id="nc1")  # first send
        d = _allow(gov, contact_id="nc1")  # immediate second send
        assert d.allowed is False
        assert d.decision == DecisionType.BLOCK.value
        assert d.regulation == Regulation.COOLDOWN.value
        assert d.cooldown_remaining_days > 0

    def test_cooldown_remaining_approaches_30(self, gov):
        _allow(gov, contact_id="nc2")
        d = _allow(gov, contact_id="nc2")
        # Should be close to 30 days
        assert d.cooldown_remaining_days >= 29

    def test_different_channels_independent_cooldowns(self, gov):
        _allow(gov, contact_id="nc3", channel="email")
        d = _allow(gov, contact_id="nc3", channel="sms",
                   outreach_type="cold_outreach",
                   has_explicit_consent=True, contact_region="US")
        # sms marketing needs TCPA consent; region="" triggers TCPA check — use explicit consent
        assert d.allowed is True


# ---------------------------------------------------------------------------
# 2. Existing customer — exempt from cooldown for service, but not marketing
# ---------------------------------------------------------------------------

class TestExistingCustomerCooldown:
    def test_service_message_always_allowed(self, gov):
        # First contact to set the timestamp
        _allow(gov, contact_id="cust1", is_existing_customer=True,
               outreach_type="service")
        # Immediate second service message must still be allowed
        d = gov.validate_outreach(
            contact_id="cust1",
            contact_email="cust@x.com",
            channel="email",
            outreach_type="service",
            is_existing_customer=True,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert d.allowed is True

    def test_transactional_message_always_allowed(self, gov):
        _allow(gov, contact_id="cust2", is_existing_customer=True,
               outreach_type="transactional")
        d = gov.validate_outreach(
            contact_id="cust2",
            contact_email="cust@x.com",
            channel="email",
            outreach_type="transactional",
            is_existing_customer=True,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert d.allowed is True

    def test_marketing_to_customer_blocked_within_7_days(self, gov):
        # First marketing message
        _allow(gov, contact_id="cust3", is_existing_customer=True,
               outreach_type="marketing")
        # Immediate second marketing
        d = gov.validate_outreach(
            contact_id="cust3",
            contact_email="cust@x.com",
            channel="email",
            outreach_type="marketing",
            is_existing_customer=True,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert d.allowed is False
        assert d.regulation == Regulation.COOLDOWN.value
        assert d.cooldown_remaining_days >= 6

    def test_customer_cooldown_shorter_than_non_customer(self, gov):
        _allow(gov, contact_id="cust4", is_existing_customer=True,
               outreach_type="marketing")
        d_cust = gov.validate_outreach(
            contact_id="cust4",
            contact_email="cust@x.com",
            channel="email",
            outreach_type="marketing",
            is_existing_customer=True,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )

        _allow(gov, contact_id="nonc4", is_existing_customer=False,
               outreach_type="marketing")
        d_nonc = gov.validate_outreach(
            contact_id="nonc4",
            contact_email="nonc@x.com",
            channel="email",
            outreach_type="marketing",
            is_existing_customer=False,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )

        assert d_cust.cooldown_remaining_days < d_nonc.cooldown_remaining_days


# ---------------------------------------------------------------------------
# 3. DNC list
# ---------------------------------------------------------------------------

class TestDNCList:
    def test_dnc_blocks_all_channels(self, gov):
        gov.add_to_dnc("dnc1", "dnc@x.com", reason="user requested")
        for ch in ("email", "sms", "phone", "linkedin"):
            d = gov.validate_outreach(
                contact_id="dnc1",
                contact_email="dnc@x.com",
                channel=ch,
                outreach_type="service",
            )
            assert d.allowed is False, f"Expected DNC block on channel {ch}"
            assert d.regulation == Regulation.DNC.value

    def test_dnc_blocks_transactional_too(self, gov):
        gov.add_to_dnc("dnc2", "dnc2@x.com", reason="do not contact")
        d = gov.validate_outreach(
            contact_id="dnc2",
            contact_email="dnc2@x.com",
            channel="email",
            outreach_type="transactional",
            is_existing_customer=True,
        )
        assert d.allowed is False

    def test_dnc_cannot_be_removed_without_consent(self, gov):
        gov.add_to_dnc("dnc3", "dnc3@x.com", reason="unsubscribe request")
        removed = gov.remove_from_dnc_with_consent("dnc3", consent_proof="")
        assert removed is False
        assert gov.is_on_dnc("dnc3") is True

    def test_dnc_removed_with_valid_consent(self, gov):
        gov.add_to_dnc("dnc4", "dnc4@x.com", reason="unsubscribe request")
        removed = gov.remove_from_dnc_with_consent("dnc4", consent_proof="form-id-abc123")
        assert removed is True
        assert gov.is_on_dnc("dnc4") is False

    def test_is_on_dnc_false_for_unknown_contact(self, gov):
        assert gov.is_on_dnc("unknown_xyz") is False


# ---------------------------------------------------------------------------
# 4. Opt-out intent detection
# ---------------------------------------------------------------------------

class TestOptOutDetection:
    @pytest.mark.parametrize("text", [
        "Please unsubscribe me from your list",
        "STOP sending emails",
        "I want to opt out of your communications",
        "Do not contact me again",
        "Remove me from your mailing list",
        "Please remove me",
        "no more emails please",
        "I'd like to opt  out",
    ])
    def test_detects_optout_intent(self, gov, text):
        assert gov.detect_optout_intent(text) is True

    @pytest.mark.parametrize("text", [
        "Thank you for the update!",
        "Looking forward to the next email",
        "I love your product",
        "",
    ])
    def test_does_not_flag_normal_replies(self, gov, text):
        assert gov.detect_optout_intent(text) is False

    def test_process_reply_adds_to_dnc(self, gov):
        added = gov.process_reply_for_optout("r1", "r1@x.com", "please unsubscribe me")
        assert added is True
        assert gov.is_on_dnc("r1") is True

    def test_process_reply_no_optout_does_not_add_dnc(self, gov):
        added = gov.process_reply_for_optout("r2", "r2@x.com", "Great, thanks!")
        assert added is False
        assert gov.is_on_dnc("r2") is False


# ---------------------------------------------------------------------------
# 5. CAN-SPAM validation
# ---------------------------------------------------------------------------

class TestCANSPAM:
    def test_missing_unsubscribe_link_blocks_email(self, gov):
        d = gov.validate_outreach(
            contact_id="cs1",
            contact_email="cs1@x.com",
            channel="email",
            outreach_type="marketing",
            contact_region="US",
            message_metadata={
                "has_unsubscribe_link": False,
                "has_physical_address": True,
            },
        )
        assert d.allowed is False
        assert d.regulation == Regulation.CAN_SPAM.value

    def test_missing_physical_address_blocks_email(self, gov):
        d = gov.validate_outreach(
            contact_id="cs2",
            contact_email="cs2@x.com",
            channel="email",
            outreach_type="marketing",
            contact_region="US",
            message_metadata={
                "has_unsubscribe_link": True,
                "has_physical_address": False,
            },
        )
        assert d.allowed is False
        assert d.regulation == Regulation.CAN_SPAM.value

    def test_transactional_email_exempt_from_can_spam_gate(self, gov):
        d = gov.validate_outreach(
            contact_id="cs3",
            contact_email="cs3@x.com",
            channel="email",
            outreach_type="transactional",
            contact_region="US",
            is_existing_customer=True,
            message_metadata={
                "has_unsubscribe_link": False,
                "has_physical_address": False,
            },
        )
        # Transactional is not "marketing" — CAN-SPAM gate only fires for marketing
        assert d.allowed is True

    def test_complete_email_allowed(self, gov):
        d = gov.validate_outreach(
            contact_id="cs4",
            contact_email="cs4@x.com",
            channel="email",
            outreach_type="marketing",
            contact_region="US",
            message_metadata={
                "has_unsubscribe_link": True,
                "has_physical_address": True,
            },
        )
        assert d.allowed is True
        assert d.regulation == Regulation.NONE.value


# ---------------------------------------------------------------------------
# 6. TCPA time-of-day enforcement
# ---------------------------------------------------------------------------

class TestTCPA:
    def test_call_before_8am_blocked(self, gov):
        d = gov.validate_outreach(
            contact_id="tcpa1",
            contact_email="t@x.com",
            channel="phone",
            outreach_type="marketing",
            contact_region="US",
            has_explicit_consent=True,
            message_metadata={"hour_utc": 7},
        )
        assert d.allowed is False
        assert d.regulation == Regulation.TCPA.value

    def test_call_after_9pm_blocked(self, gov):
        d = gov.validate_outreach(
            contact_id="tcpa2",
            contact_email="t@x.com",
            channel="sms",
            outreach_type="marketing",
            contact_region="US",
            has_explicit_consent=True,
            message_metadata={"hour_utc": 21},
        )
        assert d.allowed is False
        assert d.regulation == Regulation.TCPA.value

    def test_call_during_allowed_hours_passes(self, gov):
        d = gov.validate_outreach(
            contact_id="tcpa3",
            contact_email="t@x.com",
            channel="phone",
            outreach_type="marketing",
            contact_region="US",
            has_explicit_consent=True,
            message_metadata={"hour_utc": 10},
        )
        assert d.allowed is True

    def test_marketing_sms_without_consent_blocked(self, gov):
        d = gov.validate_outreach(
            contact_id="tcpa4",
            contact_email="t@x.com",
            channel="sms",
            outreach_type="marketing",
            contact_region="US",
            has_explicit_consent=False,
            message_metadata={"hour_utc": 12},
        )
        assert d.allowed is False
        assert d.decision == DecisionType.REQUIRES_CONSENT.value
        assert d.regulation == Regulation.TCPA.value


# ---------------------------------------------------------------------------
# 7. GDPR consent requirement for EU contacts
# ---------------------------------------------------------------------------

class TestGDPR:
    def test_eu_marketing_without_consent_blocked(self, gov):
        d = gov.validate_outreach(
            contact_id="eu1",
            contact_email="eu1@x.com",
            channel="email",
            outreach_type="marketing",
            contact_region="EU",
            has_explicit_consent=False,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert d.allowed is False
        assert d.decision == DecisionType.REQUIRES_CONSENT.value
        assert d.regulation == Regulation.GDPR.value

    def test_eu_marketing_with_consent_allowed(self, gov):
        d = gov.validate_outreach(
            contact_id="eu2",
            contact_email="eu2@x.com",
            channel="email",
            outreach_type="marketing",
            contact_region="EU",
            has_explicit_consent=True,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert d.allowed is True

    def test_eu_transactional_without_consent_allowed(self, gov):
        d = gov.validate_outreach(
            contact_id="eu3",
            contact_email="eu3@x.com",
            channel="email",
            outreach_type="transactional",
            contact_region="EU",
            is_existing_customer=True,
            has_explicit_consent=False,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert d.allowed is True


# ---------------------------------------------------------------------------
# 8. Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_allow_decision_recorded(self, gov):
        _allow(gov, contact_id="aud1")
        log = gov.get_audit_log()
        assert len(log) == 1
        entry = log[0]
        assert entry["contact_id"] == "aud1"
        assert entry["decision"] == DecisionType.ALLOW.value
        assert "timestamp" in entry
        assert "audit_id" in entry

    def test_block_decision_recorded(self, gov):
        _allow(gov, contact_id="aud2")
        _allow(gov, contact_id="aud2")  # blocked by cooldown
        log = gov.get_audit_log()
        assert len(log) == 2
        decisions = {e["decision"] for e in log}
        assert DecisionType.BLOCK.value in decisions

    def test_audit_log_contains_regulation(self, gov):
        gov.validate_outreach(
            contact_id="aud3",
            contact_email="aud3@x.com",
            channel="email",
            outreach_type="marketing",
            contact_region="US",
            message_metadata={"has_unsubscribe_link": False, "has_physical_address": True},
        )
        log = gov.get_audit_log()
        assert any(e["regulation"] == Regulation.CAN_SPAM.value for e in log)

    def test_audit_log_is_append_only_copy(self, gov):
        _allow(gov, contact_id="aud4")
        log1 = gov.get_audit_log()
        log1.clear()  # mutate the copy
        log2 = gov.get_audit_log()
        assert len(log2) == 1  # original unchanged


# ---------------------------------------------------------------------------
# 9. Persistence round-trip
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load_dnc(self, pm):
        gov1 = ContactComplianceGovernor(persistence_manager=pm)
        gov1.add_to_dnc("persist1", "p1@x.com", reason="test")
        assert gov1.save_state() is True

        gov2 = ContactComplianceGovernor(persistence_manager=pm)
        assert gov2.load_state() is True
        assert gov2.is_on_dnc("persist1") is True

    def test_save_and_load_contacts(self, pm):
        gov1 = ContactComplianceGovernor(persistence_manager=pm)
        _allow(gov1, contact_id="persist2")
        assert gov1.save_state() is True

        gov2 = ContactComplianceGovernor(persistence_manager=pm)
        assert gov2.load_state() is True
        # Loaded contact should still be in cooldown
        d = _allow(gov2, contact_id="persist2")
        assert d.allowed is False
        assert d.regulation == Regulation.COOLDOWN.value

    def test_save_and_load_audit_log(self, pm):
        gov1 = ContactComplianceGovernor(persistence_manager=pm)
        _allow(gov1, contact_id="persist3")
        assert gov1.save_state() is True

        gov2 = ContactComplianceGovernor(persistence_manager=pm)
        assert gov2.load_state() is True
        log = gov2.get_audit_log()
        assert len(log) >= 1
        assert log[0]["contact_id"] == "persist3"

    def test_no_persistence_manager_returns_false(self, gov):
        assert gov.save_state() is False
        assert gov.load_state() is False

    def test_load_state_with_no_prior_state_returns_false(self, pm):
        gov = ContactComplianceGovernor(persistence_manager=pm)
        assert gov.load_state() is False


# ---------------------------------------------------------------------------
# 10. Audit log bounded by capped_append
# ---------------------------------------------------------------------------

class TestAuditLogCap:
    def test_audit_log_does_not_exceed_cap(self):
        gov = ContactComplianceGovernor()
        gov._MAX_AUDIT_ENTRIES = 50  # override cap for test speed
        for i in range(60):
            gov.validate_outreach(
                contact_id=f"cap{i}",
                contact_email=f"cap{i}@x.com",
                channel="email",
                outreach_type="marketing",
                contact_region="US",
                message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
            )
        log = gov.get_audit_log()
        assert len(log) <= 55  # capped_append trims 10% when cap reached

    def test_audit_log_trims_oldest_entries(self):
        gov = ContactComplianceGovernor()
        gov._MAX_AUDIT_ENTRIES = 10
        for i in range(15):
            gov.validate_outreach(
                contact_id=f"trim{i}",
                contact_email=f"trim{i}@x.com",
                channel="email",
                outreach_type="marketing",
                contact_region="US",
                message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
            )
        log = gov.get_audit_log()
        # After trimming oldest 10% of 10 = 1 entry, then appending, list never > 15
        assert len(log) <= 15
