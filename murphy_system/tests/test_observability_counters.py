"""
Tests for the Murphy System Observability Summary Counters.
"""

import os
import time

import pytest


from observability_counters import (
    VALID_CATEGORIES,
    CounterEntry,
    ObservabilitySummaryCounters,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def counters():
    return ObservabilitySummaryCounters()


# ---------------------------------------------------------------------------
# CounterEntry Dataclass
# ---------------------------------------------------------------------------

class TestCounterEntry:
    def test_defaults(self):
        entry = CounterEntry(name="x", category="behavior_fix", last_updated="t")
        assert entry.value == 0
        assert entry.metadata == {}

    def test_custom_values(self):
        entry = CounterEntry(
            name="n", category="documentation", value=5,
            last_updated="ts", metadata={"k": "v"},
        )
        assert entry.value == 5
        assert entry.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_returns_id(self, counters):
        cid = counters.register_counter("fix-1", "behavior_fix")
        assert isinstance(cid, str) and len(cid) == 12

    def test_register_all_valid_categories(self, counters):
        for cat in VALID_CATEGORIES:
            cid = counters.register_counter(f"c-{cat}", cat)
            info = counters.get_counter(cid)
            assert info["status"] == "ok"
            assert info["category"] == cat

    def test_register_invalid_category_raises(self, counters):
        with pytest.raises(ValueError, match="Invalid category"):
            counters.register_counter("bad", "nonexistent")

    def test_registered_counter_starts_at_zero(self, counters):
        cid = counters.register_counter("c", "documentation")
        assert counters.get_counter(cid)["value"] == 0


# ---------------------------------------------------------------------------
# Increment
# ---------------------------------------------------------------------------

class TestIncrement:
    def test_increment_default_delta(self, counters):
        cid = counters.register_counter("c", "behavior_fix")
        result = counters.increment(cid)
        assert result["status"] == "ok"
        assert result["value"] == 1

    def test_increment_custom_delta(self, counters):
        cid = counters.register_counter("c", "behavior_fix")
        counters.increment(cid, delta=5)
        assert counters.get_counter(cid)["value"] == 5

    def test_increment_accumulates(self, counters):
        cid = counters.register_counter("c", "behavior_fix")
        counters.increment(cid, delta=3)
        counters.increment(cid, delta=7)
        assert counters.get_counter(cid)["value"] == 10

    def test_increment_unknown_counter(self, counters):
        result = counters.increment("nonexistent")
        assert result["status"] == "error"

    def test_increment_records_reason_in_history(self, counters):
        cid = counters.register_counter("c", "behavior_fix")
        counters.increment(cid, reason="patched null check")
        history = counters.get_history()
        assert history[0]["reason"] == "patched null check"

    def test_increment_updates_last_updated(self, counters):
        cid = counters.register_counter("c", "behavior_fix")
        before = counters.get_counter(cid)["last_updated"]
        time.sleep(0.01)
        counters.increment(cid)
        after = counters.get_counter(cid)["last_updated"]
        assert after >= before


# ---------------------------------------------------------------------------
# record_fix
# ---------------------------------------------------------------------------

class TestRecordFix:
    def test_record_fix_creates_counter(self, counters):
        cid = counters.record_fix("auth", "null_check", "fixed null deref")
        info = counters.get_counter(cid)
        assert info["status"] == "ok"
        assert info["category"] == "behavior_fix"
        assert info["value"] == 1

    def test_record_fix_reuses_existing_counter(self, counters):
        cid1 = counters.record_fix("auth", "null_check", "first")
        cid2 = counters.record_fix("auth", "null_check", "second")
        assert cid1 == cid2
        assert counters.get_counter(cid1)["value"] == 2

    def test_record_fix_appears_in_history(self, counters):
        counters.record_fix("mod", "edge", "desc")
        history = counters.get_history(category="behavior_fix")
        assert len(history) == 1
        assert history[0]["reason"] == "desc"


# ---------------------------------------------------------------------------
# record_coverage
# ---------------------------------------------------------------------------

class TestRecordCoverage:
    def test_record_coverage_creates_counter(self, counters):
        cid = counters.record_coverage("gateway", 10, "added permutation tests")
        info = counters.get_counter(cid)
        assert info["status"] == "ok"
        assert info["category"] == "permutation_coverage"
        assert info["value"] == 10

    def test_record_coverage_reuses_existing_counter(self, counters):
        cid1 = counters.record_coverage("gateway", 5, "batch 1")
        cid2 = counters.record_coverage("gateway", 3, "batch 2")
        assert cid1 == cid2
        assert counters.get_counter(cid1)["value"] == 8

    def test_record_coverage_appears_in_history(self, counters):
        counters.record_coverage("gw", 2, "reason")
        history = counters.get_history(category="permutation_coverage")
        assert len(history) == 1


# ---------------------------------------------------------------------------
# Category Summary
# ---------------------------------------------------------------------------

class TestCategorySummary:
    def test_empty_summary(self, counters):
        summary = counters.get_category_summary()
        assert summary["status"] == "ok"
        assert summary["total"] == 0

    def test_summary_tracks_totals(self, counters):
        counters.record_fix("a", "t", "d")
        counters.record_coverage("b", 4, "d")
        summary = counters.get_category_summary()
        assert summary["categories"]["behavior_fix"] == 1
        assert summary["categories"]["permutation_coverage"] == 4
        assert summary["total"] == 5


# ---------------------------------------------------------------------------
# Behavior vs Permutation Ratio
# ---------------------------------------------------------------------------

class TestRatio:
    def test_ratio_zero_when_empty(self, counters):
        r = counters.get_behavior_vs_permutation_ratio()
        assert r["status"] == "ok"
        assert r["ratio"] == 0.0

    def test_ratio_inf_when_no_coverage(self, counters):
        counters.record_fix("m", "t", "d")
        r = counters.get_behavior_vs_permutation_ratio()
        assert r["ratio"] == float("inf")

    def test_ratio_calculated(self, counters):
        counters.record_fix("m", "t", "d")
        counters.record_fix("m", "t", "d2")
        counters.record_coverage("m", 4, "d")
        r = counters.get_behavior_vs_permutation_ratio()
        assert r["ratio"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Module Summary
# ---------------------------------------------------------------------------

class TestModuleSummary:
    def test_empty_modules(self, counters):
        ms = counters.get_module_summary()
        assert ms["status"] == "ok"
        assert ms["modules"] == {}

    def test_groups_by_module(self, counters):
        counters.record_fix("auth", "t", "d")
        counters.record_coverage("auth", 3, "d")
        counters.record_fix("gateway", "t", "d")
        ms = counters.get_module_summary()
        assert "auth" in ms["modules"]
        assert "gateway" in ms["modules"]
        assert ms["modules"]["auth"]["total_value"] == 4
        assert ms["modules"]["auth"]["counters"] == 2


# ---------------------------------------------------------------------------
# Improvement Velocity
# ---------------------------------------------------------------------------

class TestImprovementVelocity:
    def test_velocity_empty(self, counters):
        v = counters.get_improvement_velocity()
        assert v["status"] == "ok"
        assert v["velocity_per_hour"] == 0.0

    def test_velocity_with_fixes(self, counters):
        counters.record_fix("m", "t", "d")
        counters.record_fix("m", "t", "d2")
        v = counters.get_improvement_velocity(window_hours=24)
        assert v["fixes_in_window"] == 2
        assert v["velocity_per_hour"] == pytest.approx(2 / 24)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class TestHistory:
    def test_history_empty(self, counters):
        assert counters.get_history() == []

    def test_history_ordered_recent_first(self, counters):
        counters.record_fix("a", "t", "first")
        counters.record_fix("b", "t", "second")
        h = counters.get_history()
        assert h[0]["reason"] == "second"
        assert h[1]["reason"] == "first"

    def test_history_filter_by_category(self, counters):
        counters.record_fix("a", "t", "fix")
        counters.record_coverage("b", 1, "cov")
        h = counters.get_history(category="behavior_fix")
        assert len(h) == 1
        assert h[0]["category"] == "behavior_fix"

    def test_history_limit(self, counters):
        for i in range(10):
            counters.record_fix("m", "t", f"fix-{i}")
        h = counters.get_history(limit=3)
        assert len(h) == 3


# ---------------------------------------------------------------------------
# Full Status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_structure(self, counters):
        counters.record_fix("m", "t", "d")
        s = counters.get_status()
        assert s["status"] == "ok"
        assert "counters" in s
        assert "category_summary" in s
        assert "ratio" in s
        assert s["total_events"] == 1

    def test_status_empty(self, counters):
        s = counters.get_status()
        assert s["total_events"] == 0
        assert s["counters"] == {}


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_get_unknown_counter(self, counters):
        result = counters.get_counter("does_not_exist")
        assert result["status"] == "error"

    def test_zero_delta_increment(self, counters):
        cid = counters.register_counter("c", "behavior_fix")
        counters.increment(cid, delta=0)
        assert counters.get_counter(cid)["value"] == 0


# ---------------------------------------------------------------------------
# Clear / Reset
# ---------------------------------------------------------------------------

class TestClear:
    def test_clear_resets_counters(self, counters):
        counters.record_fix("m", "t", "d")
        counters.clear()
        assert counters.get_history() == []
        assert counters.get_category_summary()["total"] == 0
        assert counters.get_status()["counters"] == {}

    def test_clear_allows_fresh_registration(self, counters):
        cid1 = counters.register_counter("a", "behavior_fix")
        counters.clear()
        cid2 = counters.register_counter("a", "behavior_fix")
        assert cid1 != cid2
