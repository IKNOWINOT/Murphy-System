"""End-to-end integration test: full grant application workflow."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.billing.grants.api import create_grants_router
from src.billing.grants import sessions, task_queue, prerequisites
from src.billing.grants.models import GrantTrack, TaskType


@pytest.fixture(autouse=True)
def clear_stores():
    sessions._SESSIONS.clear()
    task_queue._TASKS.clear()
    prerequisites._SESSION_PREREQ_STATUS.clear()
    yield


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(create_grants_router())
    return TestClient(app)


class TestEndToEndWorkflow:
    """End-to-end test: Create session → run match → create tasks → complete tasks → verify progress."""

    def test_full_track_b_workflow(self, client):
        # 1. Create session
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "e2e-tenant",
            "track": "track_b_customer",
        })
        assert create_resp.status_code == 201
        session_id = create_resp.json()["session"]["session_id"]

        # 2. Run eligibility match
        match_resp = client.post(
            f"/api/grants/sessions/{session_id}/match",
            json={
                "profile_data": {
                    "entity_type": "small_business",
                    "state": "OR",
                    "verticals": ["building_automation", "energy_management"],
                    "project_cost": 500_000.0,
                    "is_rural": False,
                    "has_ein": True,
                    "has_sam_gov": False,
                }
            }
        )
        assert match_resp.status_code == 200
        match_data = match_resp.json()
        assert match_data["total_evaluated"] > 0
        assert match_data["eligible_count"] > 0

        # 3. Retrieve stored results
        results_resp = client.get(f"/api/grants/sessions/{session_id}/results")
        assert results_resp.status_code == 200
        assert len(results_resp.json()["results"]) > 0

        # 4. Verify session still accessible
        get_resp = client.get(f"/api/grants/sessions/{session_id}")
        assert get_resp.status_code == 200

    def test_full_track_a_murphy_workflow(self, client):
        # 1. Create Track A session
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "murphy-system",
            "track": "track_a_murphy",
        })
        assert create_resp.status_code == 201
        session_id = create_resp.json()["session"]["session_id"]

        # 2. Get Murphy profiles
        profiles_resp = client.get("/api/grants/profiles/murphy")
        assert profiles_resp.status_code == 200
        sbir_profile = profiles_resp.json()["profiles"]["murphy_sbir_profile"]

        # 3. Match with SBIR profile
        match_resp = client.post(
            f"/api/grants/sessions/{session_id}/match",
            json={"profile_data": sbir_profile}
        )
        assert match_resp.status_code == 200
        eligible_count = match_resp.json()["eligible_count"]
        assert eligible_count > 0

    def test_task_lifecycle(self, client):
        # Create session
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "task-e2e",
            "track": "track_b_customer",
        })
        session_id = create_resp.json()["session"]["session_id"]

        # Create tasks directly via task_queue module
        t1 = task_queue.create_task(
            session_id, TaskType.needs_review, "Get EIN", "Register with IRS",
            priority=10
        )
        t2 = task_queue.create_task(
            session_id, TaskType.needs_review, "Register SAM.gov", "Create SAM.gov account",
            priority=20, depends_on=[t1.task_id]
        )
        t3 = task_queue.create_task(
            session_id, TaskType.waiting_on_external, "Wait SAM.gov", "SAM.gov takes 10 days",
            priority=30, depends_on=[t2.task_id]
        )

        # Check initial state
        tasks_resp = client.get(f"/api/grants/sessions/{session_id}/tasks")
        assert tasks_resp.status_code == 200
        assert tasks_resp.json()["progress"]["total"] == 3
        assert tasks_resp.json()["progress"]["completed"] == 0

        # Get next tasks — only t1 (unblocked)
        next_resp = client.get(f"/api/grants/sessions/{session_id}/tasks/next")
        assert next_resp.status_code == 200
        next_task_ids = [t["task_id"] for t in next_resp.json()["next_tasks"]]
        assert t1.task_id in next_task_ids
        assert t2.task_id not in next_task_ids

        # Complete t1
        complete_resp = client.post(
            f"/api/grants/sessions/{session_id}/tasks/{t1.task_id}/complete",
            json={"result_data": {"ein": "12-3456789"}}
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["progress"]["completed"] == 1

        # Now t2 should be in next tasks
        next_resp2 = client.get(f"/api/grants/sessions/{session_id}/tasks/next")
        next_task_ids2 = [t["task_id"] for t in next_resp2.json()["next_tasks"]]
        assert t2.task_id in next_task_ids2

        # Complete t2
        client.post(
            f"/api/grants/sessions/{session_id}/tasks/{t2.task_id}/complete",
            json={"result_data": {}}
        )

        # Complete t3
        done_resp = client.post(
            f"/api/grants/sessions/{session_id}/tasks/{t3.task_id}/complete",
            json={"result_data": {}}
        )
        assert done_resp.json()["progress"]["completion_pct"] == 100.0

    def test_prerequisite_progression(self, client):
        create_resp = client.post("/api/grants/sessions", json={
            "tenant_id": "prereq-e2e",
            "track": "track_a_murphy",
        })
        session_id = create_resp.json()["session"]["session_id"]

        # Get initial prereq state
        prereq_resp = client.get(f"/api/grants/prerequisites?session_id={session_id}")
        assert prereq_resp.status_code == 200
        initial_summary = prereq_resp.json()["summary"]
        assert initial_summary["completed"] == 0

        # Complete EIN
        client.post(
            f"/api/grants/prerequisites/ein/status?session_id={session_id}",
            json={"status": "completed"}
        )

        # Complete SAM.gov
        client.post(
            f"/api/grants/prerequisites/sam_gov/status?session_id={session_id}",
            json={"status": "completed"}
        )

        # Check progress increased
        prereq_resp2 = client.get(f"/api/grants/prerequisites?session_id={session_id}")
        summary2 = prereq_resp2.json()["summary"]
        assert summary2["completed"] == 2
        assert summary2["completion_pct"] > 0.0
        assert len(summary2["ready_to_apply"]) > 0

    def test_tenant_isolation_end_to_end(self, client):
        # Tenant A creates a session
        resp_a = client.post("/api/grants/sessions", json={
            "tenant_id": "tenant-isolation-a",
            "track": "track_b_customer",
        })
        sid_a = resp_a.json()["session"]["session_id"]

        # Tenant B creates a session
        resp_b = client.post("/api/grants/sessions", json={
            "tenant_id": "tenant-isolation-b",
            "track": "track_b_customer",
        })
        sid_b = resp_b.json()["session"]["session_id"]

        # Tenant B cannot access Tenant A's session
        resp = client.get(f"/api/grants/sessions/{sid_a}?tenant_id=tenant-isolation-b")
        assert resp.status_code == 404

        # Tenant A cannot access Tenant B's session
        resp = client.get(f"/api/grants/sessions/{sid_b}?tenant_id=tenant-isolation-a")
        assert resp.status_code == 404

        # Each can access their own
        assert client.get(f"/api/grants/sessions/{sid_a}?tenant_id=tenant-isolation-a").status_code == 200
        assert client.get(f"/api/grants/sessions/{sid_b}?tenant_id=tenant-isolation-b").status_code == 200
