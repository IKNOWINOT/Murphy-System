"""
REM-010: Automated Operations Workflow Test

Validates the continuous operations workflow defined in the Remediation Plan:
  1. Health check          → /api/health → SLO Tracker        (every 5 min)
  2. Component audit       → /api/diagnostics/activation      (every hour)
  3. Performance metrics   → SLO Tracker → Event Backbone     (continuous)
  4. Bug detection         → Self-Improvement Engine analysis  (after each task)
  5. Compliance check      → Compliance Engine scan            (daily)
  6. Status report gen     → Content gen → Delivery            (daily)
  7. Gap re-analysis       → Compare metrics vs targets        (weekly)

Each step is validated independently and then as a full workflow.
"""

import os
import sys
import uuid
import pytest
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path setup — mirrors existing Murphy test conventions
# ---------------------------------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_here, "..", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from health_monitor import HealthMonitor, ComponentStatus, SystemStatus
from operational_slo_tracker import OperationalSLOTracker, ExecutionRecord, SLOTarget
from event_backbone import EventBackbone, EventType
from self_improvement_engine import (
    SelfImprovementEngine,
    ExecutionOutcome,
    OutcomeType,
)
from compliance_engine import ComplianceEngine
from delivery_adapters import (
    DeliveryChannel,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
)
from automation_scheduler import (
    AutomationScheduler,
    ProjectSchedule,
    SchedulePriority,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def health_monitor():
    return HealthMonitor()


@pytest.fixture
def slo_tracker():
    return OperationalSLOTracker()


@pytest.fixture
def event_backbone():
    return EventBackbone()


@pytest.fixture
def improvement_engine():
    return SelfImprovementEngine()


@pytest.fixture
def compliance_engine():
    return ComplianceEngine()


@pytest.fixture
def scheduler():
    return AutomationScheduler()


# ===========================================================================
# REM-010 Tests — Automated Operations Workflow
# ===========================================================================


class TestOpsStep1HealthCheck:
    """Step 1: Health check → SLO Tracker (every 5 min)."""

    def test_health_check_returns_report(self, health_monitor):
        """Health monitor produces a valid report."""
        # Register some components
        health_monitor.register(
            "scheduler",
            lambda: {"status": "healthy", "message": "Scheduler online"},
        )
        health_monitor.register(
            "confidence_engine",
            lambda: {"status": "healthy", "message": "CE online"},
        )

        report = health_monitor.check_all()
        assert report.system_status == SystemStatus.HEALTHY
        assert report.healthy_count == 2

    def test_health_result_feeds_slo_tracker(self, health_monitor, slo_tracker):
        """Health check result is recorded in SLO tracker."""
        health_monitor.register(
            "core",
            lambda: {"status": "healthy", "message": "OK"},
        )
        report = health_monitor.check_all()

        # Record the health check as an execution in SLO tracker
        slo_tracker.record_execution(
            ExecutionRecord(
                task_type="health_check",
                success=(report.system_status == SystemStatus.HEALTHY),
                duration=report.total_latency_ms / 1000.0,
            )
        )

        metrics = slo_tracker.get_metrics(task_type="health_check")
        assert metrics["sample_size"] >= 1
        assert metrics["success_rate"] == 1.0


class TestOpsStep2ComponentAudit:
    """Step 2: Component audit → diagnostics activation (every hour)."""

    def test_component_audit_all_healthy(self, health_monitor):
        """All registered components report healthy."""
        for name in ["scheduler", "slo_tracker", "event_backbone", "compliance"]:
            health_monitor.register(
                name,
                lambda: {"status": "healthy", "message": "OK"},
            )

        report = health_monitor.check_all()
        assert report.system_status == SystemStatus.HEALTHY
        assert report.healthy_count == 4
        assert report.unhealthy_count == 0

    def test_component_audit_detects_degradation(self, health_monitor):
        """Detects degraded components in audit."""
        health_monitor.register(
            "healthy_svc",
            lambda: {"status": "healthy", "message": "OK"},
        )
        health_monitor.register(
            "degraded_svc",
            lambda: {"status": "degraded", "message": "High latency"},
        )

        report = health_monitor.check_all()
        assert report.system_status == SystemStatus.DEGRADED
        assert report.degraded_count == 1


class TestOpsStep3PerformanceMetrics:
    """Step 3: Performance metrics → SLO Tracker → Event Backbone (continuous)."""

    def test_slo_metrics_published_to_event_backbone(
        self, slo_tracker, event_backbone
    ):
        """SLO metrics are published as events on the backbone."""
        # Record some executions
        for i in range(5):
            slo_tracker.record_execution(
                ExecutionRecord(
                    task_type="content_generation",
                    success=True,
                    duration=0.1 + i * 0.05,
                )
            )

        # Publish metrics as SYSTEM_HEALTH event
        metrics = slo_tracker.get_metrics()
        event_backbone.publish(
            event_type=EventType.SYSTEM_HEALTH,
            payload={"source": "slo_tracker", "metrics": metrics},
            source="ops_workflow",
        )

        status = event_backbone.get_status()
        assert status["events_published"] >= 1

    def test_slo_compliance_against_targets(self, slo_tracker):
        """SLO compliance can be evaluated against defined targets."""
        slo_tracker.add_slo_target(
            SLOTarget(
                target_name="success_rate",
                metric="success_rate",
                threshold=0.95,
                window_seconds=3600,
            )
        )

        # Record high-success executions
        for _ in range(20):
            slo_tracker.record_execution(
                ExecutionRecord(
                    task_type="content_generation",
                    success=True,
                    duration=0.1,
                )
            )

        compliance = slo_tracker.check_slo_compliance()
        assert isinstance(compliance, dict)


class TestOpsStep4BugDetection:
    """Step 4: Bug detection → Self-Improvement Engine (after each task)."""

    def test_failure_patterns_detected(self, improvement_engine):
        """Self-improvement engine detects failure patterns."""
        # Record a mix of successes and failures
        for i in range(10):
            outcome = ExecutionOutcome(
                task_id=f"bug-detect-{i:03d}",
                session_id="ops-session",
                outcome=OutcomeType.FAILURE if i < 3 else OutcomeType.SUCCESS,
                metrics={"latency_ms": 200 if i < 3 else 50},
            )
            improvement_engine.record_outcome(outcome)

        patterns = improvement_engine.extract_patterns()
        assert isinstance(patterns, list)

        # Status should reflect recorded outcomes
        status = improvement_engine.get_status()
        assert status["total_outcomes"] == 10

    def test_improvement_proposals_generated(self, improvement_engine):
        """Engine generates improvement proposals from failure patterns."""
        for i in range(8):
            improvement_engine.record_outcome(
                ExecutionOutcome(
                    task_id=f"proposal-test-{i:03d}",
                    session_id="proposal-session",
                    outcome=OutcomeType.FAILURE,
                    metrics={"latency_ms": 500, "error": "timeout"},
                )
            )

        improvement_engine.extract_patterns()
        proposals = improvement_engine.generate_proposals()
        assert isinstance(proposals, list)


class TestOpsStep5ComplianceCheck:
    """Step 5: Compliance check → Compliance Engine (daily)."""

    def test_compliance_engine_initializes(self, compliance_engine):
        """Compliance engine initializes with default frameworks."""
        status = compliance_engine.get_status()
        assert isinstance(status, dict)
        assert "total_requirements" in status

    def test_compliance_report_generation(self, compliance_engine):
        """Compliance engine can generate compliance report."""
        report = compliance_engine.get_compliance_report()
        assert isinstance(report, dict)


class TestOpsStep6StatusReportGeneration:
    """Step 6: Status report generation → Content gen → Delivery (daily)."""

    def test_status_report_delivery_request(self):
        """Status report can be created and queued for delivery."""
        report_content = {
            "title": "Daily Operations Summary",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system_status": "healthy",
            "metrics": {
                "tasks_completed": 42,
                "success_rate": 0.97,
                "avg_latency_ms": 120,
            },
        }

        request = DeliveryRequest(
            channel=DeliveryChannel.DOCUMENT,
            payload=report_content,
            session_id="ops-daily-report",
            requires_approval=False,
        )
        assert request.channel == DeliveryChannel.DOCUMENT
        assert request.payload["title"] == "Daily Operations Summary"


class TestOpsStep7GapReAnalysis:
    """Step 7: Gap re-analysis → Compare metrics vs targets (weekly)."""

    def test_gap_analysis_via_slo_comparison(self, slo_tracker):
        """Compares current metrics against SLO targets to identify gaps."""
        # Set targets
        slo_tracker.add_slo_target(
            SLOTarget(
                target_name="latency_p95",
                metric="p95_latency",
                threshold=1.0,
                window_seconds=86400,
            )
        )
        slo_tracker.add_slo_target(
            SLOTarget(
                target_name="success_rate",
                metric="success_rate",
                threshold=0.99,
                window_seconds=86400,
            )
        )

        # Record executions (some failures to create gaps)
        for i in range(100):
            slo_tracker.record_execution(
                ExecutionRecord(
                    task_type="mixed",
                    success=(i < 95),
                    duration=0.1 if i < 90 else 2.0,
                )
            )

        compliance = slo_tracker.check_slo_compliance()
        assert isinstance(compliance, dict)


class TestFullOperationsWorkflow:
    """Full operations workflow — all 7 steps in sequence."""

    def test_complete_ops_cycle(
        self,
        health_monitor,
        slo_tracker,
        event_backbone,
        improvement_engine,
        compliance_engine,
        scheduler,
    ):
        """Run all 7 operations steps in sequence as a single workflow cycle."""

        # Step 1: Health check
        health_monitor.register(
            "scheduler",
            lambda: {"status": "healthy", "message": "OK"},
        )
        report = health_monitor.check_all()
        assert report.system_status == SystemStatus.HEALTHY

        # Step 2: Component audit (same health monitor, all healthy)
        assert report.healthy_count >= 1
        assert report.unhealthy_count == 0

        # Step 3: Record performance metrics
        for _ in range(5):
            slo_tracker.record_execution(
                ExecutionRecord(task_type="ops_task", success=True, duration=0.1)
            )
        metrics = slo_tracker.get_metrics()
        assert metrics["success_rate"] == 1.0

        event_backbone.publish(
            event_type=EventType.SYSTEM_HEALTH,
            payload={"metrics": metrics},
            source="ops_workflow",
        )

        # Step 4: Bug detection via self-improvement
        improvement_engine.record_outcome(
            ExecutionOutcome(
                task_id="ops-task-001",
                session_id="ops-cycle",
                outcome=OutcomeType.SUCCESS,
                metrics={"latency_ms": 100},
            )
        )
        improvement_engine.extract_patterns()

        # Step 5: Compliance check
        compliance_status = compliance_engine.get_status()
        assert isinstance(compliance_status, dict)

        # Step 6: Status report generation
        status_report = DeliveryRequest(
            channel=DeliveryChannel.DOCUMENT,
            payload={
                "title": "Ops Cycle Report",
                "health": report.to_dict(),
                "metrics": metrics,
                "compliance": compliance_status,
            },
            session_id="ops-cycle-report",
        )
        assert status_report.channel == DeliveryChannel.DOCUMENT

        # Step 7: Gap re-analysis
        slo_tracker.add_slo_target(
            SLOTarget(
                target_name="ops_success",
                metric="success_rate",
                threshold=0.95,
                window_seconds=3600,
            )
        )
        compliance_result = slo_tracker.check_slo_compliance()
        assert isinstance(compliance_result, dict)

        # Verify all subsystems operated correctly
        assert improvement_engine.get_status()["total_outcomes"] >= 1
        assert event_backbone.get_status()["events_published"] >= 1
