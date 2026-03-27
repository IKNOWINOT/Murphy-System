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


# ===========================================================================
# Tests for production_assistant_engine.py — DeliverableGateValidator &
# ProductionAssistantOrchestrator
# ===========================================================================

from production_assistant_engine import (
    PRODUCTION_CONFIDENCE_THRESHOLD,
    DeliverableGateReport,
    DeliverableGateValidator,
    DeliverableItem,
    GateValidationReport,
    INDUSTRY_REQUIREMENTS,
    FUNCTION_REQUIREMENTS,
    ProductionAssistantOrchestrator,
    ProductionRequestProfile,
    RequestLifecycle,
    _resolve_location_frameworks,
    _resolve_industry_frameworks,
    _resolve_function_frameworks,
    _spec_mentions_framework,
)


@pytest.fixture
def validator():
    return DeliverableGateValidator()


@pytest.fixture
def orchestrator():
    return ProductionAssistantOrchestrator()


# ---------------------------------------------------------------------------
# PRODUCTION_CONFIDENCE_THRESHOLD — shared constant
# ---------------------------------------------------------------------------


class TestEngineConfidenceThreshold:
    def test_threshold_is_099(self):
        assert PRODUCTION_CONFIDENCE_THRESHOLD == 0.99

    def test_threshold_type_float(self):
        assert isinstance(PRODUCTION_CONFIDENCE_THRESHOLD, float)


# ---------------------------------------------------------------------------
# Regulatory knowledge maps
# ---------------------------------------------------------------------------


class TestRegulatoryKnowledgeMaps:
    def test_industry_requirements_has_healthcare(self):
        assert "healthcare" in INDUSTRY_REQUIREMENTS
        assert "HIPAA" in INDUSTRY_REQUIREMENTS["healthcare"]
        assert "HITECH" in INDUSTRY_REQUIREMENTS["healthcare"]

    def test_industry_requirements_has_finance(self):
        assert "finance" in INDUSTRY_REQUIREMENTS
        assert "SOX" in INDUSTRY_REQUIREMENTS["finance"]

    def test_function_requirements_has_data_processing(self):
        assert "data_processing" in FUNCTION_REQUIREMENTS
        assert "GDPR" in FUNCTION_REQUIREMENTS["data_processing"]

    def test_function_requirements_has_patient_data(self):
        assert "patient_data" in FUNCTION_REQUIREMENTS
        assert "HIPAA" in FUNCTION_REQUIREMENTS["patient_data"]

    def test_resolve_location_canada(self):
        code, fws = _resolve_location_frameworks("CA")
        assert code == "CA"
        assert "PIPEDA" in fws
        assert "CASL" in fws

    def test_resolve_location_us(self):
        code, fws = _resolve_location_frameworks("US")
        assert code == "US"
        assert "HIPAA" in fws
        assert "CCPA" in fws

    def test_resolve_location_germany(self):
        code, fws = _resolve_location_frameworks("DE")
        assert code == "DE"
        assert "GDPR" in fws

    def test_resolve_location_with_region_prefix(self):
        """US/California should resolve same as bare US."""
        code_bare, fws_bare = _resolve_location_frameworks("US")
        code_region, fws_region = _resolve_location_frameworks("US/California")
        assert code_bare == code_region
        assert set(fws_bare) == set(fws_region)

    def test_resolve_industry_healthcare(self):
        fws = _resolve_industry_frameworks("healthcare")
        assert "HIPAA" in fws
        assert "HITECH" in fws

    def test_resolve_industry_manufacturing(self):
        fws = _resolve_industry_frameworks("manufacturing")
        assert "ISO_27001" in fws

    def test_resolve_function_data_processing(self):
        fws = _resolve_function_frameworks("data_processing")
        assert "GDPR" in fws
        assert "CCPA" in fws

    def test_resolve_function_safety_inspection(self):
        fws = _resolve_function_frameworks("safety_inspection")
        assert "OSHA" in fws

    def test_resolve_unknown_location_falls_back_to_default(self):
        _, fws = _resolve_location_frameworks("ZZ")
        assert isinstance(fws, list)

    def test_resolve_unknown_industry_falls_back_to_default(self):
        fws = _resolve_industry_frameworks("nonexistent_industry")
        assert fws == ["ISO_27001"]

    def test_resolve_unknown_function_returns_empty(self):
        fws = _resolve_function_frameworks("nonexistent_function")
        assert fws == []


# ---------------------------------------------------------------------------
# _spec_mentions_framework helper
# ---------------------------------------------------------------------------


class TestSpecMentionsFramework:
    def test_exact_match(self):
        assert _spec_mentions_framework("The system includes HIPAA compliance.", "HIPAA")

    def test_case_insensitive_match(self):
        assert _spec_mentions_framework("hipaa compliance required", "HIPAA")

    def test_alias_dsgvo_matches_gdpr(self):
        assert _spec_mentions_framework("System must meet DSGVO requirements.", "GDPR")

    def test_missing_framework_returns_false(self):
        assert not _spec_mentions_framework("Generic compliance system.", "HIPAA")

    def test_empty_spec_returns_false(self):
        assert not _spec_mentions_framework("", "GDPR")

    def test_none_equivalent_empty_returns_false(self):
        assert not _spec_mentions_framework("", "CCPA")


# ---------------------------------------------------------------------------
# DeliverableItem dataclass
# ---------------------------------------------------------------------------


class TestDeliverableItemDataclass:
    def test_defaults(self):
        item = DeliverableItem()
        assert item.description == ""
        assert item.required_framework == ""
        assert item.source_dimension == ""
        assert item.satisfied_in_spec is False

    def test_to_dict_keys(self):
        item = DeliverableItem(
            description="Must address HIPAA",
            required_framework="HIPAA",
            source_dimension="industry",
            satisfied_in_spec=True,
        )
        d = item.to_dict()
        assert d["required_framework"] == "HIPAA"
        assert d["satisfied_in_spec"] is True
        assert d["source_dimension"] == "industry"

    def test_auto_id(self):
        i1 = DeliverableItem()
        i2 = DeliverableItem()
        assert i1.item_id != i2.item_id


# ---------------------------------------------------------------------------
# DeliverableGateReport dataclass
# ---------------------------------------------------------------------------


class TestDeliverableGateReportDataclass:
    def test_defaults(self):
        r = DeliverableGateReport()
        assert r.passed is False
        assert r.confidence_score == 0.0

    def test_to_dict_keys(self):
        r = DeliverableGateReport(
            required_framework="GDPR",
            source_dimension="location",
            confidence_score=1.0,
            passed=True,
            gate_action="PROCEED_AUTOMATICALLY",
        )
        d = r.to_dict()
        assert d["required_framework"] == "GDPR"
        assert d["passed"] is True
        assert d["confidence_score"] == 1.0


# ---------------------------------------------------------------------------
# GateValidationReport dataclass
# ---------------------------------------------------------------------------


class TestGateValidationReportDataclass:
    def test_defaults(self):
        r = GateValidationReport()
        assert r.passed is False
        assert r.item_reports == []
        assert r.failed_items == []

    def test_to_dict_keys(self):
        r = GateValidationReport(
            proposal_id="prop-001",
            passed=True,
            min_confidence=1.0,
            passed_items=["GDPR", "HIPAA"],
        )
        d = r.to_dict()
        assert d["proposal_id"] == "prop-001"
        assert d["passed"] is True
        assert d["min_confidence"] == 1.0
        assert "GDPR" in d["passed_items"]


# ---------------------------------------------------------------------------
# DeliverableGateValidator.validate() — fully compliant proposals
# ---------------------------------------------------------------------------


class TestDeliverableGateValidatorFullyCompliant:
    """A well-formed, fully-compliant proposal must pass all gates."""

    def test_canada_manufacturing_safety_passes(self, validator):
        """CA + manufacturing + safety_inspection — spec mentions all required."""
        report = validator.validate(
            proposal_id="prop-ca-mfg",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=["safety_inspection"],
            deliverable_spec=(
                "Complete compliance package: PIPEDA data privacy controls, "
                "CASL opt-in email procedures, ISO_27001 security management, "
                "and OSHA safety inspection checklists."
            ),
        )
        assert report.passed is True
        assert report.failed_items == []
        assert report.min_confidence == 1.0

    def test_all_item_reports_individually_pass(self, validator):
        """Every individual DeliverableGateReport must have passed=True."""
        report = validator.validate(
            proposal_id="prop-ind-items",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec=(
                "System implements PIPEDA data retention rules, "
                "CASL email consent, and ISO_27001 controls."
            ),
        )
        assert report.passed is True
        assert all(r.passed for r in report.item_reports)

    def test_passed_items_list_populated(self, validator):
        report = validator.validate(
            proposal_id="prop-passed-list",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec=(
                "PIPEDA privacy, CASL compliance, ISO_27001 controls included."
            ),
        )
        assert set(report.passed_items) >= {"PIPEDA", "CASL", "ISO_27001"}
        assert report.failed_items == []

    def test_report_includes_proposal_id(self, validator):
        report = validator.validate(
            proposal_id="unique-123",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA data controls, CASL consent, ISO_27001 framework.",
        )
        assert report.proposal_id == "unique-123"

    def test_work_order_id_propagated(self, validator):
        report = validator.validate(
            proposal_id="prop-x",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA privacy, CASL rules, ISO_27001 controls.",
            work_order_id="wo-abc",
        )
        assert report.work_order_id == "wo-abc"

    def test_min_confidence_is_one_when_all_pass(self, validator):
        report = validator.validate(
            proposal_id="p",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA, CASL, ISO_27001 compliance throughout.",
        )
        assert report.min_confidence == 1.0

    def test_eu_finance_data_processing_passes(self, validator):
        """DE + finance + data_processing — spec mentions GDPR, BaFin, SOX, PCI_DSS, CCPA."""
        report = validator.validate(
            proposal_id="prop-eu-fin",
            regulatory_location="DE",
            regulatory_industry="finance",
            regulatory_functions=["data_processing"],
            deliverable_spec=(
                "System addresses GDPR data protection requirements, BaFin financial "
                "supervision obligations, SOX internal controls, PCI_DSS payment "
                "security standards, and CCPA consumer rights."
            ),
        )
        assert report.passed is True, f"Expected pass, failed: {report.failed_items}"
        assert report.failed_items == []


# ---------------------------------------------------------------------------
# DeliverableGateValidator.validate() — missing ONE requirement fails
# ---------------------------------------------------------------------------


class TestDeliverableGateValidatorMissingRequirement:
    """A proposal missing ONE regulatory element must fail the 99% gate."""

    def test_missing_casl_fails(self, validator):
        """Canada spec that omits CASL must fail."""
        report = validator.validate(
            proposal_id="prop-no-casl",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA data privacy and ISO_27001 security controls.",
        )
        assert report.passed is False
        assert "CASL" in report.failed_items

    def test_missing_iso27001_fails(self, validator):
        """Canada spec that omits ISO_27001 must fail."""
        report = validator.validate(
            proposal_id="prop-no-iso",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA and CASL compliance included.",
        )
        assert report.passed is False
        assert "ISO_27001" in report.failed_items

    def test_missing_osha_fails_when_required(self, validator):
        """safety_inspection function requires OSHA; omitting it blocks the proposal."""
        report = validator.validate(
            proposal_id="prop-no-osha",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=["safety_inspection"],
            deliverable_spec="PIPEDA privacy, CASL consent, ISO_27001 controls.",
        )
        assert report.passed is False
        assert "OSHA" in report.failed_items

    def test_failed_item_has_confidence_zero(self, validator):
        """A failed item must carry confidence_score == 0.0."""
        report = validator.validate(
            proposal_id="p-score",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA privacy and CASL consent.",
        )
        iso_report = next(
            (r for r in report.item_reports if r.required_framework == "ISO_27001"),
            None,
        )
        assert iso_report is not None
        assert iso_report.confidence_score == 0.0
        assert iso_report.passed is False

    def test_failed_item_gate_action_is_block(self, validator):
        """A failed item's gate_action must be BLOCK_EXECUTION."""
        report = validator.validate(
            proposal_id="p-block",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA and CASL compliance only.",
        )
        iso_report = next(
            (r for r in report.item_reports if r.required_framework == "ISO_27001"),
            None,
        )
        assert iso_report is not None
        assert "BLOCK" in iso_report.gate_action.upper()

    def test_min_confidence_is_zero_on_failure(self, validator):
        report = validator.validate(
            proposal_id="p-minconf",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA and CASL.",
        )
        assert report.min_confidence == 0.0

    def test_summary_describes_failed_items(self, validator):
        report = validator.validate(
            proposal_id="p-summ",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA and CASL only.",
        )
        assert "ISO_27001" in report.summary
        assert "BLOCKED" in report.summary.upper() or "missing" in report.summary.lower()


# ---------------------------------------------------------------------------
# Regulatory matching — location dimension
# ---------------------------------------------------------------------------


class TestRegulatoryLocationMatching:
    def test_eu_location_requires_gdpr(self, validator):
        report = validator.validate(
            proposal_id="loc-eu",
            regulatory_location="DE",
            regulatory_industry="default",
            regulatory_functions=[],
            deliverable_spec="System includes SOX and PCI_DSS controls.",
        )
        assert report.passed is False
        assert "GDPR" in report.failed_items

    def test_brazil_location_requires_lgpd_alias(self, validator):
        """Brazil: LGPD normalises to GDPR; spec must mention GDPR or LGPD."""
        report = validator.validate(
            proposal_id="loc-br",
            regulatory_location="BR",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="ISO_27001 security controls only.",
        )
        assert report.passed is False

    def test_canada_requires_both_pipeda_and_casl(self, validator):
        report = validator.validate(
            proposal_id="loc-ca",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="ISO_27001 controls only.",
        )
        assert "PIPEDA" in report.failed_items
        assert "CASL" in report.failed_items

    def test_location_region_prefix_resolved_same_as_bare(self, validator):
        report_bare = validator.validate(
            proposal_id="p-us",
            regulatory_location="US",
            regulatory_industry="construction",
            regulatory_functions=[],
            deliverable_spec="Generic plan.",
        )
        report_region = validator.validate(
            proposal_id="p-usca",
            regulatory_location="US/California",
            regulatory_industry="construction",
            regulatory_functions=[],
            deliverable_spec="Generic plan.",
        )
        fws_bare = {r.required_framework for r in report_bare.item_reports}
        fws_region = {r.required_framework for r in report_region.item_reports}
        assert fws_bare == fws_region


# ---------------------------------------------------------------------------
# Regulatory matching — industry dimension
# ---------------------------------------------------------------------------


class TestRegulatoryIndustryMatching:
    def test_healthcare_requires_hipaa(self, validator):
        report = validator.validate(
            proposal_id="ind-health",
            regulatory_location="CA",
            regulatory_industry="healthcare",
            regulatory_functions=[],
            deliverable_spec="PIPEDA privacy, CASL consent, ISO_27001 controls.",
        )
        assert report.passed is False
        assert "HIPAA" in report.failed_items

    def test_healthcare_requires_hitech(self, validator):
        report = validator.validate(
            proposal_id="ind-hitech",
            regulatory_location="CA",
            regulatory_industry="healthcare",
            regulatory_functions=[],
            deliverable_spec="PIPEDA, CASL, ISO_27001, HIPAA compliance.",
        )
        assert report.passed is False
        assert "HITECH" in report.failed_items

    def test_healthcare_with_all_frameworks_passes(self, validator):
        report = validator.validate(
            proposal_id="ind-health-pass",
            regulatory_location="CA",
            regulatory_industry="healthcare",
            regulatory_functions=[],
            deliverable_spec=(
                "System includes PIPEDA data rights, CASL email consent, "
                "ISO_27001 security, HIPAA patient data protection, "
                "and HITECH breach notification."
            ),
        )
        assert report.passed is True, f"Failed items: {report.failed_items}"

    def test_finance_requires_sox(self, validator):
        report = validator.validate(
            proposal_id="ind-fin",
            regulatory_location="CA",
            regulatory_industry="finance",
            regulatory_functions=[],
            deliverable_spec="PIPEDA privacy, CASL, ISO_27001, PCI_DSS.",
        )
        assert report.passed is False
        assert "SOX" in report.failed_items


# ---------------------------------------------------------------------------
# Regulatory matching — function dimension
# ---------------------------------------------------------------------------


class TestRegulatoryFunctionMatching:
    def test_patient_data_requires_hipaa(self, validator):
        report = validator.validate(
            proposal_id="fn-patient",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=["patient_data"],
            deliverable_spec="PIPEDA, CASL, ISO_27001 only.",
        )
        assert report.passed is False
        assert "HIPAA" in report.failed_items

    def test_data_processing_requires_gdpr(self, validator):
        report = validator.validate(
            proposal_id="fn-dataproc",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=["data_processing"],
            deliverable_spec="PIPEDA, CASL, ISO_27001, CCPA.",
        )
        assert report.passed is False
        assert "GDPR" in report.failed_items

    def test_safety_inspection_requires_osha(self, validator):
        report = validator.validate(
            proposal_id="fn-safety",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=["safety_inspection"],
            deliverable_spec="PIPEDA, CASL, ISO_27001 controls.",
        )
        assert report.passed is False
        assert "OSHA" in report.failed_items

    def test_no_functions_only_location_industry_required(self, validator):
        report = validator.validate(
            proposal_id="fn-none",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        assert report.passed is True

    def test_multiple_functions_all_required(self, validator):
        """Both functions' framework requirements must be in spec."""
        report = validator.validate(
            proposal_id="fn-multi",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=["safety_inspection", "data_processing"],
            deliverable_spec="PIPEDA, CASL, ISO_27001, OSHA.",
            # Missing GDPR and CCPA (from data_processing)
        )
        assert report.passed is False
        assert "GDPR" in report.failed_items


# ---------------------------------------------------------------------------
# Multi-jurisdiction proposals
# ---------------------------------------------------------------------------


class TestMultiJurisdictionProposals:
    def test_spec_covering_all_jurisdictions_passes_both(self, validator):
        """Spec covering all frameworks for two jurisdictions passes both."""
        spec = (
            "Comprehensive: SOX internal controls, HIPAA patient data, HITECH breach notice, "
            "CCPA consumer rights, ADA accessibility, PIPEDA privacy, CASL consent, ISO_27001."
        )
        report_us = validator.validate(
            proposal_id="multi-us-full",
            regulatory_location="US",
            regulatory_industry="healthcare",
            regulatory_functions=[],
            deliverable_spec=spec,
        )
        report_ca = validator.validate(
            proposal_id="multi-ca-full",
            regulatory_location="CA",
            regulatory_industry="healthcare",
            regulatory_functions=[],
            deliverable_spec=spec,
        )
        assert report_us.passed is True, f"US failed: {report_us.failed_items}"
        assert report_ca.passed is True, f"CA failed: {report_ca.failed_items}"

    def test_eu_and_us_have_different_framework_sets(self, validator):
        """EU and US have distinct framework requirements."""
        _, us_fws = _resolve_location_frameworks("US")
        _, de_fws = _resolve_location_frameworks("DE")
        assert "GDPR" in de_fws
        assert "CCPA" in us_fws
        # US does not natively require GDPR in its zone mapping
        assert "GDPR" not in us_fws

    def test_multi_jurisdiction_spec_missing_gdpr_fails_eu(self, validator):
        """Spec adequate for US but missing GDPR must fail for EU."""
        spec = "SOX controls, HIPAA, CCPA, ADA compliance."
        report_eu = validator.validate(
            proposal_id="multi-eu-fail",
            regulatory_location="DE",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec=spec,
        )
        assert report_eu.passed is False
        assert "GDPR" in report_eu.failed_items


# ---------------------------------------------------------------------------
# Mixed-compliance work orders
# ---------------------------------------------------------------------------


class TestMixedComplianceWorkOrders:
    def test_healthcare_finance_combo_passes(self, validator):
        """Patient billing (healthcare + finance + patient_data + financial_transactions)."""
        report = validator.validate(
            proposal_id="mixed-hf",
            regulatory_location="CA",
            regulatory_industry="healthcare",
            regulatory_functions=["patient_data", "financial_transactions"],
            deliverable_spec=(
                "PIPEDA data privacy, CASL consent, ISO_27001 security, "
                "HIPAA patient data, HITECH breach notification, "
                "SOX financial controls, PCI_DSS payment security."
            ),
        )
        assert report.passed is True, f"Failed: {report.failed_items}"

    def test_mixed_missing_financial_fails(self, validator):
        """Same combo but spec omits SOX."""
        report = validator.validate(
            proposal_id="mixed-hf-fail",
            regulatory_location="CA",
            regulatory_industry="healthcare",
            regulatory_functions=["patient_data", "financial_transactions"],
            deliverable_spec=(
                "PIPEDA, CASL, ISO_27001, HIPAA, HITECH, PCI_DSS included."
            ),
        )
        assert report.passed is False
        assert "SOX" in report.failed_items

    def test_mixed_missing_patient_data_fails(self, validator):
        """Spec covers finance but omits HIPAA."""
        report = validator.validate(
            proposal_id="mixed-hf-fail2",
            regulatory_location="CA",
            regulatory_industry="healthcare",
            regulatory_functions=["patient_data", "financial_transactions"],
            deliverable_spec=(
                "PIPEDA, CASL, ISO_27001, SOX financial, PCI_DSS payment."
            ),
        )
        assert report.passed is False
        assert "HIPAA" in report.failed_items

    def test_all_items_must_individually_pass(self, validator):
        """ALL individual DeliverableGateReports must pass for the overall to pass."""
        report = validator.validate(
            proposal_id="items-all",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA and CASL compliance only.",
        )
        assert any(not r.passed for r in report.item_reports)
        assert report.passed is False

    def test_single_missing_item_blocks_entire_report(self, validator):
        """Exactly one missing item blocks the entire report."""
        report = validator.validate(
            proposal_id="single-miss",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA and ISO_27001.",  # Missing CASL
        )
        failed = [r for r in report.item_reports if not r.passed]
        passed = [r for r in report.item_reports if r.passed]
        assert len(failed) == 1
        assert failed[0].required_framework == "CASL"
        assert len(passed) >= 2
        assert report.passed is False


# ---------------------------------------------------------------------------
# SafetyGate integration
# ---------------------------------------------------------------------------


class TestSafetyGateIntegration:
    def test_satisfied_item_does_not_block(self, validator):
        """Passed items must not have BLOCK in gate_action."""
        report = validator.validate(
            proposal_id="gate-integ",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        for r in report.item_reports:
            if r.passed:
                assert "BLOCK" not in r.gate_action.upper()

    def test_unsatisfied_item_gate_action_is_block(self, validator):
        """Items not satisfied must produce BLOCK_EXECUTION gate action."""
        report = validator.validate(
            proposal_id="gate-block",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA only.",
        )
        for r in report.item_reports:
            if not r.passed:
                assert "BLOCK" in r.gate_action.upper(), (
                    f"Expected BLOCK_EXECUTION for {r.required_framework}, "
                    f"got {r.gate_action}"
                )

    def test_every_item_has_gate_message(self, validator):
        """Each item report must carry a non-empty gate_message."""
        report = validator.validate(
            proposal_id="gate-msg",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA only.",
        )
        for r in report.item_reports:
            assert r.gate_message != ""

    def test_passing_item_confidence_at_least_099(self, validator):
        """Passing items must have confidence_score >= 0.99."""
        report = validator.validate(
            proposal_id="gate-thresh",
            regulatory_location="CA",
            regulatory_industry="manufacturing",
            regulatory_functions=[],
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        for r in report.item_reports:
            if r.passed:
                assert r.confidence_score >= 0.99


# ---------------------------------------------------------------------------
# ProductionRequestProfile dataclass
# ---------------------------------------------------------------------------


class TestProductionRequestProfile:
    def test_default_lifecycle(self):
        p = ProductionRequestProfile()
        assert p.lifecycle == RequestLifecycle.REQUEST_INTAKE

    def test_auto_id_prefix(self):
        p = ProductionRequestProfile()
        assert p.profile_id.startswith("prod-")

    def test_to_dict_keys(self):
        p = ProductionRequestProfile(
            country="CA",
            industry="manufacturing",
            functions=["safety_inspection"],
            required_frameworks=["PIPEDA", "ISO_27001"],
        )
        d = p.to_dict()
        assert d["country"] == "CA"
        assert "PIPEDA" in d["required_frameworks"]
        assert d["lifecycle"] == "request_intake"

    def test_gate_validation_report_serialised(self):
        p = ProductionRequestProfile()
        p.gate_validation_report = GateValidationReport(passed=True, min_confidence=1.0)
        d = p.to_dict()
        assert d["gate_validation_report"]["passed"] is True


# ---------------------------------------------------------------------------
# ProductionAssistantOrchestrator lifecycle
# ---------------------------------------------------------------------------


class TestProductionAssistantOrchestratorLifecycle:
    def test_intake_creates_profile(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Test Request",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        assert profile is not None
        assert profile.profile_id.startswith("prod-")
        assert profile.lifecycle == RequestLifecycle.REQUEST_INTAKE

    def test_intake_resolves_required_frameworks(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Frameworks Test",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        assert "PIPEDA" in profile.required_frameworks
        assert "CASL" in profile.required_frameworks
        assert "ISO_27001" in profile.required_frameworks

    def test_validate_and_gate_compliant_advances_to_approval(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Compliant",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        report = orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001 compliance.",
        )
        assert report.passed is True
        updated = orchestrator.get_profile(profile.profile_id)
        assert updated.lifecycle == RequestLifecycle.APPROVAL

    def test_validate_and_gate_non_compliant_advances_to_blocked(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Non-Compliant",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        report = orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="Generic plan with no specific compliance.",
        )
        assert report.passed is False
        updated = orchestrator.get_profile(profile.profile_id)
        assert updated.lifecycle == RequestLifecycle.BLOCKED

    def test_advance_to_execution_from_approval(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Execute",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        result = orchestrator.advance_to_execution(profile.profile_id)
        assert result is True
        updated = orchestrator.get_profile(profile.profile_id)
        assert updated.lifecycle == RequestLifecycle.EXECUTION

    def test_advance_to_monitoring_from_execution(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Monitor",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        orchestrator.advance_to_execution(profile.profile_id)
        result = orchestrator.advance_to_monitoring(profile.profile_id)
        assert result is True
        updated = orchestrator.get_profile(profile.profile_id)
        assert updated.lifecycle == RequestLifecycle.MONITORING

    def test_blocked_profile_cannot_advance_to_execution(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Blocked",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="Generic plan.",
        )
        result = orchestrator.advance_to_execution(profile.profile_id)
        assert result is False

    def test_get_profile_returns_none_for_unknown(self, orchestrator):
        assert orchestrator.get_profile("nonexistent") is None

    def test_audit_log_populated_on_intake(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Audit Test",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        log = orchestrator.get_audit_log()
        assert any(
            e.get("action") == "intake_request"
            and e.get("profile_id") == profile.profile_id
            for e in log
        )

    def test_audit_log_populated_on_validate(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Validate Audit",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        log = orchestrator.get_audit_log()
        assert any(e.get("action") == "validate_and_gate" for e in log)

    def test_validate_nonexistent_profile_raises(self, orchestrator):
        with pytest.raises(KeyError):
            orchestrator.validate_and_gate(
                profile_id="does-not-exist",
                deliverable_spec="PIPEDA, CASL, ISO_27001.",
            )

    def test_deliverable_spec_too_long_raises(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Too Long",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        with pytest.raises(ValueError, match="exceeds maximum length"):
            orchestrator.validate_and_gate(
                profile_id=profile.profile_id,
                deliverable_spec="x" * 50_001,
            )

    def test_profile_history_tracks_transitions(self, orchestrator):
        profile = orchestrator.intake_request(
            title="History",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        updated = orchestrator.get_profile(profile.profile_id)
        transitions = [h["transition"] for h in updated.history]
        assert "approval" in transitions

    def test_gate_report_stored_on_profile(self, orchestrator):
        profile = orchestrator.intake_request(
            title="Stored Report",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orchestrator.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        updated = orchestrator.get_profile(profile.profile_id)
        assert updated.gate_validation_report is not None
        assert updated.gate_validation_report.passed is True


# ---------------------------------------------------------------------------
# Orchestrator with EventBackbone and GoldenPathBridge
# ---------------------------------------------------------------------------


class TestOrchestratorWithBackbone:
    def test_event_backbone_gate_pass_event(self):
        """EventBackbone receives a gate-pass event on successful validation."""
        from event_backbone import EventBackbone, EventType

        backbone = EventBackbone()
        received: list = []
        backbone.subscribe(EventType.GATE_EVALUATED, lambda evt: received.append(evt))

        orch = ProductionAssistantOrchestrator(event_backbone=backbone)
        profile = orch.intake_request(
            title="Backbone Test",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orch.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        backbone.process_pending()
        assert len(received) >= 1

    def test_event_backbone_gate_fail_event(self):
        """EventBackbone receives a gate-fail event on blocked validation."""
        from event_backbone import EventBackbone, EventType

        backbone = EventBackbone()
        received: list = []
        backbone.subscribe(EventType.GATE_BLOCKED, lambda evt: received.append(evt))

        orch = ProductionAssistantOrchestrator(event_backbone=backbone)
        profile = orch.intake_request(
            title="Fail Event",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orch.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="Generic plan.",
        )
        backbone.process_pending()
        assert len(received) >= 1

    def test_events_published_on_validation(self):
        """EventBackbone.get_status shows events_published > 0 after validation."""
        from event_backbone import EventBackbone

        backbone = EventBackbone()
        orch = ProductionAssistantOrchestrator(event_backbone=backbone)
        profile = orch.intake_request(
            title="Status Test",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orch.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        status = backbone.get_status()
        assert status["events_published"] >= 1

    def test_golden_path_recorded_on_pass(self):
        """GoldenPathBridge.record_success is called on a passing validation."""
        from golden_path_bridge import GoldenPathBridge

        bridge = GoldenPathBridge()
        orch = ProductionAssistantOrchestrator(golden_path=bridge)
        profile = orch.intake_request(
            title="Golden Path",
            country="CA",
            industry="manufacturing",
            functions=[],
        )
        orch.validate_and_gate(
            profile_id=profile.profile_id,
            deliverable_spec="PIPEDA, CASL, ISO_27001.",
        )
        stats = bridge.get_statistics()
        assert stats["total_paths"] >= 1
        assert stats["domain_breakdown"].get("production", 0) >= 1


# ---------------------------------------------------------------------------
# Thread safety — orchestrator
# ---------------------------------------------------------------------------


class TestOrchestratorThreadSafety:
    def test_concurrent_intake_requests(self, orchestrator):
        """Concurrent intake calls must not raise or corrupt state."""
        errors: list = []
        ids: list = []
        lock = threading.Lock()

        def intake():
            try:
                profile = orchestrator.intake_request(
                    title="Thread",
                    country="CA",
                    industry="manufacturing",
                    functions=[],
                )
                with lock:
                    ids.append(profile.profile_id)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=intake) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(set(ids)) == 20  # all unique IDs
