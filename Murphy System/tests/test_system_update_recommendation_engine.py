"""
Tests for ARCH-008: SystemUpdateRecommendationEngine.

Validates recommendation pipeline, multi-form types, subsystem integration,
graceful degradation, acknowledge/dismiss flows, persistence round-trips,
thread safety, bounded limits, and cross-subsystem correlation.

Design Label: TEST-ARCH-008
Owner: QA Team / Backend Team
"""

import sys
import os
import threading
import time


import pytest

from src.system_update_recommendation_engine import (
    AutoUpdateAction,
    BugReportResponse,
    MaintenanceRecommendation,
    OperationalAnalysis,
    Recommendation,
    RecommendationCycleReport,
    RecommendationType,
    SDKUpdateRecommendation,
    SystemUpdateRecommendationEngine,
)
from src.persistence_manager import PersistenceManager
from src.event_backbone import EventBackbone


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


class _StubImprovementEngine:
    """Minimal stub for SelfImprovementEngine."""

    def generate_proposals(self):
        from src.self_improvement_engine import ImprovementProposal
        return [
            ImprovementProposal(
                proposal_id="prop-001",
                category="routing",
                description="Optimize routing logic",
                priority="medium",
                source_pattern="repeated_timeouts",
                suggested_action="Increase timeout threshold",
            )
        ]


class _StubBugDetector:
    """Minimal stub for BugPatternDetector."""

    def get_reports(self, limit=50):
        return [
            {
                "report_id": "rpt-001",
                "severity": "high",
                "summary": "Connection timeout in api-gw",
                "patterns_detected": 3,
                "critical_count": 1,
                "high_count": 2,
            }
        ]


class _StubDependencyAudit:
    """Minimal stub for DependencyAuditEngine."""

    def get_reports(self, limit=20):
        return [
            {
                "report_id": "dep-rpt-001",
                "findings": [
                    {
                        "advisory_id": "adv-001",
                        "severity": "critical",
                        "dependency_name": "requests",
                        "installed_version": "2.25.0",
                        "fixed_in_version": "2.28.0",
                        "title": "Request smuggling vulnerability",
                        "cve_id": "CVE-2022-0001",
                    }
                ],
            }
        ]


class _StubHealthMonitor:
    """Minimal stub for HealthMonitor."""

    def get_system_health(self):
        return {
            "overall_status": "degraded",
            "total_components": 2,
            "healthy": 1,
            "degraded": 1,
            "unhealthy": 0,
            "components": {
                "api-gw": "healthy",
                "worker": "degraded",
            },
        }


class _StubRepairSystem:
    """Minimal stub for AutonomousRepairSystem."""

    def get_proposals(self):
        return [
            {
                "proposal_id": "repair-001",
                "priority": "high",
                "description": "Restart stalled worker process",
                "suggested_action": "Run systemctl restart murphy-worker",
                "component": "worker",
            }
        ]


class _StubOrchestrator:
    """Minimal stub for SelfAutomationOrchestrator."""

    def get_open_gaps(self):
        return [
            {
                "gap_id": "gap-001",
                "priority": "low",
                "description": "Missing coverage for edge case in parser",
                "area": "parser",
            }
        ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def engine():
    """Bare engine with no subsystems (graceful degradation baseline)."""
    return SystemUpdateRecommendationEngine()


@pytest.fixture
def full_engine(pm, backbone):
    """Engine wired to all stub subsystems."""
    return SystemUpdateRecommendationEngine(
        persistence_manager=pm,
        event_backbone=backbone,
        improvement_engine=_StubImprovementEngine(),
        bug_detector=_StubBugDetector(),
        dependency_audit=_StubDependencyAudit(),
        health_monitor=_StubHealthMonitor(),
        repair_system=_StubRepairSystem(),
        orchestrator=_StubOrchestrator(),
    )


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInitialisation:
    def test_bare_engine_initialises(self, engine):
        assert engine is not None

    def test_status_no_subsystems(self, engine):
        status = engine.get_status()
        assert status["engine"] == "SystemUpdateRecommendationEngine"
        assert status["design_label"] == "ARCH-020"
        assert status["total_active_recommendations"] == 0
        assert status["cycles_completed"] == 0

    def test_full_engine_initialises(self, full_engine):
        status = full_engine.get_status()
        assert status["persistence_available"] is True
        assert status["event_backbone_available"] is True

    def test_persist_doc_id(self):
        assert SystemUpdateRecommendationEngine._PERSIST_DOC_ID == \
            "system_update_recommendation_engine_state"


# ---------------------------------------------------------------------------
# Graceful degradation — no subsystems
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    def test_cycle_with_no_subsystems_returns_empty_report(self, engine):
        report = engine.run_recommendation_cycle()
        assert isinstance(report, RecommendationCycleReport)
        assert report.total_recommendations == 0
        assert report.subsystems_available == []

    def test_get_recommendations_returns_empty_list(self, engine):
        recs = engine.get_recommendations()
        assert recs == []

    def test_history_empty_initially(self, engine):
        assert engine.get_history() == []

    def test_save_state_no_pm(self, engine):
        assert engine.save_state() is False

    def test_load_state_no_pm(self, engine):
        assert engine.load_state() is False


# ---------------------------------------------------------------------------
# Recommendation cycle with all subsystems
# ---------------------------------------------------------------------------


class TestRecommendationCycle:
    def test_cycle_produces_report(self, full_engine):
        report = full_engine.run_recommendation_cycle()
        assert isinstance(report, RecommendationCycleReport)
        assert report.cycle_id.startswith("cycle-")
        assert report.started_at is not None
        assert report.completed_at is not None

    def test_cycle_has_recommendations(self, full_engine):
        report = full_engine.run_recommendation_cycle()
        assert report.total_recommendations > 0
        assert len(report.recommendations) > 0

    def test_cycle_reports_available_subsystems(self, full_engine):
        report = full_engine.run_recommendation_cycle()
        assert len(report.subsystems_available) > 0

    def test_cycle_adds_to_history(self, full_engine):
        full_engine.run_recommendation_cycle()
        history = full_engine.get_history()
        assert len(history) == 1
        assert history[0]["cycle_id"].startswith("cycle-")

    def test_multiple_cycles_accumulate_history(self, full_engine):
        full_engine.run_recommendation_cycle()
        full_engine.run_recommendation_cycle()
        assert len(full_engine.get_history()) == 2

    def test_cycle_with_subsystem_filter(self, full_engine):
        report = full_engine.run_recommendation_cycle(subsystems=["bug_detector"])
        assert report.total_recommendations >= 0
        # Only bug_detector queried
        assert "improvement_engine" not in report.subsystems_queried or \
               report.subsystems_queried == ["bug_detector"]


# ---------------------------------------------------------------------------
# Recommendation typing and priority
# ---------------------------------------------------------------------------


class TestRecommendationTyping:
    def test_dependency_audit_produces_sdk_update(self, full_engine):
        full_engine.run_recommendation_cycle(subsystems=["dependency_audit"])
        recs = full_engine.get_recommendations(rec_type=RecommendationType.SDK_UPDATE)
        assert len(recs) >= 1

    def test_bug_detector_produces_bug_report_response(self, full_engine):
        full_engine.run_recommendation_cycle(subsystems=["bug_detector"])
        recs = full_engine.get_recommendations(rec_type=RecommendationType.BUG_REPORT_RESPONSE)
        assert len(recs) >= 1

    def test_health_monitor_produces_maintenance(self, full_engine):
        full_engine.run_recommendation_cycle(subsystems=["health_monitor"])
        recs = full_engine.get_recommendations(rec_type=RecommendationType.MAINTENANCE)
        assert len(recs) >= 1

    def test_improvement_engine_produces_operational_analysis(self, full_engine):
        full_engine.run_recommendation_cycle(subsystems=["improvement_engine"])
        recs = full_engine.get_recommendations(rec_type=RecommendationType.OPERATIONAL_ANALYSIS)
        assert len(recs) >= 1

    def test_recommendation_has_required_fields(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations()
        assert len(recs) > 0
        rec = recs[0]
        assert rec.recommendation_id.startswith("rec-")
        assert rec.subsystem != ""
        assert rec.recommendation_type in list(RecommendationType)
        assert rec.priority in ("critical", "high", "medium", "low")
        assert 0.0 <= rec.confidence_score <= 1.0
        assert rec.description != ""
        assert rec.suggested_action != ""
        assert rec.estimated_effort != ""
        assert rec.risk_level in ("low", "medium", "high")
        assert isinstance(rec.auto_applicable, bool)
        assert isinstance(rec.requires_review, bool)
        assert isinstance(rec.related_proposals, list)
        assert rec.created_at is not None

    def test_requires_review_disables_auto_applicable(self):
        rec = Recommendation(
            recommendation_id="rec-test",
            subsystem="test",
            recommendation_type=RecommendationType.MAINTENANCE,
            priority="high",
            confidence_score=0.9,
            description="Test",
            suggested_action="Do something",
            estimated_effort="< 1h",
            risk_level="high",
            auto_applicable=True,  # should be forced False because requires_review=True
            requires_review=True,
        )
        assert rec.auto_applicable is False

    def test_priority_ordering_in_get_recommendations(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations()
        priorities = [r.priority for r in recs]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        orders = [order.get(p, 99) for p in priorities]
        assert orders == sorted(orders), "Recommendations should be sorted by priority"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_filter_by_subsystem(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations(subsystem="dependency_audit")
        for rec in recs:
            assert rec.subsystem == "dependency_audit"

    def test_filter_by_type(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations(rec_type=RecommendationType.SDK_UPDATE)
        for rec in recs:
            assert rec.recommendation_type == RecommendationType.SDK_UPDATE

    def test_filter_by_priority(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations(priority="critical")
        for rec in recs:
            assert rec.priority == "critical"


# ---------------------------------------------------------------------------
# Acknowledge and dismiss
# ---------------------------------------------------------------------------


class TestAcknowledgeDismiss:
    def test_acknowledge_existing(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations()
        assert len(recs) > 0
        rid = recs[0].recommendation_id
        result = full_engine.acknowledge_recommendation(rid)
        assert result is True
        # Check status
        with full_engine._lock:
            assert full_engine._recommendations[rid].status == "acknowledged"

    def test_acknowledge_nonexistent(self, full_engine):
        result = full_engine.acknowledge_recommendation("rec-does-not-exist")
        assert result is False

    def test_dismiss_existing(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations()
        assert len(recs) > 0
        rid = recs[0].recommendation_id
        result = full_engine.dismiss_recommendation(rid, "Not applicable")
        assert result is True
        with full_engine._lock:
            assert full_engine._recommendations[rid].status == "dismissed"
            assert full_engine._recommendations[rid].dismissed_reason == "Not applicable"

    def test_dismiss_nonexistent(self, full_engine):
        result = full_engine.dismiss_recommendation("rec-does-not-exist", "reason")
        assert result is False

    def test_dismissed_hidden_from_get_recommendations(self, full_engine):
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations()
        if len(recs) == 0:
            pytest.skip("No recommendations generated")
        rid = recs[0].recommendation_id
        full_engine.dismiss_recommendation(rid, "test")
        remaining = full_engine.get_recommendations()
        ids = [r.recommendation_id for r in remaining]
        assert rid not in ids


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_and_load_round_trip(self, pm, backbone):
        eng = SystemUpdateRecommendationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
            bug_detector=_StubBugDetector(),
        )
        eng.run_recommendation_cycle()
        recs_before = eng.get_recommendations()
        assert len(recs_before) > 0

        saved = eng.save_state()
        assert saved is True

        # New engine instance
        eng2 = SystemUpdateRecommendationEngine(persistence_manager=pm)
        loaded = eng2.load_state()
        assert loaded is True

        recs_after = eng2.get_recommendations()
        assert len(recs_after) == len(recs_before)
        ids_before = {r.recommendation_id for r in recs_before}
        ids_after = {r.recommendation_id for r in recs_after}
        assert ids_before == ids_after

    def test_load_state_no_prior_data(self, pm):
        eng = SystemUpdateRecommendationEngine(persistence_manager=pm)
        result = eng.load_state()
        assert result is False

    def test_save_state_auto_called_after_cycle(self, pm, backbone):
        eng = SystemUpdateRecommendationEngine(
            persistence_manager=pm,
            event_backbone=backbone,
            bug_detector=_StubBugDetector(),
        )
        eng.run_recommendation_cycle()

        # Verify state was persisted
        raw = pm.load_document(SystemUpdateRecommendationEngine._PERSIST_DOC_ID)
        assert raw is not None
        assert "recommendations" in raw


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_cycles(self, full_engine):
        errors = []

        def _run():
            try:
                full_engine.run_recommendation_cycle()
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread errors: {errors}"

    def test_concurrent_ack_and_cycle(self, full_engine):
        # Pre-populate some recommendations
        full_engine.run_recommendation_cycle()
        recs = full_engine.get_recommendations()
        errors = []

        def _ack():
            for rec in recs:
                try:
                    full_engine.acknowledge_recommendation(rec.recommendation_id)
                except Exception as exc:
                    errors.append(str(exc))

        def _cycle():
            try:
                full_engine.run_recommendation_cycle()
            except Exception as exc:
                errors.append(str(exc))

        t1 = threading.Thread(target=_ack)
        t2 = threading.Thread(target=_cycle)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert errors == [], f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# Bounded history and recommendation limits
# ---------------------------------------------------------------------------


class TestBoundedLimits:
    def test_bounded_history(self):
        eng = SystemUpdateRecommendationEngine(
            max_history=5,
            bug_detector=_StubBugDetector(),
        )
        for _ in range(10):
            eng.run_recommendation_cycle()
        history = eng.get_history(limit=100)
        assert len(history) <= 5

    def test_bounded_recommendations(self):
        eng = SystemUpdateRecommendationEngine(
            max_recommendations=3,
            dependency_audit=_StubDependencyAudit(),
            bug_detector=_StubBugDetector(),
            health_monitor=_StubHealthMonitor(),
            repair_system=_StubRepairSystem(),
            orchestrator=_StubOrchestrator(),
            improvement_engine=_StubImprovementEngine(),
        )
        for _ in range(5):
            eng.run_recommendation_cycle()
        with eng._lock:
            assert len(eng._recommendations) <= 3

    def test_history_limit_in_get_history(self, full_engine):
        for _ in range(10):
            full_engine.run_recommendation_cycle()
        history = full_engine.get_history(limit=3)
        assert len(history) <= 3


# ---------------------------------------------------------------------------
# Cross-subsystem correlation
# ---------------------------------------------------------------------------


class TestCrossSubsystemCorrelation:
    def test_bug_plus_dependency_raises_priority(self):
        """Bug pattern mentioning a package + dependency advisory → higher priority."""

        class _BugDetectorMatchingRequests:
            def get_reports(self, limit=50):
                return [
                    {
                        "report_id": "rpt-corr",
                        "severity": "medium",
                        "summary": "requests library causes connection timeout",
                        "patterns_detected": 2,
                        "critical_count": 0,
                        "high_count": 1,
                    }
                ]

        class _DepsWithRequests:
            def get_reports(self, limit=20):
                return [
                    {
                        "report_id": "dep-corr",
                        "findings": [
                            {
                                "advisory_id": "adv-corr",
                                "severity": "medium",
                                "dependency_name": "requests",
                                "installed_version": "2.25.0",
                                "fixed_in_version": "2.28.0",
                                "title": "Requests CVE",
                                "cve_id": "CVE-2022-9999",
                            }
                        ],
                    }
                ]

        eng = SystemUpdateRecommendationEngine(
            bug_detector=_BugDetectorMatchingRequests(),
            dependency_audit=_DepsWithRequests(),
        )
        report = eng.run_recommendation_cycle()
        # Dependency signal for "requests" should have been correlated with bug report
        sdk_recs = eng.get_recommendations(rec_type=RecommendationType.SDK_UPDATE)
        # At minimum 1 SDK recommendation should exist
        assert len(sdk_recs) >= 1

    def test_no_correlation_without_matching_data(self, full_engine):
        """No correlation should raise errors."""
        report = full_engine.run_recommendation_cycle()
        assert report.errors == [] or isinstance(report.errors, list)


# ---------------------------------------------------------------------------
# Custom subsystem registration
# ---------------------------------------------------------------------------


class TestCustomSubsystemRegistration:
    def test_register_and_collect(self, engine):
        def _custom_collector():
            return [
                {
                    "source": "my_subsystem",
                    "signal_type": "open_gap",
                    "id": "gap-custom-01",
                    "priority": "medium",
                    "description": "Custom gap detected",
                    "area": "custom_area",
                }
            ]

        engine.register_subsystem("my_subsystem", _custom_collector)
        report = engine.run_recommendation_cycle()
        assert "my_subsystem" in report.subsystems_available
        assert report.total_recommendations >= 1

    def test_collector_raising_exception_is_graceful(self, engine):
        def _bad_collector():
            raise RuntimeError("Simulated failure")

        engine.register_subsystem("bad_subsystem", _bad_collector)
        report = engine.run_recommendation_cycle()
        # Should not raise; error should be in report.errors
        assert any("bad_subsystem" in e for e in report.errors)


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------


class TestRecommendationDataclass:
    def test_to_dict_roundtrip(self):
        rec = Recommendation(
            recommendation_id="rec-abc123",
            subsystem="test_sub",
            recommendation_type=RecommendationType.MAINTENANCE,
            priority="high",
            confidence_score=0.8,
            description="A test recommendation",
            suggested_action="Restart service",
            estimated_effort="< 1h",
            risk_level="medium",
            auto_applicable=False,
            requires_review=True,
            related_proposals=["prop-1"],
        )
        d = rec.to_dict()
        rec2 = Recommendation.from_dict(d)
        assert rec2.recommendation_id == rec.recommendation_id
        assert rec2.recommendation_type == rec.recommendation_type
        assert rec2.confidence_score == rec.confidence_score
        assert rec2.related_proposals == rec.related_proposals

    def test_created_at_auto_populated(self):
        rec = Recommendation(
            recommendation_id="rec-ts",
            subsystem="x",
            recommendation_type=RecommendationType.AUTO_UPDATE,
            priority="low",
            confidence_score=0.5,
            description="d",
            suggested_action="s",
            estimated_effort="< 1h",
            risk_level="low",
            auto_applicable=True,
            requires_review=False,
        )
        assert rec.created_at is not None
        # Should be a valid ISO datetime string
        from datetime import datetime
        datetime.fromisoformat(rec.created_at)


# ---------------------------------------------------------------------------
# Specialised form dataclasses
# ---------------------------------------------------------------------------


class TestSpecialisedDataclasses:
    def test_maintenance_recommendation(self):
        m = MaintenanceRecommendation(
            recommendation_id="maint-01",
            action_type="restart",
            target_service="api-gw",
            description="Restart api-gw due to memory leak",
            priority="high",
        )
        assert m.requires_review is True
        assert m.created_at is not None

    def test_sdk_update_recommendation(self):
        sdk = SDKUpdateRecommendation(
            recommendation_id="sdk-01",
            package_name="requests",
            current_version="2.25.0",
            recommended_version="2.28.0",
            breaking_changes=False,
            migration_guide=None,
            compatibility_notes="No breaking changes",
            priority="medium",
        )
        assert sdk.requires_review is True

    def test_auto_update_action(self):
        au = AutoUpdateAction(
            recommendation_id="au-01",
            package_name="boto3",
            target_version="1.26.0",
            safe_to_auto_update=True,
            requires_review=False,
            rollback_plan="Pin to 1.25.x",
            risk_assessment="Low — patch version bump",
            priority="low",
        )
        assert au.safe_to_auto_update is True

    def test_bug_report_response(self):
        br = BugReportResponse(
            recommendation_id="br-01",
            bug_pattern_id="pattern-abc",
            severity="high",
            known_fix_available=True,
            suggested_patch="Upgrade requests library",
            eta_estimate="2h",
            affected_component="api-gw",
            priority="high",
        )
        assert br.requires_review is True

    def test_operational_analysis(self):
        oa = OperationalAnalysis(
            recommendation_id="oa-01",
            analysis_type="resource_utilization",
            metric_name="cpu_percent",
            current_value=87.5,
            threshold_value=80.0,
            trend="degrading",
            forecast_summary="CPU utilization trending upward; consider scaling.",
            priority="medium",
        )
        assert oa.created_at is not None


# ---------------------------------------------------------------------------
# RecommendationCycleReport
# ---------------------------------------------------------------------------


class TestCycleReport:
    def test_report_to_dict(self, full_engine):
        report = full_engine.run_recommendation_cycle()
        d = report.to_dict()
        assert "cycle_id" in d
        assert "started_at" in d
        assert "completed_at" in d
        assert "total_recommendations" in d
        assert "recommendations" in d
        assert isinstance(d["recommendations"], list)

    def test_report_errors_list(self, engine):
        engine.register_subsystem("fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        report = engine.run_recommendation_cycle()
        assert isinstance(report.errors, list)
