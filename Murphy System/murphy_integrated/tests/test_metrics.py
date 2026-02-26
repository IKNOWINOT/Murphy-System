"""
Tests for the Prometheus-compatible metrics module.
"""

import pytest
from src.metrics import (
    inc_counter,
    set_gauge,
    observe_histogram,
    render_metrics,
    register_module_health,
    get_system_health,
    _counters,
    _gauges,
    _histograms,
    _module_health,
    _lock,
    _health_lock,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Reset metrics state between tests."""
    with _lock:
        _counters.clear()
        _gauges.clear()
        _histograms.clear()
    with _health_lock:
        _module_health.clear()
    yield


class TestCounters:
    def test_increment_creates_counter(self):
        inc_counter("murphy_requests_total")
        assert _counters["murphy_requests_total"] == 1.0

    def test_increment_by_amount(self):
        inc_counter("murphy_requests_total", amount=5)
        assert _counters["murphy_requests_total"] == 5.0

    def test_increment_accumulates(self):
        inc_counter("murphy_requests_total")
        inc_counter("murphy_requests_total")
        inc_counter("murphy_requests_total")
        assert _counters["murphy_requests_total"] == 3.0

    def test_counter_with_labels(self):
        inc_counter("murphy_requests_total", labels={"method": "GET"})
        inc_counter("murphy_requests_total", labels={"method": "POST"})
        assert _counters['murphy_requests_total{method="GET"}'] == 1.0
        assert _counters['murphy_requests_total{method="POST"}'] == 1.0


class TestGauges:
    def test_set_gauge(self):
        set_gauge("murphy_active_sessions", 42)
        assert _gauges["murphy_active_sessions"] == 42

    def test_gauge_overwrite(self):
        set_gauge("murphy_active_sessions", 10)
        set_gauge("murphy_active_sessions", 20)
        assert _gauges["murphy_active_sessions"] == 20

    def test_gauge_with_labels(self):
        set_gauge("murphy_active_sessions", 5, labels={"module": "rosetta"})
        assert _gauges['murphy_active_sessions{module="rosetta"}'] == 5


class TestHistograms:
    def test_observe(self):
        observe_histogram("murphy_request_duration_seconds", 0.15)
        observe_histogram("murphy_request_duration_seconds", 0.25)
        assert len(_histograms["murphy_request_duration_seconds"]) == 2

    def test_observe_with_labels(self):
        observe_histogram("murphy_request_duration_seconds", 0.1, labels={"endpoint": "/health"})
        assert len(_histograms['murphy_request_duration_seconds{endpoint="/health"}']) == 1


class TestRenderMetrics:
    def test_render_includes_uptime(self):
        output = render_metrics()
        assert "murphy_uptime_seconds" in output
        assert "# TYPE murphy_uptime_seconds gauge" in output

    def test_render_includes_counters(self):
        inc_counter("murphy_test_counter", 3)
        output = render_metrics()
        assert "murphy_test_counter 3" in output
        assert "# TYPE murphy_test_counter counter" in output

    def test_render_includes_gauges(self):
        set_gauge("murphy_test_gauge", 99)
        output = render_metrics()
        assert "murphy_test_gauge 99" in output
        assert "# TYPE murphy_test_gauge gauge" in output

    def test_render_includes_histograms(self):
        observe_histogram("murphy_test_hist", 0.5)
        observe_histogram("murphy_test_hist", 1.5)
        output = render_metrics()
        assert "murphy_test_hist_count 2" in output
        assert "murphy_test_hist_sum 2.0000" in output

    def test_render_empty_metrics(self):
        output = render_metrics()
        # Should still have uptime
        assert "murphy_uptime_seconds" in output


class TestHealthAggregation:
    def test_no_modules_registered(self):
        health = get_system_health()
        assert health["status"] == "healthy"
        assert health["module_count"] == 0

    def test_healthy_module(self):
        register_module_health("rosetta", lambda: {"status": "ok", "agents": 5})
        health = get_system_health()
        assert health["status"] == "healthy"
        assert health["modules"]["rosetta"]["agents"] == 5

    def test_degraded_on_error(self):
        register_module_health("broken", lambda: {"status": "error", "error": "down"})
        health = get_system_health()
        assert health["status"] == "degraded"

    def test_multiple_modules(self):
        register_module_health("rosetta", lambda: {"status": "ok"})
        register_module_health("robotics", lambda: {"status": "ok"})
        register_module_health("avatar", lambda: {"status": "ok"})
        health = get_system_health()
        assert health["status"] == "healthy"
        assert health["module_count"] == 3

    def test_exception_in_status_fn(self):
        def bad_fn():
            raise RuntimeError("oops")
        register_module_health("crashy", bad_fn)
        health = get_system_health()
        assert health["status"] == "degraded"
        assert "oops" in health["modules"]["crashy"]["error"]

    def test_uptime_present(self):
        health = get_system_health()
        assert "uptime_seconds" in health
        assert health["uptime_seconds"] >= 0
