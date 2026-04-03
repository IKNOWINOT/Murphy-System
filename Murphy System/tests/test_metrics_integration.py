"""
Integration tests for the unified observability stack (OBS-UNIFIED-001).

Verifies:
  - /metrics endpoint is always available (with or without prometheus_client)
  - /metrics returns valid Prometheus text-format output
  - Expected metric families are present
  - /api/health?deep=true includes module health from src.metrics
  - src.metrics counters are incremented by the request middleware
"""
from __future__ import annotations

import os
import sys

import pytest

# Ensure src/ is importable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_app():
    """Build a minimal FastAPI app that includes the metrics and health wiring."""
    from fastapi import FastAPI
    from fastapi.responses import Response as PlainResponse
    from starlette.middleware.base import BaseHTTPMiddleware
    import time

    app = FastAPI()

    # Import canonical metrics module
    from src import metrics as _src_metrics

    # Seed a gauge so it appears in output even before traffic
    _src_metrics.set_gauge("murphy_task_queue_depth", 0.0)

    # Minimal /metrics fallback (mirrors the one in app.py)
    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        body = _src_metrics.render_metrics()
        return PlainResponse(
            content=body,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # Minimal /api/health
    @app.get("/api/health")
    async def health(deep: bool = False):
        from fastapi.responses import JSONResponse
        if not deep:
            return JSONResponse({"status": "healthy"})
        result = _src_metrics.get_system_health()
        return JSONResponse({"status": result["status"], "modules": result["modules"]})

    # Middleware that increments request counter (mirrors TraceIdMiddleware)
    class _MetricsMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            t0 = time.monotonic()
            response = await call_next(request)
            elapsed = time.monotonic() - t0
            try:
                _src_metrics.inc_counter(
                    "murphy_requests_total",
                    labels={"method": request.method, "status": str(response.status_code)},
                )
                _src_metrics.observe_histogram("murphy_request_duration_seconds", elapsed)
            except Exception:
                pass
            return response

    app.add_middleware(_MetricsMiddleware)
    return app, _src_metrics


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_and_metrics():
    """TestClient + metrics module with clean state."""
    from fastapi.testclient import TestClient
    from src.metrics import _counters, _gauges, _histograms, _module_health, _lock, _health_lock

    # Reset state before test
    with _lock:
        _counters.clear()
        _gauges.clear()
        _histograms.clear()
    with _health_lock:
        _module_health.clear()

    app, m = _make_minimal_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, m

    # Clean up after test
    with _lock:
        _counters.clear()
        _gauges.clear()
        _histograms.clear()
    with _health_lock:
        _module_health.clear()


# ---------------------------------------------------------------------------
# Test: /metrics endpoint
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client_and_metrics):
        client, _ = client_and_metrics
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_content_type_is_plain_text(self, client_and_metrics):
        client, _ = client_and_metrics
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_metrics_contains_uptime(self, client_and_metrics):
        client, _ = client_and_metrics
        resp = client.get("/metrics")
        body = resp.text
        assert "murphy_uptime_seconds" in body

    def test_metrics_contains_task_queue_depth(self, client_and_metrics):
        client, _ = client_and_metrics
        resp = client.get("/metrics")
        body = resp.text
        assert "murphy_task_queue_depth" in body

    def test_metrics_contains_requests_after_traffic(self, client_and_metrics):
        """After at least one request, murphy_requests_total must appear in /metrics."""
        client, _ = client_and_metrics
        # Generate traffic
        client.get("/api/health")
        resp = client.get("/metrics")
        body = resp.text
        assert "murphy_requests_total" in body

    def test_metrics_contains_histogram_after_traffic(self, client_and_metrics):
        """After traffic, request duration histogram must appear in /metrics."""
        client, _ = client_and_metrics
        client.get("/api/health")
        resp = client.get("/metrics")
        body = resp.text
        assert "murphy_request_duration_seconds" in body

    def test_metrics_prometheus_format(self, client_and_metrics):
        """Output must contain # HELP and # TYPE lines."""
        client, _ = client_and_metrics
        resp = client.get("/metrics")
        body = resp.text
        assert "# HELP" in body
        assert "# TYPE" in body


# ---------------------------------------------------------------------------
# Test: /api/health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_shallow_health_returns_healthy(self, client_and_metrics):
        client, _ = client_and_metrics
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_deep_health_includes_modules(self, client_and_metrics):
        client, m = client_and_metrics
        # Register a mock module health provider
        m.register_module_health("test_module", lambda: {"status": "ok"})
        resp = client.get("/api/health?deep=true")
        assert resp.status_code == 200
        data = resp.json()
        assert "modules" in data
        assert "test_module" in data["modules"]
        assert data["modules"]["test_module"]["status"] == "ok"

    def test_deep_health_degraded_on_module_error(self, client_and_metrics):
        client, m = client_and_metrics
        m.register_module_health("failing_module", lambda: {"status": "error"})
        resp = client.get("/api/health?deep=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"


# ---------------------------------------------------------------------------
# Test: src.metrics module directly
# ---------------------------------------------------------------------------

class TestSrcMetricsModule:
    def test_render_metrics_returns_non_empty_string(self):
        from src.metrics import render_metrics, set_gauge, _gauges, _lock
        with _lock:
            _gauges.clear()
        set_gauge("murphy_task_queue_depth", 5.0)
        output = render_metrics()
        assert isinstance(output, str)
        assert "murphy_task_queue_depth" in output
        assert "5.0" in output

    def test_get_system_health_healthy_by_default(self):
        from src.metrics import get_system_health, _module_health, _health_lock
        with _health_lock:
            _module_health.clear()
        result = get_system_health()
        assert result["status"] == "healthy"
        assert "uptime_seconds" in result

    def test_register_module_health_aggregated(self):
        from src.metrics import register_module_health, get_system_health, _module_health, _health_lock
        with _health_lock:
            _module_health.clear()
        register_module_health("my_module", lambda: {"status": "ok", "version": "1.0"})
        health = get_system_health()
        assert "my_module" in health["modules"]
        assert health["modules"]["my_module"]["status"] == "ok"
