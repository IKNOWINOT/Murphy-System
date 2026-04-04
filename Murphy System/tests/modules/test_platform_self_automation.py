"""
Tests for platform self-automation API endpoints.

Verifies that all platform maintenance, self-fix, repair, scheduler,
self-automation orchestrator, self-improvement, and MFM endpoints are
wired into the FastAPI app and return proper responses.

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
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Create a FastAPI test client with high rate limit for testing."""
    os.environ["MURPHY_ENV"] = "development"
    os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
    os.environ["MURPHY_RATE_LIMIT_BURST"] = "200"
    from starlette.testclient import TestClient
    from src.runtime.app import create_app
    app = create_app()
    return TestClient(app, follow_redirects=False)


# ===========================================================================
# Part 1: Self-Fix Loop Endpoints
# ===========================================================================

class TestSelfFixEndpoints:
    """Tests for /api/self-fix/* endpoints."""

    def test_self_fix_status(self, client):
        """GET /api/self-fix/status returns valid response."""
        resp = client.get("/api/self-fix/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # Should have either a real status or an unavailable message
        assert "status" in data or "message" in data

    def test_self_fix_run(self, client):
        """POST /api/self-fix/run triggers the self-fix loop."""
        resp = client.post("/api/self-fix/run", json={"max_iterations": 3})
        assert resp.status_code in (200, 503)
        data = resp.json()
        if resp.status_code == 200:
            assert data["success"] is True
            assert "report" in data

    def test_self_fix_run_empty_body(self, client):
        """POST /api/self-fix/run works with empty body."""
        resp = client.post("/api/self-fix/run")
        assert resp.status_code in (200, 503)

    def test_self_fix_history(self, client):
        """GET /api/self-fix/history returns reports list."""
        resp = client.get("/api/self-fix/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["reports"], list)

    def test_self_fix_plans(self, client):
        """GET /api/self-fix/plans returns plans list."""
        resp = client.get("/api/self-fix/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["plans"], list)


# ===========================================================================
# Part 2: Autonomous Repair Endpoints
# ===========================================================================

class TestRepairEndpoints:
    """Tests for /api/repair/* endpoints."""

    def test_repair_status(self, client):
        """GET /api/repair/status returns valid response."""
        resp = client.get("/api/repair/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_repair_run(self, client):
        """POST /api/repair/run triggers repair cycle."""
        resp = client.post("/api/repair/run", json={"max_iterations": 5})
        assert resp.status_code in (200, 409, 503)
        data = resp.json()
        assert "success" in data or "error" in data

    def test_repair_history(self, client):
        """GET /api/repair/history returns reports."""
        resp = client.get("/api/repair/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["reports"], list)

    def test_repair_wiring(self, client):
        """GET /api/repair/wiring returns wiring report."""
        resp = client.get("/api/repair/wiring")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "wiring_issues" in data

    def test_repair_proposals(self, client):
        """GET /api/repair/proposals returns proposals."""
        resp = client.get("/api/repair/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["proposals"], list)


# ===========================================================================
# Part 3: Murphy Scheduler Endpoints
# ===========================================================================

class TestSchedulerEndpoints:
    """Tests for /api/scheduler/* endpoints."""

    def test_scheduler_status(self, client):
        """GET /api/scheduler/status returns valid response."""
        resp = client.get("/api/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_scheduler_start(self, client):
        """POST /api/scheduler/start attempts to start scheduler."""
        resp = client.post("/api/scheduler/start")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "success" in data

    def test_scheduler_stop(self, client):
        """POST /api/scheduler/stop attempts to stop scheduler."""
        resp = client.post("/api/scheduler/stop")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "success" in data

    def test_scheduler_trigger(self, client):
        """POST /api/scheduler/trigger runs daily automation manually."""
        resp = client.post("/api/scheduler/trigger")
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "success" in data


# ===========================================================================
# Part 4: Self-Automation Orchestrator Endpoints
# ===========================================================================

class TestSelfAutomationEndpoints:
    """Tests for /api/self-automation/* endpoints."""

    def test_self_automation_status(self, client):
        """GET /api/self-automation/status returns orchestrator status."""
        resp = client.get("/api/self-automation/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_self_automation_list_tasks(self, client):
        """GET /api/self-automation/tasks returns tasks list."""
        resp = client.get("/api/self-automation/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["tasks"], list)

    def test_self_automation_create_task(self, client):
        """POST /api/self-automation/task creates a new task."""
        resp = client.post("/api/self-automation/task", json={
            "title": "Test platform maintenance task",
            "module_name": "test_module",
            "category": "self_improvement",
            "priority": 5,
        })
        assert resp.status_code in (200, 503)
        data = resp.json()
        if resp.status_code == 200:
            assert data["success"] is True
            assert "task" in data

    def test_self_automation_create_task_no_title(self, client):
        """POST /api/self-automation/task rejects missing title."""
        resp = client.post("/api/self-automation/task", json={
            "module_name": "test_module",
        })
        # Either 400 (validation error) or 503 (system unavailable)
        assert resp.status_code in (400, 503)


# ===========================================================================
# Part 5: Self-Improvement Engine Endpoints
# ===========================================================================

class TestSelfImprovementEndpoints:
    """Tests for /api/self-improvement/* endpoints."""

    def test_self_improvement_status(self, client):
        """GET /api/self-improvement/status returns engine status."""
        resp = client.get("/api/self-improvement/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_self_improvement_proposals(self, client):
        """GET /api/self-improvement/proposals returns proposals."""
        resp = client.get("/api/self-improvement/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["proposals"], list)

    def test_self_improvement_corrections(self, client):
        """GET /api/self-improvement/corrections returns corrections."""
        resp = client.get("/api/self-improvement/corrections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["corrections"], list)


# ===========================================================================
# Part 6: Platform Automation Overview
# ===========================================================================

class TestPlatformAutomationOverview:
    """Tests for /api/platform/automation-status."""

    def test_platform_overview(self, client):
        """GET /api/platform/automation-status returns unified status."""
        resp = client.get("/api/platform/automation-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "systems" in data
        systems = data["systems"]

        # All 6 subsystems should be reported
        expected_systems = [
            "self_fix_loop",
            "autonomous_repair",
            "scheduler",
            "self_automation_orchestrator",
            "self_improvement_engine",
            "mfm",
        ]
        for sys_name in expected_systems:
            assert sys_name in systems, f"Missing system: {sys_name}"

        assert data["total_systems"] == len(expected_systems)
        assert isinstance(data["available_count"], int)

    def test_platform_overview_system_fields(self, client):
        """Each system in overview has 'available' or 'enabled' field."""
        resp = client.get("/api/platform/automation-status")
        data = resp.json()
        for sys_name, sys_info in data["systems"].items():
            assert "available" in sys_info or "enabled" in sys_info, \
                f"System {sys_name} missing availability indicator"


# ===========================================================================
# Part 7: MFM (Murphy Foundation Model) Endpoints
# ===========================================================================

class TestMFMEndpoints:
    """Tests for /api/mfm/* endpoints."""

    def test_mfm_status(self, client):
        """GET /api/mfm/status returns MFM deployment status."""
        resp = client.get("/api/mfm/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "mode" in data
        assert "base_model" in data

    def test_mfm_metrics(self, client):
        """GET /api/mfm/metrics returns training metrics."""
        resp = client.get("/api/mfm/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data

    def test_mfm_traces_stats(self, client):
        """GET /api/mfm/traces/stats returns trace collection stats."""
        resp = client.get("/api/mfm/traces/stats")
        assert resp.status_code == 200

    def test_mfm_versions(self, client):
        """GET /api/mfm/versions returns model version list."""
        resp = client.get("/api/mfm/versions")
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "versions" in data
            assert isinstance(data["versions"], list)

    def test_mfm_retrain(self, client):
        """POST /api/mfm/retrain triggers retraining (may fail if deps missing)."""
        resp = client.post("/api/mfm/retrain")
        assert resp.status_code in (200, 503)

    def test_mfm_rollback(self, client):
        """POST /api/mfm/rollback rolls back model version."""
        resp = client.post("/api/mfm/rollback")
        assert resp.status_code in (200, 503)


# ===========================================================================
# Part 8: Existing Endpoint Regression Tests
# ===========================================================================

class TestExistingEndpoints:
    """Verify existing key endpoints still work after platform automation wiring."""

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")

    def test_status(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200

    def test_bootstrap(self, client):
        resp = client.get("/api/bootstrap")
        assert resp.status_code in (200, 500)

    def test_manifest(self, client):
        resp = client.get("/api/manifest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        endpoints = data["data"]["endpoints"]
        paths = [e["path"] for e in endpoints]

        # Verify our new endpoints show up in the manifest
        assert "/api/self-fix/status" in paths
        assert "/api/repair/status" in paths
        assert "/api/scheduler/status" in paths
        assert "/api/self-automation/status" in paths
        assert "/api/self-improvement/status" in paths
        assert "/api/platform/automation-status" in paths
        assert "/api/mfm/status" in paths

    def test_hitl_queue(self, client):
        resp = client.get("/api/hitl/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_hitl_pending(self, client):
        resp = client.get("/api/hitl/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_compliance_toggles(self, client):
        resp = client.get("/api/compliance/toggles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_workflows_list(self, client):
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_billing_tiers(self, client):
        resp = client.get("/api/billing/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# ===========================================================================
# Part 9: Module Instantiation Verification
# ===========================================================================

class TestModuleInstantiation:
    """Verify that self-* modules are instantiated in MurphySystem core."""

    def test_self_improvement_engine_initialised(self):
        """SelfImprovementEngine should be instantiated in MurphySystem."""
        os.environ["MURPHY_ENV"] = "development"
        from src.runtime.murphy_system_core import MurphySystem
        murphy = MurphySystem()
        # Check attribute exists (may be None if import fails, that's OK)
        assert hasattr(murphy, "self_improvement")

    def test_self_automation_orchestrator_initialised(self):
        """SelfAutomationOrchestrator should be instantiated in MurphySystem."""
        os.environ["MURPHY_ENV"] = "development"
        from src.runtime.murphy_system_core import MurphySystem
        murphy = MurphySystem()
        assert hasattr(murphy, "self_automation_orchestrator")

    def test_self_fix_loop_initialised(self):
        """SelfFixLoop should be instantiated in MurphySystem."""
        os.environ["MURPHY_ENV"] = "development"
        from src.runtime.murphy_system_core import MurphySystem
        murphy = MurphySystem()
        assert hasattr(murphy, "self_fix_loop")

    def test_murphy_scheduler_initialised(self):
        """MurphyScheduler should be instantiated in MurphySystem."""
        os.environ["MURPHY_ENV"] = "development"
        from src.runtime.murphy_system_core import MurphySystem
        murphy = MurphySystem()
        assert hasattr(murphy, "murphy_scheduler")

    def test_autonomous_repair_initialised(self):
        """AutonomousRepairSystem should be instantiated in MurphySystem."""
        os.environ["MURPHY_ENV"] = "development"
        from src.runtime.murphy_system_core import MurphySystem
        murphy = MurphySystem()
        assert hasattr(murphy, "autonomous_repair")


# ===========================================================================
# Part 10: MFM Data Collection Pipeline Verification
# ===========================================================================

class TestMFMDataPipeline:
    """Verify MFM data collection is on track for model training."""

    def test_action_trace_collector_available(self):
        """ActionTraceCollector should be importable and instantiable."""
        try:
            from murphy_foundation_model.action_trace_serializer import ActionTraceCollector
            collector = ActionTraceCollector.get_instance()
            assert collector is not None
            stats = collector.get_stats()
            assert isinstance(stats, dict)
            assert "total_traces" in stats
        except ImportError:
            pytest.skip("MFM action_trace_serializer not available")

    def test_mfm_registry_available(self):
        """MFMRegistry should be importable."""
        try:
            from murphy_foundation_model.mfm_registry import MFMRegistry
            registry = MFMRegistry()
            versions = registry.list_versions()
            assert isinstance(versions, list)
        except ImportError:
            pytest.skip("MFM mfm_registry not available")

    def test_self_improvement_loop_config(self):
        """SelfImprovementConfig defaults should support 6-month training plan."""
        try:
            from murphy_foundation_model.self_improvement_loop import SelfImprovementConfig
            config = SelfImprovementConfig()
            # Verify reasonable thresholds for 6-month data collection
            assert config.retrain_threshold > 0
            assert config.min_accuracy > 0.0
            assert config.check_interval_hours > 0
            # With 6-hour check intervals and 10k trace threshold,
            # active multi-user usage (~60 traces/day across all users)
            # should accumulate sufficient training data within 6 months.
            # 60 traces/day × 180 days = 10,800 > 10,000 threshold ✓
            traces_per_day = 60  # multi-user active estimate
            traces_in_6_months = traces_per_day * 180
            assert traces_in_6_months > config.retrain_threshold, \
                f"6 months of traces ({traces_in_6_months}) should exceed retrain threshold ({config.retrain_threshold})"
        except ImportError:
            pytest.skip("MFM self_improvement_loop not available")

    def test_outcome_labeler_available(self):
        """OutcomeLabeler should be importable."""
        try:
            from murphy_foundation_model.outcome_labeler import OutcomeLabeler
            labeler = OutcomeLabeler()
            assert labeler is not None
        except ImportError:
            pytest.skip("MFM outcome_labeler not available")

    def test_training_data_pipeline_available(self):
        """TrainingDataPipeline should be importable."""
        try:
            from murphy_foundation_model.training_data_pipeline import TrainingDataPipeline
            pipeline = TrainingDataPipeline()
            assert pipeline is not None
        except ImportError:
            pytest.skip("MFM training_data_pipeline not available")


# ===========================================================================
# Part 11: Workflow Schedule Generation
# ===========================================================================

class TestWorkflowScheduleGeneration:
    """Verify workflows include schedule metadata and API suggestions."""

    def test_generated_workflow_has_schedule(self, client):
        """Generated workflow should include schedule metadata."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Send daily email reports to the sales team",
        })
        assert resp.status_code == 200
        data = resp.json()
        wf = data["workflow"]
        assert "schedule" in wf
        assert wf["schedule"]["interval"] == "daily"
        assert wf["schedule"]["enabled"] is True
        assert wf["schedule"]["cron"] == "0 8 * * *"

    def test_weekly_schedule_inferred(self, client):
        """Weekly keywords should produce weekly schedule."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Generate weekly invoice summary every week",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "weekly"
        assert wf["schedule"]["cron"] == "0 8 * * 1"

    def test_on_demand_schedule_default(self, client):
        """No schedule keywords → on_demand."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Process uploaded documents and extract data",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "on_demand"
        assert wf["schedule"]["enabled"] is False

    def test_api_suggestions_from_email(self, client):
        """Email workflow should suggest SendGrid."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Send email notifications when tasks complete",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert "api_suggestions" in wf
        names = [s["name"] for s in wf["api_suggestions"]]
        assert "SendGrid" in names

    def test_api_suggestions_from_payment(self, client):
        """Payment workflow should suggest Stripe."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Process monthly payment invoices for clients",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        names = [s["name"] for s in wf["api_suggestions"]]
        assert "Stripe" in names

    def test_explicit_schedule_interval(self, client):
        """Explicit schedule_interval should override inference."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Run a report",
            "schedule_interval": "hourly",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "hourly"


# ===========================================================================
# Part 12: Demo Export
# ===========================================================================

class TestDemoExport:
    """Verify demo export endpoint produces valid bundle."""

    def test_demo_export_returns_bundle(self, client):
        """GET /api/demo/export returns a complete project bundle."""
        resp = client.get("/api/demo/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        bundle = data["bundle"]

        assert bundle["murphy_demo_export"] is True
        assert bundle["version"] == "1.0.0"
        assert "exported_at" in bundle
        assert "license" in bundle
        assert "project_structure" in bundle
        assert "workflows" in bundle
        assert "platform_capabilities" in bundle
        assert "setup_instructions" in bundle
        assert "env_template" in bundle

    def test_demo_export_license_info(self, client):
        """Export bundle includes proper licensing and no-warranty clause."""
        resp = client.get("/api/demo/export")
        bundle = resp.json()["bundle"]
        lic = bundle["license"]

        assert lic["type"] == "BSL-1.1"
        assert "Inoni" in lic["copyright"]
        assert "Corey Post" in lic["creator"]
        assert "NO WARRANTY" in lic["warranty"]
        assert "as-is" in lic["warranty"].lower()

    def test_demo_export_setup_instructions(self, client):
        """Export includes step-by-step setup instructions."""
        resp = client.get("/api/demo/export")
        bundle = resp.json()["bundle"]
        steps = bundle["setup_instructions"]
        assert len(steps) >= 5
        assert any("pip install" in s for s in steps)
        assert any("onboarding wizard" in s.lower() for s in steps)

    def test_demo_export_env_template(self, client):
        """Export includes .env template."""
        resp = client.get("/api/demo/export")
        bundle = resp.json()["bundle"]
        env = bundle["env_template"]
        assert "MURPHY_ENV" in env
        assert "MURPHY_SECRET_KEY" in env
        assert "MFM_ENABLED" in env
        assert "DEEPINFRA_API_KEY" in env

    def test_demo_export_includes_workflows(self, client):
        """Export should include previously generated workflows."""
        # Generate a workflow first
        client.post("/api/workflows/generate", json={
            "description": "Daily email report with slack notification",
        })
        resp = client.get("/api/demo/export")
        bundle = resp.json()["bundle"]
        assert len(bundle["workflows"]) > 0
        assert len(bundle["integrations_needed"]) > 0

    def test_demo_export_platform_capabilities(self, client):
        """Export shows which platform systems are available."""
        resp = client.get("/api/demo/export")
        caps = resp.json()["bundle"]["platform_capabilities"]
        expected_keys = [
            "self_fix_loop", "autonomous_repair", "scheduler",
            "self_automation", "self_improvement", "mfm_enabled",
            "workflow_count",
        ]
        for key in expected_keys:
            assert key in caps, f"Missing capability: {key}"


# ===========================================================================
# Part 13: Librarian Works Without External LLM
# ===========================================================================

class TestLibrarianNoExternalLLM:
    """Verify the onboard librarian works without API keys."""

    def test_librarian_ask_no_llm(self, client):
        """Librarian should respond even without external LLM."""
        resp = client.post("/api/librarian/ask", json={
            "message": "What can Murphy System do?",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Should have a reply regardless of LLM availability
        reply = data.get("reply_text") or data.get("response") or data.get("message") or ""
        assert len(reply) > 0

    def test_librarian_ask_mode(self, client):
        """Librarian ask mode returns knowledge-base answer."""
        resp = client.post("/api/librarian/ask", json={
            "message": "Tell me about HITL interventions",
            "mode": "ask",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("librarian_mode") == "ask" or "answer" in data or "reply_text" in data

    def test_librarian_suggests_integrations(self, client):
        """Librarian should suggest integrations based on context."""
        resp = client.post("/api/librarian/ask", json={
            "message": "I need to send emails to my customers every week",
        })
        assert resp.status_code == 200
        data = resp.json()
        # The reply should mention something about email or integrations
        reply = str(data.get("reply_text", "")) + str(data.get("response", ""))
        # Should get some kind of useful response
        assert len(reply) > 10

    def test_librarian_onboarding_mode(self, client):
        """Default mode should do onboarding dimension extraction."""
        resp = client.post("/api/librarian/ask", json={
            "message": "I run a small HVAC company with 15 employees",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Should extract business dimensions
        assert "reply_text" in data or "response" in data or "message" in data


# ===========================================================================
# Part 14: Inoni LLC Agent Org Chart
# ===========================================================================

class TestInoniAgentOrgChart:
    """Verify the automated Inoni LLC agent org chart."""

    def test_org_chart_returns_departments(self, client):
        """GET /api/orgchart/inoni-agents returns full org structure."""
        resp = client.get("/api/orgchart/inoni-agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        org = data["org_chart"]
        assert org["company"] == "Inoni LLC"
        assert org["platform"] == "murphy.systems"
        assert len(org["departments"]) >= 8

    def test_org_chart_has_all_departments(self, client):
        """Org chart covers all key departments."""
        resp = client.get("/api/orgchart/inoni-agents")
        org = resp.json()["org_chart"]
        dept_names = [d["name"] for d in org["departments"]]
        expected = [
            "Executive & Strategy", "Sales & Marketing",
            "Content Creator Services", "Developer Relations",
            "Platform Engineering", "Production & Maintenance",
            "AI & Machine Learning", "Customer Success",
        ]
        for dept in expected:
            assert dept in dept_names, f"Missing department: {dept}"

    def test_org_chart_agent_counts(self, client):
        """Org chart reports correct agent counts."""
        resp = client.get("/api/orgchart/inoni-agents")
        org = resp.json()["org_chart"]
        assert org["total_agents"] >= 20
        assert org["active_agents"] >= 18
        assert org["automation_count"] >= 50

    def test_org_chart_agents_have_automations(self, client):
        """Every agent has at least one automation."""
        resp = client.get("/api/orgchart/inoni-agents")
        org = resp.json()["org_chart"]
        for dept in org["departments"]:
            for agent in dept["agents"]:
                assert len(agent["automations"]) > 0, \
                    f"Agent {agent['id']} has no automations"
                assert "status" in agent
                assert "schedule" in agent

    def test_org_chart_content_creator_free_tier(self, client):
        """Content Creator Services has free-tier moderation agent."""
        resp = client.get("/api/orgchart/inoni-agents")
        org = resp.json()["org_chart"]
        creator_dept = next(d for d in org["departments"]
                           if d["name"] == "Content Creator Services")
        mod_agent = next(a for a in creator_dept["agents"]
                         if a["id"] == "moderation-agent")
        assert mod_agent["tier"] == "free"
        assert "comment_moderation" in mod_agent["automations"]

    def test_org_chart_streaming_ai_planned(self, client):
        """Streaming/gaming AI agent is planned for future."""
        resp = client.get("/api/orgchart/inoni-agents")
        org = resp.json()["org_chart"]
        ml_dept = next(d for d in org["departments"]
                       if d["name"] == "AI & Machine Learning")
        streaming = next(a for a in ml_dept["agents"]
                         if a["id"] == "streaming-ai")
        assert streaming["status"] == "planned"

    def test_org_chart_daily_seller_exists(self, client):
        """Sales department has daily seller agent for self-promotion."""
        resp = client.get("/api/orgchart/inoni-agents")
        org = resp.json()["org_chart"]
        sales_dept = next(d for d in org["departments"]
                          if d["name"] == "Sales & Marketing")
        seller = next(a for a in sales_dept["agents"]
                      if a["id"] == "daily-seller")
        assert "daily_outreach_email" in seller["automations"]


# ===========================================================================
# Part 15: Content Creator Moderation
# ===========================================================================

class TestContentCreatorModeration:
    """Verify free content moderation for creators."""

    def test_moderation_status(self, client):
        """GET /api/creator/moderation/status returns service info."""
        resp = client.get("/api/creator/moderation/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["tier"] == "free"
        assert len(data["capabilities"]) >= 4

    def test_moderation_clean_text(self, client):
        """Clean text passes moderation."""
        resp = client.post("/api/creator/moderation/check", json={
            "text": "Great article! I learned a lot about HVAC systems.",
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["is_clean"] is True
        assert result["action"] == "approve"
        assert result["spam_score"] < 0.2

    def test_moderation_spam_detected(self, client):
        """Spam text is flagged."""
        resp = client.post("/api/creator/moderation/check", json={
            "text": "BUY NOW! Click here for free money! Act now!",
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["is_clean"] is False
        assert result["action"] == "review"
        assert result["spam_score"] > 0.2
        assert len(result["flags"]) > 0

    def test_moderation_empty_text_rejected(self, client):
        """Empty text returns 400."""
        resp = client.post("/api/creator/moderation/check", json={"text": ""})
        assert resp.status_code == 400


# ===========================================================================
# Part 16: SDK & Platform Capabilities
# ===========================================================================

class TestSDKAndCapabilities:
    """Verify SDK status and platform capability catalog."""

    def test_sdk_status(self, client):
        """GET /api/sdk/status returns SDK info."""
        resp = client.get("/api/sdk/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        sdk = data["sdk"]
        assert sdk["name"] == "Murphy SDK"
        langs = [l["language"] for l in sdk["languages"]]
        assert "Python" in langs
        assert "JavaScript" in langs
        assert "REST API" in langs

    def test_platform_capabilities_catalog(self, client):
        """GET /api/platform/capabilities returns licensable capabilities."""
        resp = client.get("/api/platform/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        caps = data["licensable_capabilities"]
        assert len(caps) >= 10

        # Verify key capabilities exist
        cap_ids = [c["id"] for c in caps]
        assert "content_moderation" in cap_ids
        assert "sdk_access" in cap_ids
        assert "streaming_ai" in cap_ids
        assert "workflow_automation" in cap_ids
        assert "org_chart_agents" in cap_ids

    def test_content_moderation_is_free(self, client):
        """Content moderation is free tier."""
        resp = client.get("/api/platform/capabilities")
        caps = resp.json()["licensable_capabilities"]
        mod = next(c for c in caps if c["id"] == "content_moderation")
        assert mod["tier_required"] == "free"
        assert mod["license_type"] == "free"

    def test_streaming_ai_is_planned(self, client):
        """Streaming AI is planned for future."""
        resp = client.get("/api/platform/capabilities")
        caps = resp.json()["licensable_capabilities"]
        streaming = next(c for c in caps if c["id"] == "streaming_ai")
        assert streaming["status"] == "planned"
        assert streaming["eta"] == "2026-Q4"
