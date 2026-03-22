"""Tests for grants Pydantic v2 models."""

import pytest
from datetime import datetime, timezone

from src.billing.grants.models import (
    Application,
    ApplicationStatus,
    EligibilityResult,
    Grant,
    GrantSession,
    GrantTrack,
    HitlTask,
    PrereqStatus,
    Prerequisite,
    ProgramType,
    TaskType,
)


class TestProgramType:
    def test_all_values_exist(self):
        assert ProgramType.federal_tax_credit == "federal_tax_credit"
        assert ProgramType.federal_grant == "federal_grant"
        assert ProgramType.sba_loan == "sba_loan"
        assert ProgramType.usda_program == "usda_program"
        assert ProgramType.state_incentive == "state_incentive"
        assert ProgramType.utility_program == "utility_program"
        assert ProgramType.pace_financing == "pace_financing"
        assert ProgramType.green_bank == "green_bank"
        assert ProgramType.espc == "espc"
        assert ProgramType.rd_tax_credit == "rd_tax_credit"

    def test_is_str_enum(self):
        assert isinstance(ProgramType.federal_grant, str)


class TestGrantTrack:
    def test_values(self):
        assert GrantTrack.track_a_murphy == "track_a_murphy"
        assert GrantTrack.track_b_customer == "track_b_customer"


class TestApplicationStatus:
    def test_all_values(self):
        for value in ("draft", "in_review", "submitted", "accepted", "rejected"):
            assert ApplicationStatus(value) is not None


class TestTaskType:
    def test_all_values(self):
        for value in ("auto_filled", "needs_review", "blocked_human_required", "waiting_on_external"):
            assert TaskType(value) is not None


class TestPrereqStatus:
    def test_all_values(self):
        for value in ("not_started", "in_progress", "waiting_on_external", "completed"):
            assert PrereqStatus(value) is not None


class TestGrantModel:
    def test_minimal_grant(self):
        g = Grant(
            id="test_grant",
            name="Test Grant",
            program_type=ProgramType.federal_grant,
            agency="Test Agency",
            description="A test grant",
            min_amount=1000.0,
            max_amount=50000.0,
        )
        assert g.id == "test_grant"
        assert g.eligible_states == []
        assert g.eligible_entity_types == []
        assert g.eligible_verticals == []
        assert g.requirements == []
        assert g.tags == []
        assert g.longevity_years == 5

    def test_full_grant(self):
        g = Grant(
            id="full_grant",
            name="Full Grant",
            program_type=ProgramType.state_incentive,
            agency="State Agency",
            description="A full grant",
            min_amount=500.0,
            max_amount=100000.0,
            eligible_entity_types=["small_business"],
            eligible_verticals=["energy_management"],
            eligible_states=["CA", "OR"],
            application_url="https://example.com",
            deadline_pattern="Annual",
            longevity_years=10,
            requirements=["Requirement 1"],
            tags=["tag1"],
        )
        assert g.eligible_states == ["CA", "OR"]
        assert g.longevity_years == 10

    def test_serialization(self):
        g = Grant(
            id="ser_grant",
            name="Serialize Test",
            program_type=ProgramType.sba_loan,
            agency="SBA",
            description="desc",
            min_amount=1.0,
            max_amount=100.0,
        )
        data = g.model_dump()
        assert data["id"] == "ser_grant"
        assert data["program_type"] == "sba_loan"


class TestGrantSession:
    def test_defaults(self):
        now = datetime.now(timezone.utc)
        s = GrantSession(
            session_id="sess-1",
            tenant_id="tenant-a",
            track=GrantTrack.track_b_customer,
            created_at=now,
            updated_at=now,
        )
        assert s.profile_data == {}
        assert s.completed_tasks == []
        assert s.pending_tasks == []

    def test_with_profile_data(self):
        now = datetime.now(timezone.utc)
        s = GrantSession(
            session_id="sess-2",
            tenant_id="tenant-b",
            track=GrantTrack.track_a_murphy,
            created_at=now,
            updated_at=now,
            profile_data={"state": "OR"},
        )
        assert s.profile_data["state"] == "OR"


class TestApplication:
    def test_defaults(self):
        app = Application(
            application_id="app-1",
            grant_id="sbir_phase1",
            session_id="sess-1",
        )
        assert app.status == ApplicationStatus.draft
        assert app.form_data == {}
        assert app.confidence_score == 0.0
        assert app.hitl_notes == ""
        assert app.submitted_at is None


class TestHitlTask:
    def test_defaults(self):
        t = HitlTask(
            task_id="task-1",
            session_id="sess-1",
            task_type=TaskType.needs_review,
            title="Review",
            description="Please review this.",
        )
        assert t.status == "pending"
        assert t.priority == 50
        assert t.estimated_minutes == 30
        assert t.depends_on == []
        assert t.form_fields == {}


class TestPrerequisite:
    def test_defaults(self):
        p = Prerequisite(
            prereq_id="ein",
            name="EIN",
            description="Get EIN",
            verification_url="https://irs.gov",
        )
        assert p.status == PrereqStatus.not_started
        assert p.blocks == []
        assert p.estimated_days == 1


class TestEligibilityResult:
    def test_basic(self):
        r = EligibilityResult(
            grant_id="sbir_phase1",
            eligible=True,
            confidence=0.85,
            reasons=["State match"],
            estimated_value=100000.0,
            action_items=["Register in SAM.gov"],
        )
        assert r.eligible is True
        assert r.confidence == 0.85
        data = r.model_dump()
        assert data["grant_id"] == "sbir_phase1"
