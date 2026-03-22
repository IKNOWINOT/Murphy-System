# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.billing.grants.api import router
import src.billing.grants.submission.submission_manager as sm_module
import src.billing.grants.submission.submission_tracker as st_module


@pytest.fixture(autouse=True)
def clear_state():
    sm_module._packages.clear()
    sm_module._package_index.clear()
    st_module._statuses.clear()
    yield
    sm_module._packages.clear()
    sm_module._package_index.clear()
    st_module._statuses.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_generate_returns_200(client):
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                       json={"portal": "grants_gov"})
    assert resp.status_code == 200


def test_generate_returns_package_id(client):
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                       json={"portal": "grants_gov"})
    data = resp.json()
    assert "package_id" in data


def test_generate_returns_instructions(client):
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                       json={"portal": "grants_gov"})
    data = resp.json()
    assert "instructions" in data
    assert len(data["instructions"]) > 0


def test_get_submission_returns_package(client):
    client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                json={"portal": "grants_gov"})
    resp = client.get("/api/grants/sessions/s1/applications/a1/submission")
    assert resp.status_code == 200
    assert "package_id" in resp.json()


def test_get_submission_404_if_not_generated(client):
    resp = client.get("/api/grants/sessions/s_none/applications/a_none/submission")
    assert resp.status_code == 404


def test_get_files_returns_list(client):
    client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                json={"portal": "grants_gov"})
    resp = client.get("/api/grants/sessions/s1/applications/a1/submission/files")
    assert resp.status_code == 200
    assert "files" in resp.json()


def test_get_files_has_correct_count_for_grants_gov(client):
    client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                json={"portal": "grants_gov"})
    resp = client.get("/api/grants/sessions/s1/applications/a1/submission/files")
    assert len(resp.json()["files"]) == 3


def test_mark_submitted_returns_200(client):
    client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                json={"portal": "grants_gov"})
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/mark-submitted",
                       json={"confirmation_number": "GG-2024-001"})
    assert resp.status_code == 200


def test_mark_submitted_stores_confirmation(client):
    client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                json={"portal": "grants_gov"})
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/mark-submitted",
                       json={"confirmation_number": "GG-2024-CONF"})
    assert resp.json()["confirmation_number"] == "GG-2024-CONF"


def test_put_status_updates(client):
    client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                json={"portal": "grants_gov"})
    resp = client.put("/api/grants/sessions/s1/applications/a1/submission/status",
                      json={"status": "confirmed"})
    assert resp.status_code == 200


def test_get_status_returns_status(client):
    client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                json={"portal": "grants_gov"})
    resp = client.get("/api/grants/sessions/s1/applications/a1/submission/status")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_get_deadlines_returns_list(client):
    resp = client.get("/api/grants/deadlines")
    assert resp.status_code == 200
    assert "deadlines" in resp.json()


def test_get_deadline_alerts_returns_list(client):
    resp = client.get("/api/grants/deadlines/alerts")
    assert resp.status_code == 200
    assert "alerts" in resp.json()


def test_dismiss_nonexistent_alert_returns_404(client):
    resp = client.put("/api/grants/deadlines/alerts/nonexistent-id/dismiss")
    assert resp.status_code == 404


def test_auto_submit_returns_not_yet_available(client):
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/auto-submit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_yet_available"


def test_auto_submit_has_manual_url(client):
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/auto-submit")
    data = resp.json()
    assert "manual_instructions_url" in data
    assert "s1" in data["manual_instructions_url"]


def test_download_file_returns_content(client):
    gen_resp = client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                           json={"portal": "grants_gov"})
    pkg_data = gen_resp.json()
    fid = pkg_data["files"][0]["file_id"]
    resp = client.get(f"/api/grants/sessions/s1/applications/a1/submission/files/{fid}/download")
    assert resp.status_code == 200
    assert "content" in resp.json()


def test_generate_with_application_data(client):
    resp = client.post("/api/grants/sessions/s1/applications/a1/submission/generate",
                       json={"portal": "grants_gov", "application_data": {"opportunity_number": "FOA-TEST"}})
    assert resp.status_code == 200
