# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import pytest
from dataclasses import asdict
from src.billing.grants.submission.submission_manager import SubmissionManager
from src.billing.grants.submission.models import SubmissionPackage, SubmissionFile, SubmissionStep


ALL_PORTALS = ["grants_gov", "sam_gov", "sbir_gov", "research_gov", "sba_portal", "energy_trust", "generic"]


@pytest.fixture
def manager():
    return SubmissionManager()


def test_submission_package_is_dataclass(manager):
    pkg = manager.generate_package("s1", "a1", "grants_gov", {})
    assert isinstance(pkg, SubmissionPackage)


def test_submission_file_has_required_fields(manager):
    pkg = manager.generate_package("s1", "a1", "grants_gov", {})
    assert len(pkg.files) > 0
    f = pkg.files[0]
    assert f.file_id
    assert f.filename
    assert f.format
    assert f.content_type
    assert f.size_bytes > 0
    assert f.description


def test_submission_step_has_required_fields(manager):
    pkg = manager.generate_package("s1", "a1", "grants_gov", {})
    assert len(pkg.instructions) > 0
    step = pkg.instructions[0]
    assert step.step_number >= 1
    assert step.instruction


def test_generate_grants_gov_package(manager):
    pkg = manager.generate_package("s1", "a1", "grants_gov", {"opportunity_number": "FOA-001"})
    assert pkg.portal == "grants_gov"
    assert pkg.format == "xml"
    assert len(pkg.files) == 3
    assert len(pkg.instructions) == 10


def test_generate_sam_gov_package(manager):
    pkg = manager.generate_package("s2", "a2", "sam_gov", {})
    assert pkg.portal == "sam_gov"
    assert pkg.format == "csv"


def test_generate_sbir_gov_package(manager):
    pkg = manager.generate_package("s3", "a3", "sbir_gov", {})
    assert pkg.portal == "sbir_gov"
    assert pkg.format == "web_form"


def test_generate_research_gov_package(manager):
    pkg = manager.generate_package("s4", "a4", "research_gov", {})
    assert pkg.portal == "research_gov"
    assert pkg.format == "web_form"


def test_generate_sba_portal_package(manager):
    pkg = manager.generate_package("s5", "a5", "sba_portal", {})
    assert pkg.portal == "sba_portal"


def test_generate_energy_trust_package(manager):
    pkg = manager.generate_package("s6", "a6", "energy_trust", {})
    assert pkg.portal == "energy_trust"


def test_generate_generic_package(manager):
    pkg = manager.generate_package("s7", "a7", "generic", {})
    assert pkg.portal == "generic"


def test_package_status_is_generated(manager):
    pkg = manager.generate_package("s8", "a8", "grants_gov", {})
    assert pkg.status == "generated"


def test_package_has_package_id(manager):
    pkg = manager.generate_package("s9", "a9", "grants_gov", {})
    assert pkg.package_id
    assert len(pkg.package_id) > 0


def test_get_package_returns_same_package(manager):
    pkg = manager.generate_package("s10", "a10", "grants_gov", {})
    retrieved = manager.get_package("s10", "a10")
    assert retrieved is not None
    assert retrieved.package_id == pkg.package_id


def test_package_serializable(manager):
    pkg = manager.generate_package("s11", "a11", "grants_gov", {})
    d = asdict(pkg)
    assert "package_id" in d
    assert "files" in d
    assert "instructions" in d


def test_all_portals_generate_packages(manager):
    for portal in ALL_PORTALS:
        pkg = manager.generate_package("sx", "ax", portal, {})
        assert pkg.portal == portal
        assert len(pkg.instructions) >= 3
