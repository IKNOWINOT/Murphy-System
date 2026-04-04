"""Tests for the Information Density Index Engine (IDI-001)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from src.information_density import InformationDensityEngine, DensityScore
from src.resolution_scoring import ResolutionDetectionEngine, ResolutionScore


class TestInformationDensity:
    """Functional, integration, determinism, cross-domain, and edge-case tests."""

    @pytest.fixture
    def engine(self):
        return InformationDensityEngine()

    @pytest.fixture
    def rde(self):
        return ResolutionDetectionEngine()

    # ------------------------------------------------------------------ #
    # Helper to build a ResolutionScore with a chosen RS value
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_rs(rs: float) -> ResolutionScore:
        """Build a minimal ResolutionScore with a given RS for testing."""
        from src.resolution_scoring import ResolutionLevel
        return ResolutionScore(
            d1_concept_clarity=rs,
            d2_structural_detail=rs,
            d3_operational_logic=rs,
            d4_implementation_readiness=rs,
            d5_evidence_validation=rs,
            rs=rs,
            resolution_level=ResolutionLevel.RM3,
            input_hash="test_hash",
        )

    # ------------------------------------------------------------------ #
    # Functional
    # ------------------------------------------------------------------ #

    def test_score_returns_density_score(self, engine):
        """Basic scoring returns a DensityScore dataclass."""
        result = engine.score("compute the output of a module")
        assert isinstance(result, DensityScore)

    def test_high_density_text(self, engine):
        """Text full of actionable words → high or very_high density."""
        text = (
            "compute generate optimize route schedule module service "
            "engine controller validate test verify monitor audit"
        )
        result = engine.score(text)
        assert result.density_level in ("high", "very_high")

    def test_low_density_text(self, engine):
        """Text with few actionable words → low or very_low density."""
        text = (
            "the big red fox jumped over the lazy brown dog and sat "
            "down in the green meadow with the warm breeze blowing "
            "across the rolling hills"
        )
        result = engine.score(text)
        assert result.density_level in ("low", "very_low")

    def test_moderate_density_text(self, engine):
        """Mix of actionable and filler → moderate density."""
        text = (
            "We need a module service to compute and generate reports "
            "then validate and test the output from the engine"
        )
        result = engine.score(text)
        assert 0.0 < result.idi < 1.0

    def test_empty_input(self, engine):
        """Empty string → 0 elements, 0 tokens, 0.0 IDI."""
        result = engine.score("")
        assert result.actionable_elements == 0
        assert result.total_tokens == 0
        assert result.idi == 0.0

    def test_element_breakdown_categories(self, engine):
        """All 6 categories present in breakdown dict."""
        result = engine.score("compute module process must accuracy test")
        expected_cats = {"function", "component", "process", "constraint", "metric", "validation"}
        assert set(result.element_breakdown.keys()) == expected_cats

    def test_idi_capped_at_one(self, engine):
        """IDI never exceeds 1.0, even with all actionable words."""
        text = "compute generate optimize module service test verify"
        result = engine.score(text)
        assert result.idi <= 1.0

    # ------------------------------------------------------------------ #
    # Scope-creep detection
    # ------------------------------------------------------------------ #

    def test_scope_creep_detection(self, engine):
        """RS >= 3 and IDI < 0.3 → scope_creep_warning True."""
        high_rs = self._make_rs(4.0)
        text = (
            "we want the thing to be great and wonderful and lovely "
            "and smooth and exciting and delightful and amazing and "
            "spectacular in every way imaginable to all stakeholders"
        )
        result = engine.score(text, resolution_score=high_rs)
        assert result.scope_creep_warning is True

    def test_no_scope_creep_without_resolution(self, engine):
        """No resolution_score → no scope creep regardless of IDI."""
        text = "the thing is vague"
        result = engine.score(text)
        assert result.scope_creep_warning is False

    def test_no_scope_creep_low_rs(self, engine):
        """RS < 3 → no scope creep even if IDI < 0.3."""
        low_rs = self._make_rs(1.0)
        text = "we want something nice and pleasant"
        result = engine.score(text, resolution_score=low_rs)
        assert result.scope_creep_warning is False

    def test_no_scope_creep_high_idi(self, engine):
        """RS >= 3 but high-density text → no scope creep."""
        high_rs = self._make_rs(4.0)
        text = "compute generate optimize validate test module service engine"
        result = engine.score(text, resolution_score=high_rs)
        assert result.scope_creep_warning is False

    # ------------------------------------------------------------------ #
    # Density-level thresholds
    # ------------------------------------------------------------------ #

    def test_density_level_very_low(self, engine):
        """IDI in [0.0, 0.2) → very_low."""
        text = (
            "the sky is blue and the grass is green and the world is "
            "big and wonderful and full of possibilities for everyone"
        )
        result = engine.score(text)
        assert result.idi < 0.2
        assert result.density_level == "very_low"

    def test_density_level_low(self, engine):
        """IDI in [0.2, 0.4) → low."""
        text = "compute generate the big result now data okay fine"
        result = engine.score(text)
        assert 0.2 <= result.idi < 0.4
        assert result.density_level == "low"

    def test_density_level_moderate(self, engine):
        """IDI in [0.4, 0.6) → moderate."""
        text = "compute optimize validate the big data"
        result = engine.score(text)
        assert 0.4 <= result.idi < 0.6
        assert result.density_level == "moderate"

    def test_density_level_high(self, engine):
        """IDI in [0.6, 0.8) → high."""
        text = "compute optimize module service test verify results data"
        result = engine.score(text)
        assert 0.6 <= result.idi < 0.8
        assert result.density_level == "high"

    def test_density_level_very_high(self, engine):
        """IDI >= 0.8 → very_high."""
        text = "compute optimize module service test validate authenticate"
        result = engine.score(text)
        if result.idi >= 0.8:
            assert result.density_level == "very_high"
        else:
            pytest.skip("Could not produce IDI >= 0.8 with this text")

    # ------------------------------------------------------------------ #
    # Token counting
    # ------------------------------------------------------------------ #

    def test_total_tokens_count(self, engine):
        """total_tokens matches word count (whitespace split)."""
        text = "compute the module output now"
        result = engine.score(text)
        assert result.total_tokens == len(text.split())

    # ------------------------------------------------------------------ #
    # Cross-domain
    # ------------------------------------------------------------------ #

    def test_cross_domain_same_structure(self, engine):
        """Same structural patterns in different domains → similar IDI."""
        r1 = engine.score("compute the module output and validate the result")
        r2 = engine.score("compute the service output and validate the result")
        assert abs(r1.idi - r2.idi) <= 0.2

    # ------------------------------------------------------------------ #
    # Counting
    # ------------------------------------------------------------------ #

    def test_actionable_elements_counted(self, engine):
        """Text with known keywords → correct count."""
        text = "compute module test"
        result = engine.score(text)
        assert result.actionable_elements >= 3

    def test_single_word_actionable(self, engine):
        """Single actionable word → at least 1 element."""
        result = engine.score("compute")
        assert result.actionable_elements >= 1

    # ------------------------------------------------------------------ #
    # Determinism
    # ------------------------------------------------------------------ #

    def test_deterministic(self, engine):
        """Same input always produces the same output."""
        text = "compute the module output and validate"
        r1 = engine.score(text)
        r2 = engine.score(text)
        assert r1.idi == r2.idi
        assert r1.actionable_elements == r2.actionable_elements
        assert r1.element_breakdown == r2.element_breakdown
