"""Tests for the grants API endpoints using FastAPI TestClient."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.billing.grants.api import create_grants_router
from src.billing.grants import sessions, task_queue, prerequisites


@pytest.fixture(autouse=True)
def clear_stores():
    """Clear in-memory stores before each test."""
    sessions._SESSIONS.clear()
    task_queue._TASKS.clear()
    prerequisites._SESSION_PREREQ_STATUS.clear()
    yield


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(create_grants_router())
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/api/grants/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["catalog_size"] > 0


class TestCatalogEndpoints:
    def test_list_catalog(self, client):
        resp = client.get("/api/grants/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        assert len(data["grants"]) == data["count"]

    def test_filter_by_program_type(self, client):
        resp = client.get("/api/grants/catalog?program_type=federal_grant")
        assert resp.status_code == 200
        data = resp.json()
        for g in data["grants"]:
            assert g["program_type"] == "federal_grant"

    def test_filter_by_state(self, client):
        resp = client.get("/api/grants/catalog?state=OR")
        assert resp.status_code == 200
        data = resp.json()
        for g in data["grants"]:
            assert "OR" in g["eligible_states"] or g["eligible_states"] == []

    def test_get_grant_by_id(self, client):
        resp = client.get("/api/grants/catalog/sbir_phase1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["grant"]["id"] == "sbir_phase1"

    def test_get_unknown_grant(self, client):
        resp = client.get("/api/grants/catalog/totally_unknown_grant")
        assert resp.status_code == 404


class TestSessionEndpoints:
    def test_create_session(self, client):
        resp = client.post("/api/grants/sessions", json={
            "tenant_id": "tenant-api-test",
            "track": "track_b_customer",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["session"]["tenant_id"] == "tenant-api-test"
        assert data["session"]["session_id"]

    def test_create_session_track_a(self, client):
        resp = client.post("/api/grants/sessions", json={
            "tenant_id": "murphy",
            "track": "track_a_murphy",
        })
        assert resp.status_code == 201
        assert resp.json()["session"]["track"] == "track_a_murphy"

    def test_create_session_invalid_track(self, client):
        resp = client.post("/api/grants/sessions", json={
            "tenant_id": "t1",
            "track": "invalid_track",
        })
        assert resp.status_code == 400

    def test_create_session_invalid_tenant_id(self, client):
        resp = client.post("/api/grants/sessions", json={
            "tenant_id": "<script>alert(1)</script>",
            "track": "track_b_customer",
        })
        assert resp.status_code == 400

    def test_get_session(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "tenant-x",
            "track": "track_b_customer",
        })
        session_id = create_resp.json()["session"]["session_id"]
        resp = client.get(f"/api/grants/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["session"]["session_id"] == session_id

    def test_get_session_with_tenant_isolation(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "tenant-a",
            "track": "track_b_customer",
        })
        session_id = create_resp.json()["session"]["session_id"]

        # Wrong tenant cannot access
        resp = client.get(f"/api/grants/sessions/{session_id}?tenant_id=tenant-b")
        assert resp.status_code == 404

    def test_get_unknown_session(self, client):
        resp = client.get("/api/grants/sessions/nonexistent-session-id")
        assert resp.status_code == 404

    def test_delete_session(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "tenant-del",
            "track": "track_b_customer",
        })
        session_id = create_resp.json()["session"]["session_id"]
        del_resp = client.delete(f"/api/grants/sessions/{session_id}")
        assert del_resp.status_code == 200

        # Session gone
        get_resp = client.get(f"/api/grants/sessions/{session_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_session(self, client):
        resp = client.delete("/api/grants/sessions/nonexistent-del")
        assert resp.status_code == 404


class TestMatchEndpoints:
    def test_run_match(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "t1", "track": "track_b_customer"
        })
        session_id = create_resp.json()["session"]["session_id"]

        resp = client.post(f"/api/grants/sessions/{session_id}/match", json={
            "profile_data": {
                "entity_type": "small_business",
                "state": "OR",
                "verticals": ["energy_management"],
                "is_rural": False,
                "has_ein": True,
                "has_sam_gov": False,
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["total_evaluated"] > 0

    def test_get_results(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "t2", "track": "track_b_customer"
        })
        session_id = create_resp.json()["session"]["session_id"]

        client.post(f"/api/grants/sessions/{session_id}/match", json={
            "profile_data": {"entity_type": "small_business", "state": "CA"}
        })

        resp = client.get(f"/api/grants/sessions/{session_id}/results")
        assert resp.status_code == 200
        assert "results" in resp.json()


class TestTaskEndpoints:
    def _make_session(self, client):
        resp = client.post("/api/grants/sessions", json={
            "tenant_id": "task-tenant", "track": "track_b_customer"
        })
        return resp.json()["session"]["session_id"]

    def test_list_tasks_empty(self, client):
        sid = self._make_session(client)
        resp = client.get(f"/api/grants/sessions/{sid}/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_get_next_tasks_empty(self, client):
        sid = self._make_session(client)
        resp = client.get(f"/api/grants/sessions/{sid}/tasks/next")
        assert resp.status_code == 200
        assert resp.json()["next_tasks"] == []

    def test_complete_nonexistent_task(self, client):
        sid = self._make_session(client)
        resp = client.post(
            f"/api/grants/sessions/{sid}/tasks/nonexistent-task-id/complete",
            json={"result_data": {}}
        )
        assert resp.status_code == 404


class TestPrerequisiteEndpoints:
    def test_list_prerequisites(self, client):
        resp = client.get("/api/grants/prerequisites")
        assert resp.status_code == 200
        data = resp.json()
        assert "prerequisites" in data
        assert len(data["prerequisites"]) > 0

    def test_list_prerequisites_with_session(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "prereq-tenant", "track": "track_b_customer"
        })
        sid = create_resp.json()["session"]["session_id"]
        resp = client.get(f"/api/grants/prerequisites?session_id={sid}")
        assert resp.status_code == 200
        assert "summary" in resp.json()

    def test_update_prereq_status(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "prereq-tenant2", "track": "track_b_customer"
        })
        sid = create_resp.json()["session"]["session_id"]

        resp = client.post(
            f"/api/grants/prerequisites/ein/status?session_id={sid}",
            json={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["prereq_id"] == "ein"
        assert data["status"] == "completed"

    def test_update_invalid_prereq_id(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "prereq-tenant3", "track": "track_b_customer"
        })
        sid = create_resp.json()["session"]["session_id"]
        resp = client.post(
            f"/api/grants/prerequisites/nonexistent_prereq/status?session_id={sid}",
            json={"status": "completed"}
        )
        assert resp.status_code == 404

    def test_update_invalid_status(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "prereq-tenant4", "track": "track_b_customer"
        })
        sid = create_resp.json()["session"]["session_id"]
        resp = client.post(
            f"/api/grants/prerequisites/ein/status?session_id={sid}",
            json={"status": "invalid_status"}
        )
        assert resp.status_code == 400


class TestMurphyProfilesEndpoint:
    def test_get_murphy_profiles(self, client):
        resp = client.get("/api/grants/profiles/murphy")
        assert resp.status_code == 200
        data = resp.json()
        assert "profiles" in data
        assert "murphy_sbir_profile" in data["profiles"]
        assert "murphy_doe_profile" in data["profiles"]
        assert "murphy_nsf_profile" in data["profiles"]
        assert "murphy_manufacturing_profile" in data["profiles"]
