"""
Tests for Murphy Osmosis Engine (Subsystem 4).
Murphy System - Copyright 2024-2026 Corey Post, Inoni LLC - License: BSL 1.1
"""

import pytest

from src.murphy_osmosis_engine import (
    AbsorbedCapabilityRegistry,
    CapabilityObserver,
    ImplementationStatus,
    InsightExtractor,
    MurphyImplementationBuilder,
    OsmosisCandidate,
    OsmosisPipeline,
    PatternExtractor,
    SoftwareCapability,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline():
    return OsmosisPipeline()


@pytest.fixture
def observer():
    return CapabilityObserver("SomeAPI", "multiply_by_2")


@pytest.fixture
def numeric_observations():
    """Observations that represent output = input * 2."""
    return [
        {"input": 1.0, "output": 2.0},
        {"input": 2.0, "output": 4.0},
        {"input": 5.0, "output": 10.0},
        {"input": 10.0, "output": 20.0},
    ]


# ---------------------------------------------------------------------------
# SoftwareCapability
# ---------------------------------------------------------------------------

class TestSoftwareCapability:

    def test_creation(self):
        cap = SoftwareCapability(
            source_software="AcrobatPDF",
            capability_name="extract_text",
            description="Extract text from PDF",
        )
        assert cap.source_software == "AcrobatPDF"
        assert cap.murphy_implementation_status == ImplementationStatus.OBSERVED

    def test_capability_id_auto_generated(self):
        cap = SoftwareCapability(source_software="X", capability_name="Y", description="Z")
        assert cap.capability_id is not None
        assert len(cap.capability_id) > 0


# ---------------------------------------------------------------------------
# Capability Observer
# ---------------------------------------------------------------------------

class TestCapabilityObserver:

    def test_observe_and_count(self, observer):
        observer.observe(1.0, 2.0)
        observer.observe(2.0, 4.0)
        assert observer.get_observation_count() == 2

    def test_observations_stored(self, observer):
        observer.observe(5, 10, metadata={"note": "test"})
        obs = observer.get_observations()
        assert len(obs) == 1
        assert obs[0]["input"] == 5
        assert obs[0]["output"] == 10
        assert obs[0]["metadata"]["note"] == "test"

    def test_empty_initially(self, observer):
        assert observer.get_observation_count() == 0


# ---------------------------------------------------------------------------
# Pattern Extractor
# ---------------------------------------------------------------------------

class TestPatternExtractor:

    def test_numeric_pattern(self, numeric_observations):
        extractor = PatternExtractor()
        pattern = extractor.extract(numeric_observations)
        assert "numeric" in pattern["core_algorithm_description"].lower()
        assert pattern["sample_count"] == 4

    def test_string_pattern(self):
        obs = [
            {"input": "hello", "output": "HELLO"},
            {"input": "world", "output": "WORLD"},
        ]
        extractor = PatternExtractor()
        pattern = extractor.extract(obs)
        assert "string" in pattern["core_algorithm_description"].lower()

    def test_empty_observations(self):
        extractor = PatternExtractor()
        pattern = extractor.extract([])
        assert pattern["sample_count"] == 0
        assert "No observations" in pattern["core_algorithm_description"]

    def test_identifies_ratio(self, numeric_observations):
        extractor = PatternExtractor()
        pattern = extractor.extract(numeric_observations)
        assert "2.0" in pattern["core_algorithm_description"] or "×" in pattern["core_algorithm_description"]


# ---------------------------------------------------------------------------
# Murphy Implementation Builder
# ---------------------------------------------------------------------------

class TestMurphyImplementationBuilder:

    def test_builds_numeric_transform(self, numeric_observations):
        cap = SoftwareCapability(source_software="X", capability_name="mul2", description="multiply by 2")
        extractor = PatternExtractor()
        pattern = extractor.extract(numeric_observations)
        builder = MurphyImplementationBuilder()
        fn = builder.build(cap, pattern)
        assert callable(fn)
        result = fn(5.0)
        assert abs(result - 10.0) < 0.1

    def test_builds_string_transform(self):
        obs = [{"input": "hello", "output": "hello processed"}]
        cap = SoftwareCapability(source_software="X", capability_name="proc", description="process string")
        extractor = PatternExtractor()
        pattern = extractor.extract(obs)
        builder = MurphyImplementationBuilder()
        fn = builder.build(cap, pattern)
        assert callable(fn)
        result = fn("test")
        assert isinstance(result, str)

    def test_identity_fallback(self):
        obs = [{"input": {"a": 1}, "output": {"b": 2}}]
        cap = SoftwareCapability(source_software="X", capability_name="transform", description="dict transform")
        extractor = PatternExtractor()
        pattern = extractor.extract(obs)
        builder = MurphyImplementationBuilder()
        fn = builder.build(cap, pattern)
        assert callable(fn)


# ---------------------------------------------------------------------------
# Osmosis Candidate
# ---------------------------------------------------------------------------

class TestOsmosisCandidate:

    def test_passes_test_cases(self, numeric_observations):
        cap = SoftwareCapability(source_software="X", capability_name="mul2", description="x2")
        extractor = PatternExtractor()
        pattern = extractor.extract(numeric_observations)
        builder = MurphyImplementationBuilder()
        fn = builder.build(cap, pattern)

        test_cases = [
            {"input": 1.0, "expected_output": 2.0},
            {"input": 3.0, "expected_output": 6.0},
        ]
        candidate = OsmosisCandidate(
            candidate_id="cand-1",
            capability=cap,
            implementation_fn=fn,
            test_cases=test_cases,
        )
        result = candidate.run_test_cases()
        assert result["passed"] >= 1
        assert candidate.sandbox_tested is True

    def test_effectiveness_score_range(self, numeric_observations):
        cap = SoftwareCapability(source_software="X", capability_name="mul2", description="x2")
        fn = lambda x: x * 2  # noqa: E731
        candidate = OsmosisCandidate(
            candidate_id="cand-2",
            capability=cap,
            implementation_fn=fn,
            test_cases=[{"input": 5.0, "expected_output": 10.0}],
        )
        candidate.run_test_cases()
        assert 0.0 <= candidate.effectiveness_score <= 1.0


# ---------------------------------------------------------------------------
# Absorbed Capability Registry
# ---------------------------------------------------------------------------

class TestAbsorbedCapabilityRegistry:

    def test_register_and_get(self):
        reg = AbsorbedCapabilityRegistry()
        cap = SoftwareCapability(source_software="X", capability_name="Y", description="Z")
        reg.register(cap)
        assert reg.get(cap.capability_id) is not None

    def test_list_by_status(self):
        reg = AbsorbedCapabilityRegistry()
        cap1 = SoftwareCapability(source_software="A", capability_name="a", description="a",
                                  murphy_implementation_status=ImplementationStatus.OBSERVED)
        cap2 = SoftwareCapability(source_software="B", capability_name="b", description="b",
                                  murphy_implementation_status=ImplementationStatus.PRODUCTION)
        reg.register(cap1)
        reg.register(cap2)
        assert len(reg.list_by_status(ImplementationStatus.OBSERVED)) == 1
        assert len(reg.list_by_status(ImplementationStatus.PRODUCTION)) == 1

    def test_update_status(self):
        reg = AbsorbedCapabilityRegistry()
        cap = SoftwareCapability(source_software="X", capability_name="Y", description="Z")
        reg.register(cap)
        reg.update_status(cap.capability_id, ImplementationStatus.VALIDATED)
        assert reg.get(cap.capability_id).murphy_implementation_status == ImplementationStatus.VALIDATED

    def test_update_nonexistent(self):
        reg = AbsorbedCapabilityRegistry()
        assert reg.update_status("bad-id", ImplementationStatus.PRODUCTION) is False


# ---------------------------------------------------------------------------
# Insight Extractor
# ---------------------------------------------------------------------------

class TestInsightExtractor:

    def test_empty_insights(self):
        ie = InsightExtractor()
        result = ie.extract_insights()
        assert result["total"] == 0

    def test_approval_rate(self):
        ie = InsightExtractor()
        ie.record_interaction("review", "approved")
        ie.record_interaction("review", "approved")
        ie.record_interaction("review", "rejected", context={"reason": "missing_stamp"})
        result = ie.extract_insights()
        assert abs(result["approval_rate"] - 2/3) < 0.01

    def test_top_rejection_reasons(self):
        ie = InsightExtractor()
        for _ in range(3):
            ie.record_interaction("r", "rejected", context={"reason": "missing_stamp"})
        ie.record_interaction("r", "rejected", context={"reason": "wrong_format"})
        result = ie.extract_insights()
        assert result["top_rejection_reasons"][0]["reason"] == "missing_stamp"


# ---------------------------------------------------------------------------
# Osmosis Pipeline (integration)
# ---------------------------------------------------------------------------

class TestOsmosisPipeline:

    def test_absorb_with_valid_observations(self, pipeline, numeric_observations):
        cap = pipeline.absorb(
            source_software="SomeAPI",
            capability_name="double_value",
            description="Doubles a numeric value",
            observations=numeric_observations,
            test_cases=[
                {"input": 2.0, "expected_output": 4.0},
                {"input": 5.0, "expected_output": 10.0},
            ],
        )
        assert cap.capability_id is not None
        assert cap.murphy_implementation_status in (
            ImplementationStatus.VALIDATED, ImplementationStatus.OBSERVED
        )

    def test_absorb_updates_registry(self, pipeline, numeric_observations):
        cap = pipeline.absorb(
            source_software="ToolX",
            capability_name="scale",
            description="Scale values",
            observations=numeric_observations,
        )
        all_caps = pipeline.get_registry().list_all()
        assert any(c.capability_id == cap.capability_id for c in all_caps)

    def test_promote_validated_capability(self, pipeline, numeric_observations):
        cap = pipeline.absorb(
            source_software="ToolY",
            capability_name="triple",
            description="Triple",
            observations=[{"input": 1.0, "output": 3.0}, {"input": 2.0, "output": 6.0}],
            test_cases=[{"input": 1.0, "expected_output": 3.0}],
        )
        if cap.murphy_implementation_status == ImplementationStatus.VALIDATED:
            promoted = pipeline.promote_to_production(cap.capability_id)
            assert promoted is True

    def test_empty_observations(self, pipeline):
        cap = pipeline.absorb(
            source_software="EmptyTool",
            capability_name="unknown",
            description="No data",
            observations=[],
        )
        assert cap is not None
