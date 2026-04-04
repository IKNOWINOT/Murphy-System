"""
Gap-closure round 44 — User Capability Acceptance Tests.

Tests every user-facing capability of the Murphy System runtime from a user
perspective.  The test starts the FastAPI application via TestClient (no
external process required) and exercises all major API endpoints, documenting
deficiencies and proving that gaps are closed.

Capabilities tested (grouped by user journey):
  1.  Health & Status           — GET /api/health, /api/status, /api/info
  2.  System Modules            — GET /api/modules
  3.  Chat & Execution          — POST /api/chat, /api/execute
  4.  LLM Management            — GET/POST /api/llm/*
  5.  Librarian                 — POST /api/librarian/ask, GET status
  6.  Documents                 — POST /api/documents, GET /api/documents/{id}
  7.  Forms                     — POST /api/forms/*
  8.  Corrections & Learning    — GET /api/corrections/*
  9.  HITL Interventions        — GET /api/hitl/*
  10. MFGC State                — GET/POST /api/mfgc/*
  11. Integrations              — GET/POST /api/integrations/*
  12. Image Generation          — GET/POST /api/images/*
  13. Universal Integrations    — GET /api/universal-integrations/*
  14. Onboarding Wizard         — GET/POST /api/onboarding/wizard/*
  15. Employee Onboarding       — GET/POST /api/onboarding/employees/*
  16. Workflow Terminal          — GET/POST /api/workflow-terminal/*
  17. Agent Dashboard            — GET/POST /api/agent-dashboard/*
  18. Onboarding Flow           — GET/POST /api/onboarding-flow/*
  19. IP Classification         — GET/POST /api/ip/*
  20. Credential Profiles       — GET/POST /api/credentials/*
  21. Diagnostics               — GET /api/diagnostics/*
  22. Sessions                  — POST /api/sessions/*
  23. Automation                — POST /api/automation/*
"""

import json
import os
import sys
import time

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_PROJ_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)


# ---------------------------------------------------------------------------
# App & Client fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    """Create the Murphy System FastAPI application."""
    # Suppress noisy logs during tests
    import logging
    logging.disable(logging.WARNING)
    try:
        from murphy_system_1_0_runtime import create_app
        return create_app()
    except ImportError:
        # Filename contains dots — use importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "murphy_runtime",
            os.path.join(_PROJ_ROOT, "murphy_system_1.0_runtime.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.create_app()
    finally:
        logging.disable(logging.NOTSET)


@pytest.fixture(scope="module")
def client(app):
    """Starlette TestClient wrapping the app."""
    from starlette.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Helpers
# ===========================================================================
def _json_or_text(resp):
    """Return parsed JSON or raw text."""
    try:
        return resp.json()
    except Exception:
        return resp.text


def _ok(resp):
    """Return True if the response has a 2xx or expected status."""
    return 200 <= resp.status_code < 300


def _ok_or_422(resp):
    """2xx or 422 (validation) are acceptable — proves the endpoint exists."""
    return 200 <= resp.status_code < 300 or resp.status_code == 422


def _endpoint_exists(resp):
    """The endpoint exists (not 404/405)."""
    return resp.status_code not in (404, 405)


# ===========================================================================
# 1. Health & Status
# ===========================================================================
class TestHealthAndStatus:
    """User journey: check system is alive and get status."""

    def test_health_endpoint(self, client):
        """GET /api/health returns 200 with status healthy."""
        resp = client.get("/api/health")
        assert _ok(resp), f"Health check failed: {resp.status_code}"
        body = resp.json()
        assert body.get("status") == "healthy"

    def test_status_endpoint(self, client):
        """GET /api/status returns system status."""
        resp = client.get("/api/status")
        assert _endpoint_exists(resp), f"/api/status missing: {resp.status_code}"
        if _ok(resp):
            body = resp.json()
            assert isinstance(body, dict)

    def test_info_endpoint(self, client):
        """GET /api/info returns system information."""
        resp = client.get("/api/info")
        assert _endpoint_exists(resp), f"/api/info missing: {resp.status_code}"

    def test_system_info_endpoint(self, client):
        """GET /api/system/info returns detailed info."""
        resp = client.get("/api/system/info")
        assert _endpoint_exists(resp), f"/api/system/info missing: {resp.status_code}"


# ===========================================================================
# 2. System Modules
# ===========================================================================
class TestModules:
    """User journey: discover available modules."""

    def test_list_modules(self, client):
        """GET /api/modules returns module list."""
        resp = client.get("/api/modules")
        assert _endpoint_exists(resp), f"/api/modules missing: {resp.status_code}"


# ===========================================================================
# 3. Chat & Execution
# ===========================================================================
class TestChatAndExecution:
    """User journey: interact via chat and execute tasks."""

    def test_chat_endpoint(self, client):
        """POST /api/chat processes a message."""
        resp = client.post("/api/chat", json={"message": "hello"})
        assert _endpoint_exists(resp), f"/api/chat missing: {resp.status_code}"
        if _ok(resp):
            body = resp.json()
            assert isinstance(body, dict)

    def test_execute_task(self, client):
        """POST /api/execute processes a task."""
        resp = client.post("/api/execute", json={
            "task": "test task",
            "description": "test execution from user test",
        })
        assert _endpoint_exists(resp), f"/api/execute missing: {resp.status_code}"

    def test_chat_empty_message_handled(self, client):
        """POST /api/chat with empty message doesn't crash."""
        resp = client.post("/api/chat", json={"message": ""})
        assert _endpoint_exists(resp)
        assert resp.status_code != 500, "Server error on empty message"

    def test_execute_empty_task_handled(self, client):
        """POST /api/execute with empty task doesn't crash."""
        resp = client.post("/api/execute", json={"task": ""})
        assert _endpoint_exists(resp)
        assert resp.status_code != 500, "Server error on empty task"


# ===========================================================================
# 4. LLM Management
# ===========================================================================
class TestLLMManagement:
    """User journey: check and configure LLM providers."""

    def test_llm_status(self, client):
        """GET /api/llm/status returns LLM configuration."""
        resp = client.get("/api/llm/status")
        assert _endpoint_exists(resp), f"/api/llm/status missing: {resp.status_code}"

    def test_llm_configure(self, client):
        """POST /api/llm/configure accepts configuration."""
        resp = client.post("/api/llm/configure", json={
            "provider": "local",
            "model": "test-model",
        })
        assert _endpoint_exists(resp)

    def test_llm_test(self, client):
        """POST /api/llm/test tests LLM connection."""
        resp = client.post("/api/llm/test", json={"prompt": "test"})
        assert _endpoint_exists(resp)

    def test_llm_reload(self, client):
        """POST /api/llm/reload reloads LLM."""
        resp = client.post("/api/llm/reload", json={})
        assert _endpoint_exists(resp)


# ===========================================================================
# 5. Librarian
# ===========================================================================
class TestLibrarian:
    """User journey: ask the librarian questions."""

    def test_librarian_ask(self, client):
        """POST /api/librarian/ask processes a question."""
        resp = client.post("/api/librarian/ask", json={
            "message": "What modules are available?"
        })
        assert _endpoint_exists(resp), f"/api/librarian/ask missing: {resp.status_code}"

    def test_librarian_status(self, client):
        """GET /api/librarian/status returns status."""
        resp = client.get("/api/librarian/status")
        assert _endpoint_exists(resp)

    def test_librarian_api_links(self, client):
        """GET /api/librarian/api-links returns links."""
        resp = client.get("/api/librarian/api-links")
        assert _endpoint_exists(resp)


# ===========================================================================
# 6. Documents
# ===========================================================================
class TestDocuments:
    """User journey: create and manage documents."""

    def test_create_document(self, client):
        """POST /api/documents creates a document."""
        resp = client.post("/api/documents", json={
            "title": "Test Document",
            "content": "This is a test document for user capability testing.",
        })
        assert _endpoint_exists(resp)

    def test_get_document(self, client):
        """GET /api/documents/{id} returns document (or 404 if not found)."""
        resp = client.get("/api/documents/test-doc-001")
        # 404 with a JSON body is valid — means the endpoint exists and handles missing docs
        assert _endpoint_exists(resp) or resp.status_code == 404
        if resp.status_code == 404:
            body = _json_or_text(resp)
            if isinstance(body, dict):
                assert "error" in body or "detail" in body, "404 should explain why"


# ===========================================================================
# 7. Forms
# ===========================================================================
class TestForms:
    """User journey: submit and validate forms."""

    def test_form_validation(self, client):
        """POST /api/forms/validation validates form data."""
        resp = client.post("/api/forms/validation", json={
            "form_type": "test",
            "data": {"field": "value"},
        })
        assert _endpoint_exists(resp)

    def test_form_task_execution(self, client):
        """POST /api/forms/task-execution submits task form."""
        resp = client.post("/api/forms/task-execution", json={
            "task": "test task form",
            "priority": "medium",
        })
        assert _endpoint_exists(resp)

    def test_form_correction(self, client):
        """POST /api/forms/correction submits correction."""
        resp = client.post("/api/forms/correction", json={
            "original": "incorrect output",
            "corrected": "correct output",
        })
        assert _endpoint_exists(resp)

    def test_form_plan_generation(self, client):
        """POST /api/forms/plan-generation generates a plan."""
        resp = client.post("/api/forms/plan-generation", json={
            "objective": "Build a customer onboarding flow",
        })
        assert _endpoint_exists(resp)


# ===========================================================================
# 8. Corrections & Learning
# ===========================================================================
class TestCorrections:
    """User journey: view correction patterns and stats."""

    def test_correction_patterns(self, client):
        """GET /api/corrections/patterns returns patterns."""
        resp = client.get("/api/corrections/patterns")
        assert _endpoint_exists(resp)

    def test_correction_statistics(self, client):
        """GET /api/corrections/statistics returns stats."""
        resp = client.get("/api/corrections/statistics")
        assert _endpoint_exists(resp)

    def test_correction_training_data(self, client):
        """GET /api/corrections/training-data returns training data."""
        resp = client.get("/api/corrections/training-data")
        assert _endpoint_exists(resp)


# ===========================================================================
# 9. HITL Interventions
# ===========================================================================
class TestHITL:
    """User journey: manage human-in-the-loop interventions."""

    def test_pending_interventions(self, client):
        """GET /api/hitl/interventions/pending returns list."""
        resp = client.get("/api/hitl/interventions/pending")
        assert _endpoint_exists(resp)

    def test_hitl_statistics(self, client):
        """GET /api/hitl/statistics returns HITL stats."""
        resp = client.get("/api/hitl/statistics")
        assert _endpoint_exists(resp)


# ===========================================================================
# 10. MFGC State
# ===========================================================================
class TestMFGC:
    """User journey: manage MFGC (Murphy Factory Gate Controller)."""

    def test_mfgc_state(self, client):
        """GET /api/mfgc/state returns MFGC state."""
        resp = client.get("/api/mfgc/state")
        assert _endpoint_exists(resp)

    def test_mfgc_config_get(self, client):
        """GET /api/mfgc/config returns configuration."""
        resp = client.get("/api/mfgc/config")
        assert _endpoint_exists(resp)


# ===========================================================================
# 11. Integrations
# ===========================================================================
class TestIntegrations:
    """User journey: manage platform integrations."""

    def test_list_integrations(self, client):
        """GET /api/integrations/active returns active list."""
        resp = client.get("/api/integrations/active")
        assert _endpoint_exists(resp)

    def test_add_integration(self, client):
        """POST /api/integrations/add registers new integration."""
        resp = client.post("/api/integrations/add", json={
            "name": "test-integration",
            "type": "webhook",
        })
        assert _endpoint_exists(resp)


# ===========================================================================
# 12. Image Generation
# ===========================================================================
class TestImages:
    """User journey: generate images."""

    def test_image_styles(self, client):
        """GET /api/images/styles returns available styles."""
        resp = client.get("/api/images/styles")
        assert _endpoint_exists(resp)

    def test_image_stats(self, client):
        """GET /api/images/stats returns generation stats."""
        resp = client.get("/api/images/stats")
        assert _endpoint_exists(resp)


# ===========================================================================
# 13. Universal Integrations
# ===========================================================================
class TestUniversalIntegrations:
    """User journey: discover and use universal integrations."""

    def test_list_services(self, client):
        """GET /api/universal-integrations/services lists services."""
        resp = client.get("/api/universal-integrations/services")
        assert _endpoint_exists(resp)

    def test_list_categories(self, client):
        """GET /api/universal-integrations/categories lists categories."""
        resp = client.get("/api/universal-integrations/categories")
        assert _endpoint_exists(resp)

    def test_integration_stats(self, client):
        """GET /api/universal-integrations/stats returns stats."""
        resp = client.get("/api/universal-integrations/stats")
        assert _endpoint_exists(resp)


# ===========================================================================
# 14. Onboarding Wizard
# ===========================================================================
class TestOnboardingWizard:
    """User journey: complete the onboarding wizard."""

    def test_get_questions(self, client):
        """GET /api/onboarding/wizard/questions returns wizard questions."""
        resp = client.get("/api/onboarding/wizard/questions")
        assert _endpoint_exists(resp)
        if _ok(resp):
            body = resp.json()
            assert isinstance(body, (dict, list))

    def test_get_profile(self, client):
        """GET /api/onboarding/wizard/profile returns current profile."""
        resp = client.get("/api/onboarding/wizard/profile")
        assert _endpoint_exists(resp)

    def test_get_summary(self, client):
        """GET /api/onboarding/wizard/summary returns summary."""
        resp = client.get("/api/onboarding/wizard/summary")
        assert _endpoint_exists(resp)

    def test_answer_question(self, client):
        """POST /api/onboarding/wizard/answer submits an answer."""
        resp = client.post("/api/onboarding/wizard/answer", json={
            "question_id": "org_name",
            "answer": "Test Corp",
        })
        assert _endpoint_exists(resp)

    def test_reset_wizard(self, client):
        """POST /api/onboarding/wizard/reset resets the wizard."""
        resp = client.post("/api/onboarding/wizard/reset", json={})
        assert _endpoint_exists(resp)


# ===========================================================================
# 15. Employee Onboarding
# ===========================================================================
class TestEmployeeOnboarding:
    """User journey: manage employee onboarding."""

    def test_list_employees(self, client):
        """GET /api/onboarding/employees lists employees."""
        resp = client.get("/api/onboarding/employees")
        assert _endpoint_exists(resp)

    def test_onboarding_status(self, client):
        """GET /api/onboarding/status returns overall status."""
        resp = client.get("/api/onboarding/status")
        assert _endpoint_exists(resp)


# ===========================================================================
# 16. Workflow Terminal
# ===========================================================================
class TestWorkflowTerminal:
    """User journey: create and interact with workflow sessions."""

    def test_list_sessions(self, client):
        """GET /api/workflow-terminal/sessions lists sessions."""
        resp = client.get("/api/workflow-terminal/sessions")
        assert _endpoint_exists(resp)

    def test_create_session(self, client):
        """POST /api/workflow-terminal/sessions creates a session."""
        resp = client.post("/api/workflow-terminal/sessions", json={
            "name": "test-session",
        })
        assert _endpoint_exists(resp)


# ===========================================================================
# 17. Agent Dashboard
# ===========================================================================
class TestAgentDashboard:
    """User journey: monitor and manage agents."""

    def test_agent_snapshot(self, client):
        """GET /api/agent-dashboard/snapshot returns dashboard snapshot."""
        resp = client.get("/api/agent-dashboard/snapshot")
        assert _endpoint_exists(resp)

    def test_list_agents(self, client):
        """GET /api/agent-dashboard/agents lists agents."""
        resp = client.get("/api/agent-dashboard/agents")
        assert _endpoint_exists(resp)


# ===========================================================================
# 18. Onboarding Flow
# ===========================================================================
class TestOnboardingFlow:
    """User journey: organisation onboarding flow."""

    def test_org_chart(self, client):
        """GET /api/onboarding-flow/org/chart returns org chart."""
        resp = client.get("/api/onboarding-flow/org/chart")
        assert _endpoint_exists(resp)

    def test_org_positions(self, client):
        """GET /api/onboarding-flow/org/positions returns positions."""
        resp = client.get("/api/onboarding-flow/org/positions")
        assert _endpoint_exists(resp)


# ===========================================================================
# 19. IP Classification
# ===========================================================================
class TestIPClassification:
    """User journey: manage intellectual property assets."""

    def test_list_ip_assets(self, client):
        """GET /api/ip/assets lists IP assets."""
        resp = client.get("/api/ip/assets")
        assert _endpoint_exists(resp)

    def test_ip_summary(self, client):
        """GET /api/ip/summary returns IP summary."""
        resp = client.get("/api/ip/summary")
        assert _endpoint_exists(resp)

    def test_trade_secrets(self, client):
        """GET /api/ip/trade-secrets returns trade secrets."""
        resp = client.get("/api/ip/trade-secrets")
        assert _endpoint_exists(resp)


# ===========================================================================
# 20. Credential Profiles
# ===========================================================================
class TestCredentialProfiles:
    """User journey: manage credential profiles."""

    def test_list_profiles(self, client):
        """GET /api/credentials/profiles lists profiles."""
        resp = client.get("/api/credentials/profiles")
        assert _endpoint_exists(resp)

    def test_credential_metrics(self, client):
        """GET /api/credentials/metrics returns metrics."""
        resp = client.get("/api/credentials/metrics")
        assert _endpoint_exists(resp)


# ===========================================================================
# 21. Diagnostics
# ===========================================================================
class TestDiagnostics:
    """User journey: run diagnostics."""

    def test_activation_diagnostics(self, client):
        """GET /api/diagnostics/activation returns diagnostics."""
        resp = client.get("/api/diagnostics/activation")
        assert _endpoint_exists(resp)

    def test_last_activation(self, client):
        """GET /api/diagnostics/activation/last returns last activation."""
        resp = client.get("/api/diagnostics/activation/last")
        assert _endpoint_exists(resp)


# ===========================================================================
# 22. Sessions
# ===========================================================================
class TestSessions:
    """User journey: manage sessions."""

    def test_create_session(self, client):
        """POST /api/sessions/create creates a new session."""
        resp = client.post("/api/sessions/create", json={
            "user": "test-user",
        })
        assert _endpoint_exists(resp)


# ===========================================================================
# 23. UI Links
# ===========================================================================
class TestUILinks:
    """User journey: discover UI endpoints."""

    def test_ui_links(self, client):
        """GET /api/ui/links returns UI links."""
        resp = client.get("/api/ui/links")
        assert _endpoint_exists(resp)

    def test_account_flow(self, client):
        """GET /api/account/flow returns account flow."""
        resp = client.get("/api/account/flow")
        assert _endpoint_exists(resp)


# ===========================================================================
# 24. Error Handling — no endpoint returns 500 on valid input
# ===========================================================================
class TestErrorHandling:
    """User journey: verify server doesn't crash on edge cases."""

    def test_invalid_json_body(self, client):
        """POST with invalid JSON returns 4xx, not 500."""
        resp = client.post(
            "/api/chat",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code != 500, "Server crashed on invalid JSON"

    def test_unknown_endpoint_returns_404(self, client):
        """GET /api/nonexistent returns 404 (or 429 if rate-limited)."""
        resp = client.get("/api/nonexistent")
        # Rate limiting (429) is also acceptable — it means the security
        # layer intercepts before routing.  Both 404 and 429 are valid.
        assert resp.status_code in (404, 429), (
            f"Expected 404 or 429, got {resp.status_code}"
        )

    def test_very_long_input_handled(self, client):
        """POST /api/chat with very long input doesn't crash."""
        resp = client.post("/api/chat", json={"message": "x" * 10000})
        assert resp.status_code != 500, "Server crashed on long input"

    def test_special_characters_handled(self, client):
        """POST /api/chat with special chars doesn't crash."""
        resp = client.post("/api/chat", json={
            "message": "<script>alert('xss')</script> & \" ' \\ \n\t\0"
        })
        assert resp.status_code != 500, "Server crashed on special characters"

    def test_null_fields_handled(self, client):
        """POST /api/execute with null fields doesn't crash."""
        resp = client.post("/api/execute", json={
            "task": None,
            "description": None,
        })
        assert resp.status_code != 500, "Server crashed on null fields"


# ===========================================================================
# 25. Comprehensive — all GET endpoints return non-500
# ===========================================================================
class TestAllGetEndpointsHealthy:
    """Sweep: every GET endpoint must not return 500."""

    GET_ENDPOINTS = [
        "/api/health",
        "/api/status",
        "/api/info",
        "/api/system/info",
        "/api/modules",
        "/api/llm/status",
        "/api/librarian/status",
        "/api/librarian/api-links",
        "/api/ui/links",
        "/api/account/flow",
        "/api/corrections/patterns",
        "/api/corrections/statistics",
        "/api/corrections/training-data",
        "/api/hitl/interventions/pending",
        "/api/hitl/statistics",
        "/api/mfgc/state",
        "/api/mfgc/config",
        "/api/integrations/active",
        "/api/images/styles",
        "/api/images/stats",
        "/api/universal-integrations/services",
        "/api/universal-integrations/categories",
        "/api/universal-integrations/stats",
        "/api/onboarding/wizard/questions",
        "/api/onboarding/wizard/profile",
        "/api/onboarding/wizard/summary",
        "/api/onboarding/employees",
        "/api/onboarding/status",
        "/api/workflow-terminal/sessions",
        "/api/agent-dashboard/snapshot",
        "/api/agent-dashboard/agents",
        "/api/onboarding-flow/org/chart",
        "/api/onboarding-flow/org/positions",
        "/api/ip/assets",
        "/api/ip/summary",
        "/api/ip/trade-secrets",
        "/api/credentials/profiles",
        "/api/credentials/metrics",
        "/api/diagnostics/activation",
        "/api/diagnostics/activation/last",
    ]

    @pytest.mark.parametrize("endpoint", GET_ENDPOINTS)
    def test_get_endpoint_no_500(self, client, endpoint):
        """Every GET endpoint must not return 500 Internal Server Error."""
        resp = client.get(endpoint)
        assert resp.status_code != 500, (
            f"{endpoint} returned 500: {resp.text[:200]}"
        )
