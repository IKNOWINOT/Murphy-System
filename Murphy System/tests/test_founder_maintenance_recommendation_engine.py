# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Comprehensive tests for FOUNDER-001: FounderMaintenanceRecommendationEngine.

Validates:
  - Recommendation creation for each category type
  - Recommendation lifecycle (pending → approved → applied)
  - Subsystem registration and health polling
  - Priority scoring algorithm
  - Auto-applicable safety gate (enabled/disabled)
  - Persistence save/load round-trip
  - Bounded collection limits (CWE-770 safe)
  - Thread safety with concurrent operations
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

from founder_maintenance_recommendation_engine import (
    FounderMaintenanceRecommendationEngine,
    MaintenanceRecommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    SubsystemRegistration,
    _PRIORITY_WEIGHT,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_engine(
    auto_applicable_gate: bool = True,
    max_recommendations: int = 100,
    persistence_manager=None,
    event_backbone=None,
) -> FounderMaintenanceRecommendationEngine:
    return FounderMaintenanceRecommendationEngine(
        auto_applicable_gate=auto_applicable_gate,
        max_recommendations=max_recommendations,
        persistence_manager=persistence_manager,
        event_backbone=event_backbone,
    )


def _add_rec(
    engine: FounderMaintenanceRecommendationEngine,
    category: RecommendationCategory = RecommendationCategory.MAINTENANCE,
    priority: RecommendationPriority = RecommendationPriority.MEDIUM,
    subsystem: str = "test_subsystem",
    auto_applicable: bool = False,
) -> MaintenanceRecommendation:
    return engine.add_recommendation(
        subsystem=subsystem,
        category=category,
        priority=priority,
        title=f"Test {category.value} recommendation",
        description="Test description",
        suggested_action="Take action",
        auto_applicable=auto_applicable,
    )


# ---------------------------------------------------------------------------
# 1. Recommendation creation — all categories
# ---------------------------------------------------------------------------


class TestRecommendationCreation:
    """Test that recommendations can be created for every category."""

    @pytest.mark.parametrize("category", list(RecommendationCategory))
    def test_create_each_category(self, category: RecommendationCategory) -> None:
        engine = _make_engine()
        rec = _add_rec(engine, category=category)
        assert rec.category == category
        assert rec.id in [r.id for r in engine.list_recommendations()]

    @pytest.mark.parametrize("priority", list(RecommendationPriority))
    def test_create_each_priority(self, priority: RecommendationPriority) -> None:
        engine = _make_engine()
        rec = _add_rec(engine, priority=priority)
        assert rec.priority == priority

    def test_recommendation_has_required_fields(self) -> None:
        engine = _make_engine()
        rec = engine.add_recommendation(
            subsystem="my_subsystem",
            category=RecommendationCategory.SDK_UPDATE,
            priority=RecommendationPriority.HIGH,
            title="Update requests",
            description="requests 2.25.0 has CVE-XXX",
            suggested_action="pip install requests>=2.28.0",
            auto_applicable=True,
        )
        assert rec.id
        assert rec.subsystem == "my_subsystem"
        assert rec.category == RecommendationCategory.SDK_UPDATE
        assert rec.priority == RecommendationPriority.HIGH
        assert rec.title == "Update requests"
        assert rec.auto_applicable is True
        assert rec.status == RecommendationStatus.PENDING
        assert rec.created_at
        assert rec.expires_at
        assert rec.score > 0

    def test_recommendation_default_status_is_pending(self) -> None:
        engine = _make_engine()
        rec = _add_rec(engine)
        assert rec.status == RecommendationStatus.PENDING

    def test_to_dict_and_from_dict_round_trip(self) -> None:
        engine = _make_engine()
        rec = _add_rec(engine, category=RecommendationCategory.BUG_RESPONSE)
        d = rec.to_dict()
        restored = MaintenanceRecommendation.from_dict(d)
        assert restored.id == rec.id
        assert restored.category == rec.category
        assert restored.priority == rec.priority
        assert restored.status == rec.status
        assert restored.score == rec.score


# ---------------------------------------------------------------------------
# 2. Recommendation lifecycle
# ---------------------------------------------------------------------------


class TestRecommendationLifecycle:
    """Test pending → approved → applied transitions."""

    def test_approve_pending(self) -> None:
        engine = _make_engine()
        rec = _add_rec(engine)
        assert rec.status == RecommendationStatus.PENDING
        approved = engine.approve(rec.id)
        assert approved.status == RecommendationStatus.APPROVED

    def test_reject_pending(self) -> None:
        engine = _make_engine()
        rec = _add_rec(engine)
        rejected = engine.reject(rec.id, reason="not needed")
        assert rejected.status == RecommendationStatus.REJECTED
        assert rejected.metadata.get("rejection_reason") == "not needed"

    def test_reject_approved(self) -> None:
        engine = _make_engine()
        rec = _add_rec(engine)
        engine.approve(rec.id)
        rejected = engine.reject(rec.id)
        assert rejected.status == RecommendationStatus.REJECTED

    def test_apply_requires_approval_when_gate_enabled(self) -> None:
        engine = _make_engine(auto_applicable_gate=True)
        rec = _add_rec(engine, auto_applicable=True)
        with pytest.raises(ValueError, match="must be approved"):
            engine.apply(rec.id)

    def test_apply_after_approval_when_gate_enabled(self) -> None:
        engine = _make_engine(auto_applicable_gate=True)
        rec = _add_rec(engine)
        engine.approve(rec.id)
        applied = engine.apply(rec.id)
        assert applied.status == RecommendationStatus.APPLIED

    def test_apply_already_applied_raises(self) -> None:
        engine = _make_engine(auto_applicable_gate=True)
        rec = _add_rec(engine)
        engine.approve(rec.id)
        engine.apply(rec.id)
        with pytest.raises(ValueError, match="already applied"):
            engine.apply(rec.id)

    def test_apply_rejected_raises(self) -> None:
        engine = _make_engine(auto_applicable_gate=True)
        rec = _add_rec(engine)
        engine.reject(rec.id)
        with pytest.raises(ValueError, match="rejected"):
            engine.apply(rec.id)

    def test_approve_nonexistent_raises(self) -> None:
        engine = _make_engine()
        with pytest.raises(KeyError):
            engine.approve("nonexistent-id")

    def test_reject_nonexistent_raises(self) -> None:
        engine = _make_engine()
        with pytest.raises(KeyError):
            engine.reject("nonexistent-id")

    def test_approve_already_applied_raises(self) -> None:
        engine = _make_engine(auto_applicable_gate=True)
        rec = _add_rec(engine)
        engine.approve(rec.id)
        engine.apply(rec.id)
        with pytest.raises(ValueError):
            engine.approve(rec.id)

    def test_full_lifecycle_pending_approved_applied(self) -> None:
        engine = _make_engine(auto_applicable_gate=True)
        rec = _add_rec(engine)
        assert rec.status == RecommendationStatus.PENDING
        engine.approve(rec.id)
        fetched = engine.get_recommendation(rec.id)
        assert fetched.status == RecommendationStatus.APPROVED
        engine.apply(rec.id)
        fetched = engine.get_recommendation(rec.id)
        assert fetched.status == RecommendationStatus.APPLIED


# ---------------------------------------------------------------------------
# 3. Auto-applicable safety gate
# ---------------------------------------------------------------------------


class TestAutoApplicableSafetyGate:
    """Test gate enabled vs disabled behaviour."""

    def test_gate_enabled_auto_applicable_still_needs_approval(self) -> None:
        engine = _make_engine(auto_applicable_gate=True)
        rec = _add_rec(engine, auto_applicable=True)
        with pytest.raises(ValueError):
            engine.apply(rec.id)

    def test_gate_disabled_auto_applicable_can_skip_approval(self) -> None:
        engine = _make_engine(auto_applicable_gate=False)
        rec = _add_rec(engine, auto_applicable=True)
        applied = engine.apply(rec.id)
        assert applied.status == RecommendationStatus.APPLIED

    def test_gate_disabled_non_auto_still_needs_approval(self) -> None:
        engine = _make_engine(auto_applicable_gate=False)
        rec = _add_rec(engine, auto_applicable=False)
        with pytest.raises(ValueError, match="requires approval"):
            engine.apply(rec.id)

    def test_gate_disabled_non_auto_can_apply_after_approval(self) -> None:
        engine = _make_engine(auto_applicable_gate=False)
        rec = _add_rec(engine, auto_applicable=False)
        engine.approve(rec.id)
        applied = engine.apply(rec.id)
        assert applied.status == RecommendationStatus.APPLIED


# ---------------------------------------------------------------------------
# 4. Subsystem registration and health polling
# ---------------------------------------------------------------------------


class TestSubsystemRegistration:
    """Test register_subsystem, list_subsystems, scan_all."""

    def test_register_and_list(self) -> None:
        engine = _make_engine()
        call_count = {"n": 0}

        def health() -> Dict[str, Any]:
            call_count["n"] += 1
            return {"healthy": True}

        def recs() -> List[Dict[str, Any]]:
            return []

        reg_id = engine.register_subsystem(
            name="my_subsystem",
            description="Test subsystem",
            health_check=health,
            get_recommendations=recs,
            criticality=3,
        )
        assert reg_id
        subs = engine.list_subsystems()
        names = [s["name"] for s in subs]
        assert "my_subsystem" in names

    def test_scan_calls_health_check(self) -> None:
        engine = _make_engine()
        call_count = {"n": 0}

        def health() -> Dict[str, Any]:
            call_count["n"] += 1
            return {"healthy": True}

        engine.register_subsystem(
            name="ping_sub",
            description="Ping subsystem",
            health_check=health,
            get_recommendations=lambda: [],
        )
        engine.scan_all()
        assert call_count["n"] >= 1

    def test_scan_collects_recommendations_from_subsystem(self) -> None:
        engine = _make_engine()

        def health() -> Dict[str, Any]:
            return {"healthy": True}

        def recs() -> List[Dict[str, Any]]:
            return [
                {
                    "category": "MAINTENANCE",
                    "priority": "high",
                    "title": "Clean up logs",
                    "description": "Log rotation needed",
                    "suggested_action": "Run log cleanup",
                    "auto_applicable": False,
                }
            ]

        engine.register_subsystem("rec_sub", "Rec subsystem", health, recs)
        result = engine.scan_all()
        assert result["new_recommendations"] >= 1

    def test_unregister_subsystem(self) -> None:
        engine = _make_engine()
        engine.register_subsystem("rem_sub", "Remove me", lambda: {}, lambda: [])
        assert any(s["name"] == "rem_sub" for s in engine.list_subsystems())
        removed = engine.unregister_subsystem("rem_sub")
        assert removed is True
        assert not any(s["name"] == "rem_sub" for s in engine.list_subsystems())

    def test_unregister_nonexistent_returns_false(self) -> None:
        engine = _make_engine()
        assert engine.unregister_subsystem("does_not_exist") is False

    def test_health_check_exception_does_not_crash_scan(self) -> None:
        engine = _make_engine()

        def bad_health() -> Dict[str, Any]:
            raise RuntimeError("health check failed")

        engine.register_subsystem("bad_sub", "Bad subsystem", bad_health, lambda: [])
        result = engine.scan_all()
        assert result["scanned_subsystems"] >= 1

    def test_get_recommendations_exception_does_not_crash_scan(self) -> None:
        engine = _make_engine()

        def bad_recs() -> List[Dict[str, Any]]:
            raise RuntimeError("recs failed")

        engine.register_subsystem("bad_recs_sub", "Bad recs", lambda: {}, bad_recs)
        result = engine.scan_all()
        # Should complete without error
        assert "scanned_subsystems" in result

    def test_criticality_clamped_to_1_5(self) -> None:
        engine = _make_engine()
        engine.register_subsystem("low_sub", "Low", lambda: {}, lambda: [], criticality=0)
        engine.register_subsystem("high_sub", "High", lambda: {}, lambda: [], criticality=100)
        subs = {s["name"]: s for s in engine.list_subsystems()}
        assert subs["low_sub"]["criticality"] == 1
        assert subs["high_sub"]["criticality"] == 5


# ---------------------------------------------------------------------------
# 5. Priority scoring algorithm
# ---------------------------------------------------------------------------


class TestScoringAlgorithm:
    """Test that higher priority / criticality / category produce higher scores."""

    def test_critical_scores_higher_than_low(self) -> None:
        engine = _make_engine()
        critical_rec = _add_rec(engine, priority=RecommendationPriority.CRITICAL)
        low_rec = _add_rec(engine, priority=RecommendationPriority.LOW)
        assert critical_rec.score > low_rec.score

    def test_bug_response_scores_higher_than_maintenance_same_priority(self) -> None:
        engine = _make_engine()
        bug_rec = _add_rec(engine, category=RecommendationCategory.BUG_RESPONSE)
        maint_rec = _add_rec(engine, category=RecommendationCategory.MAINTENANCE)
        # same priority (MEDIUM), BUG_RESPONSE category score (12) > MAINTENANCE (5)
        assert bug_rec.score > maint_rec.score

    def test_auto_applicable_bonus(self) -> None:
        engine = _make_engine()
        auto_rec = _add_rec(engine, auto_applicable=True)
        manual_rec = _add_rec(engine, auto_applicable=False)
        assert auto_rec.score > manual_rec.score

    def test_list_recommendations_sorted_by_score(self) -> None:
        engine = _make_engine()
        _add_rec(engine, priority=RecommendationPriority.LOW)
        _add_rec(engine, priority=RecommendationPriority.CRITICAL)
        _add_rec(engine, priority=RecommendationPriority.MEDIUM)
        recs = engine.list_recommendations()
        scores = [r.score for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_higher_criticality_subsystem_scores_higher(self) -> None:
        engine = _make_engine()
        # Register two subsystems with different criticality
        engine.register_subsystem("crit5", "Crit 5", lambda: {}, lambda: [], criticality=5)
        engine.register_subsystem("crit1", "Crit 1", lambda: {}, lambda: [], criticality=1)
        # Add recommendations for each via scan
        with engine._lock:
            from founder_maintenance_recommendation_engine import MaintenanceRecommendation, RecommendationCategory, RecommendationPriority, RecommendationStatus
            rec5 = MaintenanceRecommendation(
                id="rec-5", subsystem="crit5",
                category=RecommendationCategory.MAINTENANCE,
                priority=RecommendationPriority.MEDIUM,
                title="High crit rec", description="", suggested_action="",
                auto_applicable=False,
            )
            rec1 = MaintenanceRecommendation(
                id="rec-1", subsystem="crit1",
                category=RecommendationCategory.MAINTENANCE,
                priority=RecommendationPriority.MEDIUM,
                title="Low crit rec", description="", suggested_action="",
                auto_applicable=False,
            )
            rec5.score = engine._compute_score(rec5, 5)
            rec1.score = engine._compute_score(rec1, 1)
            engine._recommendations["rec-5"] = rec5
            engine._recommendations["rec-1"] = rec1

        r5 = engine.get_recommendation("rec-5")
        r1 = engine.get_recommendation("rec-1")
        assert r5.score > r1.score


# ---------------------------------------------------------------------------
# 6. Persistence save/load round-trip
# ---------------------------------------------------------------------------


class TestPersistenceRoundTrip:
    """Test save/load via PersistenceManager mock."""

    def _make_mock_pm(self) -> Any:
        store: Dict[str, Any] = {}
        pm = MagicMock()
        pm.save_document.side_effect = lambda doc_id, data: store.update({doc_id: data})
        pm.load_document.side_effect = lambda doc_id: store.get(doc_id)
        pm._store = store
        return pm

    def test_recommendations_persisted_on_add(self) -> None:
        pm = self._make_mock_pm()
        engine = _make_engine(persistence_manager=pm)
        _add_rec(engine, category=RecommendationCategory.SDK_UPDATE)
        pm.save_document.assert_called()

    def test_recommendations_loaded_on_init(self) -> None:
        pm = self._make_mock_pm()
        engine1 = _make_engine(persistence_manager=pm)
        rec = _add_rec(engine1, category=RecommendationCategory.SDK_UPDATE)

        # Create a fresh engine that loads from the same persistence store
        engine2 = _make_engine(persistence_manager=pm)
        loaded = engine2.get_recommendation(rec.id)
        assert loaded is not None
        assert loaded.id == rec.id
        assert loaded.category == RecommendationCategory.SDK_UPDATE

    def test_status_persisted_after_approve(self) -> None:
        pm = self._make_mock_pm()
        engine1 = _make_engine(persistence_manager=pm)
        rec = _add_rec(engine1)
        engine1.approve(rec.id)

        engine2 = _make_engine(persistence_manager=pm)
        loaded = engine2.get_recommendation(rec.id)
        assert loaded.status == RecommendationStatus.APPROVED

    def test_persistence_failure_does_not_raise(self) -> None:
        pm = MagicMock()
        pm.save_document.side_effect = IOError("disk full")
        pm.load_document.return_value = None
        engine = _make_engine(persistence_manager=pm)
        # Should not raise
        rec = _add_rec(engine)
        assert rec is not None


# ---------------------------------------------------------------------------
# 7. Bounded collection limits (CWE-770)
# ---------------------------------------------------------------------------


class TestBoundedCollections:
    """Test that the recommendation store never exceeds max_recommendations."""

    def test_collection_bounded_at_max(self) -> None:
        max_recs = 10
        engine = _make_engine(max_recommendations=max_recs)
        for i in range(max_recs + 5):
            engine.add_recommendation(
                subsystem=f"sub_{i}",
                category=RecommendationCategory.MAINTENANCE,
                priority=RecommendationPriority.LOW,
                title=f"Rec {i}",
                description="",
                suggested_action="",
            )
        with engine._lock:
            assert len(engine._recommendations) <= max_recs

    def test_oldest_evicted_first(self) -> None:
        max_recs = 3
        engine = _make_engine(max_recommendations=max_recs)
        first = engine.add_recommendation(
            subsystem="sub_first",
            category=RecommendationCategory.MAINTENANCE,
            priority=RecommendationPriority.LOW,
            title="First",
            description="",
            suggested_action="",
        )
        for i in range(max_recs + 2):
            engine.add_recommendation(
                subsystem=f"sub_{i}",
                category=RecommendationCategory.MAINTENANCE,
                priority=RecommendationPriority.LOW,
                title=f"Rec {i}",
                description="",
                suggested_action="",
            )
        # first recommendation should have been evicted
        assert engine.get_recommendation(first.id) is None


# ---------------------------------------------------------------------------
# 8. Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """Concurrent add/approve/reject operations must not corrupt state."""

    def test_concurrent_adds(self) -> None:
        engine = _make_engine(max_recommendations=500)
        errors: List[Exception] = []

        def add_many() -> None:
            for i in range(20):
                try:
                    engine.add_recommendation(
                        subsystem="concurrent_sub",
                        category=RecommendationCategory.MAINTENANCE,
                        priority=RecommendationPriority.LOW,
                        title=f"Concurrent rec {i}",
                        description="",
                        suggested_action="",
                    )
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=add_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent adds: {errors}"

    def test_concurrent_lifecycle_transitions(self) -> None:
        engine = _make_engine(max_recommendations=500)
        recs = [
            engine.add_recommendation(
                subsystem="thread_sub",
                category=RecommendationCategory.MAINTENANCE,
                priority=RecommendationPriority.MEDIUM,
                title=f"Rec {i}",
                description="",
                suggested_action="",
            )
            for i in range(50)
        ]
        errors: List[Exception] = []

        def approve_rec(rec_id: str) -> None:
            try:
                engine.approve(rec_id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=approve_rec, args=(r.id,)) for r in recs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent approvals: {errors}"

    def test_concurrent_scan(self) -> None:
        engine = _make_engine(max_recommendations=500)
        engine.register_subsystem(
            "scan_sub",
            "Scan sub",
            lambda: {"healthy": True},
            lambda: [
                {
                    "category": "MAINTENANCE",
                    "priority": "low",
                    "title": "Scan rec",
                    "description": "",
                    "suggested_action": "",
                    "auto_applicable": False,
                }
            ],
        )
        errors: List[Exception] = []

        def do_scan() -> None:
            try:
                engine.scan_all()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_scan) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent scans: {errors}"


# ---------------------------------------------------------------------------
# 9. Filtering and dashboard summary
# ---------------------------------------------------------------------------


class TestFilteringAndSummary:
    """Test list_recommendations filters and get_summary output."""

    def test_filter_by_category(self) -> None:
        engine = _make_engine()
        _add_rec(engine, category=RecommendationCategory.MAINTENANCE)
        _add_rec(engine, category=RecommendationCategory.SDK_UPDATE)
        maintenance_recs = engine.list_recommendations(category=RecommendationCategory.MAINTENANCE)
        assert all(r.category == RecommendationCategory.MAINTENANCE for r in maintenance_recs)

    def test_filter_by_priority(self) -> None:
        engine = _make_engine()
        _add_rec(engine, priority=RecommendationPriority.CRITICAL)
        _add_rec(engine, priority=RecommendationPriority.LOW)
        critical_recs = engine.list_recommendations(priority=RecommendationPriority.CRITICAL)
        assert all(r.priority == RecommendationPriority.CRITICAL for r in critical_recs)

    def test_filter_by_status(self) -> None:
        engine = _make_engine()
        r1 = _add_rec(engine)
        r2 = _add_rec(engine)
        engine.approve(r1.id)
        pending = engine.list_recommendations(status=RecommendationStatus.PENDING)
        approved = engine.list_recommendations(status=RecommendationStatus.APPROVED)
        assert r2.id in [r.id for r in pending]
        assert r1.id in [r.id for r in approved]

    def test_filter_by_subsystem(self) -> None:
        engine = _make_engine()
        _add_rec(engine, subsystem="sub_a")
        _add_rec(engine, subsystem="sub_b")
        sub_a_recs = engine.list_recommendations(subsystem="sub_a")
        assert all(r.subsystem == "sub_a" for r in sub_a_recs)

    def test_get_summary_structure(self) -> None:
        engine = _make_engine()
        _add_rec(engine, category=RecommendationCategory.BUG_RESPONSE, priority=RecommendationPriority.CRITICAL)
        _add_rec(engine, category=RecommendationCategory.SDK_UPDATE, priority=RecommendationPriority.HIGH)
        summary = engine.get_summary()
        assert "total_recommendations" in summary
        assert "counts_by_category" in summary
        assert "counts_by_status" in summary
        assert "counts_by_priority" in summary
        assert "top_pending" in summary
        assert "subsystem_health" in summary
        assert "generated_at" in summary

    def test_summary_counts_accurate(self) -> None:
        engine = _make_engine()
        _add_rec(engine, category=RecommendationCategory.MAINTENANCE)
        _add_rec(engine, category=RecommendationCategory.MAINTENANCE)
        _add_rec(engine, category=RecommendationCategory.SDK_UPDATE)
        summary = engine.get_summary()
        assert summary["counts_by_category"]["MAINTENANCE"] == 2
        assert summary["counts_by_category"]["SDK_UPDATE"] == 1
        assert summary["total_recommendations"] == 3


# ---------------------------------------------------------------------------
# 10. EventBackbone integration
# ---------------------------------------------------------------------------


class TestEventBackboneIntegration:
    """Test that recommendations publish events when backbone is available."""

    def test_event_published_on_add(self) -> None:
        backbone = MagicMock()
        engine = _make_engine(event_backbone=backbone)
        _add_rec(engine)
        backbone.publish.assert_called()

    def test_event_backbone_failure_does_not_raise(self) -> None:
        backbone = MagicMock()
        backbone.publish.side_effect = RuntimeError("backbone down")
        engine = _make_engine(event_backbone=backbone)
        rec = _add_rec(engine)  # Should not raise
        assert rec is not None


# ---------------------------------------------------------------------------
# 11. Expiry
# ---------------------------------------------------------------------------


class TestExpiry:
    """Test that recommendations are marked expired after TTL."""

    def test_expired_recommendation_marked(self) -> None:
        engine = _make_engine()
        rec = engine.add_recommendation(
            subsystem="test_sub",
            category=RecommendationCategory.MAINTENANCE,
            priority=RecommendationPriority.LOW,
            title="Expiring rec",
            description="",
            suggested_action="",
            ttl_hours=0,  # immediately expired
        )
        # Manually set expires_at in the past
        from datetime import datetime, timezone, timedelta
        rec.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert rec.is_expired()
        count = engine._expire_stale()
        assert count >= 1
        refreshed = engine.get_recommendation(rec.id)
        assert refreshed.status == RecommendationStatus.EXPIRED
