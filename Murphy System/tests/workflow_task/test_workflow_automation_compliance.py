"""
Tests for workflow execution, HITL queue, compliance enforcement,
tier-gated automations, and security validation.

Covers:
  - Workflow CRUD (create, list, get, execute)
  - AI workflow generation from natural language
  - HITL queue (real data, not mock)
  - HITL respond with input validation
  - Tier-based automation enforcement (free vs paid)
  - Tier-based compliance framework enforcement
  - Compliance conflict detection and documentation
  - Integration collection persistence
  - Librarian ask/execute modes
  - Security: input validation on HITL endpoint

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# App client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Create a FastAPI test client with higher rate limits for testing."""
    os.environ["MURPHY_ENV"] = "development"
    os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"  # High limit for tests
    os.environ["MURPHY_RATE_LIMIT_BURST"] = "200"
    from starlette.testclient import TestClient
    from src.runtime.app import create_app
    app = create_app()
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def auth_client(client):
    """Create an authenticated test client by signing up a fresh user."""
    resp = client.post("/api/auth/signup", json={
        "email": f"wftest_{os.urandom(4).hex()}@example.com",
        "password": "SecurePass123!",
        "full_name": "Workflow Tester",
        "job_title": "QA",
        "company": "TestCo",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    return client, data


@pytest.fixture
def solo_client(client):
    """Create an authenticated client with SOLO tier."""
    email = f"solo_{os.urandom(4).hex()}@example.com"
    resp = client.post("/api/auth/signup", json={
        "email": email,
        "password": "SecurePass123!",
        "full_name": "Solo User",
    })
    assert resp.status_code == 201
    data = resp.json()
    # Upgrade to SOLO tier via internal subscription manager
    try:
        from src.subscription_manager import (
            SubscriptionManager, SubscriptionTier,
            SubscriptionRecord, SubscriptionStatus,
        )
        mgr = SubscriptionManager()
        mgr._subscriptions[data["account_id"]] = SubscriptionRecord(
            account_id=data["account_id"],
            tier=SubscriptionTier.SOLO,
            status=SubscriptionStatus.ACTIVE,
        )
    except Exception:
        pass
    return client, data


# ===========================================================================
# Part 1: Workflow CRUD
# ===========================================================================

class TestWorkflowCRUD:
    def test_list_workflows_initially_empty(self, client):
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["workflows"], list)

    def test_create_workflow(self, auth_client):
        client, _ = auth_client
        resp = client.post("/api/workflows", json={
            "name": "Test Invoice Workflow",
            "nodes": [
                {"id": "n1", "label": "Client Intake", "type": "task", "data": {"action": "intake"}},
                {"id": "n2", "label": "Generate Invoice", "type": "task", "data": {"action": "invoice"}},
            ],
            "connections": [{"from": "n1", "to": "n2"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["workflow"]["name"] == "Test Invoice Workflow"
        assert len(data["workflow"]["nodes"]) == 2
        return data["workflow"]["id"]

    def test_get_workflow_by_id(self, auth_client):
        client, _ = auth_client
        # Create first
        resp = client.post("/api/workflows", json={
            "name": "Get Test Workflow",
            "nodes": [{"id": "n1", "label": "Step 1"}],
        })
        wf_id = resp.json()["workflow"]["id"]
        # Then get
        resp2 = client.get(f"/api/workflows/{wf_id}")
        assert resp2.status_code == 200
        assert resp2.json()["workflow"]["name"] == "Get Test Workflow"

    def test_get_workflow_not_found(self, client):
        resp = client.get("/api/workflows/nonexistent-id")
        assert resp.status_code == 404

    def test_list_workflows_after_create(self, auth_client):
        client, _ = auth_client
        client.post("/api/workflows", json={
            "name": "Listed Workflow",
            "nodes": [],
        })
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert any(w["name"] == "Listed Workflow" for w in data["workflows"])


# ===========================================================================
# Part 2: Workflow Execution
# ===========================================================================

class TestWorkflowExecution:
    def test_execute_nonexistent_workflow(self, auth_client):
        client, _ = auth_client
        resp = client.post("/api/workflows/nonexistent-id/execute")
        assert resp.status_code == 404

    def test_execute_workflow_free_tier_blocked(self, auth_client):
        client, _ = auth_client
        # Create workflow
        resp = client.post("/api/workflows", json={
            "name": "Exec Test Free",
            "nodes": [{"id": "n1", "label": "Step 1", "data": {}}],
        })
        wf_id = resp.json()["workflow"]["id"]
        # Execute - should be blocked for free tier
        resp2 = client.post(f"/api/workflows/{wf_id}/execute")
        assert resp2.status_code == 403
        data = resp2.json()
        assert "subscription" in data.get("error", "").lower() or "upgrade" in data.get("error", "").lower()
        assert data.get("upgrade_url") == "/ui/pricing"

    def test_execute_workflow_returns_result(self, client):
        """Execute a workflow using a fresh client (no session = no tier check)."""
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
        fresh = TestClient(create_app(), follow_redirects=False)
        # Create workflow without auth
        resp = fresh.post("/api/workflows", json={
            "name": "Exec Test Unauth",
            "nodes": [{"id": "n1", "label": "Process", "data": {"description": "test"}}],
        })
        wf_id = resp.json()["workflow"]["id"]
        resp2 = fresh.post(f"/api/workflows/{wf_id}/execute")
        # Without auth, tier check is skipped, execution proceeds
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["success"] is True
        assert data["status"] == "completed"


# ===========================================================================
# Part 3: AI Workflow Generation
# ===========================================================================

class TestWorkflowGeneration:
    def test_generate_workflow_from_description(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "Process client invoices and send email reminders for overdue payments",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "workflow" in data
        wf = data["workflow"]
        assert wf["name"]
        assert len(wf["nodes"]) > 0
        assert wf["status"] == "generated"
        assert "generation_meta" in data

    def test_generate_workflow_saves_to_store(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "Hire new engineer: post job, screen resumes, schedule interviews",
        })
        assert resp.status_code == 200
        wf_id = resp.json()["workflow"]["id"]
        # Verify it's in the workflow store
        resp2 = client.get(f"/api/workflows/{wf_id}")
        assert resp2.status_code == 200
        assert resp2.json()["workflow"]["status"] == "generated"

    def test_generate_workflow_requires_description(self, client):
        resp = client.post("/api/workflows/generate", json={})
        assert resp.status_code == 400
        assert "description" in resp.json().get("error", "").lower()

    def test_generate_workflow_empty_description(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "   ",
        })
        assert resp.status_code == 400


# ===========================================================================
# Part 4: HITL Queue (Real Data)
# ===========================================================================

class TestHITLQueue:
    def test_hitl_queue_returns_success(self, client):
        resp = client.get("/api/hitl/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "queue" in data
        assert "pending_count" in data
        assert isinstance(data["queue"], list)

    def test_hitl_pending_returns_success(self, client):
        resp = client.get("/api/hitl/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "data" in data
        assert "count" in data

    def test_hitl_interventions_pending(self, client):
        resp = client.get("/api/hitl/interventions/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "interventions" in data
        assert isinstance(data["interventions"], list)

    def test_hitl_statistics(self, client):
        resp = client.get("/api/hitl/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "statistics" in data


# ===========================================================================
# Part 5: HITL Respond with Input Validation
# ===========================================================================

class TestHITLRespond:
    def test_hitl_respond_invalid_status(self, client):
        resp = client.post("/api/hitl/interventions/test-123/respond", json={
            "status": "INVALID_STATUS",
            "response": "test",
        })
        assert resp.status_code == 400
        assert "status must be one of" in resp.json().get("error", "")

    def test_hitl_respond_valid_statuses(self, client):
        for status in ["approved", "rejected", "resolved", "deferred", "escalated"]:
            resp = client.post("/api/hitl/interventions/test-123/respond", json={
                "status": status,
                "response": f"Testing {status}",
            })
            # Will return 404 if intervention doesn't exist, but NOT 400
            assert resp.status_code in (200, 404)

    def test_hitl_respond_response_too_long(self, client):
        resp = client.post("/api/hitl/interventions/test-123/respond", json={
            "status": "approved",
            "response": "x" * 2001,
        })
        assert resp.status_code == 400
        assert "2000" in resp.json().get("error", "")

    def test_hitl_respond_nonexistent_intervention(self, client):
        resp = client.post("/api/hitl/interventions/nonexistent-id/respond", json={
            "status": "approved",
            "response": "test",
        })
        assert resp.status_code == 404


# ===========================================================================
# Part 6: Tier-Based Automation Enforcement
# ===========================================================================

class TestTierAutomationEnforcement:
    def test_free_tier_blocked_from_automation(self, auth_client):
        client, _ = auth_client
        resp = client.post("/api/automation/sales/generate_leads", json={
            "parameters": {},
        })
        assert resp.status_code == 403
        data = resp.json()
        assert "subscription" in data.get("error", "").lower()
        assert data.get("tier") == "free"

    def test_free_tier_can_view_workflows(self, auth_client):
        """Free tier can create and view workflows (just not execute)."""
        client, _ = auth_client
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_free_tier_can_generate_workflows(self, auth_client):
        """Free tier can generate workflows using daily actions."""
        client, _ = auth_client
        resp = client.post("/api/workflows/generate", json={
            "description": "Send monthly client reports via email",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ===========================================================================
# Part 7: Compliance Framework Tier Enforcement
# ===========================================================================

class TestComplianceTierEnforcement:
    def test_free_tier_compliance_blocked(self, auth_client):
        """FREE tier cannot enable compliance frameworks."""
        client, _ = auth_client
        resp = client.post("/api/compliance/toggles", json={
            "enabled": ["gdpr", "soc2"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tier_restricted"] is True
        assert data["enabled"] == []  # All stripped out
        assert "subscription" in data.get("tier_message", "").lower()

    def test_compliance_toggles_get(self, client):
        resp = client.get("/api/compliance/toggles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "enabled" in data

    def test_compliance_recommended(self, client):
        resp = client.get("/api/compliance/recommended?country=US&industry=healthcare")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "recommended" in data

    def test_compliance_report(self, client):
        resp = client.get("/api/compliance/report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "report" in data


# ===========================================================================
# Part 8: Compliance Conflict Detection
# ===========================================================================

class TestComplianceConflicts:
    def test_gdpr_ccpa_conflict_detected(self, client):
        """When GDPR and CCPA both enabled, conflict should be documented."""
        # Use a fresh client without auth session (no tier restriction)
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
        fresh = TestClient(create_app(), follow_redirects=False)
        resp = fresh.post("/api/compliance/toggles", json={
            "enabled": ["gdpr", "ccpa"],
        })
        data = resp.json()
        assert data["success"] is True
        conflicts = data.get("conflicts", [])
        # Without auth, no tier restriction → frameworks saved, conflicts detected
        gdpr_ccpa = [c for c in conflicts if set(c["frameworks"]) == {"gdpr", "ccpa"}]
        assert len(gdpr_ccpa) == 1
        assert "Data Retention" in gdpr_ccpa[0]["area"]
        assert "resolution" in gdpr_ccpa[0]

    def test_hipaa_gdpr_conflict_detected(self, client):
        """HIPAA + GDPR conflict should be documented."""
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
        fresh = TestClient(create_app(), follow_redirects=False)
        resp = fresh.post("/api/compliance/toggles", json={
            "enabled": ["hipaa", "gdpr"],
        })
        data = resp.json()
        conflicts = data.get("conflicts", [])
        hipaa_gdpr = [c for c in conflicts if set(c["frameworks"]) == {"hipaa", "gdpr"}]
        assert len(hipaa_gdpr) == 1
        assert "consent" in hipaa_gdpr[0]["resolution"].lower()

    def test_soc2_iso27001_overlap_detected(self, client):
        """SOC 2 + ISO 27001 overlap should be documented."""
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
        fresh = TestClient(create_app(), follow_redirects=False)
        resp = fresh.post("/api/compliance/toggles", json={
            "enabled": ["soc2", "iso_27001"],
        })
        data = resp.json()
        conflicts = data.get("conflicts", [])
        soc2_iso = [c for c in conflicts if set(c["frameworks"]) == {"soc2", "iso_27001"}]
        assert len(soc2_iso) == 1
        assert "unified controls" in soc2_iso[0]["resolution"].lower()

    def test_no_conflicts_for_single_framework(self, client):
        """No conflicts when only one framework is enabled."""
        from starlette.testclient import TestClient
        from src.runtime.app import create_app
        os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
        fresh = TestClient(create_app(), follow_redirects=False)
        resp = fresh.post("/api/compliance/toggles", json={
            "enabled": ["gdpr"],
        })
        data = resp.json()
        conflicts = data.get("conflicts", [])
        assert len(conflicts) == 0


# ===========================================================================
# Part 9: Librarian Ask/Execute Modes
# ===========================================================================

class TestLibrarian:
    def test_librarian_ask_mode(self, client):
        resp = client.post("/api/librarian/ask", json={
            "message": "What compliance frameworks does Murphy support?",
            "mode": "ask",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data or "response" in data or "result" in data

    def test_librarian_execute_mode(self, client):
        resp = client.post("/api/librarian/ask", json={
            "message": "Generate a workflow for client onboarding",
            "mode": "execute",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("librarian_mode") == "execute"

    def test_librarian_default_mode(self, client):
        resp = client.post("/api/librarian/ask", json={
            "message": "Hello, tell me about Murphy System",
        })
        assert resp.status_code == 200

    def test_librarian_accepts_query_key(self, client):
        resp = client.post("/api/librarian/ask", json={
            "query": "What is Murphy?",
        })
        assert resp.status_code == 200

    def test_librarian_accepts_question_key(self, client):
        resp = client.post("/api/librarian/ask", json={
            "question": "How do I create a workflow?",
        })
        assert resp.status_code == 200


# ===========================================================================
# Part 10: Integration CRUD
# ===========================================================================

class TestIntegrations:
    def test_list_integrations(self, client):
        resp = client.get("/api/integrations/all")
        assert resp.status_code == 200
        data = resp.json()
        # Should return list of integrations (possibly empty)
        assert (
            "integrations" in data
            or isinstance(data, list)
            or "success" in data
            or "committed" in data
        )

    def test_add_integration(self, client):
        resp = client.post("/api/integrations/add", json={
            "source": "https://api.example.com",
            "integration_type": "api",
            "category": "crm",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data or "request_id" in data or "id" in data

    def test_integration_catalog(self, client):
        resp = client.get("/api/integrations")
        assert resp.status_code == 200
        data = resp.json()
        assert "integrations" in data
        assert isinstance(data["integrations"], list)


# ===========================================================================
# Part 11: Health and System Status
# ===========================================================================

class TestSystemEndpoints:
    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")

    def test_status_endpoint(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200

    def test_modules_endpoint(self, client):
        resp = client.get("/api/modules")
        assert resp.status_code == 200

    def test_billing_tiers(self, client):
        resp = client.get("/api/billing/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["tiers"], list)
        # Should have FREE, SOLO, BUSINESS, PROFESSIONAL, ENTERPRISE
        tier_names = [t.get("name", "").lower() for t in data["tiers"]]
        assert "free" in tier_names or any("free" in str(t).lower() for t in data["tiers"])


# ===========================================================================
# Part 12: Compliance Scan
# ===========================================================================

class TestComplianceScan:
    def test_compliance_scan_runs(self, client):
        resp = client.post("/api/compliance/scan", json={
            "name": "test-scan",
            "context": {"environment": "test"},
        })
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert data["success"] is True
            assert "scans" in data

    def test_compliance_scan_with_frameworks(self, client):
        # First enable some frameworks (without auth = no tier restriction)
        client.post("/api/compliance/toggles", json={
            "enabled": ["gdpr", "soc2"],
        })
        resp = client.post("/api/compliance/scan", json={
            "name": "framework-scan",
        })
        assert resp.status_code in (200, 503)


# ===========================================================================
# Part 13: MFGC Gates
# ===========================================================================

class TestMFGCGates:
    def test_mfgc_gates_returns_all_gates(self, client):
        resp = client.get("/api/mfgc/gates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "gates" in data
        gates = data["gates"]
        for gate in ["executive", "operations", "qa", "hitl", "compliance", "budget"]:
            assert gate in gates


# ===========================================================================
# Part 14: Usage Daily Tracking
# ===========================================================================

class TestUsageTracking:
    def test_usage_daily_endpoint(self, auth_client):
        client, _ = auth_client
        resp = client.get("/api/usage/daily")
        assert resp.status_code == 200
        data = resp.json()
        assert "used" in data
        assert "limit" in data
        assert "remaining" in data


# ===========================================================================
# Part 15: Profile with Tier Info
# ===========================================================================

class TestProfileTierInfo:
    def test_profile_includes_tier(self, auth_client):
        client, _ = auth_client
        resp = client.get("/api/profiles/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is True
        assert data["tier"] == "free"
        assert "daily_usage" in data
        assert "terminal_config" in data
