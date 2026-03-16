"""
Tests for OPS-001: AutomationReadinessEvaluator.

Validates module registration, readiness evaluation, scoring,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-020 / OPS-001
Owner: QA Team
"""

import os
import pytest


from automation_readiness_evaluator import (
    AutomationReadinessEvaluator,
    ModuleCheck,
    PhaseScore,
    ReadinessReport,
    ReadinessVerdict,
    DEFAULT_PHASE_MODULES,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def backbone():
    return EventBackbone()


@pytest.fixture
def evaluator():
    return AutomationReadinessEvaluator()


@pytest.fixture
def wired_evaluator(pm, backbone):
    return AutomationReadinessEvaluator(
        persistence_manager=pm,
        event_backbone=backbone,
    )


# ------------------------------------------------------------------
# Module registration
# ------------------------------------------------------------------

class TestModuleRegistration:
    def test_register_module(self, evaluator):
        evaluator.register_module("OBS-001", "observability")
        status = evaluator.get_status()
        assert status["total_registered"] == 1

    def test_register_with_health_fn(self, evaluator):
        evaluator.register_module("OBS-001", "observability", health_fn=lambda: True)
        report = evaluator.evaluate()
        checks = [c for c in report.module_checks if c.design_label == "OBS-001"]
        assert len(checks) == 1
        assert checks[0].healthy is True

    def test_unregister_module(self, evaluator):
        evaluator.register_module("OBS-001", "observability")
        assert evaluator.unregister_module("OBS-001") is True
        assert evaluator.unregister_module("OBS-001") is False

    def test_expected_modules_default(self, evaluator):
        status = evaluator.get_status()
        total = sum(len(v) for v in DEFAULT_PHASE_MODULES.values())
        assert status["total_expected_modules"] == total


# ------------------------------------------------------------------
# Evaluation
# ------------------------------------------------------------------

class TestEvaluation:
    def test_empty_evaluation(self, evaluator):
        """No modules registered → NOT_READY."""
        report = evaluator.evaluate()
        assert report.verdict == ReadinessVerdict.NOT_READY
        assert report.overall_score == 0.0

    def test_partial_registration(self, evaluator):
        # Register half of expected modules
        all_labels = []
        for labels in DEFAULT_PHASE_MODULES.values():
            all_labels.extend(labels)
        for label in all_labels[:len(all_labels) // 2]:
            evaluator.register_module(label, "test")
        report = evaluator.evaluate()
        assert report.overall_score > 0.0
        assert report.total_registered > 0

    def test_full_registration(self, evaluator):
        """All modules registered → READY."""
        for phase, labels in DEFAULT_PHASE_MODULES.items():
            for label in labels:
                evaluator.register_module(label, phase)
        report = evaluator.evaluate()
        assert report.verdict == ReadinessVerdict.READY
        assert report.overall_score == 1.0

    def test_unhealthy_module(self, evaluator):
        for phase, labels in DEFAULT_PHASE_MODULES.items():
            for label in labels:
                evaluator.register_module(label, phase, health_fn=lambda: False)
        report = evaluator.evaluate()
        assert report.total_healthy == 0
        assert report.verdict == ReadinessVerdict.NOT_READY

    def test_health_fn_exception(self, evaluator):
        evaluator.register_module("OBS-001", "observability",
                                  health_fn=lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        report = evaluator.evaluate()
        check = [c for c in report.module_checks if c.design_label == "OBS-001"][0]
        assert check.healthy is False
        assert "fail" in check.message

    def test_report_to_dict(self, evaluator):
        report = evaluator.evaluate()
        d = report.to_dict()
        assert "report_id" in d
        assert "verdict" in d
        assert "phase_scores" in d

    def test_phase_scores(self, evaluator):
        evaluator.register_module("INT-001", "integration")
        report = evaluator.evaluate()
        int_score = [ps for ps in report.phase_scores if ps.phase == "integration"]
        assert len(int_score) == 1
        assert int_score[0].score == 1.0


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_evaluator, pm):
        report = wired_evaluator.evaluate()
        loaded = pm.load_document(report.report_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_evaluation_publishes_event(self, wired_evaluator, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        wired_evaluator.evaluate()
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, evaluator):
        s = evaluator.get_status()
        assert s["total_registered"] == 0
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_evaluator):
        s = wired_evaluator.get_status()
        assert s["persistence_attached"] is True
        assert s["backbone_attached"] is True
