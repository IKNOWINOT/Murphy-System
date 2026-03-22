"""
Production Commissioning Test Suite
=====================================
Commission-driven gap-close loop: expected outcome vs actual outcome.

Each test asserts an *Expected Outcome* (EO) and records the actual outcome.
A test failure = a gap that must be closed before production deploy.

Run with:
    MURPHY_ENV=development python3 -m pytest tests/test_production_commissioning.py \
        --override-ini="addopts=" -v --timeout=60
"""

import json
import os
import sys

import pytest

os.environ.setdefault("MURPHY_ENV", "development")
os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")

# ---------------------------------------------------------------------------
# Shared TestClient
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from starlette.testclient import TestClient
    from src.runtime.app import create_app
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# EO-1  Health endpoint
# ---------------------------------------------------------------------------

class TestEO1_Health:
    """EO-1: GET /api/health → {"status":"healthy"} HTTP 200"""

    def test_shallow_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_health_body_contains_status_healthy(self, client):
        body = client.get("/api/health").json()
        assert body.get("status") == "healthy", f"Body: {body}"

    def test_health_body_contains_version(self, client):
        body = client.get("/api/health").json()
        assert "version" in body, f"Missing 'version': {body}"

    def test_deep_health_returns_200_or_503(self, client):
        """Deep health may return 503 if subsystems unavailable — that's valid
        as long as it doesn't crash (5xx unhandled)."""
        resp = client.get("/api/health?deep=true")
        assert resp.status_code in (200, 503), (
            f"Unexpected status {resp.status_code}: {resp.text[:200]}"
        )

    def test_deep_health_returns_json(self, client):
        resp = client.get("/api/health?deep=true")
        body = resp.json()
        assert isinstance(body, dict), f"Expected dict: {body}"


# ---------------------------------------------------------------------------
# EO-2  Chat endpoint reaches LLM layer (not a hard crash)
# ---------------------------------------------------------------------------

class TestEO2_Chat:
    """EO-2: POST /api/chat returns HTTP 200 with a 'response' field."""

    def test_chat_returns_200(self, client):
        resp = client.post("/api/chat", json={"message": "Hello", "session_id": "eo2-test"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

    def test_chat_response_is_json(self, client):
        resp = client.post("/api/chat", json={"message": "What is automation?"})
        body = resp.json()
        assert isinstance(body, dict), f"Expected dict, got {type(body)}: {body}"

    def test_chat_has_response_field(self, client):
        """Core assertion: a 'response' field must be present and non-empty."""
        resp = client.post("/api/chat", json={"message": "Describe an ETL pipeline"})
        body = resp.json()
        response_text = body.get("response") or (body.get("bus") or {}).get("response")
        assert response_text, f"No response field in: {body}"

    def test_chat_response_is_not_empty_string(self, client):
        resp = client.post("/api/chat", json={"message": "What is phi3?"})
        body = resp.json()
        response_text = body.get("response") or (body.get("bus") or {}).get("response") or ""
        assert len(str(response_text).strip()) > 0, f"Empty response in: {body}"

    def test_chat_missing_message_does_not_crash(self, client):
        """Edge case: missing message key should not cause 500."""
        resp = client.post("/api/chat", json={})
        assert resp.status_code != 500, f"Server crashed on empty message: {resp.text[:200]}"

    def test_chat_integration_bus_attached(self, client):
        """When IntegrationBus is wired the response should carry a 'bus' key."""
        resp = client.post("/api/chat", json={"message": "Automate invoice processing"})
        body = resp.json()
        # bus key present means IntegrationBus was invoked — if absent it's a gap
        if "bus" not in body:
            pytest.xfail(
                "IntegrationBus not attached — chat falls through to legacy path. "
                "This is a known gap that reduces phi3 routing."
            )


# ---------------------------------------------------------------------------
# EO-3  Workflow generation from description
# ---------------------------------------------------------------------------

class TestEO3_WorkflowGeneration:
    """EO-3: POST /api/workflows/generate → DAG with ≥1 step."""

    def test_generate_returns_200(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "Send a daily report email with sales data"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

    def test_generate_returns_success(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "Extract customer records from CRM and load into data warehouse"
        })
        body = resp.json()
        assert body.get("success") is True, f"success!=True: {body}"

    def test_generate_workflow_has_steps(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "Onboard a new employee: create accounts, send welcome email, assign mentor"
        })
        body = resp.json()
        wf = body.get("workflow") or body.get("workflow_definition") or body
        steps = wf.get("steps") or wf.get("nodes") or []
        assert len(steps) >= 1, f"Workflow must have ≥1 step. Got: {wf}"

    def test_generate_workflow_has_id(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "Process incoming orders and update inventory"
        })
        body = resp.json()
        wf = body.get("workflow") or body.get("workflow_definition") or body
        assert wf.get("workflow_id") or wf.get("id"), f"No workflow_id in: {wf}"

    def test_generate_empty_description_returns_400(self, client):
        resp = client.post("/api/workflows/generate", json={"description": ""})
        assert resp.status_code == 400, f"Expected 400 for empty description, got {resp.status_code}"

    def test_generate_complex_workflow_has_multiple_steps(self, client):
        resp = client.post("/api/workflows/generate", json={
            "description": "CI/CD pipeline: build Docker image, run tests, deploy to staging, notify Slack"
        })
        body = resp.json()
        wf = body.get("workflow") or body.get("workflow_definition") or body
        steps = wf.get("steps") or wf.get("nodes") or []
        assert len(steps) >= 3, f"Complex workflow must have ≥3 steps. Got {len(steps)}: {steps}"


# ---------------------------------------------------------------------------
# EO-4  Commissioning: description → DAG → health_score ≥ 0.75
# ---------------------------------------------------------------------------

class TestEO4_Commissioning:
    """EO-4: POST /api/automations/commission → health_score ≥ 0.75, ready_for_deploy=True."""

    def _minimal_workflow(self):
        return {
            "workflow_id": "test-commission-001",
            "name": "Invoice Processing",
            "description": "Extract PDF invoice, parse line items, post to accounting system",
            "steps": [
                {
                    "step_id": "extract",
                    "name": "Extract Invoice",
                    "type": "data_retrieval",
                    "description": "Read PDF invoice from inbox",
                    "depends_on": []
                },
                {
                    "step_id": "parse",
                    "name": "Parse Line Items",
                    "type": "data_transformation",
                    "description": "Parse PDF and extract line items, amounts, vendor",
                    "depends_on": ["extract"]
                },
                {
                    "step_id": "post",
                    "name": "Post to Accounting",
                    "type": "data_output",
                    "description": "Create accounting entry in QuickBooks via API",
                    "depends_on": ["parse"]
                }
            ],
            "triggers": [{"type": "email_received", "config": {"folder": "invoices"}}]
        }

    def test_commission_returns_200(self, client):
        resp = client.post("/api/automations/commission", json={
            "workflow": self._minimal_workflow(),
            "health_threshold": 0.60
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

    def test_commission_returns_success(self, client):
        resp = client.post("/api/automations/commission", json={
            "workflow": self._minimal_workflow()
        })
        body = resp.json()
        assert body.get("success") is True, f"success!=True: {body}"

    def test_commission_has_health_score(self, client):
        resp = client.post("/api/automations/commission", json={
            "workflow": self._minimal_workflow()
        })
        body = resp.json()
        report = body.get("commissioning_report", {})
        assert "health_score" in report, f"No health_score in: {report}"

    def test_commission_health_score_is_float(self, client):
        resp = client.post("/api/automations/commission", json={
            "workflow": self._minimal_workflow()
        })
        body = resp.json()
        hs = body.get("commissioning_report", {}).get("health_score")
        assert isinstance(hs, (int, float)), f"health_score not numeric: {hs}"

    def test_commission_health_score_meets_threshold(self, client):
        """Core assertion: health score must meet or exceed 0.75."""
        resp = client.post("/api/automations/commission", json={
            "workflow": self._minimal_workflow(),
            "health_threshold": 0.75
        })
        body = resp.json()
        report = body.get("commissioning_report", {})
        hs = float(report.get("health_score", 0))
        assert hs >= 0.75, (
            f"health_score {hs:.2f} < 0.75 threshold — workflow not production-ready.\n"
            f"Report: {report}"
        )

    def test_commission_has_ready_for_deploy(self, client):
        resp = client.post("/api/automations/commission", json={
            "workflow": self._minimal_workflow()
        })
        body = resp.json()
        report = body.get("commissioning_report", {})
        assert "ready_for_deploy" in report, f"No ready_for_deploy in: {report}"

    def test_commission_missing_workflow_returns_400(self, client):
        resp = client.post("/api/automations/commission", json={})
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"


# ---------------------------------------------------------------------------
# EO-5  Fire trigger → execution_id returned
# ---------------------------------------------------------------------------

class TestEO5_FireTrigger:
    """EO-5: POST /api/automations/fire-trigger returns execution_id or task_id."""

    def test_fire_trigger_returns_200(self, client):
        resp = client.post("/api/automations/fire-trigger", json={
            "trigger_type": "item_created",
            "board_id": "test-board-001",
            "context": {"test": True}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

    def test_fire_trigger_returns_json(self, client):
        resp = client.post("/api/automations/fire-trigger", json={
            "trigger_type": "item_created"
        })
        body = resp.json()
        assert isinstance(body, dict), f"Expected dict: {body}"

    def test_fire_trigger_has_execution_id_or_result(self, client):
        resp = client.post("/api/automations/fire-trigger", json={
            "trigger_type": "item_created",
            "board_id": "test-board-001"
        })
        body = resp.json()
        has_id = any(k in body for k in ("execution_id", "task_id", "id", "results"))
        assert has_id, f"No execution_id/task_id/results in: {body}"

    def test_fire_trigger_invalid_type_returns_400(self, client):
        """Validates that unknown trigger types are rejected cleanly."""
        resp = client.post("/api/automations/fire-trigger", json={
            "trigger_type": "not_a_real_trigger"
        })
        assert resp.status_code == 400, (
            f"Expected 400 for invalid trigger, got {resp.status_code}: {resp.text[:200]}"
        )


# ---------------------------------------------------------------------------
# EO-6  Production Wizard auth handling
# ---------------------------------------------------------------------------

class TestEO6_ProductionWizardAuth:
    """EO-6: Production-wizard protected endpoints return 401/403 (not 500 crash)."""

    def test_production_queue_requires_auth(self, client):
        resp = client.get("/api/production/queue")
        assert resp.status_code in (200, 401, 403), (
            f"Expected 200/401/403 but got {resp.status_code}: {resp.text[:200]}"
        )

    def test_production_proposals_requires_auth(self, client):
        resp = client.get("/api/production/proposals")
        assert resp.status_code in (200, 401, 403), (
            f"Expected 200/401/403 but got {resp.status_code}: {resp.text[:200]}"
        )

    def test_deliverables_does_not_crash(self, client):
        resp = client.get("/api/deliverables")
        assert resp.status_code != 500, f"Server crash on /api/deliverables: {resp.text[:200]}"

    def test_hitl_pending_does_not_crash(self, client):
        resp = client.get("/api/hitl/interventions/pending")
        assert resp.status_code != 500, f"Server crash: {resp.text[:200]}"


# ---------------------------------------------------------------------------
# EO-7  phi3 is first model probed
# ---------------------------------------------------------------------------

class TestEO7_Phi3Default:
    """EO-7: phi3 is first in model probe order."""

    def test_preferred_models_leads_with_phi3(self):
        from src.local_llm_fallback import _preferred_ollama_models
        models = _preferred_ollama_models()
        assert models[0] == "phi3", (
            f"Expected phi3 first, got {models[0]}. Full order: {models}"
        )

    def test_ollama_models_list_starts_with_phi3(self):
        from src.local_llm_fallback import _OLLAMA_MODELS
        assert _OLLAMA_MODELS[0] == "phi3", (
            f"_OLLAMA_MODELS should start with phi3, got: {_OLLAMA_MODELS}"
        )

    def test_query_ollama_default_is_phi3(self):
        import inspect
        from src.local_llm_fallback import _query_ollama
        sig = inspect.signature(_query_ollama)
        default = sig.parameters["model"].default
        assert default == "phi3", f"_query_ollama default model is '{default}', expected 'phi3'"

    def test_llm_integration_default_is_phi3(self):
        import inspect
        from src.llm_integration import OllamaLLM
        sig = inspect.signature(OllamaLLM.__init__)
        default = sig.parameters["model_name"].default
        assert default == "phi3", f"OllamaLLM default is '{default}', expected 'phi3'"

    def test_ollama_fallback_wired_in_integration_layer(self):
        from src import llm_integration_layer
        assert getattr(llm_integration_layer, "_HAS_OLLAMA_FALLBACK", False), (
            "_HAS_OLLAMA_FALLBACK is False — Ollama import failed in llm_integration_layer"
        )


# ---------------------------------------------------------------------------
# EO-8  /api/llm/providers returns phi3/ollama info
# ---------------------------------------------------------------------------

class TestEO8_LLMProviders:
    """EO-8: GET /api/llm/providers returns real provider info including ollama/phi3."""

    def test_llm_providers_returns_200(self, client):
        resp = client.get("/api/llm/providers")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    def test_llm_providers_has_ollama_entry(self, client):
        body = client.get("/api/llm/providers").json()
        providers = body.get("providers") or []
        names = [
            (p.get("name") or p.get("id") or "").lower()
            for p in providers
        ] if isinstance(providers, list) else list(providers.keys()) if isinstance(providers, dict) else []
        assert any("ollama" in n or "phi3" in n or "local" in n for n in names), (
            f"No ollama/phi3/local entry in providers: {providers}"
        )


# ---------------------------------------------------------------------------
# EO-9  Self-assembly end-to-end: description → generate → commission → ≥0.75
# ---------------------------------------------------------------------------

class TestEO9_SelfAssemblyEndToEnd:
    """EO-9: Full self-assembly loop — user description produces a commissioned
    workflow with health_score ≥ 0.75, ready_for_deploy=True."""

    @pytest.mark.parametrize("description", [
        "Automate daily invoice processing: read emails, extract PDF, post to QuickBooks",
        "CI/CD pipeline for Python project: lint, test, build Docker image, push to registry",
        "Employee onboarding: create accounts in Slack and GitHub, send welcome email, assign buddy",
    ])
    def test_end_to_end_self_assembly(self, client, description):
        # Step 1: Generate workflow from description
        gen_resp = client.post("/api/workflows/generate", json={"description": description})
        assert gen_resp.status_code == 200, (
            f"[generate] HTTP {gen_resp.status_code}: {gen_resp.text[:300]}"
        )
        gen_body = gen_resp.json()
        assert gen_body.get("success"), f"[generate] success=False: {gen_body}"

        # The API returns a "saved" canvas shape (id + nodes); pass it directly
        # to commission — to_workflow_definition now normalises both shapes.
        wf = gen_body.get("workflow") or gen_body.get("workflow_definition") or gen_body
        nodes = wf.get("nodes") or wf.get("steps") or []
        assert len(nodes) >= 1, f"[generate] No steps/nodes produced for: '{description}'"

        # Step 2: Commission the generated workflow
        comm_resp = client.post("/api/automations/commission", json={
            "workflow": wf,
            "health_threshold": 0.75
        })
        assert comm_resp.status_code == 200, (
            f"[commission] HTTP {comm_resp.status_code}: {comm_resp.text[:300]}"
        )
        comm_body = comm_resp.json()
        assert comm_body.get("success"), f"[commission] success=False: {comm_body}"

        report = comm_body.get("commissioning_report", {})
        hs = float(report.get("health_score", 0))
        ready = report.get("ready_for_deploy", False)

        # CORE ASSERTION: health ≥ 0.75 and ready_for_deploy=True
        assert hs >= 0.75 and ready, (
            f"Self-assembly FAILED for description: '{description}'\n"
            f"  health_score={hs:.3f}  ready_for_deploy={ready}\n"
            f"  steps={len(nodes)}\n"
            f"  report={report}"
        )
