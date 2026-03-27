# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for DecisionLearner (decision_learner.py).

Validates:
  - Decision recording
  - Prediction accuracy tracking
  - Corpus growth over time
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from copilot_tenant.decision_learner import DecisionLearner, DecisionRecord


class TestDecisionRecord:
    def test_defaults(self) -> None:
        rec = DecisionRecord(decision="approve", reasoning="low risk")
        assert rec.record_id
        assert rec.decision == "approve"
        assert rec.correct is None

    def test_recorded_at_set(self) -> None:
        rec = DecisionRecord()
        assert "T" in rec.recorded_at


class TestDecisionLearner:
    def test_instantiation(self) -> None:
        learner = DecisionLearner()
        assert learner is not None

    def test_corpus_empty_at_start(self) -> None:
        learner = DecisionLearner()
        assert learner.get_decision_corpus_size() == 0

    def test_record_decision_grows_corpus(self) -> None:
        learner = DecisionLearner()
        learner.record_decision({"task": "send_email"}, "approve", "low risk")
        assert learner.get_decision_corpus_size() == 1

    def test_record_returns_id(self) -> None:
        learner = DecisionLearner()
        record_id = learner.record_decision({}, "approve", "")
        assert record_id  # non-empty string

    def test_corpus_grows_with_multiple_records(self) -> None:
        learner = DecisionLearner()
        for i in range(5):
            learner.record_decision({"i": i}, "approve", "")
        assert learner.get_decision_corpus_size() == 5

    def test_predict_returns_tuple(self) -> None:
        learner = DecisionLearner()
        pred, conf = learner.predict_decision({})
        assert isinstance(pred, str)
        assert isinstance(conf, float)

    def test_predict_empty_corpus_returns_no_prediction(self) -> None:
        learner = DecisionLearner()
        pred, conf = learner.predict_decision({})
        assert pred == "no_prediction"
        assert conf == 0.0

    def test_predict_most_frequent_decision(self) -> None:
        learner = DecisionLearner()
        for _ in range(3):
            learner.record_decision({}, "approve", "")
        for _ in range(1):
            learner.record_decision({}, "reject", "")
        pred, conf = learner.predict_decision({})
        assert pred == "approve"
        assert conf == pytest.approx(0.75)

    def test_accuracy_metrics_empty(self) -> None:
        learner = DecisionLearner()
        metrics = learner.get_accuracy_metrics()
        assert metrics["accuracy"] == 0.0
        assert metrics["corpus_size"] == 0.0

    def test_accuracy_metrics_with_records(self) -> None:
        learner = DecisionLearner()
        for _ in range(4):
            learner.record_decision({}, "approve", "")
        metrics = learner.get_accuracy_metrics()
        assert metrics["corpus_size"] == 4.0

    def test_multiple_record_then_predict(self) -> None:
        learner = DecisionLearner()
        decisions = ["approve", "approve", "reject", "approve"]
        for d in decisions:
            learner.record_decision({"ctx": "x"}, d, "test")
        pred, conf = learner.predict_decision({"ctx": "x"})
        assert pred == "approve"
        assert conf >= 0.5

    def test_thread_safe_concurrent_record(self) -> None:
        import threading
        learner = DecisionLearner()
        errors: list = []

        def _worker() -> None:
            try:
                for _ in range(20):
                    learner.record_decision({}, "approve", "")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert learner.get_decision_corpus_size() == 100
