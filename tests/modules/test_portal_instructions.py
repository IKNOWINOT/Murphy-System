# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import pytest
from src.billing.grants.submission.portal_instructions.grants_gov import GrantsGovInstructions
from src.billing.grants.submission.portal_instructions.sam_gov import SamGovInstructions
from src.billing.grants.submission.portal_instructions.sbir_gov import SbirGovInstructions
from src.billing.grants.submission.portal_instructions.research_gov import ResearchGovInstructions
from src.billing.grants.submission.portal_instructions.sba_portal import SbaPortalInstructions
from src.billing.grants.submission.portal_instructions.energy_trust import EnergyTrustInstructions
from src.billing.grants.submission.portal_instructions.generic_portal import GenericPortalInstructions
from src.billing.grants.submission.models import SubmissionStep


ALL_INSTRUCTION_CLASSES = [
    GrantsGovInstructions,
    SamGovInstructions,
    SbirGovInstructions,
    ResearchGovInstructions,
    SbaPortalInstructions,
    EnergyTrustInstructions,
    GenericPortalInstructions,
]


def test_grants_gov_generates_10_steps():
    steps = GrantsGovInstructions().generate_steps({})
    assert len(steps) == 10


def test_grants_gov_step_1_has_url():
    steps = GrantsGovInstructions().generate_steps({})
    assert steps[0].url is not None
    assert "grants.gov" in steps[0].url


def test_grants_gov_steps_in_order():
    steps = GrantsGovInstructions().generate_steps({})
    for i, step in enumerate(steps, 1):
        assert step.step_number == i


def test_grants_gov_has_upload_steps():
    steps = GrantsGovInstructions().generate_steps({})
    upload_steps = [s for s in steps if s.is_upload]
    assert len(upload_steps) >= 2


def test_sam_gov_generates_steps():
    steps = SamGovInstructions().generate_steps({})
    assert len(steps) >= 3


def test_sam_gov_first_step_has_url():
    steps = SamGovInstructions().generate_steps({})
    assert steps[0].url is not None


def test_sbir_gov_generates_steps():
    steps = SbirGovInstructions().generate_steps({})
    assert len(steps) >= 3


def test_research_gov_generates_steps():
    steps = ResearchGovInstructions().generate_steps({})
    assert len(steps) >= 3


def test_sba_portal_generates_steps():
    steps = SbaPortalInstructions().generate_steps({})
    assert len(steps) >= 3


def test_energy_trust_generates_steps():
    steps = EnergyTrustInstructions().generate_steps({})
    assert len(steps) >= 3


def test_generic_portal_generates_steps():
    steps = GenericPortalInstructions().generate_steps({})
    assert len(steps) >= 3


def test_all_portals_steps_are_submission_step_instances():
    for cls in ALL_INSTRUCTION_CLASSES:
        steps = cls().generate_steps({})
        for step in steps:
            assert isinstance(step, SubmissionStep)


def test_all_portals_steps_have_instructions():
    for cls in ALL_INSTRUCTION_CLASSES:
        steps = cls().generate_steps({})
        for step in steps:
            assert step.instruction


def test_generic_portal_uses_provided_url():
    steps = GenericPortalInstructions().generate_steps({"portal_url": "https://example.com/grants"})
    assert steps[0].url == "https://example.com/grants"


def test_grants_gov_uses_opportunity_number():
    steps = GrantsGovInstructions().generate_steps({"opportunity_number": "FOA-TEST-999"})
    step_3 = steps[2]
    assert "FOA-TEST-999" in step_3.instruction
