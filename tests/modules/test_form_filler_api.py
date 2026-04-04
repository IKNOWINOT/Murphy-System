"""
API tests for grants form filler.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

import pytest
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.billing.grants.api import router as grants_router
from src.billing.grants.form_filler.api import router as form_filler_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(grants_router)
    app.include_router(form_filler_router)
    return TestClient(app)


def test_list_programs(client):
    resp = client.get("/api/grants/programs")
    assert resp.status_code == 200
    programs = resp.json()
    assert isinstance(programs, list)
    assert len(programs) > 0


def test_get_program(client):
    resp = client.get("/api/grants/programs/sbir_phase1")
    assert resp.status_code == 200
    prog = resp.json()
    assert prog["program_id"] == "sbir_phase1"


def test_check_eligibility(client):
    resp = client.post("/api/grants/eligibility", json={
        "program_ids": ["sbir_phase1", "sba_microloan"],
        "project_params": {
            "company_type": "small_business",
            "employee_count": 25,
            "annual_revenue_usd": 500000,
            "naics_codes": ["541715"],
            "us_based": True,
            "has_uei": True,
            "has_cage": True,
            "research_focus": "AI"
        }
    })
    assert resp.status_code == 200
    results = resp.json()
    assert isinstance(results, list)


def test_create_session(client):
    resp = client.post("/api/grants/sessions", json={
        "tenant_id": "tenant1",
        "name": "Test Session",
        "metadata": {}
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data


def test_create_application(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    resp = client.post(f"/api/grants/sessions/{sid}/applications", json={
        "tenant_id": "tenant1",
        "program_id": "sbir_phase1",
        "form_id": "sbir_phase1"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "application_id" in data


def test_fill_form(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    app_resp = client.post(f"/api/grants/sessions/{sid}/applications", json={"tenant_id": "tenant1", "program_id": "sbir_phase1", "form_id": "sbir_phase1"})
    aid = app_resp.json()["application_id"]
    resp = client.post(f"/api/grants/sessions/{sid}/applications/{aid}/fill", json={"tenant_id": "tenant1"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) or "fields" in data


def test_get_filled_fields(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    app_resp = client.post(f"/api/grants/sessions/{sid}/applications", json={"tenant_id": "tenant1", "program_id": "sbir_phase1", "form_id": "sbir_phase1"})
    aid = app_resp.json()["application_id"]
    client.post(f"/api/grants/sessions/{sid}/applications/{aid}/fill", json={"tenant_id": "tenant1"})
    resp = client.get(f"/api/grants/sessions/{sid}/applications/{aid}/fields", params={"tenant_id": "tenant1"})
    assert resp.status_code == 200


def test_start_review(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    app_resp = client.post(f"/api/grants/sessions/{sid}/applications", json={"tenant_id": "tenant1", "program_id": "sbir_phase1", "form_id": "sbir_phase1"})
    aid = app_resp.json()["application_id"]
    client.post(f"/api/grants/sessions/{sid}/applications/{aid}/fill", json={"tenant_id": "tenant1"})
    resp = client.post(f"/api/grants/sessions/{sid}/applications/{aid}/review", json={"tenant_id": "tenant1", "reviewer_id": "reviewer1"})
    assert resp.status_code == 200


def test_approve_review(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    app_resp = client.post(f"/api/grants/sessions/{sid}/applications", json={"tenant_id": "tenant1", "program_id": "sbir_phase1", "form_id": "sbir_phase1"})
    aid = app_resp.json()["application_id"]
    client.post(f"/api/grants/sessions/{sid}/applications/{aid}/fill", json={"tenant_id": "tenant1"})
    client.post(f"/api/grants/sessions/{sid}/applications/{aid}/review", json={"tenant_id": "tenant1", "reviewer_id": "reviewer1"})
    resp = client.put(f"/api/grants/sessions/{sid}/applications/{aid}/review", json={"tenant_id": "tenant1", "reviewer_id": "reviewer1", "action": "approve", "notes": "OK"})
    assert resp.status_code == 200


def test_edit_field(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    app_resp = client.post(f"/api/grants/sessions/{sid}/applications", json={"tenant_id": "tenant1", "program_id": "sbir_phase1", "form_id": "sbir_phase1"})
    aid = app_resp.json()["application_id"]
    client.post(f"/api/grants/sessions/{sid}/applications/{aid}/fill", json={"tenant_id": "tenant1"})
    resp = client.put(f"/api/grants/sessions/{sid}/applications/{aid}/fields/project_title", json={"tenant_id": "tenant1", "reviewer_id": "reviewer1", "new_value": "Updated Title"})
    assert resp.status_code == 200


def test_export_json(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    app_resp = client.post(f"/api/grants/sessions/{sid}/applications", json={"tenant_id": "tenant1", "program_id": "sbir_phase1", "form_id": "sbir_phase1"})
    aid = app_resp.json()["application_id"]
    client.post(f"/api/grants/sessions/{sid}/applications/{aid}/fill", json={"tenant_id": "tenant1"})
    resp = client.get(f"/api/grants/sessions/{sid}/applications/{aid}/export/json", params={"tenant_id": "tenant1"})
    assert resp.status_code == 200


def test_export_xml(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    app_resp = client.post(f"/api/grants/sessions/{sid}/applications", json={"tenant_id": "tenant1", "program_id": "sbir_phase1", "form_id": "sbir_phase1"})
    aid = app_resp.json()["application_id"]
    client.post(f"/api/grants/sessions/{sid}/applications/{aid}/fill", json={"tenant_id": "tenant1"})
    resp = client.get(f"/api/grants/sessions/{sid}/applications/{aid}/export/xml", params={"tenant_id": "tenant1"})
    assert resp.status_code == 200


def test_list_forms(client):
    resp = client.get("/api/grants/forms")
    assert resp.status_code == 200
    forms = resp.json()
    assert isinstance(forms, list)
    assert len(forms) > 0


def test_get_prerequisites(client):
    sess_resp = client.post("/api/grants/sessions", json={"tenant_id": "tenant1", "name": "Test", "metadata": {}})
    sid = sess_resp.json()["session_id"]
    resp = client.get("/api/grants/prerequisites", params={"session_id": sid, "tenant_id": "tenant1"})
    assert resp.status_code == 200
