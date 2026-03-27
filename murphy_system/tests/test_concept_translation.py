"""Tests for ConceptTranslationEngine — concept_translation module."""

from pathlib import Path


from src.concept_translation import ConceptTranslationEngine, TechnicalAnalogue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> ConceptTranslationEngine:
    return ConceptTranslationEngine()


# ---------------------------------------------------------------------------
# 1. Functional tests
# ---------------------------------------------------------------------------

class TestFunctional:
    def test_translate_returns_technical_analogue(self):
        result = _engine().translate("Build a monitoring dashboard for servers")
        assert isinstance(result, TechnicalAnalogue)

    def test_original_text_preserved(self):
        text = "Deploy a cloud service to manage data"
        result = _engine().translate(text)
        assert result.original_text == text

    def test_extracted_concepts_structure(self):
        result = _engine().translate("The admin should monitor servers to ensure uptime")
        for concept in result.extracted_concepts:
            assert "actor" in concept
            assert "action" in concept
            assert "goal" in concept
            assert "constraint" in concept

    def test_technical_mapping_nontechnical(self):
        result = _engine().translate("We need to improve speed of the pipeline")
        analogues = [m["technical_analogue"] for m in result.technical_mapping]
        assert "optimization" in analogues

    def test_technical_mapping_component(self):
        result = _engine().translate("Each module should be independent")
        analogues = [m["technical_analogue"] for m in result.technical_mapping]
        assert "structural element" in analogues

    def test_technical_mapping_process(self):
        result = _engine().translate("The workflow must be streamlined")
        analogues = [m["technical_analogue"] for m in result.technical_mapping]
        assert "operational element" in analogues

    def test_technical_mapping_validation(self):
        result = _engine().translate("Perform a full audit of the system")
        analogues = [m["technical_analogue"] for m in result.technical_mapping]
        assert "validation element" in analogues


# ---------------------------------------------------------------------------
# 2. Regulatory detection tests
# ---------------------------------------------------------------------------

class TestRegulatoryDetection:
    def test_regulatory_detection_healthcare(self):
        result = _engine().translate("patient medical treatment in the hospital")
        fws = result.regulatory_frameworks
        assert "HIPAA" in fws
        assert "FDA" in fws

    def test_regulatory_detection_finance(self):
        result = _engine().translate("payment banking transaction processing")
        fws = result.regulatory_frameworks
        assert "PCI-DSS" in fws
        assert "SOX" in fws

    def test_regulatory_detection_privacy(self):
        result = _engine().translate("personal data privacy consent management")
        assert "GDPR" in result.regulatory_frameworks

    def test_regulatory_detection_aviation(self):
        result = _engine().translate("drone flight airspace management system")
        assert "FAA" in result.regulatory_frameworks

    def test_regulatory_detection_industrial(self):
        result = _engine().translate("factory worker safety equipment monitoring")
        assert "OSHA" in result.regulatory_frameworks

    def test_regulatory_detection_tech(self):
        result = _engine().translate("cloud software data center infrastructure")
        fws = result.regulatory_frameworks
        assert "SOC2" in fws
        assert "ISO27001" in fws

    def test_regulatory_modules_generated(self):
        result = _engine().translate("patient medical treatment")
        assert len(result.regulatory_modules) > 0
        for mod in result.regulatory_modules:
            assert "module_name" in mod
            assert "purpose" in mod

    def test_multiple_regulatory_domains(self):
        result = _engine().translate(
            "patient medical treatment with payment banking integration"
        )
        fws = result.regulatory_frameworks
        assert "HIPAA" in fws or "FDA" in fws
        assert "PCI-DSS" in fws or "SOX" in fws


# ---------------------------------------------------------------------------
# 3. Reasoning method tests
# ---------------------------------------------------------------------------

class TestReasoningMethod:
    def test_reasoning_method_deduction(self):
        result = _engine().translate(
            "According to ISO standard the system must comply with NIST framework"
        )
        assert result.reasoning_method == "deduction"

    def test_reasoning_method_induction(self):
        result = _engine().translate("We want to build a better mousetrap")
        assert result.reasoning_method == "induction"


# ---------------------------------------------------------------------------
# 4. System model tests
# ---------------------------------------------------------------------------

class TestSystemModel:
    def test_system_model_structure(self):
        result = _engine().translate(
            "The admin should monitor servers to ensure uptime with logging"
        )
        model = result.system_model
        assert "components" in model
        assert "data_flows" in model
        assert "control_logic" in model
        assert "validation_methods" in model


# ---------------------------------------------------------------------------
# 5. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_input(self):
        result = _engine().translate("")
        assert isinstance(result, TechnicalAnalogue)
        assert result.original_text == ""
        assert result.extracted_concepts == []
        assert result.technical_mapping == []

    def test_whitespace_only_input(self):
        result = _engine().translate("   ")
        assert isinstance(result, TechnicalAnalogue)

    def test_very_long_input(self):
        text = "monitor the servers and track things " * 200
        result = _engine().translate(text)
        assert isinstance(result, TechnicalAnalogue)
        assert len(result.original_text) > 0


# ---------------------------------------------------------------------------
# 6. Determinism tests
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic(self):
        engine = _engine()
        text = "Build a monitoring dashboard to track server uptime"
        r1 = engine.translate(text)
        r2 = engine.translate(text)
        assert r1.original_text == r2.original_text
        assert r1.extracted_concepts == r2.extracted_concepts
        assert r1.technical_mapping == r2.technical_mapping
        assert r1.regulatory_frameworks == r2.regulatory_frameworks
        assert r1.reasoning_method == r2.reasoning_method
        assert r1.system_model == r2.system_model


# ---------------------------------------------------------------------------
# 7. Cross-domain tests
# ---------------------------------------------------------------------------

class TestCrossDomain:
    def test_cross_domain_translation(self):
        """Similar structural patterns across domains yield similar shapes."""
        e = _engine()
        r_health = e.translate("monitor patient health to ensure safety")
        r_infra = e.translate("monitor server health to ensure safety")
        assert len(r_health.extracted_concepts) == len(r_infra.extracted_concepts)
        h_keys = {tuple(sorted(c.keys())) for c in r_health.extracted_concepts}
        i_keys = {tuple(sorted(c.keys())) for c in r_infra.extracted_concepts}
        assert h_keys == i_keys
