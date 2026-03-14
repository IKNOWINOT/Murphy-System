"""
Tests for Outreach Compliance Plan (CAMP-002).

Covers:
  - OutreachComplianceRecord / SuppressionEntry / ContactCooldownTracker /
    OutreachCampaignPlan dataclasses
  - SuppressionListManager: suppress, is_suppressed, remove_with_consent,
    process_reply_for_optout, import_dnc_list, handle_gdpr_erasure
  - CooldownEnforcer: is_in_cooldown, record_contact, 30-day / 7-day windows
  - OutreachComplianceGovernor: check_outreach, record_sent, process_reply_for_optout
  - OutreachCampaignPlanner: create_campaign_plan, build_daily_outreach_schedule,
    get_vertical_constraints
  - Compliance rules: 30-day cooldown, suppression, CAN-SPAM, TCPA, GDPR, CASL, CCPA
  - Input validation guards (CWE-20, CWE-400)
  - Thread-safety (concurrent access)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
import pytest

from src.outreach_compliance_plan import (
    BUSINESS_TYPE_VERTICALS,
    ComplianceDecision,
    ContactCooldownTracker,
    CooldownEnforcer,
    OutreachCampaignPlan,
    OutreachCampaignPlanner,
    OutreachComplianceGovernor,
    OutreachComplianceRecord,
    SuppressionEntry,
    SuppressionListManager,
    SuppressionReason,
    _COOLDOWN_DAYS_CUSTOMER,
    _COOLDOWN_DAYS_PROSPECT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def suppression_mgr():
    return SuppressionListManager()


@pytest.fixture
def cooldown_enforcer():
    return CooldownEnforcer()


@pytest.fixture
def governor():
    return OutreachComplianceGovernor()


@pytest.fixture
def planner():
    return OutreachCampaignPlanner()


def _valid_contact():
    return "prospect-001"


def _valid_email():
    return "test@example.com"


# ---------------------------------------------------------------------------
# OutreachComplianceRecord
# ---------------------------------------------------------------------------

class TestOutreachComplianceRecord:
    def test_default_fields(self):
        rec = OutreachComplianceRecord()
        assert rec.record_id
        assert rec.decision == ComplianceDecision.ALLOW.value

    def test_to_dict_keys(self):
        rec = OutreachComplianceRecord(
            contact_id="c1",
            channel="email",
            decision=ComplianceDecision.BLOCK.value,
            block_reason="on DNC",
        )
        d = rec.to_dict()
        assert d["contact_id"] == "c1"
        assert d["channel"] == "email"
        assert d["decision"] == "BLOCK"
        assert d["block_reason"] == "on DNC"


# ---------------------------------------------------------------------------
# SuppressionEntry
# ---------------------------------------------------------------------------

class TestSuppressionEntry:
    def test_to_dict_omits_email(self):
        entry = SuppressionEntry(
            contact_id="c1",
            contact_email="secret@example.com",
            reason=SuppressionReason.OPT_OUT_REPLY.value,
        )
        d = entry.to_dict()
        assert "contact_email" not in d
        assert d["contact_id"] == "c1"
        assert d["reason"] == "opt_out_reply"


# ---------------------------------------------------------------------------
# ContactCooldownTracker
# ---------------------------------------------------------------------------

class TestContactCooldownTracker:
    def test_never_contacted_not_in_cooldown(self):
        tracker = ContactCooldownTracker(contact_id="c1")
        assert not tracker.is_in_cooldown
        assert tracker.cooldown_remaining_days == 0

    def test_recently_contacted_is_in_cooldown(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        tracker = ContactCooldownTracker(
            contact_id="c1",
            last_contacted_at=recent,
            cooldown_days=30,
        )
        assert tracker.is_in_cooldown
        assert tracker.cooldown_remaining_days > 20

    def test_old_contact_not_in_cooldown(self):
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        tracker = ContactCooldownTracker(
            contact_id="c1",
            last_contacted_at=old,
            cooldown_days=30,
        )
        assert not tracker.is_in_cooldown
        assert tracker.cooldown_remaining_days == 0

    def test_customer_cooldown_shorter(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        customer = ContactCooldownTracker(
            contact_id="c1",
            is_customer=True,
            last_contacted_at=recent,
            cooldown_days=_COOLDOWN_DAYS_CUSTOMER,
        )
        prospect = ContactCooldownTracker(
            contact_id="c2",
            is_customer=False,
            last_contacted_at=recent,
            cooldown_days=_COOLDOWN_DAYS_PROSPECT,
        )
        assert customer.is_in_cooldown
        assert prospect.is_in_cooldown
        assert customer.cooldown_remaining_days < prospect.cooldown_remaining_days


# ---------------------------------------------------------------------------
# SuppressionListManager
# ---------------------------------------------------------------------------

class TestSuppressionListManager:
    def test_suppress_and_is_suppressed(self, suppression_mgr):
        suppression_mgr.suppress("c1", "test@example.com")
        assert suppression_mgr.is_suppressed("c1")

    def test_not_suppressed_by_default(self, suppression_mgr):
        assert not suppression_mgr.is_suppressed("nobody")

    def test_suppress_invalid_contact_id(self, suppression_mgr):
        with pytest.raises(ValueError, match="contact_id"):
            suppression_mgr.suppress("bad id!", "test@example.com")

    def test_suppress_invalid_email(self, suppression_mgr):
        with pytest.raises(ValueError):
            suppression_mgr.suppress("c1", "not-an-email")

    def test_remove_with_consent_works(self, suppression_mgr):
        suppression_mgr.suppress("c2", "user@example.com")
        assert suppression_mgr.is_suppressed("c2")
        result = suppression_mgr.remove_with_consent("c2", "form-12345")
        assert result is True
        assert not suppression_mgr.is_suppressed("c2")

    def test_remove_without_consent_fails(self, suppression_mgr):
        suppression_mgr.suppress("c3", "x@example.com")
        result = suppression_mgr.remove_with_consent("c3", "")
        assert result is False
        assert suppression_mgr.is_suppressed("c3")

    def test_remove_not_found(self, suppression_mgr):
        result = suppression_mgr.remove_with_consent("never-added", "consent")
        assert result is False

    def test_process_reply_opt_out_unsubscribe(self, suppression_mgr):
        result = suppression_mgr.process_reply_for_optout("c4", "c4@example.com", "Please unsubscribe me")
        assert result is True
        assert suppression_mgr.is_suppressed("c4")

    def test_process_reply_opt_out_stop(self, suppression_mgr):
        result = suppression_mgr.process_reply_for_optout("c5", "c5@example.com", "STOP")
        assert result is True

    def test_process_reply_positive_not_suppressed(self, suppression_mgr):
        result = suppression_mgr.process_reply_for_optout("c6", "c6@example.com", "Sounds great, let's connect!")
        assert result is False
        assert not suppression_mgr.is_suppressed("c6")

    def test_import_dnc_list(self, suppression_mgr):
        entries = [
            {"contact_id": "d1", "email": "d1@example.com"},
            {"contact_id": "d2", "email": "d2@example.com"},
        ]
        count = suppression_mgr.import_dnc_list(entries)
        assert count == 2
        assert suppression_mgr.is_suppressed("d1")
        assert suppression_mgr.is_suppressed("d2")

    def test_import_dnc_skips_invalid(self, suppression_mgr):
        entries = [
            {"contact_id": "bad id!", "email": "ok@example.com"},
            {"contact_id": "ok-id", "email": "ok2@example.com"},
        ]
        count = suppression_mgr.import_dnc_list(entries)
        assert count == 1

    def test_gdpr_erasure_suppresses(self, suppression_mgr):
        suppression_mgr.handle_gdpr_erasure("eu-1", "eu@example.com")
        entry = suppression_mgr.get_suppression_entry("eu-1")
        assert entry is not None
        assert entry.reason == SuppressionReason.GDPR_ERASURE.value

    def test_suppress_idempotent(self, suppression_mgr):
        suppression_mgr.suppress("c99", "c99@example.com")
        suppression_mgr.suppress("c99", "c99@example.com")
        assert suppression_mgr.is_suppressed("c99")

    def test_get_status(self, suppression_mgr):
        suppression_mgr.suppress("s1", "s1@example.com")
        status = suppression_mgr.get_status()
        assert status["suppressed_count"] == 1
        assert "capacity" in status

    def test_thread_safety_concurrent_suppress(self, suppression_mgr):
        errors = []

        def suppress_worker(contact_id: str):
            try:
                suppression_mgr.suppress(contact_id, f"{contact_id}@example.com")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=suppress_worker, args=(f"t{i}",))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ---------------------------------------------------------------------------
# CooldownEnforcer
# ---------------------------------------------------------------------------

class TestCooldownEnforcer:
    def test_new_contact_not_in_cooldown(self, cooldown_enforcer):
        assert not cooldown_enforcer.is_in_cooldown("brand-new-contact")

    def test_record_contact_puts_in_cooldown(self, cooldown_enforcer):
        cooldown_enforcer.record_contact("c1", "email")
        assert cooldown_enforcer.is_in_cooldown("c1")

    def test_30_day_cooldown_for_prospect(self, cooldown_enforcer):
        cooldown_enforcer.record_contact("p1", "email", is_customer=False)
        remaining = cooldown_enforcer.cooldown_remaining_days("p1")
        assert remaining >= 29  # just contacted

    def test_7_day_cooldown_for_customer(self, cooldown_enforcer):
        cooldown_enforcer.record_contact("cust1", "email", is_customer=True)
        remaining = cooldown_enforcer.cooldown_remaining_days("cust1")
        assert remaining <= 7

    def test_customer_has_shorter_cooldown_than_prospect(self, cooldown_enforcer):
        cooldown_enforcer.record_contact("p2", "email", is_customer=False)
        cooldown_enforcer.record_contact("c2", "email", is_customer=True)
        assert cooldown_enforcer.cooldown_remaining_days("c2") <= _COOLDOWN_DAYS_CUSTOMER
        assert cooldown_enforcer.cooldown_remaining_days("p2") <= _COOLDOWN_DAYS_PROSPECT

    def test_cooldown_remaining_zero_if_not_contacted(self, cooldown_enforcer):
        assert cooldown_enforcer.cooldown_remaining_days("never-seen") == 0

    def test_get_tracker_returns_none_for_unknown(self, cooldown_enforcer):
        assert cooldown_enforcer.get_tracker("unknown") is None

    def test_get_tracker_returns_tracker_after_contact(self, cooldown_enforcer):
        cooldown_enforcer.record_contact("c3", "linkedin")
        tracker = cooldown_enforcer.get_tracker("c3")
        assert tracker is not None
        assert tracker.contact_id == "c3"
        assert tracker.last_channel == "linkedin"

    def test_invalid_contact_id_raises(self, cooldown_enforcer):
        with pytest.raises(ValueError, match="contact_id"):
            cooldown_enforcer.is_in_cooldown("bad id!")

    def test_get_status(self, cooldown_enforcer):
        cooldown_enforcer.record_contact("c4", "email")
        status = cooldown_enforcer.get_status()
        assert status["tracked_contacts"] == 1
        assert status["cooldown_days_prospect"] == _COOLDOWN_DAYS_PROSPECT
        assert status["cooldown_days_customer"] == _COOLDOWN_DAYS_CUSTOMER


# ---------------------------------------------------------------------------
# OutreachComplianceGovernor
# ---------------------------------------------------------------------------

class TestOutreachComplianceGovernor:
    def test_allows_fresh_contact(self, governor):
        result = governor.check_outreach(
            contact_id="fresh-001",
            channel="email",
            message_metadata={
                "has_unsubscribe_link": True,
                "has_physical_address": True,
            },
        )
        assert result["allowed"] is True
        assert result["decision"] == ComplianceDecision.ALLOW.value

    def test_blocks_suppressed_contact(self, governor):
        governor._suppression.suppress("blocked-001", "blocked@example.com")
        result = governor.check_outreach(
            contact_id="blocked-001",
            channel="email",
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is False
        assert result["regulation"] == "SUPPRESSION"

    def test_blocks_contact_in_cooldown(self, governor):
        # Record a contact first to start cooldown
        governor.record_sent("cooldown-001", "email")
        result = governor.check_outreach(
            contact_id="cooldown-001",
            channel="email",
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is False
        assert result["regulation"] == "COOLDOWN"
        assert result["cooldown_remaining_days"] > 0

    def test_customer_exception_shorter_cooldown(self, governor):
        # After customer re-contact, check they respect 7-day window (not 30)
        governor.record_sent("cust-100", "email", is_customer=True)
        result = governor.check_outreach(
            contact_id="cust-100",
            channel="email",
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        # Still in cooldown but cooldown should be <= 7 days
        assert result["allowed"] is False
        assert result["cooldown_remaining_days"] <= 7

    def test_gdpr_requires_consent_for_eu(self, governor):
        result = governor.check_outreach(
            contact_id="eu-001",
            channel="email",
            contact_region="EU",
            has_explicit_consent=False,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is False
        assert result["decision"] == ComplianceDecision.REQUIRES_CONSENT.value
        assert "GDPR" in result["regulation"]

    def test_gdpr_allows_with_consent(self, governor):
        result = governor.check_outreach(
            contact_id="eu-002",
            channel="email",
            contact_region="EU",
            has_explicit_consent=True,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is True

    def test_casl_requires_consent_for_canadian(self, governor):
        result = governor.check_outreach(
            contact_id="ca-001",
            channel="email",
            contact_region="CA",
            has_explicit_consent=False,
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is False
        assert "CASL" in result["regulation"]

    def test_tcpa_blocks_sms_without_consent(self, governor):
        result = governor.check_outreach(
            contact_id="sms-001",
            channel="sms",
            has_explicit_consent=False,
        )
        assert result["allowed"] is False
        assert "TCPA" in result["regulation"]

    def test_tcpa_allows_sms_with_consent(self, governor):
        result = governor.check_outreach(
            contact_id="sms-002",
            channel="sms",
            has_explicit_consent=True,
        )
        assert result["allowed"] is True

    def test_can_spam_blocks_email_without_unsubscribe(self, governor):
        result = governor.check_outreach(
            contact_id="spam-001",
            channel="email",
            message_metadata={"has_unsubscribe_link": False, "has_physical_address": True},
        )
        assert result["allowed"] is False
        assert "CAN_SPAM" in result["regulation"]

    def test_can_spam_blocks_email_without_physical_address(self, governor):
        result = governor.check_outreach(
            contact_id="spam-002",
            channel="email",
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": False},
        )
        assert result["allowed"] is False
        assert "CAN_SPAM" in result["regulation"]

    def test_ccpa_do_not_sell_blocks(self, governor):
        result = governor.check_outreach(
            contact_id="ccpa-001",
            channel="email",
            contact_region="US",
            message_metadata={
                "has_unsubscribe_link": True,
                "has_physical_address": True,
                "ccpa_do_not_sell": True,
            },
        )
        assert result["allowed"] is False
        assert "CCPA" in result["regulation"]

    def test_invalid_channel_blocks(self, governor):
        result = governor.check_outreach(
            contact_id="bad-001",
            channel="fax",
        )
        assert result["allowed"] is False

    def test_invalid_region_blocks(self, governor):
        result = governor.check_outreach(
            contact_id="bad-002",
            channel="email",
            contact_region="MARS",
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is False

    def test_process_reply_opt_out_suppresses(self, governor):
        governor.record_sent("reply-001", "email")
        suppressed = governor.process_reply_for_optout(
            contact_id="reply-001",
            contact_email="reply001@example.com",
            reply_text="Please unsubscribe me from this list.",
        )
        assert suppressed is True
        result = governor.check_outreach(
            contact_id="reply-001",
            channel="email",
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is False

    def test_record_sent_records_cooldown(self, governor):
        governor.record_sent("rec-001", "email")
        result = governor.check_outreach(
            contact_id="rec-001",
            channel="email",
            message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
        )
        assert result["allowed"] is False
        assert result["regulation"] == "COOLDOWN"

    def test_get_audit_log(self, governor):
        governor.record_sent("audit-001", "email")
        log = governor.get_audit_log()
        assert len(log) >= 1

    def test_get_status(self, governor):
        status = governor.get_status()
        assert "suppression" in status
        assert "cooldown" in status
        assert "audit_log_size" in status

    def test_thread_safety_concurrent_check_outreach(self, governor):
        errors = []

        def worker(cid: str):
            try:
                governor.check_outreach(
                    contact_id=cid,
                    channel="email",
                    message_metadata={"has_unsubscribe_link": True, "has_physical_address": True},
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(f"thread-{i}",))
            for i in range(30)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ---------------------------------------------------------------------------
# OutreachCampaignPlan dataclass
# ---------------------------------------------------------------------------

class TestOutreachCampaignPlan:
    def test_default_compliance_flags(self):
        plan = OutreachCampaignPlan()
        assert plan.enforce_can_spam is True
        assert plan.enforce_tcpa is True
        assert plan.enforce_gdpr is True
        assert plan.enforce_casl is True
        assert plan.enforce_ccpa is True

    def test_to_dict_has_required_keys(self):
        plan = OutreachCampaignPlan(name="Test", vertical="saas", channels=["email"])
        d = plan.to_dict()
        for key in ["plan_id", "name", "vertical", "channels", "status",
                    "cooldown_days_prospect", "cooldown_days_customer",
                    "enforce_can_spam", "enforce_tcpa", "enforce_gdpr"]:
            assert key in d

    def test_to_dict_prospect_count_not_ids(self):
        plan = OutreachCampaignPlan(prospect_ids=["a", "b", "c"])
        d = plan.to_dict()
        assert "prospect_count" in d
        assert d["prospect_count"] == 3
        assert "prospect_ids" not in d


# ---------------------------------------------------------------------------
# OutreachCampaignPlanner
# ---------------------------------------------------------------------------

class TestOutreachCampaignPlanner:
    def test_create_campaign_plan_valid(self, planner):
        plan = planner.create_campaign_plan(
            name="SaaS Q1",
            vertical="saas",
            channels=["email", "linkedin"],
            prospect_ids=["p1", "p2"],
        )
        assert plan.plan_id
        assert plan.vertical == "saas"
        assert plan.channels == ["email", "linkedin"]

    def test_create_campaign_plan_invalid_vertical(self, planner):
        with pytest.raises(ValueError, match="vertical"):
            planner.create_campaign_plan(
                name="Bad",
                vertical="unknown_vertical",
                channels=["email"],
                prospect_ids=[],
            )

    def test_create_campaign_plan_invalid_channel(self, planner):
        with pytest.raises(ValueError, match="channel"):
            planner.create_campaign_plan(
                name="Bad",
                vertical="saas",
                channels=["fax"],
                prospect_ids=[],
            )

    def test_get_plan_returns_none_for_missing(self, planner):
        assert planner.get_plan("nonexistent-id") is None

    def test_get_plan_round_trip(self, planner):
        plan = planner.create_campaign_plan(
            name="Test", vertical="ecommerce", channels=["email"], prospect_ids=[]
        )
        retrieved = planner.get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    def test_build_daily_schedule_respects_max_per_day(self, planner):
        # Create 10 prospects but cap at 3 per day
        prospect_ids = [f"sched-{i}" for i in range(10)]
        plan = planner.create_campaign_plan(
            name="Capped",
            vertical="saas",
            channels=["email"],
            prospect_ids=prospect_ids,
            max_outreach_per_day=3,
        )
        contact_metadata = {
            pid: {
                "has_explicit_consent": False,
                "is_customer": False,
                "contact_region": "",
                "message_metadata": {
                    "has_unsubscribe_link": True,
                    "has_physical_address": True,
                },
            }
            for pid in prospect_ids
        }
        schedule = planner.build_daily_outreach_schedule(plan.plan_id, contact_metadata)
        assert len(schedule["scheduled"]) <= 3

    def test_build_daily_schedule_skips_suppressed(self, planner):
        planner._governor._suppression.suppress("suppressed-001", "s@example.com")
        plan = planner.create_campaign_plan(
            name="Skip DNC",
            vertical="saas",
            channels=["email"],
            prospect_ids=["suppressed-001"],
        )
        contact_metadata = {
            "suppressed-001": {
                "message_metadata": {"has_unsubscribe_link": True, "has_physical_address": True},
            }
        }
        schedule = planner.build_daily_outreach_schedule(plan.plan_id, contact_metadata)
        assert "suppressed-001" not in schedule["scheduled"]
        assert any(s["contact_id"] == "suppressed-001" for s in schedule["skipped"])

    def test_build_daily_schedule_skips_eu_without_consent(self, planner):
        plan = planner.create_campaign_plan(
            name="EU No Consent",
            vertical="saas",
            channels=["email"],
            prospect_ids=["eu-no-consent"],
        )
        contact_metadata = {
            "eu-no-consent": {
                "contact_region": "EU",
                "has_explicit_consent": False,
                "message_metadata": {"has_unsubscribe_link": True, "has_physical_address": True},
            }
        }
        schedule = planner.build_daily_outreach_schedule(plan.plan_id, contact_metadata)
        assert "eu-no-consent" not in schedule["scheduled"]

    def test_build_daily_schedule_includes_eu_with_consent(self, planner):
        plan = planner.create_campaign_plan(
            name="EU With Consent",
            vertical="saas",
            channels=["email"],
            prospect_ids=["eu-with-consent"],
        )
        contact_metadata = {
            "eu-with-consent": {
                "contact_region": "EU",
                "has_explicit_consent": True,
                "message_metadata": {"has_unsubscribe_link": True, "has_physical_address": True},
            }
        }
        schedule = planner.build_daily_outreach_schedule(plan.plan_id, contact_metadata)
        assert "eu-with-consent" in schedule["scheduled"]

    def test_build_daily_schedule_plan_not_found(self, planner):
        with pytest.raises(ValueError, match="not found"):
            planner.build_daily_outreach_schedule("nonexistent")

    def test_vertical_constraints_healthcare(self, planner):
        constraints = planner.get_vertical_constraints("healthcare")
        assert constraints.get("hipaa_required") is True
        assert "email" in constraints["channels_allowed"]

    def test_vertical_constraints_unknown_falls_back_to_base(self, planner):
        constraints = planner.get_vertical_constraints("unknown_vertical")
        assert "channels_allowed" in constraints
        assert "can_spam_required" in constraints

    def test_business_type_verticals_coverage(self):
        assert "saas" in BUSINESS_TYPE_VERTICALS
        assert "healthcare" in BUSINESS_TYPE_VERTICALS
        assert "construction" in BUSINESS_TYPE_VERTICALS
        assert len(BUSINESS_TYPE_VERTICALS) >= 12

    def test_get_status(self, planner):
        planner.create_campaign_plan("S1", "saas", ["email"], [])
        status = planner.get_status()
        assert status["plan_count"] == 1
        assert "governor_status" in status
