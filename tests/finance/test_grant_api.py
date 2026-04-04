"""
Test: Grant API Endpoints — FastAPI router tests.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.billing.grants.api import router
from src.billing.grants.sessions import _session_manager
from src.billing.grants.task_queue import _task_manager
from src.billing.grants.prerequisites import _prereq_chain

# Reset singletons before tests to avoid state leakage
import src.billing.grants.sessions as _sessions_mod
import src.billing.grants.task_queue as _task_mod
import src.billing.grants.prerequisites as _prereq_mod


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset module-level singletons before each test."""
    _sessions_mod._session_manager = None
    _task_mod._task_manager = None
    _prereq_mod._prereq_chain = None
    yield
    _sessions_mod._session_manager = None
    _task_mod._task_manager = None
    _prereq_mod._prereq_chain = None


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
def client(app, monkeypatch):
    monkeypatch.setenv("MURPHY_ENV", "development")
    return TestClient(app)


ACCOUNT_HEADERS = {"X-Account-Id": "test-account-123"}
OTHER_ACCOUNT_HEADERS = {"X-Account-Id": "other-account-456"}


# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------

def test_list_programs(client):
    resp = client.get("/api/grants/programs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 30
    assert len(data["programs"]) > 0


def test_list_programs_filter_category(client):
    resp = client.get("/api/grants/programs?category=federal_grant")
    assert resp.status_code == 200
    data = resp.json()
    for p in data["programs"]:
        assert p["category"] == "federal_grant"


def test_get_program_by_id(client):
    resp = client.get("/api/grants/programs/sbir_phase1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "sbir_phase1"


def test_get_program_not_found(client):
    resp = client.get("/api/grants/programs/nonexistent_xyz")
    assert resp.status_code == 404


def test_get_stats(client):
    resp = client.get("/api/grants/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_programs"] > 0


# ---------------------------------------------------------------------------
# Eligibility endpoint
# ---------------------------------------------------------------------------

def test_eligibility_bas_oregon(client):
    resp = client.get("/api/grants/eligibility?project_type=bas_bms&entity_type=small_business&state=OR&is_commercial=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matches"] > 0
    grant_ids = {m["grant_id"] for m in data["matches"]}
    assert "energy_trust_oregon" in grant_ids


def test_eligibility_rd_project(client):
    resp = client.get("/api/grants/eligibility?project_type=ai_platform&entity_type=small_business&state=OR&has_rd_activity=true")
    assert resp.status_code == 200
    data = resp.json()
    grant_ids = {m["grant_id"] for m in data["matches"]}
    assert "sbir_phase1" in grant_ids


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

def test_create_session(client):
    resp = client.post("/api/grants/sessions", json={"name": "My Grant Session"}, headers=ACCOUNT_HEADERS)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Grant Session"
    assert data["account_id"] == "test-account-123"
    assert "session_id" in data


def test_list_sessions(client):
    client.post("/api/grants/sessions", json={"name": "Session 1"}, headers=ACCOUNT_HEADERS)
    client.post("/api/grants/sessions", json={"name": "Session 2"}, headers=ACCOUNT_HEADERS)
    resp = client.get("/api/grants/sessions", headers=ACCOUNT_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_get_session(client):
    create_resp = client.post("/api/grants/sessions", json={"name": "Test"}, headers=ACCOUNT_HEADERS)
    session_id = create_resp.json()["session_id"]
    get_resp = client.get(f"/api/grants/sessions/{session_id}", headers=ACCOUNT_HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["session_id"] == session_id


def test_cross_tenant_session_access_denied(client):
    """Account B cannot access Account A's session."""
    create_resp = client.post("/api/grants/sessions", json={"name": "A's Session"}, headers=ACCOUNT_HEADERS)
    session_id = create_resp.json()["session_id"]
    resp = client.get(f"/api/grants/sessions/{session_id}", headers=OTHER_ACCOUNT_HEADERS)
    assert resp.status_code == 403


def test_delete_session(client):
    create_resp = client.post("/api/grants/sessions", json={"name": "To Delete"}, headers=ACCOUNT_HEADERS)
    session_id = create_resp.json()["session_id"]
    del_resp = client.delete(f"/api/grants/sessions/{session_id}", headers=ACCOUNT_HEADERS)
    assert del_resp.status_code == 200


# ---------------------------------------------------------------------------
# Form data endpoints
# ---------------------------------------------------------------------------

def test_update_and_get_form_data(client):
    create_resp = client.post("/api/grants/sessions", json={"name": "FormTest"}, headers=ACCOUNT_HEADERS)
    session_id = create_resp.json()["session_id"]

    update_resp = client.put(
        f"/api/grants/sessions/{session_id}/formdata",
        json={"data": {"company_name": "Inoni LLC", "ein": "12-3456789"}},
        headers=ACCOUNT_HEADERS,
    )
    assert update_resp.status_code == 200
    assert "company_name" in update_resp.json()["updated_fields"]

    get_resp = client.get(f"/api/grants/sessions/{session_id}/formdata", headers=ACCOUNT_HEADERS)
    assert get_resp.status_code == 200
    form_data = get_resp.json()["form_data"]
    assert "company_name" in form_data
    assert form_data["company_name"]["field_value"] == "Inoni LLC"


# ---------------------------------------------------------------------------
# Application endpoints
# ---------------------------------------------------------------------------

def test_create_and_list_application(client):
    create_resp = client.post("/api/grants/sessions", json={"name": "AppTest"}, headers=ACCOUNT_HEADERS)
    session_id = create_resp.json()["session_id"]

    app_resp = client.post(
        f"/api/grants/sessions/{session_id}/applications",
        json={"grant_id": "sbir_phase1"},
        headers=ACCOUNT_HEADERS,
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["application_id"]

    list_resp = client.get(f"/api/grants/sessions/{session_id}/applications", headers=ACCOUNT_HEADERS)
    assert list_resp.status_code == 200
    apps = list_resp.json()["applications"]
    assert any(a["application_id"] == app_id for a in apps)


def test_create_application_invalid_grant(client):
    create_resp = client.post("/api/grants/sessions", json={"name": "Test"}, headers=ACCOUNT_HEADERS)
    session_id = create_resp.json()["session_id"]
    resp = client.post(
        f"/api/grants/sessions/{session_id}/applications",
        json={"grant_id": "nonexistent_grant_xyz"},
        headers=ACCOUNT_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Prerequisites endpoints
# ---------------------------------------------------------------------------

def test_get_prerequisites(client):
    resp = client.get("/api/grants/prerequisites")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["prerequisites"]) >= 6
    prereq_ids = {p["prereq_id"] for p in data["prerequisites"]}
    assert "sam_registration" in prereq_ids
    assert "uei_number" in prereq_ids


def test_update_prerequisite_status(client):
    resp = client.put(
        "/api/grants/prerequisites/ein",
        json={"status": "completed", "notes": "EIN obtained: 12-3456789"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# Murphy profile endpoints
# ---------------------------------------------------------------------------

def test_list_profiles(client):
    resp = client.get("/api/grants/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    flavors = {p["flavor"] for p in data["profiles"]}
    assert {"rd", "energy", "manufacturing", "general"} == flavors


def test_get_profile_rd(client):
    resp = client.get("/api/grants/profiles/rd")
    assert resp.status_code == 200
    data = resp.json()
    assert data["flavor"] == "rd"
    assert len(data["target_grants"]) > 0


def test_get_profile_invalid_flavor(client):
    resp = client.get("/api/grants/profiles/nonexistent")
    assert resp.status_code == 400


def test_invalid_account_id_rejected(client, monkeypatch):
    monkeypatch.setenv("MURPHY_ENV", "production")
    resp = client.get("/api/grants/sessions")  # No X-Account-Id header
    assert resp.status_code == 401
