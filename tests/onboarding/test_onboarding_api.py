# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for onboarding API endpoints using FastAPI TestClient."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI not installed")


@pytest.fixture()
def client():
    """Fresh client+session for each test."""
    from fastapi import FastAPI
    import src.platform_onboarding.onboarding_api as api_module
    api_module._sessions.clear()
    app = FastAPI()
    router = api_module.create_onboarding_router()
    app.include_router(router)
    with TestClient(app) as c:
        # Pre-create a session so state-dependent tests work
        c.post("/api/onboarding/start", json={"account_id": "test"})
        yield c
    api_module._sessions.clear()


def test_start_returns_200(client):
    resp = client.post("/api/onboarding/start", json={"account_id": "test-1"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "started"


def test_start_returns_task_count(client):
    from src.platform_onboarding.task_catalog import TASK_CATALOG
    resp = client.post("/api/onboarding/start", json={"account_id": "test-2"})
    data = resp.json()
    assert data["total_tasks"] == len(TASK_CATALOG)


def test_status_returns_progress(client):
    resp = client.get("/api/onboarding/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "progress" in data
    assert "completion_percentage" in data["progress"]


def test_status_initial_zero_percent(client):
    resp = client.get("/api/onboarding/status")
    data = resp.json()
    assert data["progress"]["completion_percentage"] == 0.0


def test_next_tasks_returns_list(client):
    resp = client.get("/api/onboarding/next")
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks" in data
    assert len(data["tasks"]) > 0


def test_next_tasks_have_required_fields(client):
    resp = client.get("/api/onboarding/next")
    data = resp.json()
    for task in data["tasks"]:
        assert "task_id" in task
        assert "title" in task
        assert "score" in task


def test_get_all_tasks_returns_full_catalog(client):
    from src.platform_onboarding.task_catalog import TASK_CATALOG
    resp = client.get("/api/onboarding/tasks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == len(TASK_CATALOG)
    assert len(data["tasks"]) == len(TASK_CATALOG)


def test_get_task_detail(client):
    resp = client.get("/api/onboarding/tasks/1.02")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "1.02"
    assert data["title"] == "Get EIN from IRS"


def test_get_task_detail_not_found(client):
    resp = client.get("/api/onboarding/tasks/99.99")
    assert resp.status_code == 404


def test_start_task(client):
    resp = client.post("/api/onboarding/tasks/1.02/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "1.02"
    assert data["status"] == "in_progress"


def test_complete_task(client):
    resp = client.post("/api/onboarding/tasks/1.02/complete", json={"data": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "1.02"
    assert data["status"] == "completed"


def test_complete_task_returns_newly_unblocked(client):
    resp = client.post("/api/onboarding/tasks/1.02/complete", json={"data": {}})
    data = resp.json()
    assert "newly_unblocked" in data
    assert "1.01" in data["newly_unblocked"]


def test_skip_task(client):
    resp = client.post("/api/onboarding/tasks/5.01/skip")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "skipped"


def test_wait_task(client):
    resp = client.post("/api/onboarding/tasks/1.01/wait")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "waiting_on_external"
    assert "expected_completion" in data


def test_parallel_groups_endpoint(client):
    resp = client.get("/api/onboarding/parallel-groups")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert "0" in data["groups"]


def test_critical_path_endpoint(client):
    resp = client.get("/api/onboarding/critical-path")
    assert resp.status_code == 200
    data = resp.json()
    assert "critical_path" in data
    assert "1.02" in data["critical_path"]
    assert "1.01" in data["critical_path"]


def test_value_report_endpoint(client):
    resp = client.get("/api/onboarding/value-report")
    assert resp.status_code == 200
    data = resp.json()
    assert "pending" in data
    assert "captured" in data
    assert data["total_tasks_with_value"] > 0


def test_timeline_endpoint(client):
    resp = client.get("/api/onboarding/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_remaining_minutes" in data
    assert data["total_remaining_minutes"] > 0


def test_checkpoint_endpoint(client):
    resp = client.get("/api/onboarding/checkpoint")
    assert resp.status_code == 200
    data = resp.json()
    assert "checkpoint" in data


def test_resume_endpoint(client):
    start_resp = client.post("/api/onboarding/start", json={"account_id": "resume-test"})
    session_id = start_resp.json()["session_id"]
    resp = client.post("/api/onboarding/resume", json={"session_id": session_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["resumed"] is True
