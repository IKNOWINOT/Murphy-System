"""
Tests for FormFillerAgent.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import pytest
from src.billing.grants.session_manager import GrantSessionManager
from src.billing.grants.murphy_profiles import MurphyProfileManager, ProfileFlavor
from src.billing.grants.hitl_task_queue import HITLTaskQueue
from src.billing.grants.form_filler.agent import FormFillerAgent
from src.billing.grants.form_filler.form_definitions.sbir_phase1 import SBIRPhase1Form


@pytest.fixture
def agent():
    sm = GrantSessionManager()
    pm = MurphyProfileManager()
    tq = HITLTaskQueue()
    return FormFillerAgent(sm, pm, tq), sm, pm, tq


def test_agent_fills_sbir_form_with_profile(agent):
    a, sm, pm, tq = agent
    session = sm.create_session("tenant1", "Test Session", {})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    sm.save_form_data(session.session_id, "tenant1", {
        "company_name": "Acme Corp",
        "ein": "12-3456789",
        "uei": "ABC123DEF456",
        "cage_code": "1A2B3",
        "employee_count": 25,
        "annual_revenue_usd": 500000,
    })
    form_def = SBIRPhase1Form().get_definition()
    filled = a.fill_form(session.session_id, "tenant1", app.application_id, form_def)
    assert len(filled) > 0
    assert any(f.field_id == "company_legal_name" for f in filled)


def test_agent_auto_fills_company_info(agent):
    a, sm, pm, tq = agent
    session = sm.create_session("tenant1", "Test Session", {})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    sm.save_form_data(session.session_id, "tenant1", {
        "company_legal_name": "Acme Corp",
        "ein": "12-3456789",
    })
    form_def = SBIRPhase1Form().get_definition()
    filled = a.fill_form(session.session_id, "tenant1", app.application_id, form_def)
    auto_filled = [f for f in filled if f.status == "auto_filled"]
    assert len(auto_filled) > 0


def test_agent_flags_narratives_for_review(agent):
    a, sm, pm, tq = agent
    session = sm.create_session("tenant1", "Test", {})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    sm.save_form_data(session.session_id, "tenant1", {"project_description": "AI platform"})
    form_def = SBIRPhase1Form().get_definition()
    filled = a.fill_form(session.session_id, "tenant1", app.application_id, form_def)
    pd_field = next((f for f in filled if f.field_id == "project_description"), None)
    assert pd_field is not None
    assert pd_field.status in ["needs_review", "blocked_human_required"]


def test_agent_blocks_legal_certifications(agent):
    a, sm, pm, tq = agent
    session = sm.create_session("tenant1", "Test", {})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    form_def = SBIRPhase1Form().get_definition()
    filled = a.fill_form(session.session_id, "tenant1", app.application_id, form_def)
    cert_fields = [f for f in filled if f.field_id in ["authorized_rep_name", "certification_statement"]]
    assert len(cert_fields) > 0
    for cf in cert_fields:
        assert cf.status == "blocked_human_required"


def test_agent_updates_field(agent):
    a, sm, pm, tq = agent
    session = sm.create_session("tenant1", "Test", {})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    result = a.update_field(session.session_id, "tenant1", app.application_id, "project_title", "My Project", "reviewer1")
    assert result is not None
    assert result.edited_by_human is True
    assert result.value == "My Project"


def test_agent_accumulates_form_data(agent):
    a, sm, pm, tq = agent
    session = sm.create_session("tenant1", "Test", {})
    sm.save_form_data(session.session_id, "tenant1", {"company_name": "First"})
    sm.save_form_data(session.session_id, "tenant1", {"project_title": "MyProject"})
    data = sm.get_saved_form_data(session.session_id, "tenant1")
    assert data.get("company_name") == "First"
    assert data.get("project_title") == "MyProject"
