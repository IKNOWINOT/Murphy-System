"""
Tests for agent_run_recorder.py

Coverage:
  - AgentRunRecording dataclass (to_dict, from_dict, is_publishable)
  - AgentRunRecorder.record_run (success stored, non-success filtered)
  - list_recordings (filters: publishable_only, status, limit)
  - get_recording, delete_recording
  - Bounded collection (max_recordings)
  - Thread safety (concurrent record_run calls)
  - get_stats

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import os
import threading

import pytest


from agent_run_recorder import (
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_SUCCESS,
    AgentRunRecorder,
    AgentRunRecording,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_recording(**kwargs) -> AgentRunRecording:
    defaults = dict(
        run_id="run-abc-123",
        task_description="Deploy payment gateway",
        task_type="infrastructure",
        status=STATUS_SUCCESS,
        confidence_score=0.88,
        confidence_progression=[{"timestamp": "t0", "confidence": 0.88}],
        steps=[{"step_id": "s1", "success": True}],
        hitl_decisions=[],
        modules_used=["mod_a", "mod_b"],
        gates_passed=["RISK_GATE"],
        duration_seconds=42.0,
        system_version="1.0",
        started_at="2024-01-01T00:00:00Z",
        completed_at="2024-01-01T00:00:42Z",
        terminal_output=["Run started", "Run complete"],
        metadata={},
    )
    defaults.update(kwargs)
    return AgentRunRecording(**defaults)


def _make_recorder(max_recordings: int = 1000) -> AgentRunRecorder:
    return AgentRunRecorder(system_version="1.0", max_recordings=max_recordings)


# ---------------------------------------------------------------------------
# AgentRunRecording
# ---------------------------------------------------------------------------

class TestAgentRunRecording:
    def test_is_publishable_success_high_confidence(self):
        rec = _make_recording(status=STATUS_SUCCESS, confidence_score=0.90)
        assert rec.is_publishable() is True

    def test_is_publishable_success_at_threshold(self):
        rec = _make_recording(status=STATUS_SUCCESS, confidence_score=0.70)
        assert rec.is_publishable(min_confidence=0.70) is True

    def test_is_publishable_success_below_threshold(self):
        rec = _make_recording(status=STATUS_SUCCESS, confidence_score=0.50)
        assert rec.is_publishable(min_confidence=0.70) is False

    def test_is_publishable_failed_high_confidence(self):
        rec = _make_recording(status=STATUS_FAILED, confidence_score=0.99)
        assert rec.is_publishable() is False

    def test_to_dict_round_trip(self):
        rec = _make_recording()
        d = rec.to_dict()
        rec2 = AgentRunRecording.from_dict(d)
        assert rec2.run_id == rec.run_id
        assert rec2.confidence_score == rec.confidence_score
        assert rec2.modules_used == rec.modules_used

    def test_to_dict_has_required_keys(self):
        rec = _make_recording()
        d = rec.to_dict()
        for key in (
            "run_id", "task_description", "task_type", "status",
            "confidence_score", "steps", "modules_used", "gates_passed",
            "duration_seconds", "system_version",
        ):
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# AgentRunRecorder — recording storage
# ---------------------------------------------------------------------------

class TestAgentRunRecorderStore:
    def test_record_success_is_stored(self):
        recorder = _make_recorder()
        result = recorder.record_run(
            task_description="test task",
            task_type="test",
            status=STATUS_SUCCESS,
            confidence_score=0.80,
        )
        assert result is not None
        assert recorder.count() == 1

    def test_record_failed_is_filtered(self):
        recorder = _make_recorder()
        result = recorder.record_run(
            task_description="failing task",
            task_type="test",
            status=STATUS_FAILED,
            confidence_score=0.10,
        )
        assert result is None
        assert recorder.count() == 0

    def test_record_partial_is_filtered(self):
        recorder = _make_recorder()
        result = recorder.record_run(
            task_description="partial task",
            task_type="test",
            status=STATUS_PARTIAL,
            confidence_score=0.60,
        )
        assert result is None
        assert recorder.count() == 0

    def test_custom_run_id_preserved(self):
        recorder = _make_recorder()
        result = recorder.record_run(
            task_description="t",
            task_type="t",
            status=STATUS_SUCCESS,
            confidence_score=0.80,
            run_id="my-custom-id",
        )
        assert result is not None
        assert result.run_id == "my-custom-id"


# ---------------------------------------------------------------------------
# List, get, delete
# ---------------------------------------------------------------------------

class TestAgentRunRecorderQuery:
    def test_list_recordings_all(self):
        recorder = _make_recorder()
        recorder.record_run("t1", "typeA", STATUS_SUCCESS, 0.80, run_id="r1")
        recorder.record_run("t2", "typeB", STATUS_SUCCESS, 0.90, run_id="r2")
        result = recorder.list_recordings()
        assert len(result) == 2

    def test_list_publishable_only(self):
        recorder = _make_recorder()
        recorder.record_run("t1", "t", STATUS_SUCCESS, 0.80, run_id="r1")
        recorder.record_run("t2", "t", STATUS_SUCCESS, 0.50, run_id="r2")
        result = recorder.list_recordings(publishable_only=True, min_confidence=0.70)
        assert len(result) == 1
        assert result[0]["run_id"] == "r1"

    def test_list_limit(self):
        recorder = _make_recorder()
        for idx in range(5):
            recorder.record_run(f"task {idx}", "t", STATUS_SUCCESS, 0.80, run_id=f"r{idx}")
        result = recorder.list_recordings(limit=3)
        assert len(result) == 3

    def test_get_recording_found(self):
        recorder = _make_recorder()
        recorder.record_run("t", "t", STATUS_SUCCESS, 0.80, run_id="found-id")
        rec = recorder.get_recording("found-id")
        assert rec is not None
        assert rec.run_id == "found-id"

    def test_get_recording_not_found(self):
        recorder = _make_recorder()
        assert recorder.get_recording("ghost") is None

    def test_delete_recording_found(self):
        recorder = _make_recorder()
        recorder.record_run("t", "t", STATUS_SUCCESS, 0.80, run_id="del-me")
        deleted = recorder.delete_recording("del-me")
        assert deleted is True
        assert recorder.count() == 0

    def test_delete_recording_not_found(self):
        recorder = _make_recorder()
        deleted = recorder.delete_recording("not-there")
        assert deleted is False


# ---------------------------------------------------------------------------
# Bounded collection
# ---------------------------------------------------------------------------

class TestBoundedCollection:
    def test_evicts_oldest_when_full(self):
        # Use max_recordings=20 so that capped_append's 10% eviction fires:
        # after 20 entries, inserting the 21st evicts 2 (10% of 20), leaving 19.
        recorder = _make_recorder(max_recordings=20)
        for idx in range(25):
            recorder.record_run(f"t{idx}", "t", STATUS_SUCCESS, 0.80, run_id=f"r{idx}")
        assert recorder.count() <= 20

    def test_max_of_1000_default(self):
        recorder = _make_recorder()
        assert recorder._max_recordings == 1000


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_record_run(self):
        recorder = _make_recorder(max_recordings=1000)
        errors: list = []

        def worker(idx: int) -> None:
            try:
                recorder.record_run(f"task {idx}", "t", STATUS_SUCCESS, 0.80)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(idx,)) for idx in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert recorder.count() == 50


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_structure(self):
        recorder = _make_recorder()
        recorder.record_run("t", "t", STATUS_SUCCESS, 0.90, run_id="r1")
        stats = recorder.get_stats()
        assert "total_recordings" in stats
        assert "publishable_recordings" in stats
        assert "average_confidence" in stats
        assert stats["total_recordings"] == 1
        assert stats["publishable_recordings"] == 1
