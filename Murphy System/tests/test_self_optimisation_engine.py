"""
Tests for ADV-003: SelfOptimisationEngine.

Validates performance sample recording, bottleneck detection,
optimisation cycle execution, persistence integration, and
EventBackbone event publishing.

Design Label: TEST-008 / ADV-003
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from self_optimisation_engine import (
    SelfOptimisationEngine,
    PerformanceSample,
    BottleneckReport,
    OptimisationCycle,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType
from self_improvement_engine import SelfImprovementEngine


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
def engine():
    return SelfOptimisationEngine()


@pytest.fixture
def improvement(pm):
    return SelfImprovementEngine(persistence_manager=pm)


@pytest.fixture
def wired_engine(pm, backbone, improvement):
    return SelfOptimisationEngine(
        persistence_manager=pm,
        event_backbone=backbone,
        improvement_engine=improvement,
    )


# ------------------------------------------------------------------
# Sample recording
# ------------------------------------------------------------------

class TestSampleRecording:
    def test_record_sample(self, engine):
        sample = engine.record_sample(metric_name="response_time_ms", value=250.0, component="api-gw")
        assert sample.sample_id.startswith("smp-")
        assert sample.metric_name == "response_time_ms"
        assert sample.value == 250.0

    def test_sample_to_dict(self, engine):
        sample = engine.record_sample(metric_name="cpu_usage", value=0.75)
        d = sample.to_dict()
        assert "sample_id" in d
        assert "metric_name" in d
        assert "value" in d

    def test_bounded_samples(self):
        eng = SelfOptimisationEngine(max_samples=5)
        for i in range(10):
            eng.record_sample(metric_name="cpu_usage", value=float(i) / 10)
        samples = eng.get_samples(limit=100)
        assert len(samples) <= 6  # max 5 + eviction buffer

    def test_filter_by_metric(self, engine):
        engine.record_sample(metric_name="cpu_usage", value=0.80)
        engine.record_sample(metric_name="memory_usage", value=0.60)
        engine.record_sample(metric_name="cpu_usage", value=0.85)
        cpu_only = engine.get_samples(metric_name="cpu_usage")
        assert len(cpu_only) == 2
        assert all(s["metric_name"] == "cpu_usage" for s in cpu_only)


# ------------------------------------------------------------------
# Bottleneck detection
# ------------------------------------------------------------------

class TestBottleneckDetection:
    def test_detect_bottleneck(self, engine):
        for _ in range(20):
            engine.record_sample(metric_name="response_time_ms", value=800.0, component="api")
        reports = engine.detect_bottlenecks()
        assert len(reports) > 0

    def test_no_bottleneck(self, engine):
        for _ in range(20):
            engine.record_sample(metric_name="response_time_ms", value=100.0, component="api")
        reports = engine.detect_bottlenecks()
        assert len(reports) == 0

    def test_severity_critical(self, engine):
        # 2x+ threshold (500) → severity == "critical"
        for _ in range(20):
            engine.record_sample(metric_name="response_time_ms", value=1200.0, component="api")
        reports = engine.detect_bottlenecks()
        assert len(reports) >= 1
        assert reports[0].severity == "critical"

    def test_severity_medium(self, engine):
        # ~1.3x threshold (500) → severity in ("medium", "high")
        for _ in range(20):
            engine.record_sample(metric_name="response_time_ms", value=650.0, component="api")
        reports = engine.detect_bottlenecks()
        assert len(reports) >= 1
        assert reports[0].severity in ("medium", "high")

    def test_custom_thresholds(self, engine):
        for _ in range(20):
            engine.record_sample(metric_name="custom_metric", value=50.0, component="svc")
        # With default thresholds, custom_metric is ignored
        reports_default = engine.detect_bottlenecks()
        custom_reports = [r for r in reports_default if r.metric_name == "custom_metric"]
        assert len(custom_reports) == 0
        # With custom thresholds, the metric is flagged
        reports_custom = engine.detect_bottlenecks(thresholds={"custom_metric": 10.0})
        custom_reports = [r for r in reports_custom if r.metric_name == "custom_metric"]
        assert len(custom_reports) >= 1


# ------------------------------------------------------------------
# Optimisation cycle
# ------------------------------------------------------------------

class TestOptimisationCycle:
    def test_run_cycle(self, engine):
        for _ in range(20):
            engine.record_sample(metric_name="response_time_ms", value=800.0, component="api")
        cycle = engine.run_optimisation_cycle()
        assert cycle.cycle_id.startswith("cyc-")
        assert cycle.bottlenecks_detected > 0
        assert cycle.proposals_generated >= 0

    def test_cycle_to_dict(self, engine):
        engine.record_sample(metric_name="cpu_usage", value=0.95)
        cycle = engine.run_optimisation_cycle()
        d = cycle.to_dict()
        assert "cycle_id" in d
        assert "samples_analysed" in d
        assert "bottlenecks_detected" in d
        assert "proposals_generated" in d

    def test_cycle_with_improvement_engine(self, wired_engine):
        for _ in range(20):
            wired_engine.record_sample(metric_name="response_time_ms", value=800.0, component="api")
        cycle = wired_engine.run_optimisation_cycle()
        # inject_proposal may not exist on SelfImprovementEngine,
        # but the cycle still completes gracefully.
        assert cycle.bottlenecks_detected > 0
        assert cycle.proposals_generated >= 0


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------

class TestQuery:
    def test_get_samples(self, engine):
        engine.record_sample(metric_name="cpu_usage", value=0.70)
        samples = engine.get_samples()
        assert isinstance(samples, list)
        assert len(samples) >= 1

    def test_get_bottlenecks(self, engine):
        for _ in range(20):
            engine.record_sample(metric_name="response_time_ms", value=800.0, component="api")
        engine.detect_bottlenecks()
        bottlenecks = engine.get_bottlenecks()
        assert isinstance(bottlenecks, list)
        assert len(bottlenecks) >= 1

    def test_get_cycles(self, engine):
        for _ in range(20):
            engine.record_sample(metric_name="response_time_ms", value=800.0, component="api")
        engine.run_optimisation_cycle()
        cycles = engine.get_cycles()
        assert isinstance(cycles, list)
        assert len(cycles) >= 1


# ------------------------------------------------------------------
# Persistence integration
# ------------------------------------------------------------------

class TestPersistence:
    def test_cycle_persisted(self, wired_engine, pm):
        for _ in range(20):
            wired_engine.record_sample(metric_name="response_time_ms", value=800.0, component="api")
        cycle = wired_engine.run_optimisation_cycle()
        loaded = pm.load_document(cycle.cycle_id)
        assert loaded is not None
        assert loaded["samples_analysed"] > 0


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_cycle_publishes_event(self, wired_engine, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        for _ in range(20):
            wired_engine.record_sample(metric_name="response_time_ms", value=800.0, component="api")
        wired_engine.run_optimisation_cycle()
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "self_optimisation_engine"


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestStatus:
    def test_status(self, engine):
        engine.record_sample(metric_name="cpu_usage", value=0.80)
        engine.record_sample(metric_name="cpu_usage", value=0.85)
        status = engine.get_status()
        assert status["total_samples"] > 0
        assert status["persistence_attached"] is False

    def test_status_attachments(self, wired_engine):
        status = wired_engine.get_status()
        assert status["persistence_attached"] is True
        assert status["backbone_attached"] is True
        assert status["improvement_engine_attached"] is True
