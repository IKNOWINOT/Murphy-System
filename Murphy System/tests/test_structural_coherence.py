"""Tests for the Structural Coherence Score Engine (SCS-001)."""

from pathlib import Path

import pytest

from src.structural_coherence import StructuralCoherenceEngine, CoherenceScore


class TestStructuralCoherence:
    """Functional, integration, determinism, cross-domain, and edge-case tests."""

    @pytest.fixture
    def engine(self):
        return StructuralCoherenceEngine()

    # ------------------------------------------------------------------ #
    # Functional
    # ------------------------------------------------------------------ #

    def test_score_returns_coherence_score(self, engine):
        """Basic scoring returns a CoherenceScore dataclass."""
        result = engine.score("build a service")
        assert isinstance(result, CoherenceScore)

    def test_detect_contradictions_returns_list(self, engine):
        """detect_contradictions returns a list."""
        result = engine.detect_contradictions("some clean text")
        assert isinstance(result, list)

    def test_no_contradictions_clean_text(self, engine):
        """Clean text without conflicting terms → empty contradictions list."""
        result = engine.score("build a service that processes input data")
        assert result.contradictions == []

    def test_contradiction_manual_automated(self, engine):
        """'fully manual' and 'fully automated' → contradiction detected."""
        text = "The system is fully manual but also fully automated."
        result = engine.score(text)
        assert len(result.contradictions) >= 1
        assert any("fully manual" in c and "fully automated" in c for c in result.contradictions)

    def test_contradiction_realtime_batch(self, engine):
        """'real-time' and 'batch-only' → contradiction detected."""
        text = "Process data in real-time mode and also in batch-only mode."
        result = engine.score(text)
        assert any("real-time" in c and "batch-only" in c for c in result.contradictions)

    def test_contradiction_offline_cloud(self, engine):
        """'offline only' and 'cloud-based' → contradiction detected."""
        text = "The service runs offline only but is also cloud-based."
        result = engine.score(text)
        assert any("offline only" in c and "cloud-based" in c for c in result.contradictions)

    def test_multiple_contradictions(self, engine):
        """Text with 2+ contradiction pairs → 2+ contradictions."""
        text = (
            "The system is fully manual and fully automated. "
            "It runs offline only but is cloud-based."
        )
        result = engine.score(text)
        assert len(result.contradictions) >= 2

    # ------------------------------------------------------------------ #
    # Consistency
    # ------------------------------------------------------------------ #

    def test_consistency_decreases_with_contradictions(self, engine):
        """More contradictions → lower consistency score."""
        clean = engine.score("The system processes input and returns output.")
        contradicted = engine.score(
            "The system is fully manual and fully automated. "
            "It runs offline only and is cloud-based."
        )
        assert contradicted.consistency < clean.consistency

    def test_consistency_floor_at_zero(self, engine):
        """Many contradictions → consistency 0, not negative."""
        text = (
            "fully manual fully automated "
            "real-time batch-only "
            "offline only cloud-based "
            "stateless maintains state "
            "no database database required"
        )
        result = engine.score(text)
        assert result.consistency == 0.0

    # ------------------------------------------------------------------ #
    # Logical progression
    # ------------------------------------------------------------------ #

    def test_logical_progression_with_connectors(self, engine):
        """Text with 'first then finally' → logical_progression > 0."""
        text = "First fetch the data, then process it, finally return the result."
        result = engine.score(text)
        assert result.logical_progression > 0.0

    def test_logical_progression_conditional(self, engine):
        """'if then else' → logical_progression >= 3."""
        text = "If the input is valid then compute the result else return an error."
        result = engine.score(text)
        assert result.logical_progression >= 3.0

    # ------------------------------------------------------------------ #
    # Dependency clarity
    # ------------------------------------------------------------------ #

    def test_dependency_clarity_with_relationships(self, engine):
        """'sends to, depends on' → dependency_clarity > 0."""
        text = "Module A sends to module B which depends on module C."
        result = engine.score(text)
        assert result.dependency_clarity > 0.0

    # ------------------------------------------------------------------ #
    # Functional completeness
    # ------------------------------------------------------------------ #

    def test_functional_completeness_all_elements(self, engine):
        """Text with input+process+output+constraint+validation → high score."""
        text = (
            "The system accepts input, processes and transforms it, "
            "produces output as a result, enforces a constraint with "
            "a minimum threshold, and runs a test to verify correctness."
        )
        result = engine.score(text)
        assert result.functional_completeness >= 4.8
        assert len(result.missing_elements) == 0

    def test_functional_completeness_missing_elements(self, engine):
        """Text missing several categories → low score and non-empty missing list."""
        text = "The sky is blue and the grass is green."
        result = engine.score(text)
        assert result.functional_completeness < 3.0
        assert len(result.missing_elements) > 0

    # ------------------------------------------------------------------ #
    # Edge cases
    # ------------------------------------------------------------------ #

    def test_empty_input(self, engine):
        """Empty string → all zeros, empty lists."""
        result = engine.score("")
        assert result.logical_progression == 0.0
        assert result.dependency_clarity == 0.0
        assert result.functional_completeness == 0.0
        assert result.scs == pytest.approx(result.consistency / 4.0 + 0.0, abs=0.01)
        assert result.contradictions == []

    def test_scs_is_average(self, engine):
        """SCS equals the average of the four sub-scores."""
        text = (
            "First, the module receives input and processes it. "
            "Then it sends to module B and returns the output result. "
            "Validate with a test. Must meet a minimum constraint."
        )
        result = engine.score(text)
        expected = (
            result.logical_progression
            + result.dependency_clarity
            + result.consistency
            + result.functional_completeness
        ) / 4.0
        assert result.scs == pytest.approx(expected, abs=0.01)

    # ------------------------------------------------------------------ #
    # Determinism
    # ------------------------------------------------------------------ #

    def test_deterministic(self, engine):
        """Same input always produces the same output."""
        text = "First fetch data, then process, if valid send to output."
        r1 = engine.score(text)
        r2 = engine.score(text)
        assert r1.scs == r2.scs
        assert r1.logical_progression == r2.logical_progression
        assert r1.contradictions == r2.contradictions

    # ------------------------------------------------------------------ #
    # Cross-domain
    # ------------------------------------------------------------------ #

    def test_cross_domain_coherence(self, engine):
        """Same structural pattern across domains → similar SCS."""
        r1 = engine.score(
            "First the module receives input data, then processes and "
            "computes the output. Must meet a minimum threshold. "
            "Verify with a test."
        )
        r2 = engine.score(
            "First the engine receives patient data, then processes and "
            "computes the result. Must meet a minimum threshold. "
            "Verify with a test."
        )
        assert abs(r1.scs - r2.scs) <= 1.0

    # ------------------------------------------------------------------ #
    # High coherence
    # ------------------------------------------------------------------ #

    def test_high_coherence_text(self, engine):
        """Well-structured text → high SCS."""
        text = (
            "Hypothesis: the new algorithm improves throughput. "
            "First, the service accepts input via a contract schema. "
            "Then it processes data because the pipeline depends on "
            "upstream results, therefore the output is sent downstream. "
            "Must enforce a minimum boundary. Test and verify with a "
            "benchmark to confirm results."
        )
        result = engine.score(text)
        assert result.scs >= 3.0

    # ------------------------------------------------------------------ #
    # Missing elements reporting
    # ------------------------------------------------------------------ #

    def test_missing_elements_reported(self, engine):
        """Identifies which structural elements are missing."""
        text = "We have input and process the data."
        result = engine.score(text)
        assert isinstance(result.missing_elements, list)
        for elem in result.missing_elements:
            assert isinstance(elem, str)

    # ------------------------------------------------------------------ #
    # Standalone contradiction detection
    # ------------------------------------------------------------------ #

    def test_contradiction_detection_standalone(self, engine):
        """detect_contradictions works independently of score."""
        text = "The system is fully manual and fully automated."
        contradictions = engine.detect_contradictions(text)
        assert len(contradictions) >= 1
        assert any("fully manual" in c for c in contradictions)
