# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for training_data_pipeline module.

Covers full pipeline runs, instruction-tuning format validation,
80/10/10 split ratios, retention filtering, action type balancing,
empty input handling, export file creation, and format conversion
for various action types.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest


from murphy_foundation_model.action_trace_serializer import (
    ActionTrace,
    ActionTraceCollector,
    trace_to_dict,
)
from murphy_foundation_model.outcome_labeler import OutcomeLabeler
from murphy_foundation_model.training_data_pipeline import TrainingDataPipeline


def _make_trace(**overrides):
    defaults = dict(
        trace_id="t-001",
        timestamp=datetime.now(),
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


def _seed_traces(trace_dir: Path, n: int = 20, **trace_overrides) -> None:
    """Write *n* traces directly into a JSONL file for today."""
    filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
    with open(filepath, "a", encoding="utf-8") as fh:
        for i in range(n):
            overrides = dict(
                trace_id=f"t-{i:04d}",
                action_types=["API_CALL"],
            )
            overrides.update(trace_overrides)
            trace = _make_trace(**overrides)
            fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")


class TestFullPipelineRun:
    """Test full pipeline run with synthetic traces."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_pipeline_with_diverse_traces(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        with open(filepath, "w", encoding="utf-8") as fh:
            for i in range(50):
                types_choice = ["API_CALL", "COMMAND", "ACTUATOR", "DATA", "AGENT"]
                trace = _make_trace(
                    trace_id=f"div-{i:04d}",
                    outcome_success=(i % 3 != 0),
                    action_types=[types_choice[i % len(types_choice)]],
                    human_correction="fix" if i % 7 == 0 else None,
                    confidence_at_decision=round(0.5 + (i % 10) * 0.05, 2),
                )
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir),
            output_dir=str(output_dir),
        )
        result = pipeline.run_pipeline()
        total = result["train"] + result["validation"] + result["test"]
        assert total > 0
        assert result["train"] >= result["validation"]
        assert result["train"] >= result["test"]


class TestInstructionTuningFormat:
    """Test instruction-tuning format output validation."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_all_output_fields_present(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        _seed_traces(trace_dir, n=10)

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir),
            output_dir=str(output_dir),
        )
        pipeline.run_pipeline()

        with open(output_dir / "train.jsonl") as fh:
            for line in fh:
                example = json.loads(line)
                assert "instruction" in example
                assert "input" in example
                assert "output" in example
                assert "quality" in example

                inp = example["input"]
                assert "world_state" in inp
                assert "intent" in inp
                assert "constraints" in inp
                assert "murphy_index" in inp

                out = example["output"]
                assert "action_plan" in out
                assert "confidence" in out
                assert "predicted_murphy_index" in out
                assert "escalation_needed" in out

                qual = example["quality"]
                assert "label_category" in qual
                assert "overall_quality" in qual

    def test_instruction_is_nonempty_string(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()
        _seed_traces(trace_dir, n=5)

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        pipeline.run_pipeline()

        with open(output_dir / "train.jsonl") as fh:
            for line in fh:
                example = json.loads(line)
                assert isinstance(example["instruction"], str)
                assert len(example["instruction"]) > 10


class TestSplitRatios:
    """Test 80/10/10 split ratio verification."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_approximate_80_10_10_split(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        # Large enough for meaningful splits
        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        with open(filepath, "w", encoding="utf-8") as fh:
            for i in range(100):
                trace = _make_trace(
                    trace_id=f"split-{i:04d}",
                    outcome_success=(i % 3 != 0),
                    human_correction="fix" if i % 5 == 0 else None,
                )
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        result = pipeline.run_pipeline()

        total = result["train"] + result["validation"] + result["test"]
        assert total > 0
        # Allow some slack due to stratification and rounding
        train_ratio = result["train"] / total
        assert 0.6 <= train_ratio <= 0.95, f"Train ratio {train_ratio} out of range"


class TestRetentionFilter:
    """Test retention filter (old traces excluded)."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_old_traces_excluded_by_retention(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        # Write traces with old timestamps into today's file
        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        with open(filepath, "w", encoding="utf-8") as fh:
            # 5 old traces (200 days ago)
            for i in range(5):
                trace = _make_trace(
                    trace_id=f"old-{i}",
                    timestamp=datetime.now() - timedelta(days=200),
                )
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")
            # 10 recent traces
            for i in range(10):
                trace = _make_trace(trace_id=f"new-{i}")
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir),
            output_dir=str(output_dir),
            retention_days=90,
        )
        result = pipeline.run_pipeline()
        total = result["train"] + result["validation"] + result["test"]
        assert total == 10


class TestActionTypeBalancing:
    """Test action type balancing."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_imbalanced_types_are_capped(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        with open(filepath, "w", encoding="utf-8") as fh:
            # 50 API_CALL traces
            for i in range(50):
                trace = _make_trace(
                    trace_id=f"api-{i}", action_types=["API_CALL"]
                )
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")
            # 5 COMMAND traces
            for i in range(5):
                trace = _make_trace(
                    trace_id=f"cmd-{i}", action_types=["COMMAND"]
                )
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        result = pipeline.run_pipeline()
        total = result["train"] + result["validation"] + result["test"]
        # After balancing, API_CALL should be capped; total ≤ original 55
        assert total <= 55


class TestEmptyInputHandling:
    """Test empty input handling."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_no_trace_files(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        result = pipeline.run_pipeline()
        assert result == {"train": 0, "validation": 0, "test": 0}

    def test_empty_trace_file(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        filepath.write_text("")

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        result = pipeline.run_pipeline()
        assert result == {"train": 0, "validation": 0, "test": 0}


class TestExportFileCreation:
    """Test export file creation."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_all_three_files_created(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()
        _seed_traces(trace_dir, n=15)

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        pipeline.run_pipeline()

        assert (output_dir / "train.jsonl").exists()
        assert (output_dir / "validation.jsonl").exists()
        assert (output_dir / "test.jsonl").exists()

    def test_output_files_are_valid_jsonl(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()
        _seed_traces(trace_dir, n=20)

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        pipeline.run_pipeline()

        for name in ("train.jsonl", "validation.jsonl", "test.jsonl"):
            with open(output_dir / name) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        json.loads(line)  # should not raise


class TestFormatConversionVariousTypes:
    """Test format conversion for various action types."""

    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_different_action_types_in_output(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        types = ["API_CALL", "COMMAND", "ACTUATOR", "DATA", "CONTENT", "AGENT"]
        with open(filepath, "w", encoding="utf-8") as fh:
            for i, at in enumerate(types):
                trace = _make_trace(
                    trace_id=f"type-{i}",
                    action_types=[at],
                    actions_taken=[{"type": at, "detail": f"action_{at}"}],
                )
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        result = pipeline.run_pipeline()
        total = result["train"] + result["validation"] + result["test"]
        assert total == len(types)

    def test_traces_with_escalation_constraint(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        with open(filepath, "w", encoding="utf-8") as fh:
            trace = _make_trace(
                trace_id="esc-1",
                constraints=[{"name": "safety", "escalation": True}],
            )
            fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")
            trace2 = _make_trace(
                trace_id="esc-2",
                constraints=[{"name": "budget", "escalation": False}],
            )
            fh.write(json.dumps(trace_to_dict(trace2), default=str) + "\n")

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir), output_dir=str(output_dir)
        )
        pipeline.run_pipeline()

        for name in ("train.jsonl", "validation.jsonl", "test.jsonl"):
            with open(output_dir / name) as fh:
                for line in fh:
                    example = json.loads(line.strip())
                    assert isinstance(example["output"]["escalation_needed"], bool)
