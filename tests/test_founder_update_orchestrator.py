# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Comprehensive tests for ARCH-007: FounderUpdateOrchestrator.

Validates:
  - Initialization with all subsystems vs. graceful degradation with none
  - Recommendation generation from each collector (_collect_* methods)
  - Recommendation filtering by subsystem, priority, type, status
  - Accept / reject / defer lifecycle transitions
  - Health score calculation
  - Persistence save/load round-trip
  - Thread safety (concurrent access)
  - Bounded collection limits (CWE-770)
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from founder_update_orchestrator import (
    FounderRecommendation,
    FounderUpdateOrchestrator,
    FounderUpdateReport,
    RecommendationType,
    SubsystemHealthReport,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_orchestrator(
    improvement_engine=None,
    self_fix_loop=None,
    bug_detector=None,
    dependency_auditor=None,
    healing_coordinator=None,
    repair_system=None,
    innovation_farmer=None,
    event_backbone=None,
    persistence_manager=None,
    max_recommendations: int = 200,
    max_reports: int = 50,
) -> FounderUpdateOrchestrator:
    return FounderUpdateOrchestrator(
        improvement_engine=improvement_engine,
        self_fix_loop=self_fix_loop,
        bug_detector=bug_detector,
        dependency_auditor=dependency_auditor,
        healing_coordinator=healing_coordinator,
        repair_system=repair_system,
        innovation_farmer=innovation_farmer,
        event_backbone=event_backbone,
        persistence_manager=persistence_manager,
        max_recommendations=max_recommendations,
        max_reports=max_reports,
    )


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


class TestInitialization:
    def test_no_subsystems_initializes_successfully(self):
        orch = _make_orchestrator()
        assert orch is not None

    def test_all_subsystems_injected(self):
        ie = MagicMock()
        sfl = MagicMock()
        bd = MagicMock()
        da = MagicMock()
        hc = MagicMock()
        rs = MagicMock()
        inf = MagicMock()
        eb = MagicMock()
        pm = MagicMock()
        orch = _make_orchestrator(
            improvement_engine=ie,
            self_fix_loop=sfl,
            bug_detector=bd,
            dependency_auditor=da,
            healing_coordinator=hc,
            repair_system=rs,
            innovation_farmer=inf,
            event_backbone=eb,
            persistence_manager=pm,
        )
        assert orch._improvement_engine is ie
        assert orch._self_fix_loop is sfl
        assert orch._bug_detector is bd
        assert orch._dependency_auditor is da
        assert orch._healing_coordinator is hc
        assert orch._repair_system is rs
        assert orch._innovation_farmer is inf
        assert orch._event_backbone is eb
        assert orch._persistence_manager is pm

    def test_initial_state_empty(self):
        orch = _make_orchestrator()
        assert orch.get_recommendations() == []
        assert orch.get_reports() == []


# ---------------------------------------------------------------------------
# Recommendation generation — no subsystems (fallback stubs)
# ---------------------------------------------------------------------------


class TestCollectorsWithNoSubsystems:
    def setup_method(self):
        self.orch = _make_orchestrator()

    def test_collect_maintenance_returns_stub(self):
        recs = self.orch._collect_maintenance_recommendations()
        assert len(recs) >= 1
        types = {r.recommendation_type for r in recs}
        maintenance_types = {
            RecommendationType.MAINTENANCE_SCHEDULED,
            RecommendationType.MAINTENANCE_URGENT,
            RecommendationType.MAINTENANCE_PREVENTIVE,
        }
        assert types & maintenance_types  # at least one maintenance type

    def test_collect_sdk_returns_stub(self):
        recs = self.orch._collect_sdk_recommendations()
        assert len(recs) >= 1
        types = {r.recommendation_type for r in recs}
        sdk_types = {
            RecommendationType.SDK_SECURITY_UPDATE,
            RecommendationType.SDK_FEATURE_UPDATE,
            RecommendationType.SDK_BREAKING_CHANGE,
            RecommendationType.SDK_DEPRECATION_WARNING,
        }
        assert types & sdk_types

    def test_collect_auto_update_returns_stub(self):
        recs = self.orch._collect_auto_update_recommendations()
        assert len(recs) >= 1
        types = {r.recommendation_type for r in recs}
        update_types = {
            RecommendationType.AUTO_UPDATE_SAFE,
            RecommendationType.AUTO_UPDATE_REQUIRES_REVIEW,
            RecommendationType.AUTO_UPDATE_ROLLBACK,
        }
        assert types & update_types

    def test_collect_bug_response_returns_stub(self):
        recs = self.orch._collect_bug_response_recommendations()
        assert len(recs) >= 1
        types = {r.recommendation_type for r in recs}
        bug_types = {
            RecommendationType.BUG_AUTO_TRIAGE,
            RecommendationType.BUG_PATTERN_MATCH,
            RecommendationType.BUG_FIX_PROPOSAL,
            RecommendationType.BUG_WORKAROUND,
        }
        assert types & bug_types

    def test_collect_operations_returns_stub(self):
        recs = self.orch._collect_operations_recommendations()
        assert len(recs) >= 1
        types = {r.recommendation_type for r in recs}
        ops_types = {
            RecommendationType.OPS_PERFORMANCE_TREND,
            RecommendationType.OPS_CAPACITY_WARNING,
            RecommendationType.OPS_HEALTH_SCORE,
            RecommendationType.OPS_COST_OPTIMIZATION,
        }
        assert types & ops_types


# ---------------------------------------------------------------------------
# Recommendation generation — with mocked subsystems
# ---------------------------------------------------------------------------


class TestCollectorsWithSubsystems:
    def test_maintenance_urgent_from_healing_coordinator(self):
        hc = MagicMock()
        hc.get_health_status.return_value = {"active_remediations": 3}
        orch = _make_orchestrator(healing_coordinator=hc)
        recs = orch._collect_maintenance_recommendations()
        urgent = [r for r in recs if r.recommendation_type == RecommendationType.MAINTENANCE_URGENT]
        assert len(urgent) >= 1
        assert urgent[0].priority == "high"

    def test_maintenance_scheduled_from_healthy_coordinator(self):
        hc = MagicMock()
        hc.get_health_status.return_value = {"active_remediations": 0}
        orch = _make_orchestrator(healing_coordinator=hc)
        recs = orch._collect_maintenance_recommendations()
        scheduled = [r for r in recs if r.recommendation_type == RecommendationType.MAINTENANCE_SCHEDULED]
        assert len(scheduled) >= 1

    def test_maintenance_urgent_from_repair_system(self):
        rs = MagicMock()
        rs.run_diagnostics.return_value = {"issues": ["issue_1", "issue_2"]}
        orch = _make_orchestrator(repair_system=rs)
        recs = orch._collect_maintenance_recommendations()
        urgent = [r for r in recs if r.recommendation_type == RecommendationType.MAINTENANCE_URGENT]
        assert len(urgent) >= 1

    def test_maintenance_preventive_from_healthy_repair_system(self):
        rs = MagicMock()
        rs.run_diagnostics.return_value = {"issues": []}
        orch = _make_orchestrator(repair_system=rs)
        recs = orch._collect_maintenance_recommendations()
        preventive = [r for r in recs if r.recommendation_type == RecommendationType.MAINTENANCE_PREVENTIVE]
        assert len(preventive) >= 1

    def test_sdk_security_update_from_audit_engine(self):
        da = MagicMock()
        da.get_audit_summary.return_value = {
            "vulnerable_count": 2,
            "outdated_count": 0,
            "deprecated_count": 0,
            "breaking_change_count": 0,
        }
        orch = _make_orchestrator(dependency_auditor=da)
        recs = orch._collect_sdk_recommendations()
        security = [r for r in recs if r.recommendation_type == RecommendationType.SDK_SECURITY_UPDATE]
        assert len(security) >= 1
        assert security[0].priority == "critical"

    def test_sdk_feature_update_from_audit_engine(self):
        da = MagicMock()
        da.get_audit_summary.return_value = {
            "vulnerable_count": 0,
            "outdated_count": 5,
            "deprecated_count": 0,
            "breaking_change_count": 0,
        }
        orch = _make_orchestrator(dependency_auditor=da)
        recs = orch._collect_sdk_recommendations()
        feature = [r for r in recs if r.recommendation_type == RecommendationType.SDK_FEATURE_UPDATE]
        assert len(feature) >= 1

    def test_sdk_deprecation_warning(self):
        da = MagicMock()
        da.get_audit_summary.return_value = {
            "vulnerable_count": 0,
            "outdated_count": 0,
            "deprecated_count": 3,
            "breaking_change_count": 0,
        }
        orch = _make_orchestrator(dependency_auditor=da)
        recs = orch._collect_sdk_recommendations()
        dep = [r for r in recs if r.recommendation_type == RecommendationType.SDK_DEPRECATION_WARNING]
        assert len(dep) >= 1

    def test_sdk_breaking_change(self):
        da = MagicMock()
        da.get_audit_summary.return_value = {
            "vulnerable_count": 0,
            "outdated_count": 0,
            "deprecated_count": 0,
            "breaking_change_count": 1,
        }
        orch = _make_orchestrator(dependency_auditor=da)
        recs = orch._collect_sdk_recommendations()
        breaking = [r for r in recs if r.recommendation_type == RecommendationType.SDK_BREAKING_CHANGE]
        assert len(breaking) >= 1

    def test_sdk_feature_from_innovation_farmer(self):
        inf = MagicMock()
        inf.get_latest_harvest.return_value = {"proposals": ["p1", "p2"]}
        orch = _make_orchestrator(innovation_farmer=inf)
        recs = orch._collect_sdk_recommendations()
        feature = [r for r in recs if r.recommendation_type == RecommendationType.SDK_FEATURE_UPDATE
                   and r.subsystem_source == "innovation_farmer"]
        assert len(feature) >= 1

    def test_auto_update_safe_from_self_fix_loop(self):
        sfl = MagicMock()
        last_report = MagicMock()
        last_report.completed_plans = ["plan_1"]
        last_report.failed_plans = []
        sfl.get_last_report.return_value = last_report
        orch = _make_orchestrator(self_fix_loop=sfl)
        recs = orch._collect_auto_update_recommendations()
        safe = [r for r in recs if r.recommendation_type == RecommendationType.AUTO_UPDATE_SAFE]
        assert len(safe) >= 1

    def test_auto_update_requires_review_from_failed_plans(self):
        sfl = MagicMock()
        last_report = MagicMock()
        last_report.completed_plans = []
        last_report.failed_plans = ["plan_1", "plan_2"]
        sfl.get_last_report.return_value = last_report
        orch = _make_orchestrator(self_fix_loop=sfl)
        recs = orch._collect_auto_update_recommendations()
        review = [r for r in recs if r.recommendation_type == RecommendationType.AUTO_UPDATE_REQUIRES_REVIEW]
        assert len(review) >= 1

    def test_auto_update_rollback_from_repair_system(self):
        rs = MagicMock()
        rs.get_rollback_candidates.return_value = ["candidate_1"]
        orch = _make_orchestrator(repair_system=rs)
        recs = orch._collect_auto_update_recommendations()
        rollback = [r for r in recs if r.recommendation_type == RecommendationType.AUTO_UPDATE_ROLLBACK]
        assert len(rollback) >= 1

    def test_bug_pattern_match_from_detector(self):
        bd = MagicMock()
        bd.get_active_patterns.return_value = ["pattern_1", "pattern_2"]
        bd.get_triage_queue.return_value = []
        orch = _make_orchestrator(bug_detector=bd)
        recs = orch._collect_bug_response_recommendations()
        patterns = [r for r in recs if r.recommendation_type == RecommendationType.BUG_PATTERN_MATCH]
        assert len(patterns) >= 1

    def test_bug_auto_triage_with_critical(self):
        bd = MagicMock()
        bd.get_active_patterns.return_value = []
        bug1 = MagicMock()
        bug1.severity = "critical"
        bug2 = MagicMock()
        bug2.severity = "low"
        bd.get_triage_queue.return_value = [bug1, bug2]
        orch = _make_orchestrator(bug_detector=bd)
        recs = orch._collect_bug_response_recommendations()
        triage = [r for r in recs if r.recommendation_type == RecommendationType.BUG_AUTO_TRIAGE]
        assert len(triage) >= 1
        assert triage[0].priority == "critical"

    def test_bug_fix_proposal_from_improvement_engine(self):
        ie = MagicMock()
        ie.get_pending_proposals.return_value = ["proposal_1"]
        ie.get_workarounds.return_value = []
        orch = _make_orchestrator(improvement_engine=ie)
        recs = orch._collect_bug_response_recommendations()
        proposals = [r for r in recs if r.recommendation_type == RecommendationType.BUG_FIX_PROPOSAL]
        assert len(proposals) >= 1

    def test_bug_workaround_from_improvement_engine(self):
        ie = MagicMock()
        ie.get_pending_proposals.return_value = []
        ie.get_workarounds.return_value = ["workaround_1"]
        orch = _make_orchestrator(improvement_engine=ie)
        recs = orch._collect_bug_response_recommendations()
        workarounds = [r for r in recs if r.recommendation_type == RecommendationType.BUG_WORKAROUND]
        assert len(workarounds) >= 1

    def test_ops_performance_trend_from_self_fix_loop(self):
        sfl = MagicMock()
        sfl.get_metrics.return_value = {"success_rate": 0.6}
        sfl.get_last_report.return_value = None
        orch = _make_orchestrator(self_fix_loop=sfl)
        recs = orch._collect_operations_recommendations()
        perf = [r for r in recs if r.recommendation_type == RecommendationType.OPS_PERFORMANCE_TREND]
        assert len(perf) >= 1
        assert perf[0].priority == "high"

    def test_ops_health_score_from_improvement_engine(self):
        ie = MagicMock()
        ie.get_confidence_score.return_value = 0.85
        orch = _make_orchestrator(improvement_engine=ie)
        recs = orch._collect_operations_recommendations()
        health = [r for r in recs if r.recommendation_type == RecommendationType.OPS_HEALTH_SCORE]
        assert len(health) >= 1
        assert health[0].priority == "low"

    def test_ops_capacity_warning(self):
        hc = MagicMock()
        hc.get_capacity_metrics.return_value = {"usage_percent": 92.0}
        hc.get_health_status.return_value = {"active_remediations": 0}
        orch = _make_orchestrator(healing_coordinator=hc)
        recs = orch._collect_operations_recommendations()
        capacity = [r for r in recs if r.recommendation_type == RecommendationType.OPS_CAPACITY_WARNING]
        assert len(capacity) >= 1
        assert capacity[0].priority == "high"

    def test_ops_cost_optimization(self):
        da = MagicMock()
        da.get_cost_analysis.return_value = {
            "optimization_opportunities": ["opt_1", "opt_2"]
        }
        da.get_audit_summary.return_value = {
            "vulnerable_count": 0,
            "outdated_count": 0,
            "deprecated_count": 0,
            "breaking_change_count": 0,
        }
        orch = _make_orchestrator(dependency_auditor=da)
        recs = orch._collect_operations_recommendations()
        cost = [r for r in recs if r.recommendation_type == RecommendationType.OPS_COST_OPTIMIZATION]
        assert len(cost) >= 1


# ---------------------------------------------------------------------------
# Subsystem error resilience
# ---------------------------------------------------------------------------


class TestSubsystemErrorResilience:
    def test_healing_coordinator_exception_graceful(self):
        hc = MagicMock()
        hc.get_health_status.side_effect = RuntimeError("connection failed")
        orch = _make_orchestrator(healing_coordinator=hc)
        # Should not raise
        recs = orch._collect_maintenance_recommendations()
        assert isinstance(recs, list)

    def test_bug_detector_exception_graceful(self):
        bd = MagicMock()
        bd.get_active_patterns.side_effect = RuntimeError("DB unavailable")
        orch = _make_orchestrator(bug_detector=bd)
        recs = orch._collect_bug_response_recommendations()
        assert isinstance(recs, list)

    def test_repair_system_exception_graceful(self):
        rs = MagicMock()
        rs.run_diagnostics.side_effect = Exception("network timeout")
        orch = _make_orchestrator(repair_system=rs)
        recs = orch._collect_maintenance_recommendations()
        assert isinstance(recs, list)


# ---------------------------------------------------------------------------
# Full report generation
# ---------------------------------------------------------------------------


class TestGenerateFullReport:
    def test_returns_founder_update_report(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        assert isinstance(report, FounderUpdateReport)
        assert report.report_id
        assert report.generated_at
        assert 0.0 <= report.overall_health_score <= 1.0
        assert isinstance(report.all_recommendations, list)
        assert isinstance(report.subsystem_reports, list)
        assert isinstance(report.summary, dict)

    def test_report_has_all_recommendation_categories(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        types = {r.recommendation_type for r in report.all_recommendations}
        # Each collector returns at least one rec — we should see all 5 categories represented
        maintenance_types = {
            RecommendationType.MAINTENANCE_SCHEDULED,
            RecommendationType.MAINTENANCE_URGENT,
            RecommendationType.MAINTENANCE_PREVENTIVE,
        }
        sdk_types = {
            RecommendationType.SDK_SECURITY_UPDATE,
            RecommendationType.SDK_FEATURE_UPDATE,
            RecommendationType.SDK_BREAKING_CHANGE,
            RecommendationType.SDK_DEPRECATION_WARNING,
        }
        update_types = {
            RecommendationType.AUTO_UPDATE_SAFE,
            RecommendationType.AUTO_UPDATE_REQUIRES_REVIEW,
            RecommendationType.AUTO_UPDATE_ROLLBACK,
        }
        bug_types = {
            RecommendationType.BUG_AUTO_TRIAGE,
            RecommendationType.BUG_PATTERN_MATCH,
            RecommendationType.BUG_FIX_PROPOSAL,
            RecommendationType.BUG_WORKAROUND,
        }
        ops_types = {
            RecommendationType.OPS_PERFORMANCE_TREND,
            RecommendationType.OPS_CAPACITY_WARNING,
            RecommendationType.OPS_HEALTH_SCORE,
            RecommendationType.OPS_COST_OPTIMIZATION,
        }
        assert types & maintenance_types
        assert types & sdk_types
        assert types & update_types
        assert types & bug_types
        assert types & ops_types

    def test_report_stored_in_history(self):
        orch = _make_orchestrator()
        orch.generate_full_report()
        reports = orch.get_reports()
        assert len(reports) == 1

    def test_multiple_reports_accumulate(self):
        orch = _make_orchestrator()
        orch.generate_full_report()
        orch.generate_full_report()
        assert len(orch.get_reports()) == 2

    def test_recommendations_indexed_after_report(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        first_id = report.all_recommendations[0].recommendation_id
        assert orch.get_recommendation(first_id) is not None

    def test_event_emitted_on_report(self):
        eb = MagicMock()
        orch = _make_orchestrator(event_backbone=eb)
        orch.generate_full_report()
        eb.emit.assert_called()
        event_names = [call.args[0] for call in eb.emit.call_args_list]
        assert "founder_report_generated" in event_names

    def test_to_dict_serialization(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        d = report.to_dict()
        assert "report_id" in d
        assert "generated_at" in d
        assert "overall_health_score" in d
        assert "all_recommendations" in d
        assert "subsystem_reports" in d
        assert "summary" in d


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


class TestFiltering:
    def setup_method(self):
        self.orch = _make_orchestrator()
        self.orch.generate_full_report()

    def test_filter_by_subsystem(self):
        recs = self.orch.get_recommendations(subsystem="founder_update_orchestrator")
        assert all(r.subsystem_source == "founder_update_orchestrator" for r in recs)

    def test_filter_by_priority(self):
        recs = self.orch.get_recommendations(priority="low")
        assert all(r.priority == "low" for r in recs)

    def test_filter_by_type(self):
        recs = self.orch.get_recommendations(
            recommendation_type=RecommendationType.MAINTENANCE_SCHEDULED
        )
        assert all(r.recommendation_type == RecommendationType.MAINTENANCE_SCHEDULED for r in recs)

    def test_filter_by_status_pending(self):
        recs = self.orch.get_recommendations(status="pending")
        assert all(r.status == "pending" for r in recs)

    def test_filter_combined(self):
        recs = self.orch.get_recommendations(status="pending", priority="low")
        assert all(r.status == "pending" and r.priority == "low" for r in recs)

    def test_no_match_returns_empty(self):
        recs = self.orch.get_recommendations(subsystem="nonexistent_subsystem")
        assert recs == []


# ---------------------------------------------------------------------------
# Lifecycle — accept / reject / defer
# ---------------------------------------------------------------------------


class TestRecommendationLifecycle:
    def setup_method(self):
        self.orch = _make_orchestrator()
        report = self.orch.generate_full_report()
        self.first_id = report.all_recommendations[0].recommendation_id

    def test_accept_pending_recommendation(self):
        result = self.orch.accept_recommendation(self.first_id)
        assert result is True
        rec = self.orch.get_recommendation(self.first_id)
        assert rec.status == "accepted"

    def test_accept_emits_event(self):
        eb = MagicMock()
        orch = _make_orchestrator(event_backbone=eb)
        report = orch.generate_full_report()
        rid = report.all_recommendations[0].recommendation_id
        orch.accept_recommendation(rid)
        event_names = [call.args[0] for call in eb.emit.call_args_list]
        assert "recommendation_accepted" in event_names

    def test_reject_pending_recommendation(self):
        result = self.orch.reject_recommendation(self.first_id, reason="not relevant")
        assert result is True
        rec = self.orch.get_recommendation(self.first_id)
        assert rec.status == "rejected"
        assert rec.metadata.get("rejection_reason") == "not relevant"

    def test_reject_accepted_recommendation(self):
        self.orch.accept_recommendation(self.first_id)
        result = self.orch.reject_recommendation(self.first_id, reason="changed mind")
        assert result is True
        rec = self.orch.get_recommendation(self.first_id)
        assert rec.status == "rejected"

    def test_defer_pending_recommendation(self):
        until = "2099-01-01T00:00:00+00:00"
        result = self.orch.defer_recommendation(self.first_id, until=until)
        assert result is True
        rec = self.orch.get_recommendation(self.first_id)
        assert rec.status == "deferred"
        assert rec.expires_at == until
        assert rec.metadata.get("deferred_until") == until

    def test_cannot_accept_already_accepted(self):
        self.orch.accept_recommendation(self.first_id)
        result = self.orch.accept_recommendation(self.first_id)
        assert result is False

    def test_cannot_accept_rejected(self):
        self.orch.reject_recommendation(self.first_id)
        result = self.orch.accept_recommendation(self.first_id)
        assert result is False

    def test_cannot_defer_non_pending(self):
        self.orch.accept_recommendation(self.first_id)
        result = self.orch.defer_recommendation(self.first_id, until="2099-01-01T00:00:00+00:00")
        assert result is False

    def test_cannot_reject_deferred(self):
        self.orch.defer_recommendation(self.first_id, until="2099-01-01T00:00:00+00:00")
        result = self.orch.reject_recommendation(self.first_id)
        assert result is False

    def test_mark_implemented_from_accepted(self):
        self.orch.accept_recommendation(self.first_id)
        result = self.orch.mark_implemented(self.first_id)
        assert result is True
        rec = self.orch.get_recommendation(self.first_id)
        assert rec.status == "implemented"

    def test_mark_implemented_fails_if_not_accepted(self):
        result = self.orch.mark_implemented(self.first_id)
        assert result is False

    def test_nonexistent_id_returns_false_accept(self):
        assert self.orch.accept_recommendation("nonexistent") is False

    def test_nonexistent_id_returns_false_reject(self):
        assert self.orch.reject_recommendation("nonexistent") is False

    def test_nonexistent_id_returns_false_defer(self):
        assert self.orch.defer_recommendation("nonexistent", until="2099-01-01T00:00:00+00:00") is False

    def test_reject_emits_event(self):
        eb = MagicMock()
        orch = _make_orchestrator(event_backbone=eb)
        report = orch.generate_full_report()
        rid = report.all_recommendations[0].recommendation_id
        orch.reject_recommendation(rid, reason="irrelevant")
        event_names = [call.args[0] for call in eb.emit.call_args_list]
        assert "recommendation_rejected" in event_names


# ---------------------------------------------------------------------------
# Health score calculation
# ---------------------------------------------------------------------------


class TestHealthScoreCalculation:
    def _make_report(self, status: str) -> SubsystemHealthReport:
        return SubsystemHealthReport(
            subsystem_name="test_sub",
            status=status,
            last_check="2026-01-01T00:00:00+00:00",
            metrics={},
            recommendations=[],
        )

    def test_empty_reports_returns_0_5(self):
        orch = _make_orchestrator()
        assert orch._calculate_health_score([]) == 0.5

    def test_all_healthy_returns_1_0(self):
        orch = _make_orchestrator()
        reports = [self._make_report("healthy") for _ in range(5)]
        assert orch._calculate_health_score(reports) == 1.0

    def test_all_critical_returns_0_1(self):
        orch = _make_orchestrator()
        reports = [self._make_report("critical") for _ in range(3)]
        assert orch._calculate_health_score(reports) == 0.1

    def test_mixed_returns_average(self):
        orch = _make_orchestrator()
        reports = [
            self._make_report("healthy"),  # 1.0
            self._make_report("degraded"),  # 0.5
            self._make_report("critical"),  # 0.1
        ]
        score = orch._calculate_health_score(reports)
        expected = round((1.0 + 0.5 + 0.1) / 3, 4)
        assert score == expected

    def test_unknown_status_treated_as_0_5(self):
        orch = _make_orchestrator()
        reports = [self._make_report("unknown")]
        assert orch._calculate_health_score(reports) == 0.5

    def test_score_is_between_0_and_1(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        assert 0.0 <= report.overall_health_score <= 1.0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_without_persistence_manager_returns_false(self):
        orch = _make_orchestrator()
        assert orch.save_state() is False

    def test_load_without_persistence_manager_returns_false(self):
        orch = _make_orchestrator()
        assert orch.load_state() is False

    def test_save_calls_persistence_manager(self):
        pm = MagicMock()
        pm.save.return_value = None
        orch = _make_orchestrator(persistence_manager=pm)
        orch.generate_full_report()
        result = orch.save_state()
        assert result is True
        pm.save.assert_called_once()
        key, data = pm.save.call_args[0]
        assert key == "founder_update_orchestrator"
        assert "recommendations" in data

    def test_load_restores_recommendations(self):
        pm = MagicMock()
        orch1 = _make_orchestrator(persistence_manager=pm)
        orch1.generate_full_report()
        saved_recs = [r.to_dict() for r in orch1.get_recommendations()]
        assert saved_recs

        pm.load.return_value = {"recommendations": saved_recs, "reports": []}

        orch2 = _make_orchestrator(persistence_manager=pm)
        assert orch2.load_state() is True
        loaded = orch2.get_recommendations()
        assert len(loaded) == len(saved_recs)
        assert loaded[0].recommendation_id == saved_recs[0]["recommendation_id"]

    def test_load_returns_false_when_no_data(self):
        pm = MagicMock()
        pm.load.return_value = None
        orch = _make_orchestrator(persistence_manager=pm)
        assert orch.load_state() is False

    def test_save_failure_returns_false(self):
        pm = MagicMock()
        pm.save.side_effect = Exception("disk full")
        orch = _make_orchestrator(persistence_manager=pm)
        orch.generate_full_report()
        assert orch.save_state() is False

    def test_roundtrip_preserves_lifecycle_status(self):
        pm = MagicMock()
        orch1 = _make_orchestrator(persistence_manager=pm)
        report = orch1.generate_full_report()
        rid = report.all_recommendations[0].recommendation_id
        orch1.accept_recommendation(rid)

        saved_recs = [r.to_dict() for r in orch1.get_recommendations()]
        pm.load.return_value = {"recommendations": saved_recs, "reports": []}

        orch2 = _make_orchestrator(persistence_manager=pm)
        orch2.load_state()
        rec = orch2.get_recommendation(rid)
        assert rec is not None
        assert rec.status == "accepted"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_generate_full_report(self):
        orch = _make_orchestrator()
        errors = []

        def generate():
            try:
                orch.generate_full_report()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=generate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread safety errors: {errors}"
        assert len(orch.get_reports()) == 10

    def test_concurrent_accept_reject_same_recommendation(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        rid = report.all_recommendations[0].recommendation_id
        results = []
        lock = threading.Lock()

        def accept():
            r = orch.accept_recommendation(rid)
            with lock:
                results.append(("accept", r))

        def reject():
            r = orch.reject_recommendation(rid)
            with lock:
                results.append(("reject", r))

        threads = [threading.Thread(target=accept if i % 2 == 0 else reject) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final state must be a valid terminal: accepted or rejected (not pending)
        rec = orch.get_recommendation(rid)
        assert rec.status in ("accepted", "rejected")
        # At least one operation succeeded
        assert any(r for _, r in results)

    def test_concurrent_get_recommendations(self):
        orch = _make_orchestrator()
        orch.generate_full_report()
        errors = []

        def read():
            try:
                _ = orch.get_recommendations()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=read) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ---------------------------------------------------------------------------
# Bounded collections (CWE-770)
# ---------------------------------------------------------------------------


class TestBoundedCollections:
    def test_recommendations_capped_at_max(self):
        orch = _make_orchestrator(max_recommendations=10)
        # Keep generating reports until we exceed the cap
        for _ in range(20):
            orch.generate_full_report()

        # Should be bounded
        recs = orch.get_recommendations()
        assert len(recs) <= orch._max_recommendations * 1.2  # allow for capped_append buffer

    def test_reports_capped_at_max(self):
        # Use max_reports=20 so that capped_append can prune (max//10 = 2 items removed)
        orch = _make_orchestrator(max_reports=20)
        for _ in range(50):
            orch.generate_full_report()

        reports = orch.get_reports()
        # capped_append prunes max//10 items when full, so size stays bounded
        assert len(reports) <= orch._max_reports + (orch._max_reports // 10) + 1


# ---------------------------------------------------------------------------
# Data structure serialization
# ---------------------------------------------------------------------------


class TestDataStructures:
    def test_founder_recommendation_to_dict(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        rec = report.all_recommendations[0]
        d = rec.to_dict()
        assert "recommendation_id" in d
        assert "recommendation_type" in d
        assert isinstance(d["recommendation_type"], str)
        assert "subsystem_source" in d
        assert "priority" in d
        assert "confidence" in d
        assert 0.0 <= d["confidence"] <= 1.0
        assert "suggested_actions" in d
        assert isinstance(d["suggested_actions"], list)
        assert "metadata" in d
        assert "status" in d
        assert "created_at" in d

    def test_founder_recommendation_from_dict_roundtrip(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        rec = report.all_recommendations[0]
        d = rec.to_dict()
        rec2 = FounderRecommendation.from_dict(d)
        assert rec2.recommendation_id == rec.recommendation_id
        assert rec2.recommendation_type == rec.recommendation_type
        assert rec2.priority == rec.priority
        assert rec2.confidence == rec.confidence

    def test_subsystem_health_report_to_dict(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        if report.subsystem_reports:
            sr = report.subsystem_reports[0]
            d = sr.to_dict()
            assert "subsystem_name" in d
            assert "status" in d
            assert "last_check" in d
            assert "metrics" in d
            assert "recommendations" in d

    def test_founder_update_report_to_dict(self):
        orch = _make_orchestrator()
        report = orch.generate_full_report()
        d = report.to_dict()
        assert "report_id" in d
        assert "generated_at" in d
        assert "overall_health_score" in d
        assert "subsystem_reports" in d
        assert "all_recommendations" in d
        assert "summary" in d

    def test_recommendation_type_enum_values(self):
        # Verify all enum values are present
        values = {t.value for t in RecommendationType}
        assert "maintenance_scheduled" in values
        assert "maintenance_urgent" in values
        assert "maintenance_preventive" in values
        assert "sdk_security_update" in values
        assert "sdk_feature_update" in values
        assert "sdk_breaking_change" in values
        assert "sdk_deprecation_warning" in values
        assert "auto_update_safe" in values
        assert "auto_update_requires_review" in values
        assert "auto_update_rollback" in values
        assert "bug_auto_triage" in values
        assert "bug_pattern_match" in values
        assert "bug_fix_proposal" in values
        assert "bug_workaround" in values
        assert "ops_performance_trend" in values
        assert "ops_capacity_warning" in values
        assert "ops_health_score" in values
        assert "ops_cost_optimization" in values
