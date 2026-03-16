"""
Tests for DEV-005: DependencyAuditEngine.

Validates dependency registration, advisory ingestion, audit cycles,
version-range matching, persistence integration, and EventBackbone
event publishing.

Design Label: TEST-014 / DEV-005
Owner: QA Team
"""

import os
import pytest


from dependency_audit_engine import (
    DependencyAuditEngine,
    Dependency,
    Advisory,
    AuditFinding,
    DependencyAuditReport,
    _in_range,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


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
def engine():
    return DependencyAuditEngine()


@pytest.fixture
def wired_engine(pm, backbone):
    return DependencyAuditEngine(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Version range helper
# ------------------------------------------------------------------

class TestVersionRange:
    def test_wildcard(self):
        assert _in_range("1.2.3", "*") is True

    def test_exact_match(self):
        assert _in_range("1.0.0", "==1.0.0") is True
        assert _in_range("1.0.1", "==1.0.0") is False

    def test_gte_lt(self):
        assert _in_range("1.3.0", ">=1.0,<2.0") is True
        assert _in_range("2.0.0", ">=1.0,<2.0") is False
        assert _in_range("0.9.0", ">=1.0,<2.0") is False

    def test_not_equal(self):
        assert _in_range("1.0.0", "!=1.0.0") is False
        assert _in_range("1.0.1", "!=1.0.0") is True


# ------------------------------------------------------------------
# Dependency registration
# ------------------------------------------------------------------

class TestDependencyRegistration:
    def test_register(self, engine):
        dep = engine.register_dependency("requests", "2.28.0")
        assert dep.dep_id.startswith("dep-")
        assert dep.name == "requests"
        assert dep.version == "2.28.0"

    def test_register_normalises_name(self, engine):
        dep = engine.register_dependency("  Requests  ", "1.0.0")
        assert dep.name == "requests"

    def test_remove_dependency(self, engine):
        dep = engine.register_dependency("flask", "2.0.0")
        assert engine.remove_dependency(dep.dep_id) is True
        assert engine.remove_dependency(dep.dep_id) is False

    def test_bounded(self):
        eng = DependencyAuditEngine(max_dependencies=3)
        for i in range(5):
            eng.register_dependency(f"pkg{i}", "1.0.0")
        status = eng.get_status()
        assert status["total_dependencies"] <= 4


# ------------------------------------------------------------------
# Advisory ingestion
# ------------------------------------------------------------------

class TestAdvisoryIngestion:
    def test_ingest(self, engine):
        adv = engine.ingest_advisory("CVE-2023-0001", "requests", ">=2.0,<2.29")
        assert adv.advisory_id.startswith("adv-")
        assert adv.cve_id == "CVE-2023-0001"

    def test_bounded(self):
        eng = DependencyAuditEngine(max_advisories=5)
        for i in range(10):
            eng.ingest_advisory(f"CVE-{i}", "pkg", "*")
        status = eng.get_status()
        assert status["total_advisories"] <= 6


# ------------------------------------------------------------------
# Audit cycle
# ------------------------------------------------------------------

class TestAuditCycle:
    def test_finds_vulnerability(self, engine):
        engine.register_dependency("requests", "2.28.0")
        engine.ingest_advisory("CVE-2023-0001", "requests", ">=2.0,<2.29", severity="high")
        report = engine.run_audit_cycle()
        assert report.total_findings == 1
        assert report.high_count == 1

    def test_no_match_different_package(self, engine):
        engine.register_dependency("flask", "2.0.0")
        engine.ingest_advisory("CVE-2023-0001", "requests", "*")
        report = engine.run_audit_cycle()
        assert report.total_findings == 0

    def test_no_match_outside_range(self, engine):
        engine.register_dependency("requests", "3.0.0")
        engine.ingest_advisory("CVE-2023-0001", "requests", ">=2.0,<2.29")
        report = engine.run_audit_cycle()
        assert report.total_findings == 0

    def test_report_to_dict(self, engine):
        engine.register_dependency("pkg", "1.0.0")
        engine.ingest_advisory("CVE-1", "pkg", "*")
        report = engine.run_audit_cycle()
        d = report.to_dict()
        assert "report_id" in d
        assert "findings" in d

    def test_multiple_findings(self, engine):
        engine.register_dependency("requests", "2.28.0")
        engine.ingest_advisory("CVE-1", "requests", "*", severity="critical")
        engine.ingest_advisory("CVE-2", "requests", "*", severity="medium")
        report = engine.run_audit_cycle()
        assert report.total_findings == 2
        assert report.critical_count == 1
        assert report.medium_count == 1


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_engine, pm):
        wired_engine.register_dependency("pkg", "1.0.0")
        wired_engine.ingest_advisory("CVE-1", "pkg", "*")
        report = wired_engine.run_audit_cycle()
        loaded = pm.load_document(report.report_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_audit_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_engine.register_dependency("pkg", "1.0.0")
        wired_engine.ingest_advisory("CVE-1", "pkg", "*")
        wired_engine.run_audit_cycle()
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, engine):
        engine.register_dependency("pkg", "1.0.0")
        s = engine.get_status()
        assert s["total_dependencies"] == 1
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_engine):
        s = wired_engine.get_status()
        assert s["persistence_attached"] is True
        assert s["backbone_attached"] is True
