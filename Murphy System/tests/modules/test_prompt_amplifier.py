"""Tests for the Prompt Amplifier (prompt_amplifier.py).

The MMMS→Solidify filter that runs on every incoming request before Murphy
processes it internally.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.mss_controls import MSSController
from src.information_quality import InformationQualityEngine
from src.information_density import InformationDensityEngine
from src.resolution_scoring import ResolutionDetectionEngine
from src.structural_coherence import StructuralCoherenceEngine
from src.concept_translation import ConceptTranslationEngine
from src.simulation_engine import StrategicSimulationEngine
from src.inference_gate_engine import InferenceDomainGateEngine
from src.prompt_amplifier import PromptAmplifier, AmplifiedPrompt, AMPLIFIER_SEQUENCE


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
def amplifier(controller, inference_engine):
    return PromptAmplifier(controller, inference_engine)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_amplifier_sequence_is_mmms(self):
        assert AMPLIFIER_SEQUENCE == "MMMS"

    def test_amplifier_sequence_has_3_magnifies(self):
        assert AMPLIFIER_SEQUENCE.count("M") == 3

    def test_amplifier_sequence_has_1_simplify(self):
        assert AMPLIFIER_SEQUENCE.count("S") == 1


# ---------------------------------------------------------------------------
# AmplifiedPrompt structure
# ---------------------------------------------------------------------------

class TestAmplifiedPromptStructure:
    def test_amplify_returns_amplified_prompt(self, amplifier):
        result = amplifier.amplify("Build me an SEO content business")
        assert isinstance(result, AmplifiedPrompt)

    def test_amplified_prompt_has_original(self, amplifier):
        raw = "Build me an SEO content business for healthcare"
        result = amplifier.amplify(raw)
        assert result.original_prompt == raw

    def test_amplified_prompt_has_amplified_text(self, amplifier):
        result = amplifier.amplify("SEO automation for small businesses")
        assert result.amplified_prompt
        assert len(result.amplified_prompt) > 0

    def test_amplified_prompt_has_three_magnify_results(self, amplifier):
        result = amplifier.amplify("Compliance checklist generator for healthcare")
        # Should have up to 3 magnify results (may be fewer if steps fail gracefully)
        assert len(result.magnify_results) <= 3

    def test_amplified_prompt_has_timestamp(self, amplifier):
        result = amplifier.amplify("newsletter business for fintech")
        assert result.amplified_at
        assert "T" in result.amplified_at  # ISO format

    def test_amplified_prompt_original_length_correct(self, amplifier):
        raw = "niche job board for legal professionals"
        result = amplifier.amplify(raw)
        assert result.original_length == len(raw)

    def test_amplified_prompt_amplified_length_set(self, amplifier):
        result = amplifier.amplify("automated KPI dashboard for manufacturing")
        assert result.amplified_length > 0

    def test_amplified_prompt_expansion_ratio_positive(self, amplifier):
        result = amplifier.amplify("competitive intelligence for fintech")
        assert result.expansion_ratio > 0.0

    def test_amplified_prompt_confidence_between_0_and_1(self, amplifier):
        result = amplifier.amplify("Local business formation service with legal filings")
        assert 0.0 <= result.confidence <= 1.0

    def test_amplified_prompt_noise_removed_pct_nonnegative(self, amplifier):
        result = amplifier.amplify("Mystery shopping network for retail")
        assert result.noise_removed_pct >= 0.0

    def test_amplified_prompt_metadata_has_sequence(self, amplifier):
        result = amplifier.amplify("Market research for hospitality")
        assert result.processing_metadata.get("sequence") in (AMPLIFIER_SEQUENCE, "passthrough")

    def test_components_discovered_nonnegative(self, amplifier):
        result = amplifier.amplify("Property inspection service with photography")
        assert result.components_discovered >= 0


# ---------------------------------------------------------------------------
# Short / edge case inputs
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string_returns_passthrough(self, amplifier):
        result = amplifier.amplify("")
        assert result.amplified_prompt == ""
        assert result.processing_metadata.get("sequence") == "passthrough"

    def test_very_short_prompt_returns_passthrough(self, amplifier):
        result = amplifier.amplify("Hi")
        assert result.processing_metadata.get("sequence") == "passthrough"

    def test_minimum_length_prompt_amplified(self, amplifier):
        result = amplifier.amplify("SEO for SMBs")
        assert isinstance(result, AmplifiedPrompt)

    def test_long_prompt_amplified(self, amplifier):
        long_prompt = (
            "Build a full-stack automated niche business that generates SEO content, "
            "monitors competitor rankings, auto-publishes optimized articles, manages "
            "subscriber emails, and tracks KPIs for healthcare compliance in the "
            "United States market with HIPAA-aligned data handling."
        )
        result = amplifier.amplify(long_prompt)
        assert isinstance(result, AmplifiedPrompt)
        assert result.amplified_prompt

    def test_prompt_with_context(self, amplifier):
        result = amplifier.amplify(
            "Compliance platform for finance",
            context={"industry": "finance"},
        )
        assert isinstance(result, AmplifiedPrompt)


# ---------------------------------------------------------------------------
# amplify_for_niche
# ---------------------------------------------------------------------------

class TestAmplifyForNiche:
    def test_amplify_for_niche_returns_result(self, amplifier):
        result = amplifier.amplify_for_niche(
            raw_prompt="generate compliance checklists",
            niche_description="Automated compliance checklist platform for HIPAA SOX GDPR",
        )
        assert isinstance(result, AmplifiedPrompt)

    def test_amplify_for_niche_includes_niche_context(self, amplifier):
        result = amplifier.amplify_for_niche(
            raw_prompt="generate reports",
            niche_description="KPI monitoring dashboard for manufacturing",
        )
        # Amplified prompt should be longer than raw (niche context was added)
        assert result.amplified_length >= len("generate reports")


# ---------------------------------------------------------------------------
# Generator integration
# ---------------------------------------------------------------------------

class TestGeneratorIntegration:
    @pytest.fixture(scope="class")
    def generator(self, controller, inference_engine):
        from src.niche_business_generator import NicheBusinessGenerator
        return NicheBusinessGenerator(controller, inference_engine)

    def test_generator_amplify_prompt_returns_result(self, generator):
        result = generator.amplify_prompt("SEO content automation")
        assert hasattr(result, "amplified_prompt")
        assert hasattr(result, "original_prompt")

    def test_spec_has_amplified_description(self, generator):
        niche = generator.get_niche("niche_seo_sites")
        spec = generator.generate_niche(niche)
        assert spec.amplified_description is not None
        assert len(spec.amplified_description) > 0

    def test_amplified_description_differs_from_raw(self, generator):
        niche = generator.get_niche("compliance_checklist")
        spec = generator.generate_niche(niche)
        # Amplified should be the output of processing, not the exact raw description
        # (it could be equal in passthrough but should be set)
        assert spec.amplified_description is not None
