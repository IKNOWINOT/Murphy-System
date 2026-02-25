"""Tests for the Golden Path Memory Bridge module."""

import threading
import pytest

from src.golden_path_bridge import (
    GoldenPathBridge,
    GoldenPath,
    PathMatchResult,
    PathStatus,
)


@pytest.fixture
def bridge():
    return GoldenPathBridge()


# ------------------------------------------------------------------
# Recording golden paths
# ------------------------------------------------------------------

class TestRecordSuccess:
    def test_new_path_created(self, bridge):
        path_id = bridge.record_success("deploy-api", "infra", {"steps": ["build", "push"]})
        assert path_id.startswith("gp-")
        path = bridge.get_path(path_id)
        assert path is not None
        assert path.task_pattern == "deploy-api"
        assert path.domain == "infra"
        assert path.success_count == 1
        assert path.confidence_score == 0.7

    def test_update_existing_path(self, bridge):
        pid1 = bridge.record_success("deploy-api", "infra", {"steps": ["build"]})
        pid2 = bridge.record_success("deploy-api", "infra", {"steps": ["build", "push"]})
        assert pid1 == pid2
        path = bridge.get_path(pid1)
        assert path.success_count == 2
        assert path.confidence_score == pytest.approx(0.75, abs=1e-9)

    def test_metadata_merged_on_update(self, bridge):
        bridge.record_success("t", "d", {}, metadata={"a": 1})
        bridge.record_success("t", "d", {}, metadata={"b": 2})
        path = bridge.get_path(bridge.record_success("t", "d", {}))
        assert path.metadata.get("a") == 1
        assert path.metadata.get("b") == 2

    def test_spec_normalized(self, bridge):
        pid = bridge.record_success("t", "d", {"steps": [1], "custom_key": "val"})
        path = bridge.get_path(pid)
        assert "steps" in path.execution_spec
        assert "parameters" in path.execution_spec
        assert path.execution_spec["extra"]["custom_key"] == "val"


# ------------------------------------------------------------------
# Finding matching paths
# ------------------------------------------------------------------

class TestFindMatchingPaths:
    def test_exact_match_score(self, bridge):
        bridge.record_success("deploy-api", "infra", {"steps": []})
        results = bridge.find_matching_paths("deploy-api")
        assert len(results) == 1
        assert results[0].match_score == 1.0

    def test_substring_match(self, bridge):
        bridge.record_success("deploy-api-v2", "infra", {"steps": []})
        results = bridge.find_matching_paths("deploy-api")
        assert len(results) == 1
        assert 0 < results[0].match_score < 1.0

    def test_no_match(self, bridge):
        bridge.record_success("deploy-api", "infra", {"steps": []})
        results = bridge.find_matching_paths("run-tests")
        assert len(results) == 0

    def test_min_confidence_filter(self, bridge):
        pid = bridge.record_success("deploy-api", "infra", {"steps": []})
        # Force low confidence
        bridge.get_path(pid).confidence_score = 0.3
        results = bridge.find_matching_paths("deploy-api", min_confidence=0.5)
        assert len(results) == 0

    def test_domain_boost(self, bridge):
        bridge.record_success("deploy-service", "infra", {"steps": []})
        bridge.record_success("deploy-service", "backend", {"steps": []})

        results = bridge.find_matching_paths("deploy", domain="infra")
        infra_result = [r for r in results if r.domain == "infra"][0]
        backend_result = [r for r in results if r.domain == "backend"][0]
        assert infra_result.match_score > backend_result.match_score

    def test_sorted_by_combined_score(self, bridge):
        pid1 = bridge.record_success("deploy-api", "a", {"steps": []})
        pid2 = bridge.record_success("deploy-api", "b", {"steps": []})
        # Boost second path confidence
        path2 = bridge.get_path(pid2)
        path2.confidence_score = 1.0

        results = bridge.find_matching_paths("deploy-api")
        assert results[0].path_id == pid2

    def test_invalidated_paths_excluded(self, bridge):
        pid = bridge.record_success("deploy-api", "infra", {"steps": []})
        bridge.invalidate_path(pid)
        results = bridge.find_matching_paths("deploy-api")
        assert len(results) == 0


# ------------------------------------------------------------------
# Confidence scoring
# ------------------------------------------------------------------

class TestConfidenceScoring:
    def test_success_increases_confidence(self, bridge):
        bridge.record_success("t", "d", {})
        bridge.record_success("t", "d", {})
        bridge.record_success("t", "d", {})
        pid = bridge.record_success("t", "d", {})
        path = bridge.get_path(pid)
        # initial 0.7 + 3 * 0.05 = 0.85
        assert path.confidence_score == pytest.approx(0.85, abs=1e-9)

    def test_failure_decreases_confidence(self, bridge):
        bridge.record_success("t", "d", {})
        bridge.record_failure("t", "d")
        pid = bridge.record_success("t", "d", {})
        path = bridge.get_path(pid)
        # 0.7 -> fail -0.15 = 0.55 -> success +0.05 = 0.60
        assert path.confidence_score == pytest.approx(0.60, abs=1e-9)

    def test_confidence_capped_at_one(self, bridge):
        bridge.record_success("t", "d", {})
        for _ in range(20):
            bridge.record_success("t", "d", {})
        pid = bridge.record_success("t", "d", {})
        path = bridge.get_path(pid)
        assert path.confidence_score <= 1.0

    def test_confidence_floored_at_zero(self, bridge):
        bridge.record_success("t", "d", {})
        for _ in range(20):
            bridge.record_failure("t", "d")
        pid = bridge.record_success("t", "d", {})
        path = bridge.get_path(pid)
        assert path.confidence_score >= 0.0

    def test_failure_on_nonexistent_path_is_noop(self, bridge):
        bridge.record_failure("nonexistent", "d")
        assert bridge.get_statistics()["total_paths"] == 0


# ------------------------------------------------------------------
# Replay
# ------------------------------------------------------------------

class TestReplay:
    def test_replay_returns_spec(self, bridge):
        pid = bridge.record_success("t", "d", {"steps": ["a", "b"]})
        spec = bridge.replay_path(pid)
        assert spec is not None
        assert spec["steps"] == ["a", "b"]

    def test_replay_increments_success_count(self, bridge):
        pid = bridge.record_success("t", "d", {"steps": []})
        bridge.replay_path(pid)
        path = bridge.get_path(pid)
        assert path.success_count == 2

    def test_replay_increases_confidence(self, bridge):
        pid = bridge.record_success("t", "d", {})
        bridge.replay_path(pid)
        path = bridge.get_path(pid)
        assert path.confidence_score == pytest.approx(0.75, abs=1e-9)

    def test_replay_nonexistent_returns_none(self, bridge):
        assert bridge.replay_path("no-such-id") is None

    def test_replay_invalidated_returns_none(self, bridge):
        pid = bridge.record_success("t", "d", {})
        bridge.invalidate_path(pid)
        assert bridge.replay_path(pid) is None


# ------------------------------------------------------------------
# Invalidation
# ------------------------------------------------------------------

class TestInvalidation:
    def test_invalidate_sets_status(self, bridge):
        pid = bridge.record_success("t", "d", {})
        assert bridge.invalidate_path(pid, reason="config changed")
        path = bridge.get_path(pid)
        assert path.status == PathStatus.INVALIDATED
        assert path.metadata["invalidation_reason"] == "config changed"

    def test_invalidate_nonexistent_returns_false(self, bridge):
        assert bridge.invalidate_path("no-such-id") is False

    def test_invalidated_path_not_replayable(self, bridge):
        pid = bridge.record_success("t", "d", {})
        bridge.invalidate_path(pid)
        assert bridge.replay_path(pid) is None


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------

class TestStatistics:
    def test_empty_statistics(self, bridge):
        stats = bridge.get_statistics()
        assert stats["total_paths"] == 0
        assert stats["avg_confidence"] == 0.0

    def test_statistics_with_paths(self, bridge):
        bridge.record_success("a", "infra", {})
        bridge.record_success("b", "infra", {})
        bridge.record_success("c", "backend", {})
        stats = bridge.get_statistics()
        assert stats["total_paths"] == 3
        assert stats["active_paths"] == 3
        assert stats["domain_breakdown"]["infra"] == 2
        assert stats["domain_breakdown"]["backend"] == 1
        assert stats["avg_confidence"] == pytest.approx(0.7, abs=1e-9)

    def test_statistics_counts_invalidated(self, bridge):
        pid = bridge.record_success("a", "d", {})
        bridge.invalidate_path(pid)
        stats = bridge.get_statistics()
        assert stats["invalidated_paths"] == 1
        assert stats["active_paths"] == 0


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_empty_status(self, bridge):
        status = bridge.get_status()
        assert status["total_paths"] == 0
        assert status["bridge_operational"] is True

    def test_status_counts(self, bridge):
        bridge.record_success("a", "d", {})
        pid = bridge.record_success("b", "d", {})
        bridge.invalidate_path(pid)
        status = bridge.get_status()
        assert status["total_paths"] == 2
        assert status["active_paths"] == 1
        assert status["invalidated_paths"] == 1
        assert status["expired_paths"] == 0


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_record_success(self, bridge):
        errors = []

        def worker(i):
            try:
                bridge.record_success(f"task-{i % 5}", f"domain-{i % 3}", {"step": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = bridge.get_statistics()
        assert stats["total_paths"] > 0

    def test_concurrent_mixed_operations(self, bridge):
        pid = bridge.record_success("shared", "d", {"steps": []})
        errors = []

        def reader():
            try:
                for _ in range(20):
                    bridge.find_matching_paths("shared")
                    bridge.get_path(pid)
                    bridge.get_statistics()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for _ in range(20):
                    bridge.record_success("shared", "d", {"steps": []})
                    bridge.record_failure("shared", "d")
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=reader) for _ in range(5)]
            + [threading.Thread(target=writer) for _ in range(5)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
