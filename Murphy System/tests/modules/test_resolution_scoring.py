"""Tests for the Resolution Detection Engine (RDE-001)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import hashlib
import threading

import pytest

from src.resolution_scoring import (
    ResolutionDetectionEngine,
    ResolutionLevel,
    ResolutionScore,
)


class TestResolutionScoring:
    """Functional, integration, determinism, cross-domain, and edge-case tests."""

    @pytest.fixture
    def engine(self):
        return ResolutionDetectionEngine()

    # ------------------------------------------------------------------ #
    # Functional
    # ------------------------------------------------------------------ #

    def test_score_returns_resolution_score(self, engine):
        """Basic scoring returns a ResolutionScore dataclass."""
        result = engine.score("build a service")
        assert isinstance(result, ResolutionScore)

    def test_detect_level_returns_resolution_level(self, engine):
        """detect_level returns a ResolutionLevel enum member."""
        level = engine.detect_level("build a service")
        assert isinstance(level, ResolutionLevel)

    def test_score_concept_input_rm0(self, engine):
        """Vague input with no actionable keywords → RM0."""
        result = engine.score("make things better")
        assert result.resolution_level == ResolutionLevel.RM0

    def test_score_category_input_rm1(self, engine):
        """Domain mention without specifics → RM1."""
        result = engine.score("improve our healthcare system")
        assert result.resolution_level == ResolutionLevel.RM1

    def test_score_requirements_input_rm2(self, engine):
        """Requirements-level text with create/build keywords → RM2."""
        result = engine.score(
            "Create and build a system to design data processing with a step first then next"
        )
        assert result.resolution_level == ResolutionLevel.RM2

    def test_score_technical_spec_rm3(self, engine):
        """Technical spec with conditional logic, API, and test criteria → RM3+."""
        text = (
            "If the request is valid then call the API endpoint and verify "
            "the response. Otherwise return an error. Test criteria: assert "
            "status code equals 200. The pipeline stage processes the data "
            "through the subsystem layer."
        )
        result = engine.score(text)
        assert result.rs >= 3.0

    def test_score_architecture_rm4(self, engine):
        """Architecture with frontend/backend/database, pipeline, module specs."""
        text = (
            "The frontend sends requests to the backend gateway, which routes "
            "to a microservice pipeline. The backend reads from the database "
            "cache through a queue. Each module has a controller and handler. "
            "Deploy with CI/CD using Docker and Kubernetes. Test plan with "
            "coverage and monitoring dashboard."
        )
        result = engine.score(text)
        assert result.rs >= 4.0

    def test_score_implementation_rm5(self, engine):
        """Full implementation spec with build steps, workflow, verification."""
        text = (
            "Install dependencies and configure the Python FastAPI service. "
            "Deploy the prototype using Docker and Kubernetes with CI/CD. "
            "Build and compile the module. The workflow orchestrates the "
            "pipeline: first fetch data, then process, next validate, after "
            "that deploy, finally run the benchmark test plan with coverage "
            "and monitoring dashboard for latency and throughput."
        )
        result = engine.score(text)
        assert result.rs >= 5.0

    # ------------------------------------------------------------------ #
    # Determinism
    # ------------------------------------------------------------------ #

    def test_deterministic_scoring(self, engine):
        """Same text always produces the same RS and hash."""
        text = "build a module to generate reports"
        r1 = engine.score(text)
        r2 = engine.score(text)
        assert r1.rs == r2.rs
        assert r1.input_hash == r2.input_hash

    def test_deterministic_scoring_different_texts(self, engine):
        """Different texts produce different hashes."""
        r1 = engine.score("build a module")
        r2 = engine.score("deploy the service")
        assert r1.input_hash != r2.input_hash

    def test_cache_hit(self, engine):
        """Second call for the same text returns the identical cached object."""
        text = "create a gateway proxy for routing"
        r1 = engine.score(text)
        r2 = engine.score(text)
        assert r1 is r2

    # ------------------------------------------------------------------ #
    # Thread safety
    # ------------------------------------------------------------------ #

    def test_thread_safety(self, engine):
        """Concurrent scoring from multiple threads all succeed."""
        results = {}
        errors = []

        def _score(idx):
            try:
                results[idx] = engine.score(f"text variant {idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_score, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10

    # ------------------------------------------------------------------ #
    # Cross-domain
    # ------------------------------------------------------------------ #

    def test_cross_domain_software_vs_finance(self, engine):
        """Similar structure across software and finance → scores within ±0.5."""
        r1 = engine.score("Create a routing optimization service")
        r2 = engine.score("Create a portfolio optimization instrument")
        assert abs(r1.rs - r2.rs) <= 0.5

    def test_cross_domain_engineering_vs_healthcare(self, engine):
        """Similar structure across engineering and healthcare → within ±0.5."""
        r1 = engine.score("Create a scheduling service for engineering process")
        r2 = engine.score("Create a scheduling service for healthcare process")
        assert abs(r1.rs - r2.rs) <= 0.5

    def test_cross_domain_manufacturing_vs_logistics(self, engine):
        """Similar structure across manufacturing and logistics → within ±0.5."""
        r1 = engine.score("Create a scheduling engine for assembly process")
        r2 = engine.score("Create a scheduling engine for delivery process")
        assert abs(r1.rs - r2.rs) <= 0.5

    # ------------------------------------------------------------------ #
    # Edge cases
    # ------------------------------------------------------------------ #

    def test_empty_input(self, engine):
        """Empty string → RM0 with zero dimension scores."""
        result = engine.score("")
        assert result.resolution_level == ResolutionLevel.RM0
        assert result.rs == 0.0

    def test_single_word_input(self, engine):
        """A single vague word → RM0."""
        result = engine.score("hello")
        assert result.resolution_level == ResolutionLevel.RM0

    def test_rs_range_boundaries(self, engine):
        """RS 0-0.9999 → RM0, 1-1.9999 → RM1, etc."""
        from src.resolution_scoring import _rs_to_level

        assert _rs_to_level(0.0) == ResolutionLevel.RM0
        assert _rs_to_level(0.99) == ResolutionLevel.RM0
        assert _rs_to_level(1.0) == ResolutionLevel.RM1
        assert _rs_to_level(1.99) == ResolutionLevel.RM1
        assert _rs_to_level(2.0) == ResolutionLevel.RM2
        assert _rs_to_level(3.0) == ResolutionLevel.RM3
        assert _rs_to_level(4.0) == ResolutionLevel.RM4
        assert _rs_to_level(5.0) == ResolutionLevel.RM5
        assert _rs_to_level(6.0) == ResolutionLevel.RM6

    def test_input_hash_is_sha256(self, engine):
        """Hash matches hashlib.sha256(text.encode()).hexdigest()."""
        text = "deterministic hashing check"
        result = engine.score(text)
        expected = hashlib.sha256(text.encode()).hexdigest()
        assert result.input_hash == expected

    def test_all_dimensions_present(self, engine):
        """All 5 dimensions are floats between 0 and 6."""
        result = engine.score("build a system with module deploy test")
        for dim in (
            result.d1_concept_clarity,
            result.d2_structural_detail,
            result.d3_operational_logic,
            result.d4_implementation_readiness,
            result.d5_evidence_validation,
        ):
            assert isinstance(dim, float)
            assert 0.0 <= dim <= 6.0

    def test_rs_is_average_of_dimensions(self, engine):
        """rs equals the arithmetic mean of d1–d5."""
        result = engine.score("build a module to deploy and test the pipeline")
        expected = round(
            (
                result.d1_concept_clarity
                + result.d2_structural_detail
                + result.d3_operational_logic
                + result.d4_implementation_readiness
                + result.d5_evidence_validation
            )
            / 5.0,
            4,
        )
        assert result.rs == expected
