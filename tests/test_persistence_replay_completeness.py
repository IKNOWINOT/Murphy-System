"""
Tests for persistence_replay_completeness module.

Covers all five capabilities:
1. Full replay orchestration
2. State snapshots
3. Point-in-time recovery
4. Write-ahead log (WAL)
5. Snapshot diffing

Uses standard unittest.TestCase pattern with pytest fixtures.
"""

import time
import json
import threading
import pytest

from src.persistence_replay_completeness import (
    WriteAheadLog,
    SnapshotManager,
    PointInTimeRecovery,
    ReplayOrchestrator,
    PersistenceReplayCompleteness,
    ReplayMode,
    ReplayState,
    WALEntry,
    StateSnapshot,
    WAL_STATUS_PENDING,
    WAL_STATUS_COMMITTED,
    WAL_STATUS_ROLLED_BACK,
)


# ================================================================
# Fixtures
# ================================================================

@pytest.fixture
def wal(tmp_path):
    return WriteAheadLog(wal_dir=str(tmp_path / "wal"))


@pytest.fixture
def snap_mgr(tmp_path):
    return SnapshotManager(snapshot_dir=str(tmp_path / "snapshots"))


@pytest.fixture
def recovery():
    return PointInTimeRecovery()


@pytest.fixture
def orchestrator():
    return ReplayOrchestrator()


@pytest.fixture
def facade(tmp_path):
    return PersistenceReplayCompleteness(
        wal_dir=str(tmp_path / "wal"),
        snapshot_dir=str(tmp_path / "snapshots"),
    )


# ================================================================
# 1. Write-Ahead Log Tests
# ================================================================

class TestWriteAheadLog:
    def test_log_operation_returns_id(self, wal):
        entry_id = wal.log_operation("save", {"key": "value"})
        assert isinstance(entry_id, str)
        assert len(entry_id) > 0

    def test_pending_after_log(self, wal):
        wal.log_operation("save", {"doc": "a"})
        pending = wal.get_pending()
        assert len(pending) == 1
        assert pending[0]["status"] == WAL_STATUS_PENDING

    def test_commit_clears_pending(self, wal):
        entry_id = wal.log_operation("save", {"doc": "a"})
        wal.commit(entry_id, result={"ok": True})
        assert len(wal.get_pending()) == 0

    def test_commit_nonexistent_returns_false(self, wal):
        assert wal.commit("nonexistent-id") is False

    def test_rollback_marks_entry(self, wal):
        entry_id = wal.log_operation("delete", {"doc": "b"})
        assert wal.rollback(entry_id) is True
        entries = wal.get_all_entries()
        assert entries[0]["status"] == WAL_STATUS_ROLLED_BACK

    def test_rollback_nonexistent_returns_false(self, wal):
        assert wal.rollback("no-such-id") is False

    def test_clear_committed_removes_only_committed(self, wal):
        id1 = wal.log_operation("op1", {})
        wal.log_operation("op2", {})
        wal.commit(id1)
        removed = wal.clear_committed()
        assert removed == 1
        assert len(wal.get_all_entries()) == 1

    def test_persistence_across_instances(self, tmp_path):
        wal_dir = str(tmp_path / "wal_persist")
        wal1 = WriteAheadLog(wal_dir=wal_dir)
        wal1.log_operation("op", {"x": 1})
        # New instance reads from same directory
        wal2 = WriteAheadLog(wal_dir=wal_dir)
        assert len(wal2.get_pending()) == 1

    def test_wal_status(self, wal):
        wal.log_operation("a", {})
        entry_id = wal.log_operation("b", {})
        wal.commit(entry_id)
        status = wal.get_status()
        assert status["total_entries"] == 2
        assert status["pending"] == 1
        assert status["committed"] == 1


# ================================================================
# 2. State Snapshot Tests
# ================================================================

class TestSnapshotManager:
    def test_create_snapshot(self, snap_mgr):
        result = snap_mgr.create_snapshot({"counter": 1}, label="initial")
        assert "snapshot_id" in result
        assert result["label"] == "initial"

    def test_restore_snapshot(self, snap_mgr):
        state = {"counter": 42, "items": [1, 2, 3]}
        info = snap_mgr.create_snapshot(state, label="test")
        restored = snap_mgr.restore_snapshot(info["snapshot_id"])
        assert restored == state

    def test_restore_returns_deep_copy(self, snap_mgr):
        state = {"nested": {"key": "val"}}
        info = snap_mgr.create_snapshot(state, label="deep")
        restored = snap_mgr.restore_snapshot(info["snapshot_id"])
        restored["nested"]["key"] = "modified"
        restored2 = snap_mgr.restore_snapshot(info["snapshot_id"])
        assert restored2["nested"]["key"] == "val"

    def test_restore_nonexistent_returns_none(self, snap_mgr):
        assert snap_mgr.restore_snapshot("no-such-id") is None

    def test_list_snapshots_ordered(self, snap_mgr):
        snap_mgr.create_snapshot({"a": 1}, label="first")
        time.sleep(0.01)
        snap_mgr.create_snapshot({"b": 2}, label="second")
        listing = snap_mgr.list_snapshots()
        assert len(listing) == 2
        assert listing[0]["label"] == "first"
        assert listing[1]["label"] == "second"

    def test_delete_snapshot(self, snap_mgr):
        info = snap_mgr.create_snapshot({"x": 1}, label="del")
        assert snap_mgr.delete_snapshot(info["snapshot_id"]) is True
        assert snap_mgr.restore_snapshot(info["snapshot_id"]) is None

    def test_delete_nonexistent_returns_false(self, snap_mgr):
        assert snap_mgr.delete_snapshot("missing") is False

    def test_get_snapshot_info(self, snap_mgr):
        info = snap_mgr.create_snapshot({"a": 1, "b": 2}, label="info_test")
        detail = snap_mgr.get_snapshot_info(info["snapshot_id"])
        assert detail is not None
        assert "a" in detail["state_keys"]
        assert "b" in detail["state_keys"]

    def test_snapshot_status(self, snap_mgr):
        snap_mgr.create_snapshot({}, label="s")
        status = snap_mgr.get_status()
        assert status["total_snapshots"] == 1


# ================================================================
# 3. Point-in-Time Recovery Tests
# ================================================================

class TestPointInTimeRecovery:
    def test_record_and_recover(self, recovery):
        recovery.record_state({"v": 1}, label="v1", timestamp=100.0)
        recovery.record_state({"v": 2}, label="v2", timestamp=200.0)
        result = recovery.recover_to_timestamp(150.0)
        assert result is not None
        assert result["state"]["v"] == 1

    def test_recover_exact_timestamp(self, recovery):
        recovery.record_state({"v": 10}, label="exact", timestamp=500.0)
        result = recovery.recover_to_timestamp(500.0)
        assert result["state"]["v"] == 10

    def test_recover_before_earliest_returns_none(self, recovery):
        recovery.record_state({"v": 1}, timestamp=100.0)
        assert recovery.recover_to_timestamp(50.0) is None

    def test_recover_to_index(self, recovery):
        recovery.record_state({"step": "a"}, timestamp=1.0)
        recovery.record_state({"step": "b"}, timestamp=2.0)
        result = recovery.recover_to_index(0)
        assert result["state"]["step"] == "a"

    def test_recover_to_index_out_of_range(self, recovery):
        assert recovery.recover_to_index(99) is None

    def test_rollback_removes_future(self, recovery):
        recovery.record_state({"v": 1}, timestamp=10.0)
        recovery.record_state({"v": 2}, timestamp=20.0)
        recovery.record_state({"v": 3}, timestamp=30.0)
        info = recovery.rollback_to_timestamp(20.0)
        assert info["rolled_back_count"] == 1
        assert info["remaining_count"] == 2

    def test_list_checkpoints(self, recovery):
        recovery.record_state({}, label="cp1", timestamp=1.0)
        recovery.record_state({}, label="cp2", timestamp=2.0)
        cps = recovery.list_checkpoints()
        assert len(cps) == 2
        assert cps[0]["label"] == "cp1"

    def test_recovery_status(self, recovery):
        recovery.record_state({}, timestamp=5.0)
        status = recovery.get_status()
        assert status["total_checkpoints"] == 1
        assert status["timestamp_range"]["earliest"] == 5.0


# ================================================================
# 4. Replay Orchestrator Tests
# ================================================================

class TestReplayOrchestrator:
    def test_load_sequence(self, orchestrator):
        events = [{"action": "a"}, {"action": "b"}]
        info = orchestrator.load_sequence(events, session_id="s1")
        assert info["total_steps"] == 2
        assert info["session_id"] == "s1"

    def test_run_continuous(self, orchestrator):
        events = [{"n": 1}, {"n": 2}, {"n": 3}]
        orchestrator.load_sequence(events)
        result = orchestrator.run()
        assert result["executed"] == 3
        assert result["errors"] == 0

    def test_run_with_callback(self, orchestrator):
        events = [{"x": 10}]
        orchestrator.load_sequence(
            events,
            callback=lambda e: {"doubled": e["x"] * 2},
        )
        result = orchestrator.run()
        assert result["results"][0]["result"]["doubled"] == 20

    def test_run_callback_error(self, orchestrator):
        def failing(_):
            raise ValueError("boom")
        orchestrator.load_sequence([{"a": 1}], callback=failing)
        result = orchestrator.run()
        assert result["errors"] == 1
        assert "boom" in result["results"][0]["error"]

    def test_step_forward(self, orchestrator):
        orchestrator.load_sequence([{"s": 1}, {"s": 2}], mode="step")
        r1 = orchestrator.step_forward()
        assert r1 is not None
        assert r1["step_index"] == 0
        r2 = orchestrator.step_forward()
        assert r2["step_index"] == 1
        r3 = orchestrator.step_forward()
        assert r3 is None  # no more steps

    def test_pause_and_resume(self, orchestrator):
        orchestrator.load_sequence([{"a": 1}, {"a": 2}, {"a": 3}])
        orchestrator.step_forward()
        pause_info = orchestrator.pause()
        assert pause_info["state"] == "paused"
        resume_result = orchestrator.resume()
        assert resume_result["executed"] == 2  # remaining 2 steps

    def test_reset(self, orchestrator):
        orchestrator.load_sequence([{"a": 1}])
        orchestrator.run()
        reset_info = orchestrator.reset()
        assert reset_info["state"] == "idle"
        assert reset_info["steps_reset"] == 1

    def test_get_progress(self, orchestrator):
        orchestrator.load_sequence([{"a": 1}], mode="step", speed=2.0)
        progress = orchestrator.get_progress()
        assert progress["total_steps"] == 1
        assert progress["speed"] == 2.0

    def test_run_empty_sequence(self, orchestrator):
        orchestrator.load_sequence([])
        result = orchestrator.run()
        assert result["total_steps"] == 0
        assert result["executed"] == 0


# ================================================================
# 5. Snapshot Diffing Tests
# ================================================================

class TestSnapshotDiffing:
    def test_diff_added_keys(self, snap_mgr):
        a = snap_mgr.create_snapshot({"x": 1}, label="a")
        b = snap_mgr.create_snapshot({"x": 1, "y": 2}, label="b")
        diff = snap_mgr.diff_snapshots(a["snapshot_id"], b["snapshot_id"])
        assert "y" in diff["added"]
        assert len(diff["removed"]) == 0

    def test_diff_removed_keys(self, snap_mgr):
        a = snap_mgr.create_snapshot({"x": 1, "y": 2}, label="a")
        b = snap_mgr.create_snapshot({"x": 1}, label="b")
        diff = snap_mgr.diff_snapshots(a["snapshot_id"], b["snapshot_id"])
        assert "y" in diff["removed"]
        assert len(diff["added"]) == 0

    def test_diff_modified_keys(self, snap_mgr):
        a = snap_mgr.create_snapshot({"x": 1}, label="a")
        b = snap_mgr.create_snapshot({"x": 99}, label="b")
        diff = snap_mgr.diff_snapshots(a["snapshot_id"], b["snapshot_id"])
        assert "x" in diff["modified"]
        assert diff["modified"]["x"]["old"] == 1
        assert diff["modified"]["x"]["new"] == 99

    def test_diff_identical_snapshots(self, snap_mgr):
        a = snap_mgr.create_snapshot({"k": "v"}, label="a")
        b = snap_mgr.create_snapshot({"k": "v"}, label="b")
        diff = snap_mgr.diff_snapshots(a["snapshot_id"], b["snapshot_id"])
        assert diff["total_changes"] == 0

    def test_diff_missing_snapshot_returns_none(self, snap_mgr):
        a = snap_mgr.create_snapshot({}, label="a")
        assert snap_mgr.diff_snapshots(a["snapshot_id"], "missing") is None

    def test_compare_identical(self, snap_mgr):
        a = snap_mgr.create_snapshot({"a": 1}, label="a")
        b = snap_mgr.create_snapshot({"a": 1}, label="b")
        cmp = snap_mgr.compare_snapshots(a["snapshot_id"], b["snapshot_id"])
        assert cmp["identical"] is True

    def test_compare_different(self, snap_mgr):
        a = snap_mgr.create_snapshot({"a": 1}, label="a")
        b = snap_mgr.create_snapshot({"a": 2}, label="b")
        cmp = snap_mgr.compare_snapshots(a["snapshot_id"], b["snapshot_id"])
        assert cmp["identical"] is False


# ================================================================
# 6. Unified Facade Tests
# ================================================================

class TestPersistenceReplayCompleteness:
    def test_protected_operation_success(self, facade):
        result = facade.protected_operation(
            "add", {"n": 5}, executor=lambda d: {"sum": d["n"] + 1}
        )
        assert result["sum"] == 6
        assert len(facade.wal.get_pending()) == 0

    def test_protected_operation_failure_rolls_back(self, facade):
        def bad(_):
            raise RuntimeError("fail")
        with pytest.raises(RuntimeError):
            facade.protected_operation("bad_op", {}, executor=bad)
        entries = facade.wal.get_all_entries()
        assert entries[0]["status"] == WAL_STATUS_ROLLED_BACK

    def test_snapshot_and_record(self, facade):
        info = facade.snapshot_and_record({"v": 1}, label="combo")
        assert "snapshot_id" in info
        assert "checkpoint_index" in info

    def test_combined_status(self, facade):
        status = facade.get_status()
        assert "wal" in status
        assert "snapshots" in status
        assert "recovery" in status
        assert "orchestrator" in status


# ================================================================
# 7. Thread Safety Tests
# ================================================================

class TestThreadSafety:
    def test_concurrent_wal_operations(self, wal):
        ids = []
        def log_op(i):
            eid = wal.log_operation(f"op_{i}", {"i": i})
            ids.append(eid)

        threads = [threading.Thread(target=log_op, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(wal.get_all_entries()) == 10

    def test_concurrent_snapshot_creation(self, snap_mgr):
        def create_snap(i):
            snap_mgr.create_snapshot({"i": i}, label=f"snap_{i}")

        threads = [threading.Thread(target=create_snap, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(snap_mgr.list_snapshots()) == 10
