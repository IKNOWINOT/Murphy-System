"""
Tests for SAF-001: SafetyValidationPipeline.

Validates check registration, three-stage validation, fail-closed behavior,
persistence integration, and EventBackbone event publishing.

Design Label: TEST-024 / SAF-001
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from safety_validation_pipeline import (
    SafetyValidationPipeline,
    ValidationStage,
    CheckOutcome,
    OverallVerdict,
    CheckResult,
    ValidationResult,
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
def pipeline():
    return SafetyValidationPipeline()


@pytest.fixture
def wired_pipeline(pm, backbone):
    return SafetyValidationPipeline(persistence_manager=pm, event_backbone=backbone)


# ------------------------------------------------------------------
# Check registration
# ------------------------------------------------------------------

class TestCheckRegistration:
    def test_register_check(self, pipeline):
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "auth", lambda ctx: (True, "ok"))
        status = pipeline.get_status()
        assert status["registered_checks"]["pre_execution"] == 1

    def test_unregister_check(self, pipeline):
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "auth", lambda ctx: (True, "ok"))
        assert pipeline.unregister_check(ValidationStage.PRE_EXECUTION, "auth") is True
        assert pipeline.unregister_check(ValidationStage.PRE_EXECUTION, "auth") is False

    def test_register_multiple_stages(self, pipeline):
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "pre1", lambda ctx: (True, ""))
        pipeline.register_check(ValidationStage.EXECUTION, "exec1", lambda ctx: (True, ""))
        pipeline.register_check(ValidationStage.POST_EXECUTION, "post1", lambda ctx: (True, ""))
        status = pipeline.get_status()
        assert status["registered_checks"]["pre_execution"] == 1
        assert status["registered_checks"]["execution"] == 1
        assert status["registered_checks"]["post_execution"] == 1


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

class TestValidation:
    def test_empty_pipeline_passes(self, pipeline):
        result = pipeline.validate("act-1", "test")
        assert result.verdict == OverallVerdict.PASSED
        assert result.passed_count == 0

    def test_all_pass(self, pipeline):
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "auth", lambda ctx: (True, "ok"))
        pipeline.register_check(ValidationStage.POST_EXECUTION, "audit", lambda ctx: (True, "logged"))
        result = pipeline.validate("act-1", "deploy")
        assert result.verdict == OverallVerdict.PASSED
        assert result.passed_count == 2

    def test_fail_closed(self, pipeline):
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "auth", lambda ctx: (False, "denied"))
        pipeline.register_check(ValidationStage.POST_EXECUTION, "audit", lambda ctx: (True, "ok"))
        result = pipeline.validate("act-1", "deploy")
        assert result.verdict == OverallVerdict.FAILED
        assert result.failed_count == 1

    def test_check_exception_fails(self, pipeline):
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "bad",
                                lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
        result = pipeline.validate("act-1", "deploy")
        assert result.verdict == OverallVerdict.FAILED
        assert "boom" in result.checks[0].message

    def test_context_passed(self, pipeline):
        received = {}
        def capture(ctx):
            received.update(ctx)
            return (True, "ok")
        pipeline.register_check(ValidationStage.PRE_EXECUTION, "cap", capture)
        pipeline.validate("act-1", "deploy", {"user": "admin"})
        assert received.get("user") == "admin"

    def test_result_to_dict(self, pipeline):
        result = pipeline.validate("act-1", "test")
        d = result.to_dict()
        assert "result_id" in d
        assert "verdict" in d
        assert "checks" in d


# ------------------------------------------------------------------
# Persistence
# ------------------------------------------------------------------

class TestPersistence:
    def test_result_persisted(self, wired_pipeline, pm):
        result = wired_pipeline.validate("act-1", "deploy")
        loaded = pm.load_document(result.result_id)
        assert loaded is not None


# ------------------------------------------------------------------
# EventBackbone
# ------------------------------------------------------------------

class TestEventBackbone:
    def test_validation_publishes_event(self, wired_pipeline, backbone):
        received = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: received.append(e))
        wired_pipeline.validate("act-1", "deploy")
        backbone.process_pending()
        assert len(received) >= 1


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, pipeline):
        s = pipeline.get_status()
        assert s["total_results"] == 0
        assert s["persistence_attached"] is False

    def test_wired_status(self, wired_pipeline):
        s = wired_pipeline.get_status()
        assert s["persistence_attached"] is True
        assert s["backbone_attached"] is True
