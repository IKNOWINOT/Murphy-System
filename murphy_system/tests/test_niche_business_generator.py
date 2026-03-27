"""Tests for the Niche Business Generator (niche_business_generator.py).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os

import pytest


from src.mss_controls import MSSController
from src.information_quality import InformationQualityEngine
from src.information_density import InformationDensityEngine
from src.resolution_scoring import ResolutionDetectionEngine
from src.structural_coherence import StructuralCoherenceEngine
from src.concept_translation import ConceptTranslationEngine
from src.simulation_engine import StrategicSimulationEngine
from src.inference_gate_engine import InferenceDomainGateEngine, InferenceResult
from src.niche_business_generator import (
    NicheAutonomyClass,
    NicheRevenueModel,
    NicheDefinition,
    NicheDeploymentSpec,
    ContractorTask,
    ContractorDispatchInterface,
    NicheBusinessGenerator,
)


@pytest.fixture
def controller():
    rde = ResolutionDetectionEngine()
    ide = InformationDensityEngine()
    sce = StructuralCoherenceEngine()
    iqe = InformationQualityEngine(rde, ide, sce)
    cte = ConceptTranslationEngine()
    sim = StrategicSimulationEngine()
    return MSSController(iqe, cte, sim)


@pytest.fixture
def inference_engine():
    return InferenceDomainGateEngine()


@pytest.fixture
def generator(controller, inference_engine):
    return NicheBusinessGenerator(controller, inference_engine)


# ---------------------------------------------------------------------------
# Catalog tests
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_catalog_has_20_niches(self, generator):
        catalog = generator.get_catalog()
        assert len(catalog) == 20

    def test_all_full_autonomy_niches(self, generator):
        catalog = generator.get_catalog()
        full_auto = [n for n in catalog if n.autonomy_class == NicheAutonomyClass.FULL_AUTONOMY]
        assert len(full_auto) == 10

    def test_all_hybrid_niches(self, generator):
        catalog = generator.get_catalog()
        hybrid = [n for n in catalog if n.autonomy_class == NicheAutonomyClass.HYBRID]
        assert len(hybrid) == 10

    def test_get_niche_by_id(self, generator):
        niche = generator.get_niche("niche_seo_sites")
        assert niche is not None
        assert niche.niche_id == "niche_seo_sites"

    def test_get_niche_missing_returns_none(self, generator):
        niche = generator.get_niche("does_not_exist")
        assert niche is None

    def test_all_niches_have_required_modules(self, generator):
        for niche in generator.get_catalog():
            assert len(niche.murphy_modules_required) > 0, (
                f"Niche {niche.niche_id!r} has no murphy_modules_required"
            )

    def test_all_niches_have_seed_data(self, generator):
        for niche in generator.get_catalog():
            assert "industry" in niche.seed_data, (
                f"Niche {niche.niche_id!r} seed_data missing 'industry'"
            )
            assert "primary_goal" in niche.seed_data, (
                f"Niche {niche.niche_id!r} seed_data missing 'primary_goal'"
            )

    def test_all_hybrid_niches_have_contractor_templates(self, generator):
        for niche in generator.get_catalog():
            if niche.autonomy_class == NicheAutonomyClass.HYBRID:
                templates = niche.seed_data.get("contractor_task_templates", [])
                assert len(templates) > 0, (
                    f"Hybrid niche {niche.niche_id!r} has no contractor_task_templates"
                )


# ---------------------------------------------------------------------------
# generate_niche
# ---------------------------------------------------------------------------

class TestGenerateNiche:
    def test_full_autonomy_returns_deployment_spec(self, generator):
        niche = generator.get_niche("niche_seo_sites")
        spec = generator.generate_niche(niche)
        assert isinstance(spec, NicheDeploymentSpec)

    def test_hybrid_returns_deployment_spec(self, generator):
        niche = generator.get_niche("local_business_setup")
        spec = generator.generate_niche(niche)
        assert isinstance(spec, NicheDeploymentSpec)

    def test_hybrid_spec_has_contractor_tasks(self, generator):
        niche = generator.get_niche("local_business_setup")
        spec = generator.generate_niche(niche)
        assert len(spec.contractor_tasks) > 0

    def test_full_autonomy_spec_has_empty_contractor_tasks(self, generator):
        niche = generator.get_niche("niche_seo_sites")
        spec = generator.generate_niche(niche)
        assert spec.contractor_tasks == []

    def test_mss_sequence_used_is_mmsmm(self, generator):
        niche = generator.get_niche("kpi_dashboards")
        spec = generator.generate_niche(niche)
        assert spec.mss_sequence_used == "MMSMM"

    def test_spec_has_valid_inference_result(self, generator):
        niche = generator.get_niche("compliance_checklist")
        spec = generator.generate_niche(niche)
        assert isinstance(spec.inference_result, InferenceResult)

    def test_spec_has_nonzero_confidence(self, generator):
        niche = generator.get_niche("niche_job_boards")
        spec = generator.generate_niche(niche)
        assert spec.final_confidence > 0.0

    def test_spec_mss_results_non_empty(self, generator):
        niche = generator.get_niche("newsletter_businesses")
        spec = generator.generate_niche(niche)
        assert len(spec.mss_results) > 0

    def test_spec_has_dataset(self, generator):
        niche = generator.get_niche("api_aggregators")
        spec = generator.generate_niche(niche)
        assert isinstance(spec.dataset, dict)
        assert "industry" in spec.dataset


# ---------------------------------------------------------------------------
# discover_niche
# ---------------------------------------------------------------------------

class TestDiscoverNiche:
    def test_discover_creates_valid_definition(self, generator):
        description = "Automated podcast transcription service for independent creators"
        niche = generator.discover_niche(description)
        assert isinstance(niche, NicheDefinition)

    def test_discover_niche_id_is_unique(self, generator):
        description = "Online tutoring platform for coding bootcamp students"
        niche1 = generator.discover_niche(description)
        niche2 = generator.discover_niche(description)
        assert niche1.niche_id != niche2.niche_id

    def test_discover_niche_has_industry(self, generator):
        description = "Automated legal document review service"
        niche = generator.discover_niche(description)
        assert len(niche.estimated_industries) > 0

    def test_discover_physical_task_yields_hybrid(self, generator):
        description = (
            "On-site equipment installation and inspection service that requires "
            "physical field visits to customer locations"
        )
        niche = generator.discover_niche(description)
        assert niche.autonomy_class == NicheAutonomyClass.HYBRID

    def test_discover_digital_service_yields_full_autonomy(self, generator):
        description = "Automated keyword research and SEO content generation platform"
        niche = generator.discover_niche(description)
        assert niche.autonomy_class == NicheAutonomyClass.FULL_AUTONOMY

    def test_discover_niche_has_seed_data(self, generator):
        description = "Niche newsletter business for finance professionals"
        niche = generator.discover_niche(description)
        assert "industry" in niche.seed_data
        assert "primary_goal" in niche.seed_data


# ---------------------------------------------------------------------------
# validate_sequence
# ---------------------------------------------------------------------------

class TestValidateSequence:
    def test_returns_report_with_winner(self, generator):
        report = generator.validate_sequence(
            "SEO content automation platform for niche industries"
        )
        assert "winner" in report

    def test_report_has_top_5(self, generator):
        report = generator.validate_sequence("Automated niche job board generator")
        assert "top_5" in report

    def test_report_winner_is_string(self, generator):
        report = generator.validate_sequence("Compliance checklist automation tool")
        assert isinstance(report["winner"], str)


# ---------------------------------------------------------------------------
# ContractorDispatchInterface
# ---------------------------------------------------------------------------

class TestContractorDispatchInterface:
    @pytest.fixture
    def interface(self):
        return ContractorDispatchInterface()

    def test_create_task(self, interface):
        task = interface.create_task(
            niche_id="test_niche",
            description="Visit office and file paperwork",
            location_required=True,
            skill_required="runner",
            duration=2.0,
            payment=75.0,
            gate_name="filing_gate",
        )
        assert isinstance(task, ContractorTask)
        assert task.status == "pending"

    def test_dispatch_task(self, interface):
        task = interface.create_task(
            niche_id="test_niche",
            description="Inspect property",
            location_required=True,
            skill_required="inspector",
            duration=3.0,
            payment=150.0,
            gate_name="inspection_gate",
        )
        dispatched = interface.dispatch_task(task.task_id)
        assert dispatched.status == "dispatched"

    def test_submit_result(self, interface):
        task = interface.create_task(
            niche_id="test_niche",
            description="Conduct interview",
            location_required=False,
            skill_required="researcher",
            duration=1.5,
            payment=60.0,
            gate_name="interview_gate",
        )
        interface.dispatch_task(task.task_id)
        submitted = interface.submit_result(task.task_id, {"notes": "completed"})
        assert submitted.status == "submitted"

    def test_verify_submission(self, interface):
        task = interface.create_task(
            niche_id="test_niche",
            description="Notarize documents",
            location_required=True,
            skill_required="notary",
            duration=1.0,
            payment=50.0,
            gate_name="notarization_gate",
        )
        interface.dispatch_task(task.task_id)
        interface.submit_result(task.task_id, {"signed_docs": "attached"})
        verified = interface.verify_submission(task.task_id)
        assert verified is True

    def test_verify_pending_returns_false(self, interface):
        task = interface.create_task(
            niche_id="test_niche",
            description="File permit",
            location_required=True,
            skill_required="runner",
            duration=2.0,
            payment=80.0,
            gate_name="permit_gate",
        )
        # Not submitted yet
        verified = interface.verify_submission(task.task_id)
        assert verified is False

    def test_get_pending_tasks(self, interface):
        t1 = interface.create_task("n1", "Task A", True, "skill_a", 1.0, 50.0, "gate_a")
        t2 = interface.create_task("n1", "Task B", False, "skill_b", 2.0, 80.0, "gate_b")
        interface.dispatch_task(t1.task_id)
        pending = interface.get_pending_tasks()
        pending_ids = [t.task_id for t in pending]
        assert t2.task_id in pending_ids
        assert t1.task_id not in pending_ids

    def test_get_tasks_for_niche(self, interface):
        interface.create_task("niche_a", "Task 1", True, "s1", 1.0, 50.0, "g1")
        interface.create_task("niche_a", "Task 2", True, "s2", 2.0, 80.0, "g2")
        interface.create_task("niche_b", "Task 3", False, "s3", 1.0, 40.0, "g3")
        tasks = interface.get_tasks_for_niche("niche_a")
        assert len(tasks) == 2
        for t in tasks:
            assert t.niche_id == "niche_a"

    def test_verify_unknown_task_returns_false(self, interface):
        result = interface.verify_submission("nonexistent-uuid")
        assert result is False


# ---------------------------------------------------------------------------
# generate_all
# ---------------------------------------------------------------------------

class TestGenerateAll:
    def test_generate_all_returns_20_specs(self, generator):
        specs = generator.generate_all()
        assert len(specs) == 20

    def test_generate_all_returns_list_of_specs(self, generator):
        specs = generator.generate_all()
        for spec in specs:
            assert isinstance(spec, NicheDeploymentSpec)

    def test_get_contractor_interface(self, generator):
        interface = generator.get_contractor_interface()
        assert isinstance(interface, ContractorDispatchInterface)

    def test_custom_sequence_is_stored(self, controller, inference_engine):
        custom_gen = NicheBusinessGenerator(controller, inference_engine, sequence="MMS")
        assert custom_gen.sequence == "MMS"

    def test_default_sequence_is_mmsmm(self, generator):
        assert generator.sequence == "MMSMM"
