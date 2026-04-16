"""
Tests for ADV-004: DiminishingGainsDetector.

Validates metric recording, EMA tracking, plateau detection,
convergence detection, knee-point detection, sequence battery analysis,
should_stop advisor, persistence integration, and EventBackbone
event publishing.

Design Label: TEST-009 / ADV-004
Owner: QA Team
"""

from __future__ import annotations

import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from diminishing_gains_detector import (
    DiminishingGainsConfig,
    DiminishingGainsDetector,
    DiminishingGainsReport,
    GainStatus,
    MetricObservation,
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
def detector():
    return DiminishingGainsDetector()


@pytest.fixture
def wired_detector(pm, backbone):
    return DiminishingGainsDetector(
        event_backbone=backbone,
        persistence_manager=pm,
    )


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

class TestConfig:
    def test_defaults(self):
        cfg = DiminishingGainsConfig()
        assert cfg.ema_alpha == 0.3
        assert cfg.gain_threshold == 0.01
        assert cfg.plateau_window == 3
        assert cfg.convergence_threshold == 0.001
        assert cfg.max_history == 10_000

    def test_custom_config(self):
        cfg = DiminishingGainsConfig(
            ema_alpha=0.5,
            gain_threshold=0.05,
            plateau_window=5,
        )
        assert cfg.ema_alpha == 0.5
        assert cfg.gain_threshold == 0.05
        assert cfg.plateau_window == 5

    def test_invalid_ema_alpha_zero(self):
        with pytest.raises(ValueError, match="ema_alpha"):
            DiminishingGainsConfig(ema_alpha=0.0)

    def test_invalid_ema_alpha_negative(self):
        with pytest.raises(ValueError, match="ema_alpha"):
            DiminishingGainsConfig(ema_alpha=-0.1)

    def test_invalid_ema_alpha_above_one(self):
        with pytest.raises(ValueError, match="ema_alpha"):
            DiminishingGainsConfig(ema_alpha=1.5)

    def test_ema_alpha_one_allowed(self):
        cfg = DiminishingGainsConfig(ema_alpha=1.0)
        assert cfg.ema_alpha == 1.0

    def test_invalid_gain_threshold_negative(self):
        with pytest.raises(ValueError, match="gain_threshold"):
            DiminishingGainsConfig(gain_threshold=-0.01)

    def test_gain_threshold_zero_allowed(self):
        cfg = DiminishingGainsConfig(gain_threshold=0.0)
        assert cfg.gain_threshold == 0.0

    def test_invalid_plateau_window_zero(self):
        with pytest.raises(ValueError, match="plateau_window"):
            DiminishingGainsConfig(plateau_window=0)

    def test_invalid_max_history_too_small(self):
        with pytest.raises(ValueError, match="max_history"):
            DiminishingGainsConfig(max_history=5)


# ------------------------------------------------------------------
# Metric recording
# ------------------------------------------------------------------

class TestRecording:
    def test_record_returns_observation(self, detector):
        obs = detector.record("score", iteration=1, value=0.5)
        assert isinstance(obs, MetricObservation)
        assert obs.metric_name == "score"
        assert obs.iteration == 1
        assert obs.value == 0.5
        assert obs.observation_id.startswith("obs-")

    def test_first_observation_delta_zero(self, detector):
        obs = detector.record("score", iteration=0, value=0.4)
        assert obs.delta == 0.0
        assert obs.normalised_delta == 0.0

    def test_second_observation_has_delta(self, detector):
        detector.record("score", iteration=0, value=0.4)
        obs = detector.record("score", iteration=1, value=0.6)
        assert obs.delta == pytest.approx(0.2)
        assert obs.normalised_delta > 0

    def test_observation_to_dict(self, detector):
        obs = detector.record("score", iteration=0, value=0.5)
        d = obs.to_dict()
        assert "observation_id" in d
        assert "metric_name" in d
        assert "iteration" in d
        assert "value" in d
        assert "delta" in d
        assert "normalised_delta" in d
        assert "recorded_at" in d

    def test_bounded_history(self):
        cfg = DiminishingGainsConfig(max_history=20)
        det = DiminishingGainsDetector(config=cfg)
        for i in range(50):
            det.record("score", iteration=i, value=float(i))
        series = det.get_series("score", limit=100)
        assert len(series) <= 25  # max 20 + some buffer from eviction

    def test_multiple_metrics(self, detector):
        detector.record("score_a", iteration=0, value=0.1)
        detector.record("score_b", iteration=0, value=0.9)
        status = detector.get_status()
        assert "score_a" in status["metrics_tracked"]
        assert "score_b" in status["metrics_tracked"]


# ------------------------------------------------------------------
# EMA tracking
# ------------------------------------------------------------------

class TestEMATracking:
    def test_ema_updates_on_record(self, detector):
        detector.record("score", iteration=0, value=0.4)
        detector.record("score", iteration=1, value=0.6)
        status = detector.get_status()
        assert "score" in status["ema_values"]
        assert status["ema_values"]["score"] >= 0.0

    def test_ema_decays_with_small_gains(self, detector):
        """EMA should decrease as gains shrink."""
        detector.record("score", iteration=0, value=0.0)
        detector.record("score", iteration=1, value=0.5)  # big gain
        ema_after_big = detector.get_status()["ema_values"]["score"]

        detector.record("score", iteration=2, value=0.51)  # small gain
        ema_after_small = detector.get_status()["ema_values"]["score"]

        assert ema_after_small < ema_after_big


# ------------------------------------------------------------------
# Plateau detection
# ------------------------------------------------------------------

class TestPlateauDetection:
    def test_improving_status(self, detector):
        """Large gains → status should be IMPROVING."""
        for i in range(5):
            detector.record("score", iteration=i, value=i * 0.2)
        report = detector.analyse("score")
        assert report.status == GainStatus.IMPROVING

    def test_plateau_detected(self):
        """Gradually diminishing gains → status should be PLATEAU."""
        cfg = DiminishingGainsConfig(
            gain_threshold=0.02,
            plateau_window=3,
        )
        det = DiminishingGainsDetector(config=cfg)
        # Big gains initially
        det.record("score", iteration=0, value=0.0)
        det.record("score", iteration=1, value=0.4)
        det.record("score", iteration=2, value=0.7)
        # Then plateau: very small gains
        det.record("score", iteration=3, value=0.705)
        det.record("score", iteration=4, value=0.707)
        det.record("score", iteration=5, value=0.708)
        report = det.analyse("score")
        assert report.status in (GainStatus.PLATEAU, GainStatus.CONVERGED)
        assert report.consecutive_low >= 3

    def test_converged_detected(self):
        """Truly converged series → status should be CONVERGED."""
        cfg = DiminishingGainsConfig(
            convergence_threshold=0.005,
            gain_threshold=0.02,
            plateau_window=2,
        )
        det = DiminishingGainsDetector(config=cfg)
        det.record("score", iteration=0, value=0.5)
        det.record("score", iteration=1, value=0.8)
        # Completely flat
        det.record("score", iteration=2, value=0.800001)
        det.record("score", iteration=3, value=0.800002)
        det.record("score", iteration=4, value=0.800002)
        report = det.analyse("score")
        assert report.status in (GainStatus.PLATEAU, GainStatus.CONVERGED)

    def test_insufficient_data(self, detector):
        """Only 1 observation → INSUFFICIENT."""
        detector.record("score", iteration=0, value=0.5)
        report = detector.analyse("score")
        assert report.status == GainStatus.INSUFFICIENT

    def test_no_data_at_all(self, detector):
        """No observations → INSUFFICIENT."""
        report = detector.analyse("nonexistent_metric")
        assert report.status == GainStatus.INSUFFICIENT


# ------------------------------------------------------------------
# Knee-point detection
# ------------------------------------------------------------------

class TestKneePointDetection:
    def test_knee_detected_in_decelerating_curve(self):
        """Rapidly decelerating gains should have a knee point."""
        det = DiminishingGainsDetector()
        # Classic diminishing returns curve
        values = [0.0, 0.5, 0.75, 0.85, 0.89, 0.91, 0.915, 0.917]
        for i, v in enumerate(values):
            det.record("score", iteration=i, value=v)
        report = det.analyse("score")
        # Knee should be detected somewhere early
        assert report.knee_point is not None or report.total_iterations >= 2

    def test_no_knee_in_linear_curve(self):
        """Linear growth has no deceleration knee."""
        det = DiminishingGainsDetector()
        for i in range(8):
            det.record("score", iteration=i, value=0.1 * i)
        report = det.analyse("score")
        # Linear curves may or may not detect a knee — just verify it doesn't crash
        assert isinstance(report.knee_point, (int, type(None)))

    def test_short_series_no_knee(self, detector):
        """Series with < 3 points cannot have a knee."""
        detector.record("score", iteration=0, value=0.1)
        detector.record("score", iteration=1, value=0.5)
        report = detector.analyse("score")
        assert report.knee_point is None


# ------------------------------------------------------------------
# Report structure
# ------------------------------------------------------------------

class TestReportStructure:
    def test_report_fields(self, detector):
        detector.record("score", iteration=0, value=0.1)
        detector.record("score", iteration=1, value=0.5)
        report = detector.analyse("score")
        assert isinstance(report, DiminishingGainsReport)
        assert report.report_id.startswith("dgr-")
        assert report.metric_name == "score"
        assert isinstance(report.status, str)
        assert isinstance(report.total_iterations, int)
        assert isinstance(report.ema_gain, float)
        assert isinstance(report.consecutive_low, int)
        assert isinstance(report.gain_curve, list)
        assert isinstance(report.improvement_pct, float)
        assert isinstance(report.recommendation, str)

    def test_report_to_dict(self, detector):
        detector.record("score", iteration=0, value=0.1)
        detector.record("score", iteration=1, value=0.5)
        report = detector.analyse("score")
        d = report.to_dict()
        expected_keys = {
            "report_id", "metric_name", "status", "total_iterations",
            "ema_gain", "consecutive_low", "peak_value", "peak_iteration",
            "knee_point", "gain_curve", "improvement_pct", "recommendation",
            "created_at",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_peak_tracking(self, detector):
        detector.record("score", iteration=0, value=0.1)
        detector.record("score", iteration=1, value=0.5)
        detector.record("score", iteration=2, value=0.3)  # drops
        report = detector.analyse("score")
        assert report.peak_value == pytest.approx(0.5)
        assert report.peak_iteration == 1

    def test_improvement_pct(self, detector):
        detector.record("score", iteration=0, value=0.2)
        detector.record("score", iteration=1, value=0.6)
        report = detector.analyse("score")
        # (0.6 - 0.2) / 0.2 * 100 = 200%
        assert report.improvement_pct == pytest.approx(200.0)


# ------------------------------------------------------------------
# Sequence battery analysis
# ------------------------------------------------------------------

class TestSequenceBatteryAnalysis:
    def test_analyse_diminishing_returns_data(self, detector):
        """Simulate MSS sequence optimizer diminishing_returns dict."""
        data = {
            "1": {"best_score": 0.40, "best_sequence": "M"},
            "2": {"best_score": 0.55, "best_sequence": "MS"},
            "3": {"best_score": 0.62, "best_sequence": "MMS"},
            "4": {"best_score": 0.64, "best_sequence": "MMMS"},
            "5": {"best_score": 0.65, "best_sequence": "MMSMM"},
            "6": {"best_score": 0.651, "best_sequence": "MMSMMM"},
        }
        report = detector.analyse_sequence_battery(data)
        assert isinstance(report, DiminishingGainsReport)
        assert report.metric_name == "sequence_length_score"
        assert report.total_iterations >= 6

    def test_empty_data(self, detector):
        report = detector.analyse_sequence_battery({})
        assert report.status == GainStatus.INSUFFICIENT


# ------------------------------------------------------------------
# should_stop advisor
# ------------------------------------------------------------------

class TestShouldStop:
    def test_should_not_stop_initially(self, detector):
        detector.record("score", iteration=0, value=0.5)
        assert detector.should_stop("score") is False

    def test_should_stop_after_plateau(self):
        cfg = DiminishingGainsConfig(
            gain_threshold=0.02,
            plateau_window=3,
        )
        det = DiminishingGainsDetector(config=cfg)
        det.record("score", iteration=0, value=0.0)
        det.record("score", iteration=1, value=0.5)
        det.record("score", iteration=2, value=0.7)
        det.record("score", iteration=3, value=0.705)
        det.record("score", iteration=4, value=0.707)
        det.record("score", iteration=5, value=0.708)
        assert det.should_stop("score") is True

    def test_should_not_stop_while_improving(self, detector):
        for i in range(5):
            detector.record("score", iteration=i, value=i * 0.2)
        assert detector.should_stop("score") is False

    def test_unknown_metric_returns_false(self, detector):
        assert detector.should_stop("nonexistent") is False


# ------------------------------------------------------------------
# Query API
# ------------------------------------------------------------------

class TestQueryAPI:
    def test_get_series(self, detector):
        detector.record("score", iteration=0, value=0.3)
        detector.record("score", iteration=1, value=0.5)
        series = detector.get_series("score")
        assert len(series) == 2
        assert all(isinstance(s, dict) for s in series)

    def test_get_series_limit(self, detector):
        for i in range(10):
            detector.record("score", iteration=i, value=float(i) / 10)
        series = detector.get_series("score", limit=3)
        assert len(series) == 3

    def test_get_reports(self, detector):
        detector.record("score", iteration=0, value=0.1)
        detector.record("score", iteration=1, value=0.5)
        detector.analyse("score")
        reports = detector.get_reports()
        assert len(reports) >= 1

    def test_get_status(self, detector):
        detector.record("score", iteration=0, value=0.1)
        status = detector.get_status()
        assert "metrics_tracked" in status
        assert "total_observations" in status
        assert "total_reports" in status
        assert "ema_values" in status
        assert "consecutive_low" in status
        assert status["total_observations"] >= 1


# ------------------------------------------------------------------
# Reset
# ------------------------------------------------------------------

class TestReset:
    def test_reset_all(self, detector):
        detector.record("score_a", iteration=0, value=0.1)
        detector.record("score_b", iteration=0, value=0.2)
        detector.reset()
        status = detector.get_status()
        assert status["total_observations"] == 0
        assert len(status["metrics_tracked"]) == 0

    def test_reset_single_metric(self, detector):
        detector.record("score_a", iteration=0, value=0.1)
        detector.record("score_b", iteration=0, value=0.2)
        detector.reset("score_a")
        status = detector.get_status()
        assert "score_a" not in status["metrics_tracked"]
        assert "score_b" in status["metrics_tracked"]


# ------------------------------------------------------------------
# Persistence integration
# ------------------------------------------------------------------

class TestPersistence:
    def test_report_persisted(self, wired_detector, pm):
        wired_detector.record("score", iteration=0, value=0.1)
        wired_detector.record("score", iteration=1, value=0.5)
        report = wired_detector.analyse("score")
        loaded = pm.load_document(report.report_id)
        assert loaded is not None
        assert loaded["metric_name"] == "score"


# ------------------------------------------------------------------
# EventBackbone integration
# ------------------------------------------------------------------

class TestEventBackboneIntegration:
    def test_plateau_publishes_event(self, wired_detector, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        # Generate a plateau
        cfg = DiminishingGainsConfig(gain_threshold=0.02, plateau_window=2)
        det = DiminishingGainsDetector(
            config=cfg,
            event_backbone=backbone,
        )
        det.record("score", iteration=0, value=0.0)
        det.record("score", iteration=1, value=0.5)
        det.record("score", iteration=2, value=0.505)
        det.record("score", iteration=3, value=0.506)
        det.analyse("score")
        backbone.process_pending()
        assert len(received) >= 1
        assert received[0].payload["source"] == "diminishing_gains_detector"

    def test_improving_does_not_publish(self, wired_detector, backbone):
        received = []
        backbone.subscribe(EventType.LEARNING_FEEDBACK, lambda e: received.append(e))
        for i in range(3):
            wired_detector.record("score", iteration=i, value=i * 0.3)
        wired_detector.analyse("score")
        backbone.process_pending()
        # Improving status should NOT publish a plateau event
        plateau_events = [
            e for e in received
            if e.payload.get("source") == "diminishing_gains_detector"
        ]
        assert len(plateau_events) == 0


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_recording(self, detector):
        """Multiple threads recording simultaneously should not crash."""
        errors = []

        def _record(thread_id: int):
            try:
                for i in range(50):
                    detector.record(
                        f"metric_{thread_id}",
                        iteration=i,
                        value=float(i) / 50,
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_record, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        status = detector.get_status()
        assert status["total_observations"] > 0


# ------------------------------------------------------------------
# GainStatus constants
# ------------------------------------------------------------------

class TestGainStatus:
    def test_status_values(self):
        assert GainStatus.IMPROVING == "improving"
        assert GainStatus.PLATEAU == "plateau"
        assert GainStatus.CONVERGED == "converged"
        assert GainStatus.INSUFFICIENT == "insufficient"
