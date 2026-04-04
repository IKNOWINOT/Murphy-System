"""Tests for MSS Transformation Controls (mss_controls.py).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from src.mss_controls import MSSController, TransformationResult
from src.information_quality import InformationQualityEngine, InformationQuality
from src.resolution_scoring import ResolutionDetectionEngine
from src.information_density import InformationDensityEngine
from src.structural_coherence import StructuralCoherenceEngine
from src.concept_translation import ConceptTranslationEngine
from src.simulation_engine import StrategicSimulationEngine, SimulationResult


@pytest.fixture
def controller():
    rde = ResolutionDetectionEngine()
    ide = InformationDensityEngine()
    sce = StructuralCoherenceEngine()
    iqe = InformationQualityEngine(rde, ide, sce)
    cte = ConceptTranslationEngine()
    sim = StrategicSimulationEngine()
    return MSSController(iqe, cte, sim)


SAMPLE = "Create a routing optimization module with safety constraints and monitoring"
SIMPLE = "make things better"
DETAILED = (
    "Build a FastAPI service module with a PostgreSQL database backend. "
    "First, configure the REST API endpoints. Then, validate input with JSON schema. "
    "If validation fails, return a 400 error. Deploy using Docker and CI/CD pipeline. "
    "Unit test coverage must exceed 90 percent. Monitor latency and throughput via dashboard."
)


# ---- Functional: magnify ----

class TestMagnify:
    def test_returns_transformation_result(self, controller):
        result = controller.magnify(SAMPLE)
        assert isinstance(result, TransformationResult)

    def test_operator_field(self, controller):
        assert controller.magnify(SAMPLE).operator == "magnify"

    def test_target_rm_increases(self, controller):
        result = controller.magnify(SIMPLE)
        cur = int(result.input_quality.resolution_level.replace("RM", ""))
        tgt = int(result.target_rm.replace("RM", ""))
        assert tgt >= cur

    def test_output_has_concept_overview(self, controller):
        assert "concept_overview" in controller.magnify(SAMPLE).output

    def test_output_has_resolution_progression(self, controller):
        assert "resolution_progression" in controller.magnify(SAMPLE).output

    def test_simulation_is_none(self, controller):
        assert controller.magnify(SAMPLE).simulation is None


# ---- Functional: simplify ----

class TestSimplify:
    def test_returns_transformation_result(self, controller):
        assert isinstance(controller.simplify(SAMPLE), TransformationResult)

    def test_operator_field(self, controller):
        assert controller.simplify(SAMPLE).operator == "simplify"

    def test_target_rm_floor(self, controller):
        result = controller.simplify(SIMPLE)
        tgt = int(result.target_rm.replace("RM", ""))
        assert tgt >= 0

    def test_output_has_objective(self, controller):
        assert "objective" in controller.simplify(SAMPLE).output

    def test_simulation_is_none(self, controller):
        assert controller.simplify(SAMPLE).simulation is None


# ---- Functional: solidify ----

class TestSolidify:
    def test_returns_transformation_result(self, controller):
        assert isinstance(controller.solidify(SAMPLE), TransformationResult)

    def test_operator_field(self, controller):
        assert controller.solidify(SAMPLE).operator == "solidify"

    def test_targets_rm5(self, controller):
        assert controller.solidify(SAMPLE).target_rm == "RM5"

    def test_output_has_capability_definition(self, controller):
        assert "capability_definition" in controller.solidify(SAMPLE).output

    def test_output_has_implementation_steps(self, controller):
        assert "implementation_steps" in controller.solidify(SAMPLE).output

    def test_has_simulation(self, controller):
        result = controller.solidify(SAMPLE)
        assert isinstance(result.simulation, SimulationResult)


# ---- QC Metadata ----

class TestQCMetadata:
    def test_has_all_keys(self, controller):
        md = controller.magnify(SAMPLE).qc_metadata
        for key in ("who", "what", "when", "where", "why", "how"):
            assert key in md

    def test_who_default(self, controller):
        assert controller.magnify(SAMPLE).qc_metadata["who"] == "murphy_system"

    def test_who_custom(self, controller):
        result = controller.magnify(SAMPLE, context={"owner": "alice"})
        assert result.qc_metadata["who"] == "alice"


# ---- Quality assessment ----

class TestQuality:
    def test_input_quality_type(self, controller):
        assert isinstance(controller.magnify(SAMPLE).input_quality, InformationQuality)

    def test_output_quality_type(self, controller):
        assert isinstance(controller.magnify(SAMPLE).output_quality, InformationQuality)

    def test_governance_status_valid(self, controller):
        assert controller.magnify(SAMPLE).governance_status in ("approved", "conditional", "blocked")

    def test_input_text_preserved(self, controller):
        assert controller.magnify(SAMPLE).input_text == SAMPLE


# ---- Edge cases ----

class TestEdgeCases:
    def test_empty_input_magnify(self, controller):
        result = controller.magnify("")
        assert isinstance(result, TransformationResult)

    def test_empty_input_simplify(self, controller):
        result = controller.simplify("")
        assert isinstance(result, TransformationResult)

    def test_empty_input_solidify(self, controller):
        result = controller.solidify("")
        assert isinstance(result, TransformationResult)


# ---- Integration ----

class TestIntegration:
    def test_full_pipeline(self, controller):
        for op in (controller.magnify, controller.simplify, controller.solidify):
            result = op(DETAILED)
            assert isinstance(result, TransformationResult)
            assert result.input_quality.resolution_score >= 0
            assert result.output_quality.resolution_score >= 0
