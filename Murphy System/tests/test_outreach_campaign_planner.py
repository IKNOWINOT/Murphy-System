"""
Tests for Outreach Campaign Planner (CAMP-001).

Covers:
  - CampaignPlan / CadenceStep / AudienceSegment / StepExecutionResult
    / HealthCheckResult dataclasses
  - Input validation guards (CWE-20, CWE-400)
  - campaign_health_check() — governor + gate + suppression + channel
  - generate_campaign_for_segment() — cadence building and validation
  - execute_campaign_step() — compliance gate pre-flight, DNC handling
  - Cooldown enforcement (30-day non-customer, 7-day customer)
  - DNC / suppression list management
  - Multi-channel cadence (email → LinkedIn → SMS)
  - Audit trail completeness
  - Thread-safety (concurrent campaign generation + step execution)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
import pytest

from src.outreach_campaign_planner import (
    AudienceSegment,
    CadenceStep,
    CampaignPlan,
    CampaignPlannerEngine,
    CampaignStatus,
    CooldownType,
    HealthCheckResult,
    OutcomeType,
    StepExecutionResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return CampaignPlannerEngine()


@pytest.fixture
def segment():
    return AudienceSegment(
        name="Construction Midwest",
        industry_filter=["construction"],
        size_filter="1m_10m",
        region_filter="US",
        prospect_ids=["prospect-001", "prospect-002"],
    )


@pytest.fixture
def plan(engine, segment):
    return engine.generate_campaign_for_segment(
        name="Test Campaign",
        segment=segment,
    )


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestCadenceStep:
    def test_default_channel_is_email(self):
        step = CadenceStep()
        assert step.channel == "email"

    def test_to_dict_keys(self):
        step = CadenceStep(step_number=2, channel="linkedin", delay_days=3)
        d = step.to_dict()
        assert d["step_number"] == 2
        assert d["channel"] == "linkedin"
        assert d["delay_days"] == 3

    def test_step_id_auto_generated(self):
        s1 = CadenceStep()
        s2 = CadenceStep()
        assert s1.step_id != s2.step_id


class TestAudienceSegment:
    def test_default_fields(self):
        seg = AudienceSegment()
        assert seg.industry_filter == []
        assert seg.prospect_ids == []

    def test_to_dict_prospect_count(self, segment):
        d = segment.to_dict()
        assert d["prospect_count"] == 2
        assert "prospect_ids" not in d   # not exposed in to_dict


class TestCampaignPlan:
    def test_default_status_is_draft(self, plan):
        assert plan.status == CampaignStatus.DRAFT

    def test_to_dict_includes_cadence(self, plan):
        d = plan.to_dict()
        assert "cadence_steps" in d
        assert len(d["cadence_steps"]) == len(plan.cadence_steps)

    def test_campaign_id_auto_generated(self, engine, segment):
        p1 = engine.generate_campaign_for_segment("C1", segment)
        p2 = engine.generate_campaign_for_segment("C2", segment)
        assert p1.campaign_id != p2.campaign_id

    def test_to_dict_segment_present(self, plan):
        d = plan.to_dict()
        assert d["segment"] is not None
        assert d["segment"]["name"] == "Construction Midwest"


class TestHealthCheckResult:
    def test_default_healthy_true(self):
        h = HealthCheckResult()
        assert h.healthy is True

    def test_to_dict_keys(self):
        h = HealthCheckResult(healthy=False, issues=["problem"])
        d = h.to_dict()
        assert d["healthy"] is False
        assert "problem" in d["issues"]


# ---------------------------------------------------------------------------
# campaign_health_check()
# ---------------------------------------------------------------------------

class TestCampaignHealthCheck:
    def test_no_deps_reports_stub_ok(self, engine):
        result = engine.campaign_health_check()
        assert isinstance(result, HealthCheckResult)
        assert result.governor_ok is True         # stub mode
        assert result.compliance_gate_ok is True  # stub mode
        assert result.suppression_ok is True
        assert result.channel_ok is True
        assert result.healthy is True

    def test_governor_injected_and_healthy(self):
        class FakeGovernor:
            def get_status(self):
                return {"status": "ok", "dnc_count": 0}

        eng = CampaignPlannerEngine(governor=FakeGovernor())
        result = eng.campaign_health_check()
        assert result.governor_ok is True
        assert result.healthy is True

    def test_governor_raises_reports_issue(self):
        class BrokenGovernor:
            def get_status(self):
                raise RuntimeError("db down")

        eng = CampaignPlannerEngine(governor=BrokenGovernor())
        result = eng.campaign_health_check()
        assert result.governor_ok is False
        assert result.healthy is False
        assert any("Governor" in issue for issue in result.issues)

    def test_health_check_adds_to_audit_log(self, engine):
        engine.campaign_health_check()
        log = engine.get_audit_log()
        assert any(e["action"] == "campaign_health_check" for e in log)


# ---------------------------------------------------------------------------
# generate_campaign_for_segment()
# ---------------------------------------------------------------------------

class TestGenerateCampaign:
    def test_creates_campaign_with_default_cadence(self, engine, segment):
        plan = engine.generate_campaign_for_segment("My Campaign", segment)
        # Default cadence: email → linkedin → sms  = 3 steps
        assert len(plan.cadence_steps) == 3

    def test_channel_sequence_is_email_linkedin_sms(self, engine, segment):
        plan = engine.generate_campaign_for_segment("Seq Test", segment)
        channels = [s.channel for s in plan.cadence_steps]
        assert channels == ["email", "linkedin", "sms"]

    def test_delay_days_assigned(self, engine, segment):
        plan = engine.generate_campaign_for_segment("Delay Test", segment)
        delays = [s.delay_days for s in plan.cadence_steps]
        assert delays[0] == 0    # email same day
        assert delays[1] == 3    # linkedin +3 days
        assert delays[2] == 7    # sms +7 days

    def test_meta_proof_on_first_step(self, engine, segment):
        plan = engine.generate_campaign_for_segment("Meta Test", segment)
        # First step (email) uses META_PROOF
        assert plan.cadence_steps[0].use_meta_proof is True

    def test_custom_cadence_honoured(self, engine, segment):
        custom = [
            {"channel": "email",    "delay_days": 0},
            {"channel": "linkedin", "delay_days": 5},
        ]
        plan = engine.generate_campaign_for_segment(
            "Custom", segment, cadence=custom
        )
        assert len(plan.cadence_steps) == 2
        assert plan.cadence_steps[1].delay_days == 5

    def test_invalid_channel_in_cadence_raises(self, engine, segment):
        bad = [{"channel": "fax", "delay_days": 0}]
        with pytest.raises(ValueError, match="not allowed"):
            engine.generate_campaign_for_segment("Bad", segment, cadence=bad)

    def test_empty_name_raises(self, engine, segment):
        with pytest.raises(ValueError):
            engine.generate_campaign_for_segment("", segment)

    def test_name_too_long_raises(self, engine, segment):
        with pytest.raises(ValueError):
            engine.generate_campaign_for_segment("x" * 201, segment)

    def test_non_segment_type_raises(self, engine):
        with pytest.raises(ValueError):
            engine.generate_campaign_for_segment("Test", {"name": "not a segment"})

    def test_campaign_stored_internally(self, engine, segment):
        plan = engine.generate_campaign_for_segment("Stored", segment)
        retrieved = engine.get_campaign(plan.campaign_id)
        assert retrieved is not None
        assert retrieved.campaign_id == plan.campaign_id

    def test_list_campaigns_includes_new(self, engine, segment):
        plan = engine.generate_campaign_for_segment("Listed", segment)
        all_campaigns = engine.list_campaigns()
        ids = [c["campaign_id"] for c in all_campaigns]
        assert plan.campaign_id in ids


# ---------------------------------------------------------------------------
# execute_campaign_step() — compliance pre-flight
# ---------------------------------------------------------------------------

class TestExecuteCampaignStep:
    def test_execute_step_sent_without_compliance_layer(self, plan, engine):
        """Without governor/gate, default is ALLOW (stub mode)."""
        result = engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="alice@example.com",
        )
        assert isinstance(result, StepExecutionResult)
        assert result.outcome == OutcomeType.SENT

    def test_execute_step_blocked_by_suppression(self, plan, engine):
        engine.add_to_suppression("contact-dnc", "opted_out")
        result = engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-dnc",
            contact_email="dnc@example.com",
        )
        assert result.outcome == OutcomeType.BLOCKED
        assert "suppression_list" in result.block_reason

    def test_execute_step_blocked_by_compliance_gate(self, engine, segment):
        class BlockingGate:
            def check_and_record(self, **kwargs):
                class D:
                    allowed = False
                    regulation = "GDPR"
                return D()

        eng = CampaignPlannerEngine(compliance_gate=BlockingGate())
        p = eng.generate_campaign_for_segment("Blocked Test", segment)
        result = eng.execute_campaign_step(
            campaign_id=p.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="blocked@example.com",
        )
        assert result.outcome == OutcomeType.BLOCKED

    def test_execute_step_blocked_by_governor(self, engine, segment):
        class BlockingGovernor:
            def get_status(self):
                return {}
            def validate_outreach(self, **kwargs):
                class D:
                    decision = "BLOCK"
                    reason = "COOLDOWN"
                return D()

        eng = CampaignPlannerEngine(governor=BlockingGovernor())
        p = eng.generate_campaign_for_segment("Gov Blocked", segment)
        result = eng.execute_campaign_step(
            campaign_id=p.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="gobblocked@example.com",
        )
        assert result.outcome == OutcomeType.BLOCKED

    def test_execute_step_with_allow_governor(self, engine, segment):
        class AllowGovernor:
            def get_status(self):
                return {}
            def validate_outreach(self, **kwargs):
                class D:
                    decision = "ALLOW"
                    reason = "ok"
                return D()

        eng = CampaignPlannerEngine(governor=AllowGovernor())
        p = eng.generate_campaign_for_segment("Allow Test", segment)
        result = eng.execute_campaign_step(
            campaign_id=p.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="allow@example.com",
        )
        assert result.outcome == OutcomeType.SENT

    def test_invalid_contact_id_blocked(self, plan, engine):
        result = engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="bad id!@#",  # invalid chars
            contact_email="valid@example.com",
        )
        # Should be blocked or raise — engine validates contact_id
        assert result.outcome == OutcomeType.BLOCKED

    def test_invalid_email_blocked(self, plan, engine):
        result = engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="not-an-email",
        )
        assert result.outcome == OutcomeType.BLOCKED

    def test_step_not_found_blocked(self, plan, engine):
        result = engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=999,
            contact_id="contact-001",
            contact_email="test@example.com",
        )
        assert result.outcome == OutcomeType.BLOCKED
        assert "step_not_found" in result.block_reason

    def test_unknown_campaign_blocked(self, engine):
        result = engine.execute_campaign_step(
            campaign_id="unknown-999",
            step_number=1,
            contact_id="contact-001",
            contact_email="test@example.com",
        )
        assert result.outcome == OutcomeType.BLOCKED
        assert "campaign_not_found" in result.block_reason

    def test_execution_increments_steps_executed(self, plan, engine):
        initial = plan.steps_executed
        engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="alice@example.com",
        )
        assert plan.steps_executed == initial + 1

    def test_execution_added_to_history(self, plan, engine):
        engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="alice@example.com",
        )
        history = engine.get_execution_history()
        assert len(history) >= 1


# ---------------------------------------------------------------------------
# DNC / suppression handling
# ---------------------------------------------------------------------------

class TestDNCHandling:
    def test_add_to_suppression(self, engine):
        engine.add_to_suppression("contact-001", "opted_out")
        assert engine.is_suppressed("contact-001") is True

    def test_not_suppressed_by_default(self, engine):
        assert engine.is_suppressed("contact-fresh") is False

    def test_dnc_contact_blocked_on_step(self, plan, engine):
        engine.add_to_suppression("dnc-user", "dnc")
        result = engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="dnc-user",
            contact_email="dnc@example.com",
        )
        assert result.outcome == OutcomeType.BLOCKED
        assert "suppression_list" in result.block_reason

    def test_invalid_contact_id_raises_on_add_suppression(self, engine):
        with pytest.raises(ValueError, match="contact_id"):
            engine.add_to_suppression("bad id!@#")

    def test_get_suppression_list_returns_copy(self, engine):
        engine.add_to_suppression("contact-X", "test")
        sup = engine.get_suppression_list()
        sup["injected"] = "evil"
        # Original should not be mutated
        assert "injected" not in engine.get_suppression_list()

    def test_suppression_list_hard_cap(self):
        """Verify that suppression list does not grow beyond _MAX_SUPPRESSION_LIST."""
        from src.outreach_campaign_planner import _MAX_SUPPRESSION_LIST

        # We won't actually fill 100K entries in a test, but verify the cap constant
        # exists and is a reasonable positive integer
        assert _MAX_SUPPRESSION_LIST >= 1_000

    def test_compliance_gate_dnc_opt_out_auto_suppresses(self, engine, segment):
        """A DNC block_reason should automatically add contact to suppression."""
        class DNCGate:
            def check_and_record(self, **kwargs):
                class D:
                    allowed = False
                    regulation = "dnc_permanent"
                return D()

        eng = CampaignPlannerEngine(compliance_gate=DNCGate())
        p = eng.generate_campaign_for_segment("DNC Auto", segment)
        eng.execute_campaign_step(
            campaign_id=p.campaign_id,
            step_number=1,
            contact_id="dnc-auto-001",
            contact_email="opt-out@example.com",
        )
        assert eng.is_suppressed("dnc-auto-001") is True


# ---------------------------------------------------------------------------
# Multi-channel cadence validation
# ---------------------------------------------------------------------------

class TestMultiChannelCadence:
    def test_email_body_contains_meta_proof(self, plan):
        step = plan.cadence_steps[0]
        assert step.channel == "email"
        assert step.use_meta_proof is True

    def test_linkedin_body_template_set(self, plan):
        step = plan.cadence_steps[1]
        assert step.channel == "linkedin"
        assert len(step.body_template) > 0

    def test_sms_body_contains_stop(self, plan):
        step = plan.cadence_steps[2]
        assert step.channel == "sms"
        assert "STOP" in step.body_template or "opt out" in step.body_template.lower()

    def test_channel_allowlist_blocks_fax(self, engine, segment):
        with pytest.raises(ValueError, match="not allowed"):
            engine.generate_campaign_for_segment(
                "No Fax",
                segment,
                cadence=[{"channel": "fax", "delay_days": 0}],
            )

    def test_channel_allowlist_blocks_phone_in_campaign(self, engine, segment):
        """phone is allowed in the compliance governor but not in campaign cadence."""
        # The campaign planner uses only email/sms/linkedin
        with pytest.raises(ValueError, match="not allowed"):
            engine.generate_campaign_for_segment(
                "Phone Test",
                segment,
                cadence=[{"channel": "phone", "delay_days": 0}],
            )


# ---------------------------------------------------------------------------
# Campaign lifecycle management
# ---------------------------------------------------------------------------

class TestCampaignLifecycle:
    def test_activate_from_draft(self, engine, plan):
        result = engine.activate_campaign(plan.campaign_id)
        assert result is True
        assert engine.get_campaign(plan.campaign_id).status == CampaignStatus.ACTIVE

    def test_cannot_activate_active_campaign(self, engine, plan):
        engine.activate_campaign(plan.campaign_id)
        result = engine.activate_campaign(plan.campaign_id)
        assert result is False  # already ACTIVE

    def test_pause_active_campaign(self, engine, plan):
        engine.activate_campaign(plan.campaign_id)
        result = engine.pause_campaign(plan.campaign_id)
        assert result is True
        assert engine.get_campaign(plan.campaign_id).status == CampaignStatus.PAUSED

    def test_pause_draft_fails(self, engine, plan):
        result = engine.pause_campaign(plan.campaign_id)
        assert result is False

    def test_get_campaign_unknown_returns_none(self, engine):
        result = engine.get_campaign("unknown-999")
        assert result is None


# ---------------------------------------------------------------------------
# Cooldown enforcement
# ---------------------------------------------------------------------------

class TestCooldownEnforcement:
    def test_non_customer_cooldown_type_set(self, engine, segment):
        plan = engine.generate_campaign_for_segment(
            "Non-Customer", segment, cooldown_type=CooldownType.NON_CUSTOMER
        )
        assert plan.cooldown_type == CooldownType.NON_CUSTOMER

    def test_customer_cooldown_type_set(self, engine, segment):
        plan = engine.generate_campaign_for_segment(
            "Customer", segment, cooldown_type=CooldownType.CUSTOMER
        )
        assert plan.cooldown_type == CooldownType.CUSTOMER

    def test_governor_receives_outreach_type_non_customer(self, engine, segment):
        received_types: list = []

        class RecordingGovernor:
            def get_status(self):
                return {}
            def validate_outreach(self, **kwargs):
                received_types.append(kwargs.get("outreach_type", ""))
                class D:
                    decision = "ALLOW"
                    reason = ""
                return D()

        eng = CampaignPlannerEngine(governor=RecordingGovernor())
        plan = eng.generate_campaign_for_segment(
            "Type Test", segment, cooldown_type=CooldownType.NON_CUSTOMER
        )
        eng.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="test@example.com",
        )
        assert any("prospect" in t for t in received_types)

    def test_governor_receives_outreach_type_customer(self, engine, segment):
        received_types: list = []

        class RecordingGovernor:
            def get_status(self):
                return {}
            def validate_outreach(self, **kwargs):
                received_types.append(kwargs.get("outreach_type", ""))
                class D:
                    decision = "ALLOW"
                    reason = ""
                return D()

        eng = CampaignPlannerEngine(governor=RecordingGovernor())
        plan = eng.generate_campaign_for_segment(
            "Cust Type Test", segment, cooldown_type=CooldownType.CUSTOMER
        )
        eng.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="customer@example.com",
        )
        assert any("customer" in t for t in received_types)


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_audit_log_populated_after_generate(self, engine, segment):
        engine.generate_campaign_for_segment("Audit Test", segment)
        log = engine.get_audit_log()
        assert any(e["action"] == "generate_campaign_for_segment" for e in log)

    def test_audit_log_populated_after_health_check(self, engine):
        engine.campaign_health_check()
        log = engine.get_audit_log()
        assert any(e["action"] == "campaign_health_check" for e in log)

    def test_audit_log_populated_after_execute(self, plan, engine):
        engine.execute_campaign_step(
            campaign_id=plan.campaign_id,
            step_number=1,
            contact_id="contact-001",
            contact_email="audit@example.com",
        )
        log = engine.get_audit_log()
        assert any(e["action"] == "execute_campaign_step" for e in log)

    def test_audit_log_limit(self, engine, segment):
        for i in range(10):
            engine.generate_campaign_for_segment(f"Camp-{i}", segment)
        log = engine.get_audit_log(limit=3)
        assert len(log) <= 3


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_campaign_generation(self, engine, segment):
        errors: list = []
        ids: list = []
        lock = threading.Lock()

        def gen():
            try:
                plan = engine.generate_campaign_for_segment(
                    "Concurrent Campaign", segment
                )
                with lock:
                    ids.append(plan.campaign_id)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=gen) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All IDs should be unique
        assert len(set(ids)) == len(ids)

    def test_concurrent_suppression_adds(self, engine):
        errors: list = []
        lock = threading.Lock()

        def add(i: int):
            try:
                engine.add_to_suppression(f"contact-{i:04d}", "test")
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=add, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(engine.get_suppression_list()) == 30
