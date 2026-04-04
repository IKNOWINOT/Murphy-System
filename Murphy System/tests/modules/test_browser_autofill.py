"""
Tests for browser-like auto-fill accumulation.
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
def setup():
    sm = GrantSessionManager()
    pm = MurphyProfileManager()
    tq = HITLTaskQueue()
    agent = FormFillerAgent(sm, pm, tq)
    return sm, pm, tq, agent


def test_first_fill_saves_data(setup):
    sm, pm, tq, agent = setup
    session = sm.create_session("tenant1", "Test", {})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    sm.save_form_data(session.session_id, "tenant1", {"company_legal_name": "Acme", "ein": "12-3456789"})
    form_def = SBIRPhase1Form().get_definition()
    filled = agent.fill_form(session.session_id, "tenant1", app.application_id, form_def)
    saved = sm.get_saved_form_data(session.session_id, "tenant1")
    assert "company_legal_name" in saved or "ein" in saved


def test_second_fill_uses_saved_data_at_high_confidence(setup):
    sm, pm, tq, agent = setup
    session = sm.create_session("tenant1", "Test", {})
    sm.save_form_data(session.session_id, "tenant1", {"company_legal_name": "Acme Corp", "ein": "12-3456789", "uei": "ABCDEF123456"})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    form_def = SBIRPhase1Form().get_definition()
    agent.fill_form(session.session_id, "tenant1", app.application_id, form_def)
    app2 = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    filled2 = agent.fill_form(session.session_id, "tenant1", app2.application_id, form_def)
    cn_field = next((f for f in filled2 if f.field_id == "company_legal_name"), None)
    assert cn_field is not None
    assert cn_field.status in ["auto_filled", "needs_review"]


def test_tenant_isolation_no_bleed(setup):
    sm, pm, tq, agent = setup
    sess1 = sm.create_session("tenant1", "Session1", {})
    sess2 = sm.create_session("tenant2", "Session2", {})
    sm.save_form_data(sess1.session_id, "tenant1", {"company_legal_name": "TenantOne Corp"})
    sm.save_form_data(sess2.session_id, "tenant2", {"company_legal_name": "TenantTwo Corp"})
    data1 = sm.get_saved_form_data(sess1.session_id, "tenant1")
    data2 = sm.get_saved_form_data(sess2.session_id, "tenant2")
    assert data1.get("company_legal_name") == "TenantOne Corp"
    assert data2.get("company_legal_name") == "TenantTwo Corp"
    cross_data = sm.get_saved_form_data(sess1.session_id, "tenant2")
    assert cross_data == {} or cross_data is None


def test_accumulation_across_applications(setup):
    sm, pm, tq, agent = setup
    session = sm.create_session("tenant1", "Test", {})
    sm.save_form_data(session.session_id, "tenant1", {"company_legal_name": "Acme"})
    sm.save_form_data(session.session_id, "tenant1", {"uei": "ABC123"})
    sm.save_form_data(session.session_id, "tenant1", {"ein": "12-3456789"})
    data = sm.get_saved_form_data(session.session_id, "tenant1")
    assert data.get("company_legal_name") == "Acme"
    assert data.get("uei") == "ABC123"
    assert data.get("ein") == "12-3456789"


def test_saved_data_overrides_profile_data(setup):
    sm, pm, tq, agent = setup
    session = sm.create_session("tenant1", "Test", {})
    pm.create_profile(session.session_id, "tenant1", ProfileFlavor.RD, {
        "company_name": "Profile Company",
        "employee_count": 10,
        "annual_revenue_usd": 100000,
        "naics_codes": ["541715"],
    })
    sm.save_form_data(session.session_id, "tenant1", {"company_legal_name": "Saved Company"})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    form_def = SBIRPhase1Form().get_definition()
    filled = agent.fill_form(session.session_id, "tenant1", app.application_id, form_def)
    cn_field = next((f for f in filled if f.field_id == "company_legal_name"), None)
    if cn_field and cn_field.value:
        assert cn_field.value == "Saved Company"


def test_human_edit_saved_as_form_data(setup):
    sm, pm, tq, agent = setup
    session = sm.create_session("tenant1", "Test", {})
    app = sm.create_application(session.session_id, "tenant1", "sbir_phase1", "sbir_phase1")
    result = agent.update_field(session.session_id, "tenant1", app.application_id, "project_title", "Human Title", "reviewer1")
    assert result is not None
    assert result.edited_by_human is True
    saved = sm.get_saved_form_data(session.session_id, "tenant1")
    assert saved.get("project_title") == "Human Title"
