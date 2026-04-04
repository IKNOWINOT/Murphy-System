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


# ---------------------------------------------------------------------------
# Production-readiness tests (30+ new cases)
# ---------------------------------------------------------------------------

import threading

class TestPatternExtractorProduction:

    def test_numeric_multiplication_pattern(self):
        from src.murphy_osmosis_engine import PatternExtractor
        pe = PatternExtractor()
        observations = [{"input": i, "output": i * 3.0} for i in range(1, 6)]
        pattern = pe.extract(observations)
        assert "3.0" in pattern["core_algorithm_description"] or "3." in pattern["core_algorithm_description"]

    def test_string_transformation_pattern(self):
        from src.murphy_osmosis_engine import PatternExtractor
        pe = PatternExtractor()
        observations = [{"input": "hello", "output": "HELLO"}, {"input": "world", "output": "WORLD"}]
        pattern = pe.extract(observations)
        assert "String" in pattern["core_algorithm_description"]

    def test_dict_transformation_pattern(self):
        from src.murphy_osmosis_engine import PatternExtractor
        pe = PatternExtractor()
        observations = [{"input": {"a": 1}, "output": {"a": 2}}, {"input": {"b": 3}, "output": {"b": 6}}]
        pattern = pe.extract(observations)
        assert "Dictionary" in pattern["core_algorithm_description"] or "General" in pattern["core_algorithm_description"]

    def test_empty_observations_returns_defaults(self):
        from src.murphy_osmosis_engine import PatternExtractor
        pe = PatternExtractor()
        pattern = pe.extract([])
        assert pattern["sample_count"] == 0
        assert "No observations" in pattern["core_algorithm_description"]

    def test_sample_count_matches_observations(self):
        from src.murphy_osmosis_engine import PatternExtractor
        pe = PatternExtractor()
        obs = [{"input": i, "output": i * 2} for i in range(10)]
        pattern = pe.extract(obs)
        assert pattern["sample_count"] == 10

    def test_input_types_populated(self):
        from src.murphy_osmosis_engine import PatternExtractor
        pe = PatternExtractor()
        obs = [{"input": 1.0, "output": 2.0}]
        pattern = pe.extract(obs)
        assert "float" in pattern["input_types"] or "int" in pattern["input_types"]


class TestCapabilityObserverProduction:

    def test_observe_records_entry(self):
        from src.murphy_osmosis_engine import CapabilityObserver
        obs = CapabilityObserver("ToolA", "double")
        obs.observe(5, 10)
        assert obs.get_observation_count() == 1

    def test_observe_with_metadata(self):
        from src.murphy_osmosis_engine import CapabilityObserver
        obs = CapabilityObserver("ToolA", "double")
        obs.observe(5, 10, metadata={"source": "api_call"})
        records = obs.get_observations()
        assert records[0]["metadata"]["source"] == "api_call"

    def test_thread_safe_concurrent_observations(self):
        from src.murphy_osmosis_engine import CapabilityObserver
        obs = CapabilityObserver("ToolA", "double")
        def do_observe():
            for i in range(10):
                obs.observe(i, i * 2)
        threads = [threading.Thread(target=do_observe) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert obs.get_observation_count() == 50

    def test_get_observations_returns_copy(self):
        from src.murphy_osmosis_engine import CapabilityObserver
        obs = CapabilityObserver("ToolA", "double")
        obs.observe(1, 2)
        copy1 = obs.get_observations()
        copy1.append({"fake": True})
        assert obs.get_observation_count() == 1


class TestImplementationBuilderProduction:

    def test_numeric_transform_callable(self):
        from src.murphy_osmosis_engine import MurphyImplementationBuilder, SoftwareCapability
        builder = MurphyImplementationBuilder()
        cap = SoftwareCapability(source_software="ToolA", capability_name="x2",
                                  description="double", core_algorithm="output ≈ input × 2.0000")
        fn = builder.build(cap, {"core_algorithm_description": "output ≈ input × 2.0000"})
        assert abs(fn(5.0) - 10.0) < 0.001

    def test_string_transform_callable(self):
        from src.murphy_osmosis_engine import MurphyImplementationBuilder, SoftwareCapability
        builder = MurphyImplementationBuilder()
        cap = SoftwareCapability(source_software="ToolA", capability_name="stringify",
                                  description="convert to string")
        fn = builder.build(cap, {"core_algorithm_description": "String processing transformation"})
        assert fn(42) == "42"

    def test_identity_transform_callable(self):
        from src.murphy_osmosis_engine import MurphyImplementationBuilder, SoftwareCapability
        builder = MurphyImplementationBuilder()
        cap = SoftwareCapability(source_software="ToolA", capability_name="passthrough",
                                  description="identity")
        fn = builder.build(cap, {"core_algorithm_description": "General transformation pattern"})
        assert fn("hello") == "hello"
        assert fn(42) == 42


class TestOsmosisCandidateProduction:

    def test_candidate_passes_sandbox(self):
        from src.murphy_osmosis_engine import OsmosisCandidate, SoftwareCapability
        cap = SoftwareCapability(source_software="ToolA", capability_name="x2", description="double")
        candidate = OsmosisCandidate(
            candidate_id="c1",
            capability=cap,
            implementation_fn=lambda x: x * 2,
            test_cases=[{"input": i, "expected_output": i * 2} for i in range(1, 6)],
        )
        result = candidate.run_test_cases()
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert candidate.sandbox_passed is True
        assert candidate.effectiveness_score == 1.0

    def test_candidate_fails_sandbox(self):
        from src.murphy_osmosis_engine import OsmosisCandidate, SoftwareCapability
        cap = SoftwareCapability(source_software="ToolA", capability_name="broken", description="broken")
        candidate = OsmosisCandidate(
            candidate_id="c2",
            capability=cap,
            implementation_fn=lambda x: x + 999,  # wrong
            test_cases=[{"input": 1, "expected_output": 2}, {"input": 2, "expected_output": 4}],
        )
        result = candidate.run_test_cases()
        assert result["failed"] == 2
        assert candidate.sandbox_passed is False

    def test_candidate_no_test_cases(self):
        from src.murphy_osmosis_engine import OsmosisCandidate, SoftwareCapability
        cap = SoftwareCapability(source_software="ToolA", capability_name="x", description="x")
        candidate = OsmosisCandidate(candidate_id="c3", capability=cap, implementation_fn=lambda x: x)
        result = candidate.run_test_cases()
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert candidate.effectiveness_score == 0.0


class TestOsmosisPipelineProduction:

    def test_full_pipeline_validated(self):
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        pipeline = OsmosisPipeline()
        observations = [{"input": i, "output": i * 2.0} for i in range(1, 6)]
        test_cases = [{"input": i, "expected_output": i * 2.0} for i in range(1, 6)]
        cap = pipeline.absorb("ToolA", "double", "multiply by 2", observations, test_cases)
        assert cap.murphy_implementation_status == ImplementationStatus.VALIDATED
        assert cap.validation_score == 1.0

    def test_pipeline_low_score_stays_observed(self):
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        pipeline = OsmosisPipeline()
        observations = [{"input": i, "output": i * 2.0} for i in range(1, 6)]
        # Test cases that will fail (wrong expected)
        test_cases = [{"input": i, "expected_output": i * 999.0} for i in range(1, 6)]
        cap = pipeline.absorb("ToolA", "broken", "broken", observations, test_cases)
        # Should remain observed/sandbox status because score < 0.7
        assert cap.murphy_implementation_status in (ImplementationStatus.OBSERVED, ImplementationStatus.SANDBOX_TESTING)

    def test_pipeline_promote_to_production(self):
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        pipeline = OsmosisPipeline()
        observations = [{"input": i, "output": i * 2.0} for i in range(1, 6)]
        test_cases = [{"input": i, "expected_output": i * 2.0} for i in range(1, 6)]
        cap = pipeline.absorb("ToolA", "double", "double", observations, test_cases)
        promoted = pipeline.promote_to_production(cap.capability_id)
        assert promoted is True
        stored = pipeline.get_registry().get(cap.capability_id)
        assert stored.murphy_implementation_status == ImplementationStatus.PRODUCTION

    def test_registry_tracks_status(self):
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        pipeline = OsmosisPipeline()
        observations = [{"input": i, "output": i * 2.0} for i in range(1, 6)]
        test_cases = [{"input": i, "expected_output": i * 2.0} for i in range(1, 6)]
        cap = pipeline.absorb("ToolA", "x2", "double", observations, test_cases)
        validated = pipeline.get_registry().list_by_status(ImplementationStatus.VALIDATED)
        assert any(c.capability_id == cap.capability_id for c in validated)

    def test_pipeline_no_test_cases_not_sandbox_passed(self):
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        pipeline = OsmosisPipeline()
        observations = [{"input": 1, "output": 2.0}]
        cap = pipeline.absorb("ToolA", "no-tests", "no tests", observations)
        # With no test cases, effectiveness = 0.0, should not pass sandbox
        assert cap.murphy_implementation_status == ImplementationStatus.OBSERVED

    def test_insight_extractor_records_and_extracts(self):
        from src.murphy_osmosis_engine import InsightExtractor
        ie = InsightExtractor()
        for _ in range(3):
            ie.record_interaction("approve", "approved")
        ie.record_interaction("reject", "rejected", context={"reason": "too expensive"})
        insights = ie.extract_insights()
        assert insights["total"] == 4
        assert insights["approved"] == 3
        assert insights["rejected"] == 1
        assert insights["approval_rate"] == pytest.approx(0.75)

    def test_absorbed_capability_registry_update_status(self):
        from src.murphy_osmosis_engine import AbsorbedCapabilityRegistry, SoftwareCapability, ImplementationStatus
        reg = AbsorbedCapabilityRegistry()
        cap = SoftwareCapability(source_software="ToolA", capability_name="x", description="x")
        reg.register(cap)
        result = reg.update_status(cap.capability_id, ImplementationStatus.PRODUCTION)
        assert result is True
        stored = reg.get(cap.capability_id)
        assert stored.murphy_implementation_status == ImplementationStatus.PRODUCTION


import pytest


class TestOsmosisEdgeCasesProduction:

    def test_absorb_with_no_observations(self):
        from src.murphy_osmosis_engine import OsmosisPipeline, ImplementationStatus
        pipeline = OsmosisPipeline()
        cap = pipeline.absorb("ToolA", "empty", "no observations", [])
        assert cap.capability_id is not None

    def test_promote_nonexistent_capability_returns_false(self):
        from src.murphy_osmosis_engine import OsmosisPipeline
        pipeline = OsmosisPipeline()
        result = pipeline.promote_to_production("no-such-id")
        assert result is False

    def test_promote_before_validated_returns_false(self):
        from src.murphy_osmosis_engine import OsmosisPipeline
        pipeline = OsmosisPipeline()
        # Absorb with no test cases (stays OBSERVED)
        cap = pipeline.absorb("ToolA", "unvalidated", "x", [{"input": 1, "output": 2}])
        result = pipeline.promote_to_production(cap.capability_id)
        assert result is False

    def test_absorbed_capability_registry_list_all(self):
        from src.murphy_osmosis_engine import AbsorbedCapabilityRegistry, SoftwareCapability
        reg = AbsorbedCapabilityRegistry()
        for i in range(3):
            cap = SoftwareCapability(source_software="ToolA",
                                     capability_name=f"cap_{i}", description="x")
            reg.register(cap)
        assert len(reg.list_all()) == 3

    def test_insight_extractor_empty_returns_zeros(self):
        from src.murphy_osmosis_engine import InsightExtractor
        ie = InsightExtractor()
        insights = ie.extract_insights()
        assert insights["total"] == 0
        assert insights["approval_rate"] == 0.0

    def test_capability_observer_multiple_sources(self):
        from src.murphy_osmosis_engine import CapabilityObserver
        obs1 = CapabilityObserver("ToolA", "cap1")
        obs2 = CapabilityObserver("ToolB", "cap2")
        obs1.observe(1, 2)
        obs2.observe("hello", "HELLO")
        assert obs1.get_observation_count() == 1
        assert obs2.get_observation_count() == 1

    def test_pattern_extractor_general_pattern(self):
        from src.murphy_osmosis_engine import PatternExtractor
        pe = PatternExtractor()
        observations = [{"input": [1, 2, 3], "output": 6}]
        pattern = pe.extract(observations)
        assert "General" in pattern["core_algorithm_description"]

    def test_numeric_builder_with_zero_input(self):
        from src.murphy_osmosis_engine import MurphyImplementationBuilder, SoftwareCapability
        builder = MurphyImplementationBuilder()
        cap = SoftwareCapability(source_software="ToolA", capability_name="x2",
                                  description="double")
        fn = builder.build(cap, {"core_algorithm_description": "output ≈ input × 2.0000"})
        assert fn(0.0) == 0.0

    def test_osmosis_candidate_effectiveness_zero_on_no_tests(self):
        from src.murphy_osmosis_engine import OsmosisCandidate, SoftwareCapability
        cap = SoftwareCapability(source_software="X", capability_name="x", description="x")
        c = OsmosisCandidate(candidate_id="c0", capability=cap, implementation_fn=lambda x: x)
        result = c.run_test_cases()
        assert c.effectiveness_score == 0.0
        assert c.sandbox_passed is False

    def test_pipeline_registry_accessible(self):
        from src.murphy_osmosis_engine import OsmosisPipeline
        pipeline = OsmosisPipeline()
        reg = pipeline.get_registry()
        assert reg is not None
        assert reg.list_all() == []
