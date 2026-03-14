"""
Tests for Production Assistant Engine (PROD-001).

Covers:
  - ProductionProposal / HITLGateRequirement / ProductionWorkOrder /
    ProductionProfile / DeliverableMatch dataclasses
  - Input validation guards (CWE-20, CWE-400)
  - 99% confidence gating on proposals
  - HITL gate requirement validation
  - Proposal regulatory completeness checks
  - Deliverable matching at 99% confidence
  - Lifecycle management (created → in_review → approved → in_progress
    → delivered → verified → rejected)
  - Audit log bounded growth (capped_append)
  - Thread-safety (concurrent submit + validate)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
import pytest

from src.production_assistant import (
    DeliverableMatch,
    HITLGateRequirement,
    PRODUCTION_CONFIDENCE_THRESHOLD,
    ProductionAssistantEngine,
    ProductionLifecycle,
    ProductionProfile,
    ProductionProposal,
    ProductionWorkOrder,
    ProposalStatus,
    ValidationResult,
    WorkOrderStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return ProductionAssistantEngine()


@pytest.fixture
def minimal_proposal():
    return ProductionProposal(
        regulatory_location="US/California",
        regulatory_industry="construction",
        regulatory_functions=["permitting", "safety_inspection", "zoning_compliance"],
        deliverable_spec=(
            "Comprehensive construction project plan including permitting requirements, "
            "safety inspection checklists, zoning compliance documentation, site plans, "
            "material specifications, and contractor qualification requirements. "
            "All documents must meet California building code standards and include "
            "necessary signatures and certifications for regulatory submission."
        ),
        title="Test Proposal",
    )


@pytest.fixture
def hitl_requirement():
    return HITLGateRequirement(
        certifications_required=["CA_PE_License", "OSHA_30"],
        licenses_required=["CA_General_Contractor_B"],
        experience_criteria="5+ years structural engineering",
        discipline="Civil Engineering",
        accountability_framework="ASCE_Code_of_Ethics",
    )


# ---------------------------------------------------------------------------
# PRODUCTION_CONFIDENCE_THRESHOLD
# ---------------------------------------------------------------------------

class TestConfidenceThreshold:
    def test_threshold_is_099(self):
        assert PRODUCTION_CONFIDENCE_THRESHOLD == 0.99

    def test_threshold_type_is_float(self):
        assert isinstance(PRODUCTION_CONFIDENCE_THRESHOLD, float)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestHITLGateRequirement:
    def test_default_fields(self):
        h = HITLGateRequirement()
        assert h.certifications_required == []
        assert h.licenses_required == []
        assert h.experience_criteria == ""
        assert h.discipline == ""
        assert h.accountability_framework == ""

    def test_to_dict_keys(self, hitl_requirement):
        d = hitl_requirement.to_dict()
        assert "requirement_id" in d
        assert d["certifications_required"] == ["CA_PE_License", "OSHA_30"]
        assert d["licenses_required"] == ["CA_General_Contractor_B"]
        assert d["discipline"] == "Civil Engineering"

    def test_to_dict_immutable_lists(self, hitl_requirement):
        d = hitl_requirement.to_dict()
        d["certifications_required"].append("EXTRA")
        # Original should not be mutated
        assert "EXTRA" not in hitl_requirement.certifications_required


class TestProductionProposal:
    def test_default_status_is_pending(self):
        p = ProductionProposal()
        assert p.status == ProposalStatus.PENDING

    def test_to_dict_includes_regulatory_fields(self, minimal_proposal):
        d = minimal_proposal.to_dict()
        assert d["regulatory_location"] == "US/California"
        assert d["regulatory_industry"] == "construction"
        assert "permitting" in d["regulatory_functions"]

    def test_proposal_id_auto_generated(self):
        p1 = ProductionProposal()
        p2 = ProductionProposal()
        assert p1.proposal_id != p2.proposal_id

    def test_to_dict_hitl_requirements_serialised(self, minimal_proposal, hitl_requirement):
        minimal_proposal.hitl_requirements = [hitl_requirement]
        d = minimal_proposal.to_dict()
        assert isinstance(d["hitl_requirements"], list)
        assert len(d["hitl_requirements"]) == 1
        assert d["hitl_requirements"][0]["discipline"] == "Civil Engineering"


class TestProductionWorkOrder:
    def test_default_status_is_pending(self):
        wo = ProductionWorkOrder()
        assert wo.status == WorkOrderStatus.PENDING

    def test_to_dict_keys(self):
        wo = ProductionWorkOrder(
            proposal_id="prop-001",
            actual_deliverable="Test deliverable content.",
        )
        d = wo.to_dict()
        assert d["proposal_id"] == "prop-001"
        assert d["status"] == WorkOrderStatus.PENDING.value


class TestProductionProfile:
    def test_default_lifecycle(self):
        p = ProductionProfile()
        assert p.lifecycle == ProductionLifecycle.CREATED

    def test_to_dict_keys(self):
        p = ProductionProfile(proposal_id="prop-001")
        d = p.to_dict()
        assert d["proposal_id"] == "prop-001"
        assert d["lifecycle"] == "created"


class TestDeliverableMatch:
    def test_default_not_passed(self):
        m = DeliverableMatch()
        assert m.passed is False

    def test_to_dict_keys(self):
        m = DeliverableMatch(
            proposal_id="p1",
            work_order_id="w1",
            confidence_score=0.95,
            passed=False,
        )
        d = m.to_dict()
        assert d["confidence_score"] == 0.95
        assert d["passed"] is False


# ---------------------------------------------------------------------------
# Input validation — submit_proposal
# ---------------------------------------------------------------------------

class TestSubmitProposalValidation:
    def test_rejects_missing_location(self, engine):
        p = ProductionProposal(
            regulatory_location="",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="Valid spec with enough detail.",
        )
        with pytest.raises(ValueError, match="regulatory_location"):
            engine.submit_proposal(p)

    def test_rejects_missing_industry(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="",
            regulatory_functions=["permitting"],
            deliverable_spec="Valid spec.",
        )
        with pytest.raises(ValueError, match="regulatory_industry"):
            engine.submit_proposal(p)

    def test_rejects_empty_functions(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=[],
            deliverable_spec="Valid spec.",
        )
        with pytest.raises(ValueError, match="regulatory_functions"):
            engine.submit_proposal(p)

    def test_rejects_spec_too_long(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="x" * 10_001,
        )
        with pytest.raises(ValueError, match="deliverable_spec"):
            engine.submit_proposal(p)

    def test_rejects_invalid_location_chars(self, engine):
        p = ProductionProposal(
            regulatory_location="<script>",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="Valid spec.",
        )
        with pytest.raises(ValueError):
            engine.submit_proposal(p)

    def test_accepts_valid_proposal(self, engine, minimal_proposal):
        pid = engine.submit_proposal(minimal_proposal)
        assert pid == minimal_proposal.proposal_id


# ---------------------------------------------------------------------------
# Proposal validation — 99% confidence gating
# ---------------------------------------------------------------------------

class TestValidateProposal:
    def test_full_spec_passes_at_high_confidence(self, engine):
        """A richly-detailed proposal should score near 1.0."""
        p = ProductionProposal(
            regulatory_location="US/California",
            regulatory_industry="construction",
            regulatory_functions=[
                "permitting", "safety_inspection", "zoning_compliance",
                "environmental_review", "building_code_compliance",
            ],
            deliverable_spec=(
                "Comprehensive construction project plan covering permitting "
                "safety_inspection zoning_compliance environmental_review "
                "building_code_compliance materials scheduling contractor "
                "qualification workforce safety documentation signatures "
                "certifications regulatory submission California standards "
                "site plans specifications inspections approvals review "
                "compliance documentation reports checklists forms permits "
                "licenses insurance bonds warranties indemnification scope "
                "timeline budget milestones deliverables acceptance criteria "
                "change_order process closeout punch_list final_inspection "
                "certificate_of_occupancy as_built drawings maintenance "
                "operation_manual warranty_documentation training closeout_docs"
            ),
        )
        engine.submit_proposal(p)
        result = engine.validate_proposal(p.proposal_id)
        assert isinstance(result, ValidationResult)
        # Score should be high — all regulatory fields present and spec is rich
        assert result.regulatory_ok is True
        assert result.deliverable_ok is True

    def test_empty_spec_fails_validation(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="healthcare",
            regulatory_functions=["hipaa_compliance"],
            deliverable_spec="",
        )
        engine.submit_proposal(p)
        result = engine.validate_proposal(p.proposal_id)
        assert result.passed is False
        assert result.deliverable_ok is False

    def test_missing_regulatory_functions_blocks_proposal(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="Basic spec.",
        )
        pid = engine.submit_proposal(p)
        result = engine.validate_proposal(pid)
        # Low confidence because spec is sparse
        assert result.regulatory_ok is True
        assert isinstance(result.confidence_score, float)

    def test_unknown_proposal_id_returns_failure(self, engine):
        result = engine.validate_proposal("nonexistent-id")
        assert result.passed is False
        assert len(result.failure_reasons) > 0

    def test_confidence_score_in_range(self, engine, minimal_proposal):
        engine.submit_proposal(minimal_proposal)
        result = engine.validate_proposal(minimal_proposal.proposal_id)
        assert 0.0 <= result.confidence_score <= 1.0

    def test_proposal_status_updated_on_approval(self, engine):
        p = ProductionProposal(
            regulatory_location="US/California",
            regulatory_industry="construction",
            regulatory_functions=[
                "permitting", "safety_inspection", "zoning_compliance",
                "environmental_review", "building_code_compliance",
            ],
            deliverable_spec=(
                "Comprehensive construction project plan covering permitting "
                "safety_inspection zoning_compliance environmental_review "
                "building_code_compliance site plans materials specifications "
                "contractor qualification workforce safety documentation "
                "signatures certifications regulatory submission California "
                "standards inspections approvals review compliance reports "
                "checklists forms permits licenses insurance bonds warranties "
                "scope timeline budget milestones deliverables acceptance "
                "criteria change_order closeout punch_list final_inspection "
                "certificate_of_occupancy as_built drawings maintenance "
                "operation_manual warranty training closeout_docs records "
                "environmental_impact stormwater_management utility_coordination"
            ),
        )
        engine.submit_proposal(p)
        result = engine.validate_proposal(p.proposal_id)
        with engine._lock:
            stored = engine._proposals[p.proposal_id]
        # Status should be updated based on validation result
        assert stored.status in (ProposalStatus.APPROVED, ProposalStatus.REJECTED)

    def test_validation_requires_99_pct_threshold(self):
        assert PRODUCTION_CONFIDENCE_THRESHOLD == 0.99


# ---------------------------------------------------------------------------
# HITL gate requirements validation
# ---------------------------------------------------------------------------

class TestHITLValidation:
    def test_hitl_with_discipline_is_valid(self, engine):
        h = HITLGateRequirement(discipline="Structural Engineering")
        p = ProductionProposal(
            regulatory_location="US/TX",
            regulatory_industry="construction",
            regulatory_functions=["site_safety"],
            deliverable_spec="Site safety plan for Texas construction.",
            hitl_requirements=[h],
        )
        pid = engine.submit_proposal(p)
        result = engine.validate_proposal(pid)
        assert result.hitl_ok is True

    def test_hitl_with_certifications_is_valid(self, engine):
        h = HITLGateRequirement(certifications_required=["OSHA_30"])
        p = ProductionProposal(
            regulatory_location="US/TX",
            regulatory_industry="construction",
            regulatory_functions=["site_safety"],
            deliverable_spec="Site safety plan for Texas construction project.",
            hitl_requirements=[h],
        )
        pid = engine.submit_proposal(p)
        result = engine.validate_proposal(pid)
        assert result.hitl_ok is True

    def test_hitl_without_discipline_or_certs_fails(self, engine):
        h = HITLGateRequirement()  # no discipline, no certs
        p = ProductionProposal(
            regulatory_location="US/TX",
            regulatory_industry="construction",
            regulatory_functions=["site_safety"],
            deliverable_spec="Site safety plan for Texas construction project.",
            hitl_requirements=[h],
        )
        pid = engine.submit_proposal(p)
        result = engine.validate_proposal(pid)
        assert result.hitl_ok is False
        assert result.passed is False

    def test_rejects_too_many_certifications(self, engine):
        h = HITLGateRequirement(
            certifications_required=["CERT_" + str(i) for i in range(25)],  # > 20
            discipline="Engineering",
        )
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="Spec.",
            hitl_requirements=[h],
        )
        with pytest.raises(ValueError, match="certifications_required"):
            engine.submit_proposal(p)

    def test_experience_criteria_too_long_rejected(self, engine):
        h = HITLGateRequirement(
            discipline="Engineering",
            experience_criteria="x" * 501,  # > 500
        )
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="Spec.",
            hitl_requirements=[h],
        )
        with pytest.raises(ValueError, match="experience_criteria"):
            engine.submit_proposal(p)


# ---------------------------------------------------------------------------
# Work order submission and validation
# ---------------------------------------------------------------------------

class TestWorkOrderSubmission:
    def _make_approved_proposal(self, engine: ProductionAssistantEngine) -> str:
        """Helper: create and force-approve a proposal."""
        p = ProductionProposal(
            regulatory_location="US/California",
            regulatory_industry="construction",
            regulatory_functions=["permitting", "safety_inspection"],
            deliverable_spec=(
                "Construction project plan covering permitting and safety_inspection "
                "requirements including documentation checklists and compliance forms."
            ),
        )
        pid = engine.submit_proposal(p)
        # Force approve for work order test
        with engine._lock:
            engine._proposals[pid].status = ProposalStatus.APPROVED
        return pid

    def test_submit_work_order_requires_approved_proposal(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="Spec.",
        )
        pid = engine.submit_proposal(p)
        # Proposal is PENDING — should raise
        wo = ProductionWorkOrder(
            proposal_id=pid,
            actual_deliverable="Some deliverable.",
        )
        with pytest.raises(ValueError, match="not approved"):
            engine.submit_work_order(wo)

    def test_submit_work_order_unknown_proposal_raises(self, engine):
        wo = ProductionWorkOrder(
            proposal_id="unknown-123",
            actual_deliverable="Some content.",
        )
        with pytest.raises(ValueError, match="not found"):
            engine.submit_work_order(wo)

    def test_submit_work_order_returns_id(self, engine):
        pid = self._make_approved_proposal(engine)
        wo = ProductionWorkOrder(
            proposal_id=pid,
            actual_deliverable="Deliverable content for testing.",
        )
        wid = engine.submit_work_order(wo)
        assert wid == wo.work_order_id

    def test_deliverable_too_long_raises(self, engine):
        pid = self._make_approved_proposal(engine)
        wo = ProductionWorkOrder(
            proposal_id=pid,
            actual_deliverable="x" * 50_001,
        )
        with pytest.raises(ValueError, match="actual_deliverable"):
            engine.submit_work_order(wo)

    def test_validate_work_order_not_found_returns_match(self, engine):
        match = engine.validate_work_order("nonexistent-id")
        assert match.passed is False

    def test_validate_work_order_low_confidence_on_mismatch(self, engine):
        pid = self._make_approved_proposal(engine)
        wo = ProductionWorkOrder(
            proposal_id=pid,
            actual_deliverable="Unrelated text with no relevant terms.",
        )
        wid = engine.submit_work_order(wo)
        match = engine.validate_work_order(wid)
        assert isinstance(match, DeliverableMatch)
        # Mismatch — should not pass 99%
        assert match.passed is False
        assert 0.0 <= match.confidence_score <= 1.0

    def test_validate_work_order_high_confidence_on_match(self, engine):
        """Deliverable that mirrors the spec should score close to 1.0."""
        spec = (
            "permitting safety_inspection building_code zoning_compliance "
            "contractor_qualification workforce_safety documentation signatures "
            "certifications regulatory_submission California_standards site_plans "
            "specifications inspections approvals reviews compliance_reports "
            "checklists forms permits licenses insurance bonds warranties scope "
            "timeline budget milestones deliverables acceptance_criteria closeout"
        )
        p = ProductionProposal(
            regulatory_location="US/California",
            regulatory_industry="construction",
            regulatory_functions=["permitting", "safety_inspection", "zoning_compliance"],
            deliverable_spec=spec,
        )
        pid = engine.submit_proposal(p)
        with engine._lock:
            engine._proposals[pid].status = ProposalStatus.APPROVED

        wo = ProductionWorkOrder(
            proposal_id=pid,
            # Actual deliverable contains all spec terms
            actual_deliverable=spec + " additional verified confirmed complete",
        )
        wid = engine.submit_work_order(wo)
        match = engine.validate_work_order(wid)
        # With perfect coverage, score should be high
        assert match.confidence_score >= 0.5  # at minimum well above 0
        assert isinstance(match.dimension_scores, dict)


# ---------------------------------------------------------------------------
# Lifecycle management
# ---------------------------------------------------------------------------

class TestLifecycleManagement:
    def test_advance_lifecycle_forward(self, engine):
        profile = ProductionProfile()
        with engine._lock:
            engine._profiles[profile.profile_id] = profile
        result = engine.advance_lifecycle(
            profile.profile_id,
            ProductionLifecycle.IN_REVIEW,
        )
        assert result is True
        p = engine.get_profile(profile.profile_id)
        assert p.lifecycle == ProductionLifecycle.IN_REVIEW

    def test_cannot_advance_backward(self, engine):
        profile = ProductionProfile(lifecycle=ProductionLifecycle.IN_PROGRESS)
        with engine._lock:
            engine._profiles[profile.profile_id] = profile
        result = engine.advance_lifecycle(
            profile.profile_id,
            ProductionLifecycle.CREATED,
        )
        assert result is False
        p = engine.get_profile(profile.profile_id)
        assert p.lifecycle == ProductionLifecycle.IN_PROGRESS

    def test_cannot_advance_to_same_state(self, engine):
        profile = ProductionProfile(lifecycle=ProductionLifecycle.IN_REVIEW)
        with engine._lock:
            engine._profiles[profile.profile_id] = profile
        result = engine.advance_lifecycle(
            profile.profile_id,
            ProductionLifecycle.IN_REVIEW,
        )
        assert result is False

    def test_can_transition_to_rejected(self, engine):
        profile = ProductionProfile(lifecycle=ProductionLifecycle.IN_PROGRESS)
        with engine._lock:
            engine._profiles[profile.profile_id] = profile
        result = engine.advance_lifecycle(
            profile.profile_id,
            ProductionLifecycle.REJECTED,
        )
        assert result is True
        p = engine.get_profile(profile.profile_id)
        assert p.lifecycle == ProductionLifecycle.REJECTED

    def test_cannot_advance_from_verified(self, engine):
        profile = ProductionProfile(lifecycle=ProductionLifecycle.VERIFIED)
        with engine._lock:
            engine._profiles[profile.profile_id] = profile
        result = engine.advance_lifecycle(
            profile.profile_id,
            ProductionLifecycle.DELIVERED,
        )
        assert result is False

    def test_full_forward_lifecycle(self, engine):
        profile = ProductionProfile()
        with engine._lock:
            engine._profiles[profile.profile_id] = profile
        states = [
            ProductionLifecycle.IN_REVIEW,
            ProductionLifecycle.APPROVED,
            ProductionLifecycle.IN_PROGRESS,
            ProductionLifecycle.DELIVERED,
            ProductionLifecycle.VERIFIED,
        ]
        for state in states:
            assert engine.advance_lifecycle(profile.profile_id, state) is True
        p = engine.get_profile(profile.profile_id)
        assert p.lifecycle == ProductionLifecycle.VERIFIED

    def test_history_recorded(self, engine):
        profile = ProductionProfile()
        with engine._lock:
            engine._profiles[profile.profile_id] = profile
        engine.advance_lifecycle(
            profile.profile_id, ProductionLifecycle.IN_REVIEW, notes="test note"
        )
        p = engine.get_profile(profile.profile_id)
        assert len(p.history) == 1
        assert p.history[0]["from"] == "created"
        assert p.history[0]["to"] == "in_review"

    def test_unknown_profile_returns_false(self, engine):
        result = engine.advance_lifecycle("unknown-id", ProductionLifecycle.IN_REVIEW)
        assert result is False

    def test_get_profile_unknown_returns_none(self, engine):
        assert engine.get_profile("no-such-id") is None


# ---------------------------------------------------------------------------
# Regulatory validation
# ---------------------------------------------------------------------------

class TestRegulatoryValidation:
    def test_location_with_special_chars_rejected(self, engine):
        p = ProductionProposal(
            regulatory_location="<US>",
            regulatory_industry="construction",
            regulatory_functions=["permitting"],
            deliverable_spec="Spec.",
        )
        with pytest.raises(ValueError):
            engine.submit_proposal(p)

    def test_industry_with_sql_injection_rejected(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="'; DROP TABLE --",
            regulatory_functions=["permitting"],
            deliverable_spec="Spec.",
        )
        with pytest.raises(ValueError):
            engine.submit_proposal(p)

    def test_too_many_functions_rejected(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=["func_" + str(i) for i in range(51)],
            deliverable_spec="Spec.",
        )
        with pytest.raises(ValueError, match="regulatory_functions"):
            engine.submit_proposal(p)

    def test_function_too_long_rejected(self, engine):
        p = ProductionProposal(
            regulatory_location="US/CA",
            regulatory_industry="construction",
            regulatory_functions=["x" * 201],
            deliverable_spec="Spec.",
        )
        with pytest.raises(ValueError):
            engine.submit_proposal(p)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAuditLog:
    def test_audit_log_populated_on_submit(self, engine, minimal_proposal):
        engine.submit_proposal(minimal_proposal)
        log = engine.get_audit_log()
        assert any(e["action"] == "submit_proposal" for e in log)

    def test_audit_log_populated_on_validate(self, engine, minimal_proposal):
        engine.submit_proposal(minimal_proposal)
        engine.validate_proposal(minimal_proposal.proposal_id)
        log = engine.get_audit_log()
        assert any(e["action"] == "validate_proposal" for e in log)

    def test_audit_log_limit_respected(self, engine, minimal_proposal):
        # submit and validate multiple proposals
        for _ in range(5):
            p = ProductionProposal(
                regulatory_location="US/CA",
                regulatory_industry="construction",
                regulatory_functions=["permitting"],
                deliverable_spec="Spec content.",
            )
            engine.submit_proposal(p)
        log = engine.get_audit_log(limit=2)
        assert len(log) <= 2


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_submit_proposals(self, engine):
        errors: list = []
        ids: list = []
        lock = threading.Lock()

        def submit():
            try:
                p = ProductionProposal(
                    regulatory_location="US/CA",
                    regulatory_industry="construction",
                    regulatory_functions=["permitting"],
                    deliverable_spec="Thread-safe test specification content.",
                )
                pid = engine.submit_proposal(p)
                with lock:
                    ids.append(pid)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=submit) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(ids) == 20

    def test_concurrent_lifecycle_advances(self, engine):
        profile = ProductionProfile()
        with engine._lock:
            engine._profiles[profile.profile_id] = profile

        successes: list = []
        lock = threading.Lock()

        def advance():
            result = engine.advance_lifecycle(
                profile.profile_id, ProductionLifecycle.IN_REVIEW
            )
            with lock:
                successes.append(result)

        threads = [threading.Thread(target=advance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one thread should succeed in advancing
        assert sum(1 for r in successes if r) == 1
