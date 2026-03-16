"""Tests for the Niche Viability Gate (niche_viability_gate.py).

Covers: capability check, bid acquisition, cost estimation, kill condition,
profit threshold, stealth pricing, HITL request/approval/rejection, Inoni LLC
entity, checkpoints, recovery, RFP gap analysis, credential negotiation, and
COYA documentation.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os

import pytest


from src.mss_controls import MSSController
from src.information_quality import InformationQualityEngine
from src.information_density import InformationDensityEngine
from src.resolution_scoring import ResolutionDetectionEngine
from src.structural_coherence import StructuralCoherenceEngine
from src.concept_translation import ConceptTranslationEngine
from src.simulation_engine import StrategicSimulationEngine
from src.inference_gate_engine import InferenceDomainGateEngine
from src.niche_business_generator import (
    NicheBusinessGenerator,
    NicheAutonomyClass,
    NicheRevenueModel,
    NicheDefinition,
)
from src.niche_viability_gate import (
    NicheViabilityGate,
    RFPGapAnalyzer,
    CredentialNegotiationEngine,
    DeployabilityStatus,
    ModuleStatus,
    PipelineStage,
    HITLDecision,
    CredentialType,
    GenerationType,
    StealthPricingModel,
    HumanRateEstimate,
    RFPAnalysis,
    ViabilityResult,
    CapabilityCheckResult,
    CostEstimate,
    ProfitProjection,
    HITLApprovalRequest,
    HITLApprovalDecision,
    InoniLLCEntity,
    PipelineCheckpoint,
    CredentialedHITLRequest,
    NegotiationRecord,
    COYARecord,
    RequiredCredential,
    CredentialRecord,
    MURPHY_PRICE_RATIO,
    _HUMAN_RATES_BY_INDUSTRY,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def controller():
    rde = ResolutionDetectionEngine()
    ide = InformationDensityEngine()
    sce = StructuralCoherenceEngine()
    iqe = InformationQualityEngine(rde, ide, sce)
    cte = ConceptTranslationEngine()
    sim = StrategicSimulationEngine()
    return MSSController(iqe, cte, sim)


@pytest.fixture(scope="module")
def inference_engine():
    return InferenceDomainGateEngine()


@pytest.fixture(scope="module")
def gate(controller, inference_engine):
    return NicheViabilityGate(inference_engine, controller)


@pytest.fixture(scope="module")
def generator(controller, inference_engine):
    return NicheBusinessGenerator(controller, inference_engine)


@pytest.fixture
def full_autonomy_niche():
    return NicheDefinition(
        niche_id="test_seo",
        name="SEO Content Site Generator",
        description="Automated SEO content site that publishes articles and monitors rankings",
        autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
        revenue_model=NicheRevenueModel.SUBSCRIPTION,
        estimated_industries=["technology"],
        murphy_modules_required=[
            "inference_gate_engine", "mss_controls", "llm_controller",
            "adaptive_campaign_engine",
        ],
        seed_data={"industry": "technology", "company_size": "small", "primary_goal": "seo"},
    )


@pytest.fixture
def hybrid_niche():
    return NicheDefinition(
        niche_id="test_notary",
        name="Digital Notary Routing Network",
        description="Murphy routes documents and schedules notaries for in-person signing",
        autonomy_class=NicheAutonomyClass.HYBRID,
        revenue_model=NicheRevenueModel.TRANSACTION,
        estimated_industries=["legal"],
        murphy_modules_required=[
            "inference_gate_engine", "mss_controls", "llm_controller", "form_intake",
        ],
        seed_data={
            "industry": "legal",
            "company_size": "small",
            "primary_goal": "route notary requests",
            "contractor_task_templates": [
                {
                    "description": "Perform in-person notarization and return signed documents",
                    "location_required": True,
                    "skill_required": "commissioned_notary",
                    "duration_hours": 1.0,
                    "payment": 50.0,
                    "gate_name": "notarization_gate",
                }
            ],
        },
    )


@pytest.fixture
def missing_module_niche():
    return NicheDefinition(
        niche_id="test_missing",
        name="Niche With Missing Modules",
        description="A niche that requires modules that do not exist",
        autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
        revenue_model=NicheRevenueModel.SUBSCRIPTION,
        estimated_industries=["technology"],
        murphy_modules_required=["nonexistent_module_xyz", "another_missing_module"],
        seed_data={"industry": "technology", "company_size": "small", "primary_goal": "test"},
    )


# ---------------------------------------------------------------------------
# Capability check
# ---------------------------------------------------------------------------

class TestCapabilityCheck:
    def test_capable_niche_returns_result(self, gate, full_autonomy_niche):
        result = gate.check_capability(full_autonomy_niche)
        assert isinstance(result, CapabilityCheckResult)

    def test_capable_niche_is_capable(self, gate, full_autonomy_niche):
        result = gate.check_capability(full_autonomy_niche)
        assert result.is_capable is True
        assert result.missing_count == 0

    def test_missing_modules_flagged(self, gate, missing_module_niche):
        result = gate.check_capability(missing_module_niche)
        assert result.is_capable is False
        assert result.missing_count >= 1
        assert len(result.gaps) >= 1

    def test_workflow_self_sufficient_for_known_niche(self, gate, full_autonomy_niche):
        result = gate.check_capability(full_autonomy_niche)
        assert result.workflow_self_sufficient is True

    def test_module_checks_length_matches_required(self, gate, full_autonomy_niche):
        result = gate.check_capability(full_autonomy_niche)
        assert len(result.module_checks) == len(full_autonomy_niche.murphy_modules_required)


# ---------------------------------------------------------------------------
# Bid acquisition
# ---------------------------------------------------------------------------

class TestBidAcquisition:
    def test_solicit_bids_returns_list(self, gate, hybrid_niche):
        bids = gate.solicit_bids(hybrid_niche)
        assert isinstance(bids, list)
        assert len(bids) > 0

    def test_full_autonomy_niche_no_bids(self, gate, full_autonomy_niche):
        bids = gate.solicit_bids(full_autonomy_niche)
        assert bids == []

    def test_select_cheapest_qualifying_bid(self, gate, hybrid_niche):
        bids = gate.solicit_bids(hybrid_niche)
        winner = gate.select_cheapest_qualifying_bid(bids)
        assert winner is not None
        assert winner.meets_acceptance_criteria is True

    def test_cheapest_qualifying_is_cheapest_among_qualifying(self, gate, hybrid_niche):
        bids = gate.solicit_bids(hybrid_niche)
        winner = gate.select_cheapest_qualifying_bid(bids)
        qualifying_amounts = [b.bid_amount for b in bids if b.meets_acceptance_criteria]
        assert winner.bid_amount == min(qualifying_amounts)

    def test_no_qualifying_bids_returns_none(self, gate):
        from src.niche_viability_gate import ContractorBid
        bad_bids = [
            ContractorBid(
                bid_id="b1", niche_id="x", task_description="t",
                bidder_id="b", bid_amount=10.0, skill_offered="s",
                location_capable=False, meets_acceptance_criteria=False,
                evaluation_score=0.0,
            )
        ]
        result = gate.select_cheapest_qualifying_bid(bad_bids)
        assert result is None


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

class TestCostEstimation:
    def test_estimate_costs_returns_cost_estimate(self, gate, full_autonomy_niche):
        result = gate.estimate_costs(full_autonomy_niche)
        assert isinstance(result, CostEstimate)

    def test_full_autonomy_no_contractor_cost(self, gate, full_autonomy_niche):
        result = gate.estimate_costs(full_autonomy_niche)
        assert result.contractor_acquisition_cost == 0.0

    def test_hybrid_with_bid_has_contractor_cost(self, gate, hybrid_niche):
        bids = gate.solicit_bids(hybrid_niche)
        winner = gate.select_cheapest_qualifying_bid(bids)
        result = gate.estimate_costs(hybrid_niche, winner)
        assert result.contractor_acquisition_cost > 0.0

    def test_total_build_cost_is_sum(self, gate, full_autonomy_niche):
        result = gate.estimate_costs(full_autonomy_niche)
        expected = round(
            result.llm_generation_cost
            + result.contractor_acquisition_cost
            + result.delivery_cost,
            4,
        )
        assert abs(result.total_build_cost - expected) < 0.001

    def test_cost_breakdown_keys_present(self, gate, full_autonomy_niche):
        result = gate.estimate_costs(full_autonomy_niche)
        for key in ("llm_inference", "llm_mss_ops", "contractor_bid", "delivery_base"):
            assert key in result.cost_breakdown


# ---------------------------------------------------------------------------
# Kill condition
# ---------------------------------------------------------------------------

class TestKillCondition:
    def test_kill_when_cost_exceeds_revenue(self, gate):
        assert gate.check_kill_condition(1000.0, 500.0) is True

    def test_no_kill_when_revenue_exceeds_cost(self, gate):
        assert gate.check_kill_condition(10.0, 5000.0) is False

    def test_no_kill_when_equal(self, gate):
        assert gate.check_kill_condition(100.0, 100.0) is False


# ---------------------------------------------------------------------------
# Profit threshold
# ---------------------------------------------------------------------------

class TestProfitThreshold:
    def test_passes_threshold(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        projection = gate.check_profit_threshold(cost, 10000.0, 2.0)
        assert projection.passes_threshold is True

    def test_fails_threshold(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        projection = gate.check_profit_threshold(cost, cost.total_build_cost * 1.5, 2.0)
        assert projection.passes_threshold is False

    def test_projected_margin_calculation(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        projection = gate.check_profit_threshold(cost, 1000.0, 2.0)
        expected_margin = round(1000.0 / cost.total_build_cost, 4)
        assert abs(projection.projected_margin - expected_margin) < 0.01


# ---------------------------------------------------------------------------
# Stealth pricing model
# ---------------------------------------------------------------------------

class TestStealthPricing:
    def test_estimate_human_rate_returns_estimate(self, gate, full_autonomy_niche):
        est = gate.estimate_human_rate(full_autonomy_niche)
        assert isinstance(est, HumanRateEstimate)
        assert est.human_rate_monthly > 0.0

    def test_human_rate_matches_industry(self, gate, full_autonomy_niche):
        est = gate.estimate_human_rate(full_autonomy_niche)
        expected = _HUMAN_RATES_BY_INDUSTRY["technology"]
        assert est.human_rate_monthly == expected

    def test_stealth_pricing_returns_model(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        model = gate.build_stealth_pricing(full_autonomy_niche, cost)
        assert isinstance(model, StealthPricingModel)

    def test_murphy_price_is_75_pct_of_human_rate(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        model = gate.build_stealth_pricing(full_autonomy_niche, cost)
        expected = round(model.human_rate * MURPHY_PRICE_RATIO, 2)
        assert abs(model.murphy_price - expected) < 0.01

    def test_client_savings_pct_is_25(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        model = gate.build_stealth_pricing(full_autonomy_niche, cost)
        assert abs(model.client_savings_pct - 25.0) < 0.1

    def test_gross_profit_is_positive(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        model = gate.build_stealth_pricing(full_autonomy_niche, cost)
        assert model.gross_profit > 0.0

    def test_gross_margin_is_very_high_for_full_autonomy(self, gate, full_autonomy_niche):
        # Full autonomy: LLM + delivery only, no contractor.  Margin should be > 95 %.
        cost = gate.estimate_costs(full_autonomy_niche)
        model = gate.build_stealth_pricing(full_autonomy_niche, cost)
        assert model.gross_margin_pct > 95.0

    def test_gross_profit_formula(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        model = gate.build_stealth_pricing(full_autonomy_niche, cost)
        expected = round(model.murphy_price - model.total_variable_cost, 4)
        assert abs(model.gross_profit - expected) < 0.01

    def test_compare_to_human_cost_dict_keys(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        comparison = gate.compare_to_human_cost(full_autonomy_niche, cost)
        for key in ("human_rate_monthly", "murphy_price_monthly", "gross_profit", "gross_margin_pct"):
            assert key in comparison


# ---------------------------------------------------------------------------
# Inoni LLC entity
# ---------------------------------------------------------------------------

class TestInoniLLCEntity:
    def test_entity_name_format(self, gate, full_autonomy_niche):
        entity = gate.create_inoni_entity(
            full_autonomy_niche, DeployabilityStatus.PENDING_HITL_REVIEW, None
        )
        assert entity.entity_name == "Inoni SEO Content Site Generator LLC"

    def test_powered_by_is_murphy_system(self, gate, full_autonomy_niche):
        entity = gate.create_inoni_entity(
            full_autonomy_niche, DeployabilityStatus.PENDING_HITL_REVIEW, None
        )
        assert entity.powered_by == "Murphy System"

    def test_operator_is_inoni_llc(self, gate, full_autonomy_niche):
        entity = gate.create_inoni_entity(
            full_autonomy_niche, DeployabilityStatus.PENDING_HITL_REVIEW, None
        )
        assert entity.operator == "Inoni Limited Liability Company"

    def test_legal_name_matches_entity_name(self, gate, full_autonomy_niche):
        entity = gate.create_inoni_entity(
            full_autonomy_niche, DeployabilityStatus.PENDING_HITL_REVIEW, None
        )
        assert entity.legal_name == entity.entity_name


# ---------------------------------------------------------------------------
# HITL request and approval
# ---------------------------------------------------------------------------

class TestHITLFlow:
    def test_create_hitl_request_returns_request(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        profit = gate.check_profit_threshold(cost, 10000.0, 2.0)
        cap = gate.check_capability(full_autonomy_niche)
        req = gate.create_hitl_request(full_autonomy_niche, cap, cost, profit)
        assert isinstance(req, HITLApprovalRequest)

    def test_hitl_request_has_risk_profile(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        profit = gate.check_profit_threshold(cost, 10000.0, 2.0)
        cap = gate.check_capability(full_autonomy_niche)
        req = gate.create_hitl_request(full_autonomy_niche, cap, cost, profit)
        assert req.risk_profile.total_financial_exposure > 0.0
        assert "risk_accepted" in req.risk_profile.approver_liability.lower() or \
               "responsibility" in req.risk_profile.approver_liability.lower()

    def test_hitl_request_inoni_entity_name(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        profit = gate.check_profit_threshold(cost, 10000.0, 2.0)
        cap = gate.check_capability(full_autonomy_niche)
        req = gate.create_hitl_request(full_autonomy_niche, cap, cost, profit)
        assert "Inoni" in req.inoni_entity_name
        assert "LLC" in req.inoni_entity_name

    def test_approve_requires_risk_accepted(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        profit = gate.check_profit_threshold(cost, 10000.0, 2.0)
        cap = gate.check_capability(full_autonomy_niche)
        req = gate.create_hitl_request(full_autonomy_niche, cap, cost, profit)
        with pytest.raises(ValueError):
            gate.approve_hitl_request(req.request_id, "corey_post", risk_accepted=False)

    def test_approve_with_risk_accepted_returns_decision(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        profit = gate.check_profit_threshold(cost, 10000.0, 2.0)
        cap = gate.check_capability(full_autonomy_niche)
        req = gate.create_hitl_request(full_autonomy_niche, cap, cost, profit)
        decision = gate.approve_hitl_request(
            req.request_id, "corey_post", notes="approved", risk_accepted=True
        )
        assert decision.decision == HITLDecision.APPROVED
        assert decision.risk_accepted is True

    def test_reject_returns_rejected_decision(self, gate, full_autonomy_niche):
        cost = gate.estimate_costs(full_autonomy_niche)
        profit = gate.check_profit_threshold(cost, 10000.0, 2.0)
        cap = gate.check_capability(full_autonomy_niche)
        req = gate.create_hitl_request(full_autonomy_niche, cap, cost, profit)
        decision = gate.reject_hitl_request(req.request_id, "corey_post", notes="too risky")
        assert decision.decision == HITLDecision.REJECTED
        assert decision.risk_accepted is False

    def test_approve_unknown_request_raises(self, gate):
        with pytest.raises(KeyError):
            gate.approve_hitl_request("nonexistent-id", "corey_post", risk_accepted=True)


# ---------------------------------------------------------------------------
# Checkpoints and recovery
# ---------------------------------------------------------------------------

class TestCheckpointsAndRecovery:
    def test_checkpoint_is_created(self, gate, full_autonomy_niche):
        cp = gate.checkpoint(
            PipelineStage.CAPABILITY_CHECK,
            full_autonomy_niche.niche_id,
            {"test": True},
        )
        assert isinstance(cp, PipelineCheckpoint)

    def test_get_checkpoints_returns_list(self, gate, full_autonomy_niche):
        gate.checkpoint(PipelineStage.INIT, "cp_test_niche", {})
        checkpoints = gate.get_checkpoints("cp_test_niche")
        assert isinstance(checkpoints, list)
        assert len(checkpoints) >= 1

    def test_recover_returns_last_recoverable(self, gate):
        gate.checkpoint(PipelineStage.INIT, "rec_test", {}, can_recover=True)
        gate.checkpoint(PipelineStage.CAPABILITY_CHECK, "rec_test", {}, can_recover=True)
        cp = gate.recover("rec_test")
        assert cp is not None
        assert cp.can_recover is True

    def test_recover_unknown_niche_returns_none(self, gate):
        cp = gate.recover("nonexistent_niche_xyzzy")
        assert cp is None


# ---------------------------------------------------------------------------
# Full evaluate() pipeline
# ---------------------------------------------------------------------------

class TestEvaluatePipeline:
    def test_evaluate_returns_viability_result(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        assert isinstance(result, ViabilityResult)

    def test_evaluate_pending_hitl_for_capable_niche(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        assert result.deployability_status == DeployabilityStatus.PENDING_HITL_REVIEW

    def test_evaluate_not_deployable_for_missing_modules(self, gate, missing_module_niche):
        result = gate.evaluate(missing_module_niche)
        assert result.deployability_status == DeployabilityStatus.NOT_DEPLOYABLE

    def test_evaluate_has_stealth_pricing(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        assert result.stealth_pricing is not None
        assert isinstance(result.stealth_pricing, StealthPricingModel)

    def test_evaluate_stealth_pricing_uses_murphy_price(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        assert result.stealth_pricing.murphy_price > 0.0
        assert result.profit_projection is not None
        # Projected revenue should match murphy_price (75 % of human rate)
        assert abs(
            result.profit_projection.projected_revenue - result.stealth_pricing.murphy_price
        ) < 1.0

    def test_evaluate_hybrid_niche_has_bids(self, gate, hybrid_niche):
        result = gate.evaluate(hybrid_niche)
        assert len(result.contractor_bids) > 0

    def test_evaluate_has_hitl_request(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        assert result.hitl_request is not None
        assert isinstance(result.hitl_request, HITLApprovalRequest)

    def test_evaluate_has_inoni_entity(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        assert isinstance(result.inoni_entity, InoniLLCEntity)
        assert "LLC" in result.inoni_entity.entity_name

    def test_evaluate_has_checkpoints(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        assert len(result.checkpoints) >= 3

    def test_evaluate_not_deployable_returns_rejection_reasons(self, gate, missing_module_niche):
        result = gate.evaluate(missing_module_niche)
        assert len(result.rejection_reasons) > 0

    def test_finalise_after_hitl_approved(self, gate, full_autonomy_niche):
        result = gate.evaluate(full_autonomy_niche)
        req = result.hitl_request
        decision = gate.approve_hitl_request(req.request_id, "corey_post", risk_accepted=True)

        class FakeSpec:
            mss_results = [object()]
            inference_result = object()

        updated = gate.finalise_after_hitl(result, decision, FakeSpec())
        assert updated.deployability_status == DeployabilityStatus.DEPLOYABLE
        assert updated.validation_passed is True


# ---------------------------------------------------------------------------
# RFP gap analysis
# ---------------------------------------------------------------------------

class TestRFPGapAnalysis:
    @pytest.fixture(scope="class")
    def rfp_analyzer(self, controller, inference_engine):
        return RFPGapAnalyzer(inference_engine, controller)

    @pytest.fixture(scope="class")
    def seo_niche(self):
        return NicheDefinition(
            niche_id="rfp_seo",
            name="SEO Content",
            description="SEO content automation",
            autonomy_class=NicheAutonomyClass.FULL_AUTONOMY,
            revenue_model=NicheRevenueModel.SUBSCRIPTION,
            estimated_industries=["technology"],
            murphy_modules_required=["inference_gate_engine", "mss_controls"],
            seed_data={"industry": "technology", "company_size": "small", "primary_goal": "seo"},
        )

    def test_analyze_returns_rfp_analysis(self, rfp_analyzer, seo_niche):
        rfp_text = "We need monthly SEO articles, keyword research, and competitor analysis."
        result = rfp_analyzer.analyze(rfp_text, seo_niche)
        assert isinstance(result, RFPAnalysis)

    def test_digital_rfp_can_fully_deliver(self, rfp_analyzer, seo_niche):
        rfp_text = "Monthly SEO articles and performance reports"
        result = rfp_analyzer.analyze(rfp_text, seo_niche)
        assert result.can_fully_deliver is True
        assert result.requires_human_augmentation is False

    def test_physical_rfp_requires_human_augmentation(self, rfp_analyzer):
        physical_niche = NicheDefinition(
            niche_id="rfp_inspect",
            name="Property Inspection",
            description="On-site property inspection service",
            autonomy_class=NicheAutonomyClass.HYBRID,
            revenue_model=NicheRevenueModel.TRANSACTION,
            estimated_industries=["real_estate"],
            murphy_modules_required=["inference_gate_engine", "mss_controls"],
            seed_data={"industry": "real_estate", "company_size": "small", "primary_goal": "inspect"},
        )
        rfp_text = "We need on-site property inspection with photography and structural assessment"
        result = rfp_analyzer.analyze(rfp_text, physical_niche)
        assert result.requires_human_augmentation is True

    def test_rfp_has_stealth_quote(self, rfp_analyzer, seo_niche):
        rfp_text = "Monthly SEO articles and competitive analysis reports"
        result = rfp_analyzer.analyze(rfp_text, seo_niche)
        assert result.stealth_quote is not None
        assert result.stealth_quote.murphy_price > 0.0

    def test_stealth_quote_is_75_pct_of_human_rate(self, rfp_analyzer, seo_niche):
        rfp_text = "Monthly content and reports"
        result = rfp_analyzer.analyze(rfp_text, seo_niche)
        expected = round(result.human_rate_for_rfp * MURPHY_PRICE_RATIO, 2)
        assert abs(result.stealth_quote.murphy_price - expected) < 1.0

    def test_rfp_murphy_coverage_pct(self, rfp_analyzer, seo_niche):
        rfp_text = "Monthly SEO content, keyword research, competitor analysis"
        result = rfp_analyzer.analyze(rfp_text, seo_niche)
        assert 0.0 <= result.murphy_coverage_pct <= 100.0

    def test_rfp_gap_items_match_requirements(self, rfp_analyzer, seo_niche):
        rfp_text = "We need monthly reports and dashboards"
        result = rfp_analyzer.analyze(rfp_text, seo_niche)
        assert len(result.gap_items) == len(result.requirements)

    def test_generator_analyze_rfp(self, generator):
        result = generator.analyze_rfp(
            "Monthly SEO articles and keyword research reports",
            "niche_seo_sites",
        )
        assert result is not None
        assert hasattr(result, "rfp") and hasattr(result, "requirements")
        assert hasattr(result, "stealth_quote")

    def test_generator_analyze_rfp_unknown_niche_returns_none(self, generator):
        result = generator.analyze_rfp("some rfp text", "nonexistent_niche_id")
        assert result is None


# ---------------------------------------------------------------------------
# Credential + negotiation (COYA)
# ---------------------------------------------------------------------------

class TestCredentialNegotiationEngine:
    @pytest.fixture
    def cne(self):
        return CredentialNegotiationEngine()

    def test_identify_credentials_for_notary(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        assert len(creds) >= 1
        assert creds[0].is_mandatory is True
        assert creds[0].credential_type == CredentialType.LICENSE

    def test_identify_no_credential_for_general(self, cne):
        creds = cne.identify_required_credentials("general")
        assert len(creds) == 0

    def test_create_credentialed_request(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="task_001",
            niche_id="test_notary",
            task_description="Notarize and return signed documents",
            required_credential=creds[0],
            payment_ceiling=50.0,
            persona_name="Jenny",
        )
        assert isinstance(req, CredentialedHITLRequest)
        assert req.persona_name == "Jenny"
        assert "Jenny" in req.persona_intro
        assert req.status == "pending"

    def test_persona_intro_does_not_reveal_murphy(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t1", niche_id="n1",
            task_description="Notarize docs",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        # The persona intro should not mention "Murphy" or "AI"
        assert "Murphy" not in req.persona_intro
        assert "artificial intelligence" not in req.persona_intro.lower()

    def test_record_credentials(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t2", niche_id="n2",
            task_description="Notarize",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        record = cne.record_credentials(req.request_id, {
            "holder_name": "Jane Smith",
            "credential_number": "NOT-12345",
            "issue_date": "2020-01-01",
            "expiry_date": "2026-01-01",
        })
        assert isinstance(record, CredentialRecord)
        assert record.verified is True
        assert record.credential_number == "NOT-12345"

    def test_record_credentials_unknown_request_raises(self, cne):
        with pytest.raises(KeyError):
            cne.record_credentials("nonexistent-id", {"holder_name": "X"})

    def test_build_negotiation_75_25(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t3", niche_id="n3",
            task_description="Notarize docs",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        negotiation = cne.build_negotiation(req.request_id, {
            "rate": 45.0,
            "preferred_contact": "email",
            "schedule_note": "morning preferred",
        })
        assert isinstance(negotiation, NegotiationRecord)
        assert negotiation.murphy_weight >= 0.70
        assert negotiation.human_weight <= 0.30

    def test_verify_75_25_balance_passes(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t4", niche_id="n4",
            task_description="Notarize",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        neg = cne.build_negotiation(req.request_id, {"rate": 48.0})
        assert cne.verify_75_25_balance(neg) is True

    def test_agreed_rate_capped_at_ceiling(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t5", niche_id="n5",
            task_description="Notarize",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        neg = cne.build_negotiation(req.request_id, {"rate": 999.0})  # way over ceiling
        # Agreed rate should be capped at payment_ceiling
        rate_terms = [t for t in neg.human_terms if "rate" in t.description.lower()]
        assert len(rate_terms) >= 1
        agreed_val = float(rate_terms[0].value)
        assert agreed_val <= 50.0

    def test_create_coya_record(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t6", niche_id="n6",
            task_description="Notarize",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        cr = cne.record_credentials(req.request_id, {
            "holder_name": "Bob", "credential_number": "NOT-001", "issue_date": "2021-01-01",
        })
        neg = cne.build_negotiation(req.request_id, {"rate": 45.0})
        coya = cne.create_coya_record(neg, cr, "t6")
        assert isinstance(coya, COYARecord)
        assert coya.completion_status == "pending"

    def test_record_task_completion_success(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t7", niche_id="n7",
            task_description="Notarize",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        cr = cne.record_credentials(req.request_id, {
            "holder_name": "Alice", "credential_number": "NOT-002", "issue_date": "2021-06-01",
        })
        neg = cne.build_negotiation(req.request_id, {"rate": 45.0})
        coya = cne.create_coya_record(neg, cr, "t7")
        updated = cne.record_task_completion(
            coya.coya_id, completed=True, evidence={"signed_docs": "doc.pdf"}
        )
        assert updated.completion_status == "completed"
        assert updated.gate_passed is True

    def test_record_task_completion_failure(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t8", niche_id="n8",
            task_description="Notarize",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        cr = cne.record_credentials(req.request_id, {
            "holder_name": "Dave", "credential_number": "NOT-003", "issue_date": "2022-01-01",
        })
        neg = cne.build_negotiation(req.request_id, {"rate": 45.0})
        coya = cne.create_coya_record(neg, cr, "t8")
        updated = cne.record_task_completion(coya.coya_id, completed=False, evidence={})
        assert updated.completion_status == "failed"
        assert updated.gate_passed is False
        assert len(updated.discrepancies) > 0

    def test_check_commitment_fulfilled_true(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="t9", niche_id="n9",
            task_description="Notarize",
            required_credential=creds[0],
            payment_ceiling=50.0,
        )
        cr = cne.record_credentials(req.request_id, {
            "holder_name": "Eve", "credential_number": "NOT-004", "issue_date": "2020-01-01",
        })
        neg = cne.build_negotiation(req.request_id, {"rate": 45.0})
        coya = cne.create_coya_record(neg, cr, "t9")
        cne.record_task_completion(coya.coya_id, completed=True, evidence={"doc": "signed"})
        assert cne.check_commitment_fulfilled(coya.coya_id) is True

    def test_check_commitment_unknown_coya_returns_false(self, cne):
        assert cne.check_commitment_fulfilled("nonexistent") is False


# ---------------------------------------------------------------------------
# NicheBusinessGenerator integration
# ---------------------------------------------------------------------------

class TestGeneratorIntegration:
    def test_spec_has_viability_result(self, generator):
        niche = generator.get_niche("niche_seo_sites")
        spec = generator.generate_niche(niche)
        assert spec.viability_result is not None

    def test_spec_viability_has_stealth_pricing(self, generator):
        niche = generator.get_niche("compliance_checklist")
        spec = generator.generate_niche(niche)
        assert spec.viability_result.stealth_pricing is not None

    def test_spec_inoni_entity_name_format(self, generator):
        niche = generator.get_niche("niche_seo_sites")
        spec = generator.generate_niche(niche)
        assert spec.inoni_entity is not None
        assert spec.inoni_entity.entity_name.startswith("Inoni ")
        assert spec.inoni_entity.entity_name.endswith(" LLC")

    def test_spec_inoni_entity_powered_by(self, generator):
        niche = generator.get_niche("niche_seo_sites")
        spec = generator.generate_niche(niche)
        assert spec.inoni_entity.powered_by == "Murphy System"

    def test_deployment_ready_false_before_hitl(self, generator):
        niche = generator.get_niche("newsletter_businesses")
        spec = generator.generate_niche(niche)
        # Viability gate returns PENDING_HITL — not deployable until approved
        assert spec.deployment_ready is False

    def test_approve_niche_requires_risk_accepted(self, generator):
        niche = generator.get_niche("compliance_checklist")
        spec = generator.generate_niche(niche)
        request_id = spec.viability_result.hitl_request.request_id
        with pytest.raises(ValueError):
            generator.approve_niche(request_id, "corey_post", risk_accepted=False)

    def test_approve_niche_with_risk_accepted(self, generator):
        niche = generator.get_niche("competitive_intel_sites")
        spec = generator.generate_niche(niche)
        request_id = spec.viability_result.hitl_request.request_id
        decision = generator.approve_niche(request_id, "corey_post", risk_accepted=True)
        assert decision.decision == HITLDecision.APPROVED
        assert decision.risk_accepted is True
        assert decision.decided_by == "corey_post"

    def test_get_viability_gate_returns_gate(self, generator):
        gate = generator.get_viability_gate()
        assert hasattr(gate, "evaluate")
        assert hasattr(gate, "approve_hitl_request")
        assert hasattr(gate, "check_capability")

    def test_get_credential_engine(self, generator):
        engine = generator.get_credential_engine()
        assert hasattr(engine, "identify_required_credentials")
        assert hasattr(engine, "build_negotiation")
        assert hasattr(engine, "create_coya_record")

    def test_get_coya_records_returns_list(self, generator):
        records = generator.get_coya_records("niche_seo_sites")
        assert isinstance(records, list)


# ---------------------------------------------------------------------------
# Contractor quality scoring and flexible negotiation
# ---------------------------------------------------------------------------

class TestContractorQualityScoring:
    @pytest.fixture
    def cne(self):
        return CredentialNegotiationEngine()

    def _setup_negotiation(self, cne, task_id="tq1", niche_id="nq1", rate=45.0):
        """Helper: create request + record creds + build negotiation."""
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id=task_id, niche_id=niche_id,
            task_description="Notarize docs",
            required_credential=creds[0], payment_ceiling=50.0,
        )
        cr = cne.record_credentials(req.request_id, {
            "holder_name": "Alice Notary",
            "credential_number": "NOT-777",
            "issue_date": "2015-03-01",
            "expiry_date": "2027-03-01",
        })
        neg = cne.build_negotiation(req.request_id, {"rate": rate})
        return req, cr, neg

    def test_score_contractor_returns_profile(self, cne):
        req, cr, neg = self._setup_negotiation(cne)
        profile = cne.score_contractor("contractor_alice", neg, cr)
        assert hasattr(profile, "composite_score")

    def test_composite_score_between_0_and_1(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq2", "nq2")
        profile = cne.score_contractor("c2", neg, cr)
        assert 0.0 <= profile.composite_score <= 1.0

    def test_unknown_contractor_history_score_is_neutral(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq3", "nq3")
        profile = cne.score_contractor("c3", neg, cr, past_coya_records=[])
        assert profile.history_score == 0.50

    def test_established_credential_improves_longevity(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="tq4", niche_id="nq4",
            task_description="Notarize",
            required_credential=creds[0], payment_ceiling=50.0,
        )
        cr_old = cne.record_credentials(req.request_id, {
            "holder_name": "Old Pro", "credential_number": "NOT-OLD-001",
            "issue_date": "2010-01-01", "expiry_date": "2028-01-01",
        })
        neg = cne.build_negotiation(req.request_id, {"rate": 45.0})
        profile = cne.score_contractor("c_old", neg, cr_old)
        assert profile.longevity_score > 0.5

    def test_55_45_qualification_requires_strong_scores(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq5", "nq5")
        profile = cne.score_contractor("c5", neg, cr)
        # 55/45 requires composite >= 0.70, longevity >= 0.60, deal_strength >= 0.65
        if profile.qualifies_for_55_45:
            assert profile.composite_score >= 0.70
            assert profile.longevity_score >= 0.60

    def test_partner_eligible_requires_high_composite(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq6", "nq6")
        profile = cne.score_contractor("c6", neg, cr)
        if profile.partner_eligible:
            assert profile.composite_score >= 0.80

    def test_profile_assessment_notes_not_empty(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq7", "nq7")
        profile = cne.score_contractor("c7", neg, cr)
        assert len(profile.assessment_notes) > 0

    def test_evaluate_balance_standard_passes_at_75(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq8", "nq8")
        # Standard 75/25 balance should pass
        assert cne.evaluate_negotiation_balance(neg) is True

    def test_evaluate_balance_rejects_below_55(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq9", "nq9")
        neg.murphy_weight = 0.45
        assert cne.evaluate_negotiation_balance(neg) is False

    def test_evaluate_balance_rejects_low_without_quality(self, cne):
        req, cr, neg = self._setup_negotiation(cne, "tq10", "nq10")
        neg.murphy_weight = 0.60
        neg.balance_valid = False
        # Without quality profile, 0.60 is below the 0.70 standard minimum
        assert cne.evaluate_negotiation_balance(neg) is False

    def test_evaluate_balance_accepts_55_with_quality_override(self, cne):
        from src.niche_viability_gate import ContractorQualityProfile
        req, cr, neg = self._setup_negotiation(cne, "tq11", "nq11")
        neg.murphy_weight = 0.60
        neg.balance_valid = False
        # Create a strong quality profile that qualifies for 55/45
        profile = ContractorQualityProfile(
            contractor_id="c_strong",
            history_score=0.90,
            longevity_score=0.85,
            ease_of_work_score=0.85,
            negotiation_reasonableness_score=0.80,
            deal_strength_score=0.85,
            composite_score=0.85,
            qualifies_for_55_45=True,
            partner_eligible=True,
            assessment_notes="Excellent contractor",
            assessed_at="2026-01-01T00:00:00+00:00",
        )
        result = cne.evaluate_negotiation_balance(neg, quality_profile=profile)
        assert result is True
        assert neg.quality_override is True

    def test_quality_override_sets_accepted_balance(self, cne):
        from src.niche_viability_gate import ContractorQualityProfile
        req, cr, neg = self._setup_negotiation(cne, "tq12", "nq12")
        neg.murphy_weight = 0.58
        profile = ContractorQualityProfile(
            contractor_id="c_bal",
            history_score=0.90, longevity_score=0.85, ease_of_work_score=0.85,
            negotiation_reasonableness_score=0.80, deal_strength_score=0.85,
            composite_score=0.85, qualifies_for_55_45=True, partner_eligible=True,
            assessment_notes="Good", assessed_at="2026-01-01T00:00:00+00:00",
        )
        cne.evaluate_negotiation_balance(neg, quality_profile=profile)
        assert neg.accepted_balance == 0.58


# ---------------------------------------------------------------------------
# Partner program
# ---------------------------------------------------------------------------

class TestPartnerProgram:
    @pytest.fixture
    def cne(self):
        return CredentialNegotiationEngine()

    def _build_partner_eligible_profile(self, contractor_id="partner_c"):
        from src.niche_viability_gate import ContractorQualityProfile
        return ContractorQualityProfile(
            contractor_id=contractor_id,
            history_score=0.95,
            longevity_score=0.90,
            ease_of_work_score=0.90,
            negotiation_reasonableness_score=0.85,
            deal_strength_score=0.92,
            composite_score=0.91,
            qualifies_for_55_45=True,
            partner_eligible=True,
            assessment_notes="Exceptional contractor — partner eligible",
            assessed_at="2026-01-01T00:00:00+00:00",
        )

    def _build_credential(self, cne):
        creds = cne.identify_required_credentials("commissioned_notary")
        req = cne.create_credentialed_request(
            task_id="p_t1", niche_id="p_n1",
            task_description="Notarize docs",
            required_credential=creds[0], payment_ceiling=50.0,
        )
        return cne.record_credentials(req.request_id, {
            "holder_name": "Partner Pro",
            "credential_number": "NOT-PARTNER-001",
            "issue_date": "2012-01-01",
        })

    def test_register_partner_returns_record(self, cne):
        cr = self._build_credential(cne)
        profile = self._build_partner_eligible_profile()
        partner = cne.register_partner("partner_001", cr, profile, niche_ids=["notary_network"])
        assert hasattr(partner, "partner_id")
        assert partner.active is True

    def test_register_partner_not_eligible_raises(self, cne):
        from src.niche_viability_gate import ContractorQualityProfile
        cr = self._build_credential(cne)
        weak_profile = ContractorQualityProfile(
            contractor_id="weak_c", history_score=0.5, longevity_score=0.5,
            ease_of_work_score=0.5, negotiation_reasonableness_score=0.5,
            deal_strength_score=0.5, composite_score=0.55,
            qualifies_for_55_45=False, partner_eligible=False,
            assessment_notes="Not yet", assessed_at="2026-01-01T00:00:00+00:00",
        )
        with pytest.raises(ValueError):
            cne.register_partner("weak_001", cr, weak_profile)

    def test_get_preferred_partner_returns_partner(self, cne):
        cr = self._build_credential(cne)
        profile = self._build_partner_eligible_profile("partner_002")
        cne.register_partner("partner_002", cr, profile, niche_ids=["notary_network"])
        result = cne.get_preferred_partner("notary_network", "commissioned_notary")
        assert result is not None
        assert result.active is True

    def test_get_preferred_partner_unknown_niche_returns_none(self, cne):
        result = cne.get_preferred_partner("nonexistent_niche_xyz", "any_skill")
        assert result is None

    def test_get_partners_for_niche(self, cne):
        cr = self._build_credential(cne)
        profile = self._build_partner_eligible_profile("partner_003")
        cne.register_partner("partner_003", cr, profile, niche_ids=["test_niche_p"])
        partners = cne.get_partners_for_niche("test_niche_p")
        assert len(partners) >= 1

    def test_update_partner_stats_completed(self, cne):
        cr = self._build_credential(cne)
        profile = self._build_partner_eligible_profile("partner_004")
        partner = cne.register_partner("partner_004", cr, profile)
        updated = cne.update_partner_stats(partner.partner_id, task_completed=True)
        assert updated.tasks_completed == 1
        assert updated.success_rate > 0.0

    def test_update_partner_stats_failed(self, cne):
        cr = self._build_credential(cne)
        profile = self._build_partner_eligible_profile("partner_005")
        partner = cne.register_partner("partner_005", cr, profile)
        cne.update_partner_stats(partner.partner_id, task_completed=True)
        cne.update_partner_stats(partner.partner_id, task_completed=False)
        p = cne._partners[partner.partner_id]
        assert p.tasks_completed == 1
        assert p.tasks_failed == 1
        assert abs(p.success_rate - 0.5) < 0.01

    def test_update_partner_unknown_raises(self, cne):
        with pytest.raises(KeyError):
            cne.update_partner_stats("nonexistent", task_completed=True)

    def test_generator_promote_contractor_to_partner(self, generator):
        from src.niche_viability_gate import ContractorQualityProfile, CredentialRecord, CredentialType
        cr = CredentialRecord(
            record_id="gen_cr_001", holder_id="gen_c_001",
            holder_name="Gen Partner", masked_as=None,
            credential_type=CredentialType.LICENSE,
            credential_number="NOT-GEN-001", issuing_body="State",
            issue_date="2015-01-01", expiry_date="2028-01-01",
            verified=True, verification_method="self_reported",
            verified_at="2026-01-01T00:00:00+00:00", masked_for_output=True,
        )
        profile = ContractorQualityProfile(
            contractor_id="gen_c_001",
            history_score=0.95, longevity_score=0.90, ease_of_work_score=0.90,
            negotiation_reasonableness_score=0.85, deal_strength_score=0.92,
            composite_score=0.91, qualifies_for_55_45=True, partner_eligible=True,
            assessment_notes="Excellent", assessed_at="2026-01-01T00:00:00+00:00",
        )
        partner = generator.promote_contractor_to_partner(
            "gen_c_001", cr, profile, niche_ids=["niche_seo_sites"]
        )
        assert hasattr(partner, "partner_id")
        assert partner.active is True
