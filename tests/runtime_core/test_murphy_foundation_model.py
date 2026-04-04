# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Comprehensive test suite for the Murphy Foundation Model — Phase 1 & 2 modules.

Covers:
- ActionTrace dataclass and serialization helpers
- ActionTraceCollector (singleton, record, flush, load, compress, stats)
- OutcomeLabeler scoring dimensions and label categories
- TrainingDataPipeline (load → label → balance → split → export)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from murphy_foundation_model import __version__  # noqa: E402
from murphy_foundation_model.action_trace_serializer import (  # noqa: E402
    ActionTrace,
    ActionTraceCollector,
    dict_to_trace,
    trace_to_dict,
)
from murphy_foundation_model.outcome_labeler import (  # noqa: E402
    OutcomeLabeler,
    OutcomeLabels,
)
from murphy_foundation_model.training_data_pipeline import (  # noqa: E402
    TrainingDataPipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trace(
    *,
    trace_id: str = "t-001",
    success: bool = True,
    action_types: list | None = None,
    confidence: float = 0.8,
    murphy_index: float = 0.3,
    execution_time_ms: float = 120.0,
    human_correction: str | None = None,
    outcome_details: dict | None = None,
    timestamp: datetime | None = None,
) -> ActionTrace:
    """Factory for creating test traces with sensible defaults."""
    return ActionTrace(
        trace_id=trace_id,
        timestamp=timestamp or datetime.now(),
        world_state={"sensor": "value"},
        intent="do_something",
        constraints=[{"name": "budget", "max": 100}],
        confidence_at_decision=confidence,
        murphy_index_at_decision=murphy_index,
        alternatives_considered=[{"alt": "plan_b"}],
        reasoning_chain=["step1", "step2"],
        actions_taken=[{"type": "API_CALL", "target": "svc"}],
        action_types=action_types or ["API_CALL"],
        outcome_success=success,
        outcome_utility=0.7 if success else -0.3,
        outcome_details=outcome_details or {},
        human_correction=human_correction,
        phase="runtime",
        engine_used="execution_engine",
        authority_level="autonomous",
        execution_time_ms=execution_time_ms,
    )


# ---------------------------------------------------------------------------
# Package metadata
# ---------------------------------------------------------------------------

class TestPackageMetadata:
    def test_version(self):
        assert __version__ == "0.1.0"


# ---------------------------------------------------------------------------
# ActionTrace & serialization
# ---------------------------------------------------------------------------

class TestActionTraceSerialization:
    def test_round_trip(self):
        trace = _make_trace()
        d = trace_to_dict(trace)
        restored = dict_to_trace(d)
        assert restored.trace_id == trace.trace_id
        assert restored.intent == trace.intent
        assert restored.outcome_success == trace.outcome_success

    def test_timestamp_serialization(self):
        now = datetime.now()
        trace = _make_trace(timestamp=now)
        d = trace_to_dict(trace)
        assert isinstance(d["timestamp"], str)
        restored = dict_to_trace(d)
        assert isinstance(restored.timestamp, datetime)
        # Restored timestamp is normalised to UTC-aware; compare the bare values.
        assert restored.timestamp.replace(tzinfo=None) == now.replace(tzinfo=None)

    def test_labels_none_by_default(self):
        trace = _make_trace()
        assert trace.labels is None

    def test_optional_fields_default(self):
        trace = _make_trace()
        assert trace.human_correction is None
        assert trace.phase == "runtime"


# ---------------------------------------------------------------------------
# ActionTraceCollector
# ---------------------------------------------------------------------------

class TestActionTraceCollector:
    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def test_singleton(self, tmp_path):
        c1 = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        c2 = ActionTraceCollector.get_instance()
        assert c1 is c2

    def test_reset_instance(self, tmp_path):
        c1 = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        ActionTraceCollector.reset_instance()
        c2 = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        assert c1 is not c2

    def test_record_and_flush(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        trace = _make_trace()
        collector.record_trace(trace)
        collector.flush()

        files = list(tmp_path.glob("traces_*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text().strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["trace_id"] == "t-001"

    def test_load_traces(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        for i in range(5):
            collector.record_trace(_make_trace(trace_id=f"t-{i:03d}"))
        collector.flush()

        loaded = collector.load_traces()
        assert len(loaded) == 5
        assert all(isinstance(t, ActionTrace) for t in loaded)

    def test_load_traces_since_days(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        # Write a trace file backdated to 10 days ago
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"traces_{old_date}.jsonl"
        old_trace = _make_trace(trace_id="old")
        old_file.write_text(json.dumps(trace_to_dict(old_trace), default=str) + "\n")

        # Write today's trace
        collector.record_trace(_make_trace(trace_id="new"))
        collector.flush()

        # Only recent
        recent = collector.load_traces(since_days=5)
        ids = [t.trace_id for t in recent]
        assert "new" in ids
        assert "old" not in ids

        # All
        all_traces = collector.load_traces()
        assert len(all_traces) == 2

    def test_stats(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        collector.record_trace(_make_trace(success=True, action_types=["API_CALL"]))
        collector.record_trace(_make_trace(success=False, action_types=["COMMAND"]))

        stats = collector.get_stats()
        assert stats["total_traces"] == 2
        assert stats["action_type_distribution"]["API_CALL"] == 1
        assert stats["action_type_distribution"]["COMMAND"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["failure_rate"] == 0.5

    def test_auto_flush_at_100(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        for i in range(101):
            collector.record_trace(_make_trace(trace_id=f"t-{i:04d}"))
        # After 100 the buffer auto-flushed; 1 remains in buffer
        assert len(collector.traces_buffer) == 1

    def test_compress_old_files(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"traces_{old_date}.jsonl"
        old_file.write_text('{"trace_id":"old"}\n')

        compressed = collector.compress_old_files(older_than_days=5)
        assert compressed == 1
        assert not old_file.exists()
        assert (tmp_path / f"traces_{old_date}.jsonl.gz").exists()

    def test_compress_skips_recent(self, tmp_path):
        collector = ActionTraceCollector.get_instance(trace_dir=str(tmp_path))
        collector.record_trace(_make_trace())
        collector.flush()

        compressed = collector.compress_old_files(older_than_days=1)
        assert compressed == 0


# ---------------------------------------------------------------------------
# OutcomeLabeler
# ---------------------------------------------------------------------------

class TestOutcomeLabeler:
    def test_positive_label(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(success=True, human_correction=None)
        labels = labeler.label_trace(trace)
        assert labels.success is True
        assert labels.label_category == "positive"
        assert labels.human_agreement == 1.0

    def test_partial_label(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(success=True, human_correction="fixed typo")
        labels = labeler.label_trace(trace)
        assert labels.label_category == "partial"
        assert labels.human_agreement == 0.5

    def test_negative_label(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(success=False)
        labels = labeler.label_trace(trace)
        assert labels.label_category == "negative"
        assert labels.success is False

    def test_efficiency_with_baseline(self):
        labeler = OutcomeLabeler(efficiency_baseline={"API_CALL": 100.0})
        # At baseline → 1.0
        trace = _make_trace(execution_time_ms=100.0)
        assert labeler.label_trace(trace).efficiency == 1.0

        # Below baseline → 1.0
        trace = _make_trace(execution_time_ms=50.0)
        assert labeler.label_trace(trace).efficiency == 1.0

        # 5× baseline → 0.0
        trace = _make_trace(execution_time_ms=500.0)
        assert labeler.label_trace(trace).efficiency == 0.0

    def test_efficiency_without_baseline(self):
        labeler = OutcomeLabeler()
        trace = _make_trace()
        assert labeler.label_trace(trace).efficiency == 0.75

    def test_safety_score_clean(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(outcome_details={"result": "ok"})
        assert labeler.label_trace(trace).safety_score == 1.0

    def test_safety_score_with_violation(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(
            outcome_details={"error": "safety_violation detected"}
        )
        assert labeler.label_trace(trace).safety_score == 0.5

    def test_safety_score_multiple_violations(self):
        labeler = OutcomeLabeler()
        trace = _make_trace(
            outcome_details={
                "error": "safety_violation",
                "action": "rollback initiated",
            }
        )
        assert labeler.label_trace(trace).safety_score == 0.0

    def test_confidence_calibration_correct(self):
        labeler = OutcomeLabeler()
        # High confidence, successful → well calibrated
        trace = _make_trace(success=True, confidence=0.9)
        labels = labeler.label_trace(trace)
        assert labels.confidence_calibration == pytest.approx(0.9)

    def test_confidence_calibration_wrong(self):
        labeler = OutcomeLabeler()
        # High confidence, failed → poorly calibrated
        trace = _make_trace(success=False, confidence=0.9)
        labels = labeler.label_trace(trace)
        assert labels.confidence_calibration == pytest.approx(0.1)

    def test_overall_quality_range(self):
        labeler = OutcomeLabeler()
        trace = _make_trace()
        labels = labeler.label_trace(trace)
        assert 0.0 <= labels.overall_quality <= 1.0

    def test_label_traces_batch(self):
        labeler = OutcomeLabeler()
        traces = [_make_trace(trace_id=f"t-{i}") for i in range(5)]
        all_labels = labeler.label_traces(traces)
        assert len(all_labels) == 5
        assert all(isinstance(lb, OutcomeLabels) for lb in all_labels)


# ---------------------------------------------------------------------------
# TrainingDataPipeline
# ---------------------------------------------------------------------------

class TestTrainingDataPipeline:
    def setup_method(self):
        ActionTraceCollector.reset_instance()

    def teardown_method(self):
        ActionTraceCollector.reset_instance()

    def _seed_traces(self, trace_dir: Path, n: int = 20) -> None:
        """Write *n* traces directly into a JSONL file."""
        filepath = trace_dir / f"traces_{datetime.now():%Y-%m-%d}.jsonl"
        with open(filepath, "w", encoding="utf-8") as fh:
            for i in range(n):
                trace = _make_trace(
                    trace_id=f"t-{i:04d}",
                    success=(i % 3 != 0),
                    action_types=["API_CALL"] if i % 2 == 0 else ["COMMAND"],
                    human_correction="fix" if i % 5 == 0 else None,
                )
                fh.write(json.dumps(trace_to_dict(trace), default=str) + "\n")

    def test_run_pipeline(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        self._seed_traces(trace_dir, n=30)

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir),
            output_dir=str(output_dir),
        )
        result = pipeline.run_pipeline()

        assert "train" in result
        assert "validation" in result
        assert "test" in result
        total = result["train"] + result["validation"] + result["test"]
        assert total > 0

        # Verify output files
        assert (output_dir / "train.jsonl").exists()
        assert (output_dir / "validation.jsonl").exists()
        assert (output_dir / "test.jsonl").exists()

    def test_output_format(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        self._seed_traces(trace_dir, n=10)

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir),
            output_dir=str(output_dir),
        )
        pipeline.run_pipeline()

        with open(output_dir / "train.jsonl") as fh:
            first_line = fh.readline()
        example = json.loads(first_line)

        assert "instruction" in example
        assert "input" in example
        assert "output" in example
        assert "quality" in example
        assert "world_state" in example["input"]
        assert "action_plan" in example["output"]

    def test_retention_filter(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        # Write an old file
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        old_file = trace_dir / f"traces_{old_date}.jsonl"
        old_trace = _make_trace(
            trace_id="old",
            timestamp=datetime.now() - timedelta(days=100),
        )
        old_file.write_text(json.dumps(trace_to_dict(old_trace), default=str) + "\n")

        # Write a recent file
        self._seed_traces(trace_dir, n=5)

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir),
            output_dir=str(output_dir),
            retention_days=90,
        )
        result = pipeline.run_pipeline()
        total = result["train"] + result["validation"] + result["test"]
        # The old trace should be filtered out; only 5 recent remain
        assert total == 5

    def test_empty_input(self, tmp_path):
        trace_dir = tmp_path / "traces"
        output_dir = tmp_path / "output"
        trace_dir.mkdir()

        pipeline = TrainingDataPipeline(
            trace_dir=str(trace_dir),
            output_dir=str(output_dir),
        )
        result = pipeline.run_pipeline()
        assert result == {"train": 0, "validation": 0, "test": 0}


# ---------------------------------------------------------------------------
# Phase 2 stub imports
# ---------------------------------------------------------------------------

class TestPhase2Implementations:
    """Verify that Phase 2 implementations import, instantiate,
    and provide correct behaviour without ML dependencies."""

    def test_mfm_tokenizer(self):
        from murphy_foundation_model.mfm_tokenizer import (
            MFMTokenizer,
            SPECIAL_TOKENS,
            discretize_score,
        )

        tok = MFMTokenizer()
        ids = tok.encode("hello")
        assert tok.decode(ids) == "hello"
        assert tok.vocab_size > 256
        assert "<|sense|>" in tok.get_special_tokens()
        assert "<|confidence:0.50|>" in SPECIAL_TOKENS.values()
        assert "<|authority:system|>" in SPECIAL_TOKENS.values()
        assert discretize_score(0.73) == 0.75

    def test_mfm_tokenizer_encode_trace(self):
        from murphy_foundation_model.mfm_tokenizer import MFMTokenizer

        tok = MFMTokenizer()
        trace = {
            "world_state": {"temp": 22},
            "intent": "turn on AC",
            "action_plan": [{"type": "api_call", "target": "hvac"}],
            "confidence": 0.85,
            "murphy_index": 0.3,
            "authority_level": "medium",
            "gate_result": "gate_pass",
        }
        ids = tok.encode_trace(trace)
        decoded = tok.decode(ids)
        assert "<|sense|>" in decoded
        assert "<|act|>" in decoded

    def test_mfm_model(self):
        from murphy_foundation_model.mfm_model import MFMModel, MFMConfig

        config = MFMConfig()
        model = MFMModel(config)
        out = model.forward([1, 2, 3])
        assert "logits" in out
        assert model.parameter_count() == 0
        plan = model.predict_action_plan({"a": 1}, "test")
        assert plan["mode"] == "stub"

    def test_mfm_trainer(self):
        from murphy_foundation_model.mfm_trainer import (
            MFMTrainer,
            MFMTrainerConfig,
        )

        trainer = MFMTrainer(config=MFMTrainerConfig())
        # Without ML deps, train returns skipped
        result = trainer.train(train_dataset=[])
        assert result["status"] in ("skipped", "completed")

    def test_rlef_engine(self):
        from murphy_foundation_model.rlef_engine import RLEFEngine, RLEFConfig

        engine = RLEFEngine(config=RLEFConfig())
        reward = engine.compute_reward(
            {},
            {
                "success": 1.0,
                "efficiency": 0.8,
                "safety_score": 0.9,
                "confidence_calibration": 0.7,
                "human_agreement": 0.6,
            },
        )
        assert 0 < reward <= 1

    def test_rlef_preference_pairs(self):
        from murphy_foundation_model.rlef_engine import RLEFEngine

        engine = RLEFEngine()
        traces = [
            {"intent": "test", "labels": {"success": 1.0, "efficiency": 0.8,
             "safety_score": 0.9, "confidence_calibration": 0.7, "human_agreement": 0.6}},
            {"intent": "test", "labels": {"success": 0.0, "efficiency": 0.2,
             "safety_score": 0.5, "confidence_calibration": 0.3, "human_agreement": 0.2}},
        ]
        pairs = engine.create_preference_pairs(traces)
        assert len(pairs) >= 1
        assert pairs[0].chosen_reward > pairs[0].rejected_reward

    def test_mfm_inference(self):
        from murphy_foundation_model.mfm_inference import MFMInferenceService

        svc = MFMInferenceService()
        result = svc.predict({"x": 1}, "test")
        assert result.get("error") == "model_not_loaded"
        status = svc.get_status()
        assert status["loaded"] is False

    def test_shadow_deployment(self):
        from murphy_foundation_model.shadow_deployment import (
            ShadowDeployment,
            ShadowConfig,
        )

        sd = ShadowDeployment(config=ShadowConfig())
        assert not sd.is_active
        sd.start()
        assert sd.is_active
        comp = sd.compare_outputs(
            {"request_id": "r1"},
            {"action_plan": [{"type": "api_call"}], "confidence": 0.8, "latency_ms": 50},
            {"action_plan": [{"type": "api_call"}], "confidence": 0.75, "latency_ms": 200},
        )
        assert comp.action_similarity == 1.0
        metrics = sd.get_metrics()
        assert metrics["total_comparisons"] == 1
        sd.stop()
        assert not sd.is_active

    def test_self_improvement_loop(self):
        from murphy_foundation_model.self_improvement_loop import (
            SelfImprovementLoop,
            SelfImprovementConfig,
        )

        loop = SelfImprovementLoop(config=SelfImprovementConfig())
        loop.record_trace()
        assert loop.current_iteration == 0
        status = loop.get_status()
        assert status["traces_since_retrain"] == 1

    def test_mfm_registry(self):
        import tempfile
        import shutil

        from murphy_foundation_model.mfm_registry import (
            MFMRegistry,
            MFMModelVersion,
        )

        tmpdir = tempfile.mkdtemp()
        try:
            reg = MFMRegistry(registry_dir=tmpdir)
            v = MFMModelVersion(
                version_id="v1",
                version_str="v0.1",
                base_model="test",
                training_config={},
                traces_used=100,
                created_at="2024-01-01T00:00:00Z",
                metrics={"accuracy": 0.9},
                status="registered",
                checkpoint_path="/tmp/test",
            )
            reg.register_version(v)
            assert reg.get_version("v1") is not None
            assert len(reg.list_versions()) == 1
            reg.promote("v1")  # registered → shadow
            assert reg.get_version("v1").status == "shadow"
            reg.promote("v1")  # shadow → canary
            reg.promote("v1")  # canary → production
            assert reg.get_current_production().version_id == "v1"
            assert len(reg.get_promotion_history()) == 3
        finally:
            shutil.rmtree(tmpdir)
