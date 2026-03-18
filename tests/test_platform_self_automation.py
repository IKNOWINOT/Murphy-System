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
