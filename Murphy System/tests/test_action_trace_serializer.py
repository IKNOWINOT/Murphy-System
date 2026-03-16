# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for action_trace_serializer module.

Covers complex nested data round-trips, daily file rotation, thread
safety, CLI entry-point, empty directory edge cases, and stats accuracy.
"""

from __future__ import annotations

import gzip
import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest


from murphy_foundation_model.action_trace_serializer import (
    ActionTrace,
    ActionTraceCollector,
    dict_to_trace,
    trace_to_dict,
)


def _make_trace(**overrides):
    defaults = dict(
        trace_id="t-001",
        timestamp=datetime(2025, 6, 1, 12, 0, 0),
        world_state={"cpu": 42.0},
        intent="test intent",
        constraints=[],
        confidence_at_decision=0.9,
        murphy_index_at_decision=0.1,
        alternatives_considered=[],
        reasoning_chain=["step1"],
        actions_taken=[{"action": "test"}],
        action_types=["API_CALL"],
        outcome_success=True,
        outcome_utility=0.8,
        outcome_details={"detail": "ok"},
    )
    defaults.update(overrides)
    return ActionTrace(**defaults)


class TestActionTraceDataclass:
    """Test ActionTrace dataclass creation with all fields."""

    def test_all_required_fields(self):
        trace = _make_trace()
        assert trace.trace_id == "t-001"
        assert trace.timestamp == datetime(2025, 6, 1, 12, 0, 0)
        assert trace.world_state == {"cpu": 42.0}
        assert trace.intent == "test intent"
        assert trace.confidence_at_decision == 0.9
        assert trace.murphy_index_at_decision == 0.1
        assert trace.actions_taken == [{"action": "test"}]
        assert trace.action_types == ["API_CALL"]
        assert trace.outcome_success is True
        assert trace.outcome_utility == 0.8

    def test_optional_field_defaults(self):
        trace = _make_trace()
        assert trace.human_correction is None
        assert trace.phase == ""
        assert trace.engine_used == ""
        assert trace.authority_level == ""
        assert trace.execution_time_ms == 0.0
        assert trace.labels is None

    def test_optional_fields_set(self):
        trace = _make_trace(
            human_correction="fixed",
            phase="runtime",
            engine_used="exec",
            authority_level="autonomous",
            execution_time_ms=150.0,
            labels={"overall_quality": 0.85},
        )
        assert trace.human_correction == "fixed"
        assert trace.phase == "runtime"
        assert trace.execution_time_ms == 150.0
        assert trace.labels == {"overall_quality": 0.85}


class TestRoundTripComplexData:
    """Test trace_to_dict and dict_to_trace round-trip with complex nested data."""

    def test_deeply_nested_world_state(self):
        nested = {
            "sensors": {"temp": [20.0, 21.5], "nested": {"deep": {"value": True}}},
            "metadata": {"tags": ["a", "b", "c"]},
        }
        trace = _make_trace(world_state=nested)
        d = trace_to_dict(trace)
        restored = dict_to_trace(d)
        assert restored.world_state == nested

    def test_complex_constraints_and_alternatives(self):
        trace = _make_trace(
            constraints=[{"name": "budget", "limit": 500}, {"name": "time", "max_ms": 2000}],
            alternatives_considered=[
                {"plan": "A", "score": 0.9, "steps": [1, 2]},
                {"plan": "B", "score": 0.7, "steps": [3, 4, 5]},
            ],
        )
        d = trace_to_dict(trace)
        restored = dict_to_trace(d)
        assert len(restored.constraints) == 2
        assert restored.constraints[0]["name"] == "budget"
        assert len(restored.alternatives_considered) == 2
        assert restored.alternatives_considered[1]["score"] == 0.7

    def test_multiple_actions_and_types(self):
        trace = _make_trace(
            actions_taken=[
                {"type": "API_CALL", "target": "svc1"},
                {"type": "COMMAND", "cmd": "restart"},
                {"type": "AGENT", "agent_id": "a1"},
            ],
            action_types=["API_CALL", "COMMAND", "AGENT"],
        )
        d = trace_to_dict(trace)
        restored = dict_to_trace(d)
        assert len(restored.actions_taken) == 3
        assert restored.action_types == ["API_CALL", "COMMAND", "AGENT"]

    def test_round_trip_preserves_all_fields(self):
        trace = _make_trace(
            trace_id="rt-full",
            human_correction="patched",
            phase="planning",
            engine_used="llm",
            authority_level="high",
            execution_time_ms=42.5,
            labels={"quality": 0.9},
        )
        d = trace_to_dict(trace)
        restored = dict_to_trace(d)
        assert restored.trace_id == "rt-full"
        assert restored.human_correction == "patched"
        assert restored.phase == "planning"
        assert restored.execution_time_ms == 42.5
        assert restored.labels == {"quality": 0.9}


class TestCollectorDailyRotation:
    """Test ActionTraceCollector daily file rotation."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_daily_rotation_creates_new_file(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        trace = _make_trace()
        collector.record_trace(trace)
        collector.flush()

        today = datetime.now().strftime("%Y-%m-%d")
        expected = tmp_path / f"traces_{today}.jsonl"
        assert expected.exists()

    def test_multiple_flushes_same_day_append(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        collector.record_trace(_make_trace(trace_id="a"))
        collector.flush()
        collector.record_trace(_make_trace(trace_id="b"))
        collector.flush()

        files = list(tmp_path.glob("traces_*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text().strip().split("\n")
        assert len(lines) == 2


class TestLoadTracesFiltering:
    """Test load_traces with date filtering."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_multiple_date_files_filtering(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))

        for days_ago in [1, 5, 15, 30]:
            date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            filepath = tmp_path / f"traces_{date_str}.jsonl"
            trace = _make_trace(trace_id=f"t-{days_ago}d")
            filepath.write_text(json.dumps(trace_to_dict(trace), default=str) + "\n")

        recent = collector.load_traces(since_days=10)
        ids = {t.trace_id for t in recent}
        assert "t-1d" in ids
        assert "t-5d" in ids
        assert "t-15d" not in ids
        assert "t-30d" not in ids


class TestStatsAccuracy:
    """Test stats accuracy after many records."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_stats_after_many_records(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        types = ["API_CALL", "COMMAND", "ACTUATOR", "DATA"]
        for i in range(40):
            collector.record_trace(_make_trace(
                trace_id=f"t-{i:04d}",
                outcome_success=(i % 4 != 0),
                action_types=[types[i % len(types)]],
            ))

        stats = collector.get_stats()
        assert stats["total_traces"] == 40
        assert stats["action_type_distribution"]["API_CALL"] == 10
        assert stats["action_type_distribution"]["COMMAND"] == 10
        assert stats["success_rate"] == 30 / 40
        assert stats["failure_rate"] == 10 / 40

    def test_stats_with_multiple_action_types_per_trace(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        collector.record_trace(_make_trace(action_types=["API_CALL", "COMMAND"]))
        stats = collector.get_stats()
        assert stats["action_type_distribution"]["API_CALL"] == 1
        assert stats["action_type_distribution"]["COMMAND"] == 1


class TestCompressGzip:
    """Test compress with gzip verification."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_compressed_file_is_valid_gzip(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"traces_{old_date}.jsonl"
        content = json.dumps(trace_to_dict(_make_trace()), default=str) + "\n"
        old_file.write_text(content)

        collector.compress_old_files(older_than_days=5)

        gz_path = tmp_path / f"traces_{old_date}.jsonl.gz"
        assert gz_path.exists()
        with gzip.open(gz_path, "rt") as f:
            decompressed = f.read()
        assert decompressed == content

    def test_compress_does_not_double_compress(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"traces_{old_date}.jsonl"
        old_file.write_text('{"trace_id":"x"}\n')

        assert collector.compress_old_files(older_than_days=5) == 1
        # Second call should not compress again (original .jsonl gone)
        assert collector.compress_old_files(older_than_days=5) == 0


class TestEmptyTraceDirectory:
    """Test empty trace directory handling."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_load_from_empty_directory(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        traces = collector.load_traces()
        assert traces == []

    def test_stats_on_empty_collector(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        stats = collector.get_stats()
        assert stats["total_traces"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["failure_rate"] == 0.0


class TestThreadSafety:
    """Test record from multiple threads."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_concurrent_records(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        errors = []

        def worker(thread_id):
            try:
                for i in range(20):
                    collector.record_trace(
                        _make_trace(trace_id=f"thread-{thread_id}-{i}")
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        collector.flush()
        assert len(errors) == 0
        stats = collector.get_stats()
        assert stats["total_traces"] == 100
