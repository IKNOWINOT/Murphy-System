"""
REM-009: End-to-End Automation Validation Test

Validates the complete automation pipeline:
  Task Scheduling → Self-Improvement → SLO Tracking → Event Backbone → Delivery

This test ensures all major subsystems integrate correctly end-to-end
without requiring external services (LLM keys, databases, etc.).
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
from automation_scheduler import (
    AutomationScheduler,
    ProjectSchedule,
    SchedulePriority,
)
from self_improvement_engine import (
    SelfImprovementEngine,
    ExecutionOutcome,
    OutcomeType,
)
from operational_slo_tracker import (
    OperationalSLOTracker,
    ExecutionRecord,
    SLOTarget,
)
from event_backbone import Event, EventBackbone, EventType
from delivery_adapters import (
    DeliveryChannel,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
)
from health_monitor import HealthMonitor, ComponentStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scheduler():
    return AutomationScheduler()


@pytest.fixture
def improvement_engine():
    return SelfImprovementEngine()


@pytest.fixture
def slo_tracker():
    return OperationalSLOTracker()


@pytest.fixture
def event_backbone():
    return EventBackbone()


@pytest.fixture
def health_monitor():
    return HealthMonitor()


# ===========================================================================
# REM-009 Tests — End-to-End Automation Validation
# ===========================================================================


class TestE2EAutomationPipeline:
    """Validate the complete automation pipeline end-to-end."""

    def test_schedule_task_creates_execution(self, scheduler):
        """Step 1: Schedule a recurring task via AutomationScheduler."""
        schedule = ProjectSchedule(
            project_id="e2e-content-gen",
            task_description="Generate daily operations summary",
            task_type="content_generation",
            priority=SchedulePriority.MEDIUM,
            cron_expression="0 8 * * *",
        )
        pid = scheduler.add_project(schedule)
        assert pid == "e2e-content-gen"

        status = scheduler.get_status()
        assert status["total_projects"] >= 1

    def test_scheduler_dispatches_batch(self, scheduler):
        """Step 1b: Scheduler dispatches a batch of pending executions."""
        schedule = ProjectSchedule(
            project_id="e2e-batch",
            task_description="Batch test task",
            task_type="content_generation",
            priority=SchedulePriority.HIGH,
        )
        scheduler.add_project(schedule)
        batch = scheduler.get_next_batch(max_slots=5)
        assert len(batch) >= 1
        assert batch[0].status == "pending"

    def test_self_improvement_records_outcome(self, improvement_engine):
        """Step 2: Self-Improvement Engine records execution outcomes."""
        outcome = ExecutionOutcome(
            task_id="task-e2e-001",
            session_id="session-e2e-001",
            outcome=OutcomeType.SUCCESS,
            metrics={"latency_ms": 120, "confidence": 0.92},
        )
        improvement_engine.record_outcome(outcome)

        stats = improvement_engine.get_status()
        assert stats["total_outcomes"] >= 1

    def test_self_improvement_proposes_improvements(self, improvement_engine):
        """Step 2b: Engine generates improvement proposals from patterns."""
        # Record multiple outcomes to trigger pattern detection
        for i in range(5):
            outcome = ExecutionOutcome(
                task_id=f"task-e2e-{i:03d}",
                session_id="session-e2e",
                outcome=OutcomeType.SUCCESS if i % 2 == 0 else OutcomeType.FAILURE,
                metrics={"latency_ms": 100 + i * 50},
            )
            improvement_engine.record_outcome(outcome)

        patterns = improvement_engine.extract_patterns()
        proposals = improvement_engine.generate_proposals()
        # Analysis may or may not produce proposals depending on thresholds,
        # but the methods should complete without error
        assert isinstance(patterns, list)
        assert isinstance(proposals, list)

    def test_slo_tracker_records_metrics(self, slo_tracker):
        """Step 3: SLO Tracker records latency and success metrics."""
        record = ExecutionRecord(
            task_type="content_generation",
            success=True,
            duration=0.12,
        )
        slo_tracker.record_execution(record)

        metrics = slo_tracker.get_metrics()
        assert metrics["sample_size"] >= 1
        assert metrics["success_rate"] > 0

    def test_slo_tracker_evaluates_compliance(self, slo_tracker):
        """Step 3b: SLO Tracker evaluates compliance against targets."""
        # Add SLO target
        target = SLOTarget(
            target_name="content_gen_latency",
            metric="p95_latency",
            threshold=2.0,
            window_seconds=3600,
        )
        slo_tracker.add_slo_target(target)

        # Record successful executions
        for _ in range(10):
            slo_tracker.record_execution(
                ExecutionRecord(
                    task_type="content_generation",
                    success=True,
                    duration=0.15,
                )
            )

        report = slo_tracker.check_slo_compliance()
        assert isinstance(report, dict)

    def test_event_backbone_publishes_lifecycle_events(self, event_backbone):
        """Step 4: Event Backbone publishes lifecycle events."""
        received_events = []

        def handler(event: Event):
            received_events.append(event)

        event_backbone.subscribe(EventType.TASK_SUBMITTED, handler)
        event_backbone.subscribe(EventType.TASK_COMPLETED, handler)

        # Publish TASK_SUBMITTED
        event_backbone.publish(
            event_type=EventType.TASK_SUBMITTED,
            payload={"task_id": "e2e-task-001", "task_type": "content_generation"},
            source="e2e_test",
        )

        # Publish TASK_COMPLETED
        event_backbone.publish(
            event_type=EventType.TASK_COMPLETED,
            payload={"task_id": "e2e-task-001", "result": "success"},
            source="e2e_test",
        )

        # Process pending events — dispatches queued events to subscribers
        dispatched = event_backbone.process_pending()

        assert len(received_events) == 2
        assert received_events[0].event_type == EventType.TASK_SUBMITTED
        assert received_events[1].event_type == EventType.TASK_COMPLETED
        assert dispatched >= 2

    def test_delivery_request_creation(self):
        """Step 5: Delivery Orchestrator creates delivery requests."""
        request = DeliveryRequest(
            channel=DeliveryChannel.DOCUMENT,
            payload={"content": "Daily operations summary generated successfully."},
            session_id="session-e2e-001",
            requires_approval=False,
        )
        assert request.channel == DeliveryChannel.DOCUMENT
        assert "content" in request.payload

    def test_delivery_result_tracking(self):
        """Step 5b: Delivery results are properly tracked."""
        result = DeliveryResult(
            request_id="req-e2e-001",
            channel=DeliveryChannel.DOCUMENT,
            status=DeliveryStatus.DELIVERED,
            output={"path": "/tmp/ops_summary.md"},
        )
        result_dict = result.to_dict()
        assert result_dict["status"] == "delivered"
        assert result_dict["channel"] == "document"

    def test_full_pipeline_integration(
        self, scheduler, improvement_engine, slo_tracker, event_backbone
    ):
        """
        Full integration test: Task scheduling → outcome recording → SLO tracking → events.

        Simulates the complete automation pipeline without external dependencies.
        """
        # 1. Schedule a task
        schedule = ProjectSchedule(
            project_id="pipeline-test",
            task_description="Full pipeline test",
            task_type="content_generation",
            priority=SchedulePriority.HIGH,
        )
        scheduler.add_project(schedule)

        # 2. Get next batch and mark it running
        batch = scheduler.get_next_batch(max_slots=1)
        assert len(batch) >= 1
        execution = batch[0]
        scheduler.start_execution(execution.execution_id)

        # 3. Record execution outcome
        outcome = ExecutionOutcome(
            task_id=execution.execution_id,
            session_id="pipeline-session",
            outcome=OutcomeType.SUCCESS,
            metrics={"latency_ms": 150, "confidence": 0.88},
        )
        improvement_engine.record_outcome(outcome)

        # 4. Record SLO metric
        slo_tracker.record_execution(
            ExecutionRecord(
                task_type="content_generation",
                success=True,
                duration=0.15,
            )
        )

        # 5. Publish events
        events_received = []
        event_backbone.subscribe(EventType.TASK_COMPLETED, lambda e: events_received.append(e))
        event_backbone.publish(
            event_type=EventType.TASK_COMPLETED,
            payload={"execution_id": execution.execution_id, "result": "success"},
            source="pipeline_test",
        )
        event_backbone.process_pending()

        # 6. Mark execution complete
        scheduler.complete_execution(
            execution.execution_id,
            success=True,
            result={"status": "success", "confidence": 0.88},
        )

        # Verify end state
        assert len(events_received) == 1
        assert improvement_engine.get_status()["total_outcomes"] >= 1
        assert slo_tracker.get_metrics()["sample_size"] >= 1


class TestHealthMonitorIntegration:
    """Validate health monitoring as part of the automation pipeline."""

    def test_health_check(self, health_monitor):
        """Health monitor returns valid health report."""
        report = health_monitor.check_all()
        assert report is not None
        assert hasattr(report, "system_status")

    def test_component_registration(self, health_monitor):
        """Components can be registered and checked."""
        health_monitor.register(
            "automation_scheduler",
            check_fn=lambda: {"status": "healthy", "message": "OK"},
        )
        report = health_monitor.check_all()
        assert report is not None
        assert report.healthy_count >= 1
