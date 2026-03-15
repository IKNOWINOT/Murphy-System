"""
Tests for Founder Swarm Infrastructure API endpoints.

Verifies that the /api/swarm/founder/* endpoints are founder-gated
and correctly expose the SelfCodebaseSwarm infrastructure capabilities.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from fastapi.testclient import TestClient
    _HAS_TESTCLIENT = True
except ImportError:
    _HAS_TESTCLIENT = False

pytestmark = pytest.mark.skipif(
    not _HAS_TESTCLIENT,
    reason="fastapi/httpx not installed",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Create a TestClient wrapping the full Murphy app."""
    os.environ.setdefault("MURPHY_TEST_MODE", "1")
    from src.runtime.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


FOUNDER_HEADERS = {"X-User-Role": "founder"}
OWNER_HEADERS = {"X-User-Role": "owner"}
VIEWER_HEADERS = {"X-User-Role": "viewer"}


# ---------------------------------------------------------------------------
# Auth gating — non-founder should get 403
# ---------------------------------------------------------------------------

class TestFounderGating:
    def test_session_requires_founder(self, client):
        resp = client.post(
            "/api/swarm/founder/session",
            json={"focus_area": "general"},
            headers=VIEWER_HEADERS,
        )
        assert resp.status_code == 403

    def test_founder_admin_role_accepted(self, client):
        """founder_admin is a valid role in signup_gateway / inoni_org_bootstrap."""
        resp = client.get(
            "/api/swarm/founder/agents",
            headers={"X-User-Role": "founder_admin"},
        )
        assert resp.status_code == 200

    def test_agents_requires_founder(self, client):
        resp = client.get("/api/swarm/founder/agents", headers=VIEWER_HEADERS)
        assert resp.status_code == 403

    def test_proposals_requires_founder(self, client):
        resp = client.get("/api/swarm/founder/proposals", headers=VIEWER_HEADERS)
        assert resp.status_code == 403

    def test_audit_requires_founder(self, client):
        resp = client.get("/api/swarm/founder/audit", headers=VIEWER_HEADERS)
        assert resp.status_code == 403

    def test_recommendations_requires_founder(self, client):
        resp = client.get("/api/swarm/founder/recommendations", headers=VIEWER_HEADERS)
        assert resp.status_code == 403

    def test_propose_requires_founder(self, client):
        resp = client.post(
            "/api/swarm/founder/propose",
            json={"description": "test"},
            headers=VIEWER_HEADERS,
        )
        assert resp.status_code == 403

    def test_no_role_header_blocked(self, client):
        resp = client.get("/api/swarm/founder/agents")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Session endpoints (founder access)
# ---------------------------------------------------------------------------

class TestSwarmSession:
    def test_start_session(self, client):
        resp = client.post(
            "/api/swarm/founder/session",
            json={"focus_area": "general"},
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "session_id" in data
        assert data["founder_gated"] is True

    def test_start_session_owner_role(self, client):
        resp = client.post(
            "/api/swarm/founder/session",
            json={"focus_area": "security"},
            headers=OWNER_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_start_session_with_objectives(self, client):
        resp = client.post(
            "/api/swarm/founder/session",
            json={
                "focus_area": "architecture",
                "objectives": ["Reduce coupling", "Improve test coverage"],
            },
            headers=FOUNDER_HEADERS,
        )
        data = resp.json()
        assert data["ok"] is True
        assert len(data["action_plan"]) == 2

    def test_invalid_focus_area(self, client):
        resp = client.post(
            "/api/swarm/founder/session",
            json={"focus_area": "invalid_area"},
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 400

    def test_get_session_status(self, client):
        # Create session first
        create_resp = client.post(
            "/api/swarm/founder/session",
            json={"focus_area": "general"},
            headers=FOUNDER_HEADERS,
        )
        sid = create_resp.json()["session_id"]
        # Get session status
        resp = client.get(
            f"/api/swarm/founder/session/{sid}",
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["session"]["session_id"] == sid

    def test_get_session_not_found(self, client):
        resp = client.get(
            "/api/swarm/founder/session/nonexistentid12",
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Propose & Execute
# ---------------------------------------------------------------------------

class TestSwarmProposeExecute:
    def test_propose_change(self, client):
        resp = client.post(
            "/api/swarm/founder/propose",
            json={"description": "Add structured logging to auth module"},
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "proposal" in data
        assert data["proposal"]["description"]

    def test_propose_empty_description(self, client):
        resp = client.post(
            "/api/swarm/founder/propose",
            json={"description": ""},
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 400

    def test_execute_proposal(self, client):
        # Create proposal first
        create_resp = client.post(
            "/api/swarm/founder/propose",
            json={"description": "Safe infrastructure change"},
            headers=FOUNDER_HEADERS,
        )
        pid = create_resp.json()["proposal"]["proposal_id"]
        # Execute it
        resp = client.post(
            f"/api/swarm/founder/execute/{pid}",
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "result" in data


# ---------------------------------------------------------------------------
# Query endpoints
# ---------------------------------------------------------------------------

class TestSwarmQueryEndpoints:
    def test_list_agents(self, client):
        resp = client.get("/api/swarm/founder/agents", headers=FOUNDER_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["count"] >= 5
        roles = {a["role"] for a in data["agents"]}
        assert "architect" in roles

    def test_recommendations(self, client):
        resp = client.get(
            "/api/swarm/founder/recommendations",
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["recommendations"], list)

    def test_list_proposals(self, client):
        resp = client.get(
            "/api/swarm/founder/proposals",
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["proposals"], list)

    def test_audit_log(self, client):
        resp = client.get(
            "/api/swarm/founder/audit",
            headers=FOUNDER_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["audit_log"], list)


# ---------------------------------------------------------------------------
# Librarian catalog includes swarm commands
# ---------------------------------------------------------------------------

class TestLibrarianSwarmCommands:
    def test_catalog_includes_swarm_category(self, client):
        resp = client.get("/api/librarian/commands")
        assert resp.status_code == 200
        data = resp.json()
        assert "swarm" in data["categories"]

    def test_swarm_commands_present(self, client):
        resp = client.get("/api/librarian/commands")
        data = resp.json()
        swarm_cmds = [
            c for c in data["catalog"] if c["category"] == "swarm"
        ]
        assert len(swarm_cmds) >= 8
        command_names = {c["command"] for c in swarm_cmds}
        assert "swarm session start" in command_names
        assert "swarm propose" in command_names
        assert "swarm agents" in command_names
