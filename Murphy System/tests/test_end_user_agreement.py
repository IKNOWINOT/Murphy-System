"""Tests for the End User Agreement generator (end_user_agreement.py).

The EUA mitigates Inoni's risk and transfers it to the human-in-the-loop
validator and/or contractor who accepts the task.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os

import pytest


from src.end_user_agreement import (
    EUAGenerator,
    EUADocument,
    EUASection,
    EUASectionType,
    RiskTransferClause,
    AutomationRequirement,
    EUAAcceptance,
    EUAAcceptanceMethod,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def generator():
    return EUAGenerator()


@pytest.fixture
def full_autonomy_eua(generator):
    return generator.generate(
        niche_id="test_seo",
        niche_name="SEO Content Site Generator",
        inoni_entity_name="Inoni SEO Content Site Generator LLC",
        autonomy_class="full_autonomy",
        revenue_model="subscription",
        murphy_modules_required=["inference_gate_engine", "mss_controls"],
        requires_licensed_professionals=False,
        requires_physical_contractors=False,
    )


@pytest.fixture
def hybrid_eua(generator):
    return generator.generate(
        niche_id="test_notary",
        niche_name="Digital Notary Routing Network",
        inoni_entity_name="Inoni Digital Notary Routing Network LLC",
        autonomy_class="hybrid",
        revenue_model="transaction",
        murphy_modules_required=["inference_gate_engine", "mss_controls", "form_intake"],
        requires_licensed_professionals=True,
        requires_physical_contractors=True,
    )


# ---------------------------------------------------------------------------
# Document generation
# ---------------------------------------------------------------------------

class TestEUADocumentGeneration:
    def test_generates_document(self, full_autonomy_eua):
        assert isinstance(full_autonomy_eua, EUADocument)

    def test_niche_id_correct(self, full_autonomy_eua):
        assert full_autonomy_eua.niche_id == "test_seo"

    def test_inoni_entity_name_in_doc(self, full_autonomy_eua):
        assert "Inoni SEO Content Site Generator LLC" in full_autonomy_eua.inoni_entity_name

    def test_version_set(self, full_autonomy_eua):
        assert full_autonomy_eua.version == "1.0"

    def test_has_sections(self, full_autonomy_eua):
        assert len(full_autonomy_eua.sections) >= 4

    def test_has_risk_transfer_clauses(self, full_autonomy_eua):
        assert len(full_autonomy_eua.risk_transfer_clauses) >= 2

    def test_has_automation_requirements(self, full_autonomy_eua):
        assert len(full_autonomy_eua.automation_requirements) >= 3

    def test_full_text_not_empty(self, full_autonomy_eua):
        assert len(full_autonomy_eua.full_text) > 100

    def test_full_text_contains_inoni(self, full_autonomy_eua):
        assert "Inoni" in full_autonomy_eua.full_text

    def test_generated_at_set(self, full_autonomy_eua):
        assert full_autonomy_eua.generated_at

    def test_acceptance_record_none_before_acceptance(self, full_autonomy_eua):
        assert full_autonomy_eua.acceptance_record is None


# ---------------------------------------------------------------------------
# Hybrid vs. full-autonomy differences
# ---------------------------------------------------------------------------

class TestHybridEUADifferences:
    def test_hybrid_has_contractor_section(self, hybrid_eua):
        types = [s.section_type for s in hybrid_eua.sections]
        assert EUASectionType.CONTRACTOR_RESPONSIBILITY in types

    def test_full_autonomy_no_contractor_section(self, full_autonomy_eua):
        types = [s.section_type for s in full_autonomy_eua.sections]
        assert EUASectionType.CONTRACTOR_RESPONSIBILITY not in types

    def test_hybrid_has_credential_section(self, hybrid_eua):
        types = [s.section_type for s in hybrid_eua.sections]
        assert EUASectionType.CREDENTIAL_VERIFICATION in types

    def test_full_autonomy_no_credential_section(self, full_autonomy_eua):
        types = [s.section_type for s in full_autonomy_eua.sections]
        assert EUASectionType.CREDENTIAL_VERIFICATION not in types

    def test_hybrid_has_contractor_risk_clause(self, hybrid_eua):
        titles = [c.title for c in hybrid_eua.risk_transfer_clauses]
        assert any("Contractor" in t for t in titles)

    def test_hybrid_has_regulatory_risk_clause(self, hybrid_eua):
        titles = [c.title for c in hybrid_eua.risk_transfer_clauses]
        assert any("Regulatory" in t or "Domain" in t for t in titles)

    def test_hybrid_requires_credentialed_hitl(self, hybrid_eua):
        assert hybrid_eua.requires_credentialed_hitl is True

    def test_full_autonomy_not_credentialed_hitl(self, full_autonomy_eua):
        assert full_autonomy_eua.requires_credentialed_hitl is False

    def test_hybrid_has_contractor_dispatch_requirement(self, hybrid_eua):
        descriptions = [r.description for r in hybrid_eua.automation_requirements]
        assert any("contractor" in d.lower() or "dispatch" in d.lower() for d in descriptions)


# ---------------------------------------------------------------------------
# Risk transfer clauses
# ---------------------------------------------------------------------------

class TestRiskTransferClauses:
    def test_hitl_financial_risk_clause_present(self, full_autonomy_eua):
        titles = [c.title for c in full_autonomy_eua.risk_transfer_clauses]
        assert any("HITL" in t or "Financial" in t for t in titles)

    def test_risk_clause_from_party_is_inoni(self, full_autonomy_eua):
        clauses = full_autonomy_eua.risk_transfer_clauses
        inoni_clauses = [c for c in clauses if "inoni" in c.from_party.lower()]
        assert len(inoni_clauses) >= 1

    def test_risk_clause_to_party_not_empty(self, full_autonomy_eua):
        for clause in full_autonomy_eua.risk_transfer_clauses:
            assert clause.to_party

    def test_risk_clause_trigger_not_empty(self, full_autonomy_eua):
        for clause in full_autonomy_eua.risk_transfer_clauses:
            assert clause.trigger

    def test_risk_clause_text_mentions_approval(self, full_autonomy_eua):
        # The HITL financial risk clause should mention approval
        financial = next(
            (c for c in full_autonomy_eua.risk_transfer_clauses if "Financial" in c.title), None
        )
        assert financial is not None
        assert "approv" in financial.text.lower()


# ---------------------------------------------------------------------------
# Automation requirements
# ---------------------------------------------------------------------------

class TestAutomationRequirements:
    def test_generation_requirement_autonomous(self, full_autonomy_eua):
        gen_req = next(
            (r for r in full_autonomy_eua.automation_requirements
             if r.automation_type == "generation"), None
        )
        assert gen_req is not None
        assert gen_req.can_execute_autonomously is True
        assert gen_req.human_oversight_required is False

    def test_hitl_routing_not_autonomous(self, full_autonomy_eua):
        hitl_req = next(
            (r for r in full_autonomy_eua.automation_requirements
             if "HITL" in r.description or "hitl" in r.description.lower()), None
        )
        assert hitl_req is not None
        assert hitl_req.human_oversight_required is True

    def test_all_requirements_have_failure_mode(self, full_autonomy_eua):
        for req in full_autonomy_eua.automation_requirements:
            assert req.failure_mode

    def test_all_requirements_have_recovery_action(self, full_autonomy_eua):
        for req in full_autonomy_eua.automation_requirements:
            assert req.recovery_action


# ---------------------------------------------------------------------------
# EUA sections
# ---------------------------------------------------------------------------

class TestEUASections:
    def test_scope_section_present(self, full_autonomy_eua):
        types = [s.section_type for s in full_autonomy_eua.sections]
        assert EUASectionType.SCOPE_OF_AUTOMATION in types

    def test_liability_section_present(self, full_autonomy_eua):
        types = [s.section_type for s in full_autonomy_eua.sections]
        assert EUASectionType.LIABILITY_LIMITATION in types

    def test_risk_transfer_section_present(self, full_autonomy_eua):
        types = [s.section_type for s in full_autonomy_eua.sections]
        assert EUASectionType.RISK_TRANSFER in types

    def test_automation_acceptance_section_present(self, full_autonomy_eua):
        types = [s.section_type for s in full_autonomy_eua.sections]
        assert EUASectionType.AUTOMATION_ACCEPTANCE in types

    def test_binding_sections_exist(self, full_autonomy_eua):
        binding = [s for s in full_autonomy_eua.sections if s.binding]
        assert len(binding) >= 3

    def test_sections_have_risk_level(self, full_autonomy_eua):
        for s in full_autonomy_eua.sections:
            assert s.risk_level in ("low", "medium", "high", "critical")

    def test_critical_sections_are_binding(self, full_autonomy_eua):
        critical = [s for s in full_autonomy_eua.sections if s.risk_level == "critical"]
        for s in critical:
            assert s.binding is True

    def test_liability_section_caps_inoni_liability(self, full_autonomy_eua):
        liability_section = next(
            (s for s in full_autonomy_eua.sections
             if s.section_type == EUASectionType.LIABILITY_LIMITATION), None
        )
        assert liability_section is not None
        assert "limit" in liability_section.body.lower() or "not liable" in liability_section.body.lower()


# ---------------------------------------------------------------------------
# EUA acceptance recording
# ---------------------------------------------------------------------------

class TestEUAAcceptance:
    def test_record_acceptance_returns_acceptance(self, generator, full_autonomy_eua):
        acceptance = generator.record_acceptance(
            full_autonomy_eua,
            accepted_by="corey_post",
            acceptance_method=EUAAcceptanceMethod.HITL_APPROVAL,
        )
        assert isinstance(acceptance, EUAAcceptance)

    def test_acceptance_is_valid(self, generator, full_autonomy_eua):
        acceptance = generator.record_acceptance(
            full_autonomy_eua, accepted_by="corey_post"
        )
        assert acceptance.is_valid is True

    def test_acceptance_attached_to_doc(self, generator, full_autonomy_eua):
        generator.record_acceptance(full_autonomy_eua, accepted_by="operator_1")
        assert full_autonomy_eua.acceptance_record is not None

    def test_acceptance_accepted_by_recorded(self, generator, full_autonomy_eua):
        acceptance = generator.record_acceptance(
            full_autonomy_eua, accepted_by="operator_test"
        )
        assert acceptance.accepted_by == "operator_test"

    def test_acceptance_clauses_include_binding(self, generator):
        gen = EUAGenerator()
        eua = gen.generate(
            niche_id="acc_test",
            niche_name="Test Niche",
            inoni_entity_name="Inoni Test Niche LLC",
            autonomy_class="full_autonomy",
            revenue_model="subscription",
        )
        acceptance = gen.record_acceptance(eua, "op_1")
        assert len(acceptance.risk_clauses_accepted) >= 2

    def test_acceptance_with_conditions(self, generator, hybrid_eua):
        acceptance = generator.record_acceptance(
            hybrid_eua,
            accepted_by="op_2",
            conditions_noted=["Must review contractor credentials monthly"],
        )
        assert len(acceptance.conditions_noted) == 1

    def test_get_acceptance_by_id(self, generator):
        gen = EUAGenerator()
        eua = gen.generate(
            niche_id="get_test",
            niche_name="Get Test",
            inoni_entity_name="Inoni Get Test LLC",
            autonomy_class="full_autonomy",
            revenue_model="subscription",
        )
        acceptance = gen.record_acceptance(eua, "op_3")
        retrieved = gen.get_acceptance(acceptance.acceptance_id)
        assert retrieved is not None
        assert retrieved.accepted_by == "op_3"

    def test_get_acceptance_unknown_id_returns_none(self, generator):
        result = generator.get_acceptance("nonexistent-id")
        assert result is None


# ---------------------------------------------------------------------------
# Full text rendering
# ---------------------------------------------------------------------------

class TestFullTextRendering:
    def test_full_text_has_entity_name(self, full_autonomy_eua):
        assert full_autonomy_eua.inoni_entity_name in full_autonomy_eua.full_text

    def test_full_text_has_murphy_system(self, full_autonomy_eua):
        assert "Murphy System" in full_autonomy_eua.full_text

    def test_full_text_has_hitl_reference(self, full_autonomy_eua):
        assert "HITL" in full_autonomy_eua.full_text or "Human-in-the-Loop" in full_autonomy_eua.full_text

    def test_full_text_ends_with_acceptance_statement(self, full_autonomy_eua):
        assert "APPROVING" in full_autonomy_eua.full_text.upper()

    def test_full_text_has_automation_section(self, full_autonomy_eua):
        assert "AUTOMATION" in full_autonomy_eua.full_text.upper()

    def test_full_text_has_risk_transfer_section(self, full_autonomy_eua):
        assert "RISK TRANSFER" in full_autonomy_eua.full_text.upper()


# ---------------------------------------------------------------------------
# Generator integration
# ---------------------------------------------------------------------------

class TestGeneratorIntegration:
    @pytest.fixture(scope="class")
    def gen_instance(self):
        import os
        from src.mss_controls import MSSController
        from src.information_quality import InformationQualityEngine
        from src.information_density import InformationDensityEngine
        from src.resolution_scoring import ResolutionDetectionEngine
        from src.structural_coherence import StructuralCoherenceEngine
        from src.concept_translation import ConceptTranslationEngine
        from src.simulation_engine import StrategicSimulationEngine
        from src.inference_gate_engine import InferenceDomainGateEngine
        from src.niche_business_generator import NicheBusinessGenerator

        rde = ResolutionDetectionEngine()
        ide = InformationDensityEngine()
        sce = StructuralCoherenceEngine()
        iqe = InformationQualityEngine(rde, ide, sce)
        cte = ConceptTranslationEngine()
        sim = StrategicSimulationEngine()
        ctrl = MSSController(iqe, cte, sim)
        eng = InferenceDomainGateEngine()
        return NicheBusinessGenerator(ctrl, eng)

    def test_spec_has_eua(self, gen_instance):
        niche = gen_instance.get_niche("niche_seo_sites")
        spec = gen_instance.generate_niche(niche)
        assert spec.eua is not None

    def test_spec_eua_is_eua_document(self, gen_instance):
        niche = gen_instance.get_niche("niche_seo_sites")
        spec = gen_instance.generate_niche(niche)
        assert hasattr(spec.eua, "sections")
        assert hasattr(spec.eua, "risk_transfer_clauses")

    def test_spec_eua_inoni_entity_name(self, gen_instance):
        niche = gen_instance.get_niche("newsletter_businesses")
        spec = gen_instance.generate_niche(niche)
        assert "Inoni" in spec.eua.inoni_entity_name
        assert "LLC" in spec.eua.inoni_entity_name

    def test_get_eua_returns_document(self, gen_instance):
        eua = gen_instance.get_eua("niche_seo_sites")
        assert eua is not None
        assert hasattr(eua, "full_text")

    def test_get_eua_unknown_returns_none(self, gen_instance):
        eua = gen_instance.get_eua("nonexistent_niche")
        assert eua is None
