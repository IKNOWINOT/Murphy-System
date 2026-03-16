"""Tests for the Onboarding Team Pipeline module."""

import os

import pytest
from src.onboarding_team_pipeline import (
    OnboardingTeamPipeline,
    TeamMember,
    TeamDiscoveryResult,
    RosettaGenerationResult,
)


@pytest.fixture
def pipeline():
    return OnboardingTeamPipeline(
        shadow_integration=None,
        rosetta_builder=None,
        living_documents={},
    )


class TestExtractTeamMembers:
    def test_parses_have_role_named_format(self, pipeline):
        msg = "I have a floor manager named Jake"
        result = pipeline.extract_team_members(msg)
        names = [m.name for m in result.members]
        assert "Jake" in names
        jake = next(m for m in result.members if m.name == "Jake")
        assert "floor manager" in jake.role.lower() or "manager" in jake.role.lower()

    def test_parses_accountant_sarah_format(self, pipeline):
        msg = "Our accountant Sarah handles invoicing and billing"
        result = pipeline.extract_team_members(msg)
        names = [m.name for m in result.members]
        assert "Sarah" in names

    def test_parses_name_is_our_role_format(self, pipeline):
        msg = "Jake is our floor manager"
        result = pipeline.extract_team_members(msg)
        names = [m.name for m in result.members]
        assert "Jake" in names

    def test_handles_multiple_members(self, pipeline):
        msg = (
            "I have a floor manager named Jake and our accountant Sarah handles invoicing. "
            "Mike is our sales rep."
        )
        result = pipeline.extract_team_members(msg)
        names = [m.name for m in result.members]
        assert len(names) >= 2

    def test_empty_message_returns_no_members(self, pipeline):
        result = pipeline.extract_team_members("Hello, how are you?")
        assert result.members == [] or len(result.members) == 0

    def test_confidence_increases_with_more_members(self, pipeline):
        msg1 = "Jake is our manager"
        msg2 = "Jake is our manager and Sarah handles invoicing"
        r1 = pipeline.extract_team_members(msg1)
        r2 = pipeline.extract_team_members(msg2)
        assert r2.confidence >= r1.confidence

    def test_org_structure_populated(self, pipeline):
        msg = "Jake is our floor manager"
        result = pipeline.extract_team_members(msg)
        assert isinstance(result.org_structure, dict)


class TestGenerateRosettaForMember:
    def test_generates_shadow_agent_id_and_rosetta_doc_id(self, pipeline):
        member = TeamMember(
            name="Jake",
            role="Floor Manager",
            responsibilities=["supervising staff", "coordinating schedules"],
            department="Operations",
            automation_scope=["workflow_coordination", "scheduling"],
        )
        result = pipeline.generate_rosetta_for_member(member, {})
        assert result.shadow_agent_id.startswith("shadow-jake-")
        assert result.rosetta_doc_id.startswith("rosetta-jake-")
        assert result.hitl_model == "shadow"

    def test_generates_meaningful_summary(self, pipeline):
        member = TeamMember(
            name="Sarah",
            role="Accountant",
            responsibilities=["invoicing", "billing"],
            department="Finance",
            automation_scope=["invoice_processing"],
        )
        result = pipeline.generate_rosetta_for_member(member, {})
        assert "Sarah" in result.rosetta_summary
        assert result.domain in ["finance", "operations", "general_operations",
                                  "finance", "sales", "human_resources"]

    def test_automation_scope_populated(self, pipeline):
        member = TeamMember(
            name="Mike",
            role="Sales Rep",
            responsibilities=["lead generation"],
            department="Sales",
        )
        result = pipeline.generate_rosetta_for_member(member, {})
        assert isinstance(result.automation_scope, list)
        assert len(result.automation_scope) > 0


class TestBuildHitlSummary:
    def test_includes_all_members(self, pipeline):
        members = [
            TeamMember(name="Jake", role="Floor Manager", department="Operations"),
            TeamMember(name="Sarah", role="Accountant", department="Finance"),
        ]
        results = [
            pipeline.generate_rosetta_for_member(m, {}) for m in members
        ]
        summary = pipeline.build_hitl_summary(results)
        assert "Jake" in summary
        assert "Sarah" in summary
        assert "Does this sound close?" in summary

    def test_empty_results_returns_helpful_message(self, pipeline):
        summary = pipeline.build_hitl_summary([])
        assert len(summary) > 0

    def test_summary_starts_with_header(self, pipeline):
        member = TeamMember(name="Jake", role="Manager", department="Operations")
        result = pipeline.generate_rosetta_for_member(member, {})
        summary = pipeline.build_hitl_summary([result])
        assert "agentic team" in summary.lower()


class TestConfirmationCallbacks:
    def test_on_confirmed_does_not_raise(self, pipeline):
        member = TeamMember(name="Jake", role="Manager", department="Operations")
        result = pipeline.generate_rosetta_for_member(member, {})
        pipeline.on_confirmed([result])  # should not raise

    def test_on_confirmed_solidifies_docs_in_living_documents(self):
        class MockDoc:
            def __init__(self):
                self.solidified = False
            def solidify(self):
                self.solidified = True

        doc = MockDoc()
        doc_id = "rosetta-test-123"
        p = OnboardingTeamPipeline(living_documents={doc_id: doc})
        member = TeamMember(name="Jake", role="Manager", department="Operations")
        result = RosettaGenerationResult(
            member=member,
            shadow_agent_id="shadow-jake-abc",
            rosetta_doc_id=doc_id,
            rosetta_summary="Jake (Manager, Operations): ...",
            domain="operations",
            automation_scope=["workflow_coordination"],
        )
        p.on_confirmed([result])
        assert doc.solidified is True

    def test_on_rejected_does_not_solidify(self):
        class MockDoc:
            def __init__(self):
                self.solidified = False
            def solidify(self):
                self.solidified = True

        doc = MockDoc()
        doc_id = "rosetta-test-456"
        p = OnboardingTeamPipeline(living_documents={doc_id: doc})
        member = TeamMember(name="Sarah", role="Accountant", department="Finance")
        result = RosettaGenerationResult(
            member=member,
            shadow_agent_id="shadow-sarah-abc",
            rosetta_doc_id=doc_id,
            rosetta_summary="Sarah (Accountant, Finance): ...",
            domain="finance",
            automation_scope=["invoice_processing"],
        )
        p.on_rejected([result], feedback="Wrong scope")
        assert doc.solidified is False
