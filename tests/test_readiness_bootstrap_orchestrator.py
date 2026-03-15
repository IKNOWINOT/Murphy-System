"""
Tests for ORCH-002: ReadinessBootstrapOrchestrator.

Validates bootstrap execution, subsystem seeding, idempotency,
skipping unattached modules, persistence, and EventBackbone integration.

Design Label: TEST-030 / ORCH-002
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from readiness_bootstrap_orchestrator import (
    ReadinessBootstrapOrchestrator,
    BootstrapTaskStatus,
    BootstrapTask,
    BootstrapReport,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType
from kpi_tracker import KPITracker
from automation_rbac_controller import AutomationRBACController
from tenant_resource_governor import TenantResourceGovernor
from alert_rules_engine import AlertRulesEngine
from risk_mitigation_tracker import RiskMitigationTracker


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def bootstrapper():
    return ReadinessBootstrapOrchestrator()


@pytest.fixture
def full_bootstrapper(pm, backbone):
    return ReadinessBootstrapOrchestrator(
        persistence_manager=pm,
        event_backbone=backbone,
        kpi_tracker=KPITracker(),
        rbac_controller=AutomationRBACController(),
        tenant_governor=TenantResourceGovernor(),
        alert_engine=AlertRulesEngine(),
        risk_tracker=RiskMitigationTracker(),
    )


# ------------------------------------------------------------------
# Bootstrap execution
# ------------------------------------------------------------------

class TestBootstrapExecution:
    def test_all_skipped_when_unattached(self, bootstrapper):
        report = bootstrapper.run_bootstrap()
        # 5 controller-dependent tasks skip; domain_gates is self-contained
        assert report.skipped_count == 5
        assert report.completed_count == 1

    def test_full_bootstrap_succeeds(self, full_bootstrapper):
        report = full_bootstrapper.run_bootstrap()
        assert report.completed_count == 6
        assert report.failed_count == 0

    def test_bootstrap_sets_flag(self, full_bootstrapper):
        assert full_bootstrapper.is_bootstrapped() is False
        full_bootstrapper.run_bootstrap()
        assert full_bootstrapper.is_bootstrapped() is True

    def test_report_to_dict(self, bootstrapper):
        report = bootstrapper.run_bootstrap()
        d = report.to_dict()
        assert "report_id" in d
        assert "tasks" in d
        assert len(d["tasks"]) == 6


# ------------------------------------------------------------------
# Subsystem seeding
# ------------------------------------------------------------------

class TestSubsystemSeeding:
    def test_kpi_baselines_seeded(self, full_bootstrapper):
        report = full_bootstrapper.run_bootstrap()
        kpi_task = [t for t in report.tasks if t.subsystem == "kpi_tracker"]
        assert len(kpi_task) == 1
        assert kpi_task[0].status == BootstrapTaskStatus.COMPLETED
        assert "8" in kpi_task[0].message

    def test_rbac_roles_seeded(self, full_bootstrapper):
        report = full_bootstrapper.run_bootstrap()
        rbac_task = [t for t in report.tasks if t.subsystem == "rbac_controller"]
        assert len(rbac_task) == 1
        assert rbac_task[0].status == BootstrapTaskStatus.COMPLETED

    def test_tenant_limits_seeded(self, full_bootstrapper):
        report = full_bootstrapper.run_bootstrap()
        tenant_task = [t for t in report.tasks if t.subsystem == "tenant_governor"]
        assert len(tenant_task) == 1
        assert tenant_task[0].status == BootstrapTaskStatus.COMPLETED


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, full_bootstrapper, pm):
        report = full_bootstrapper.run_bootstrap()
        loaded = pm.load_document(report.report_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_bootstrap_publishes_event(self, full_bootstrapper, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        full_bootstrapper.run_bootstrap()
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status_unattached(self, bootstrapper):
        s = bootstrapper.get_status()
        assert s["bootstrapped"] is False
        assert s["kpi_attached"] is False

    def test_status_attached(self, full_bootstrapper):
        s = full_bootstrapper.get_status()
        assert s["kpi_attached"] is True
        assert s["rbac_attached"] is True
        assert s["tenant_attached"] is True
