"""
Tests for the Dashboard live-metrics API endpoints.

Covers:
- GET /api/dashboards/live-metrics/snapshot returns JSON
- SSE endpoint exists and returns text/event-stream content type
- Snapshot includes required keys
- Interval parameter validation on SSE endpoint
"""

import pytest

pytest.importorskip("fastapi", reason="FastAPI not installed")
pytest.importorskip("httpx", reason="httpx not installed")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.dashboards.api import create_dashboard_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_client() -> TestClient:
    app = FastAPI()
    router = create_dashboard_router()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Snapshot endpoint
# ---------------------------------------------------------------------------

class TestLiveMetricsSnapshot:
    def test_snapshot_returns_200(self):
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics/snapshot")
        assert resp.status_code == 200

    def test_snapshot_returns_json(self):
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics/snapshot")
        data = resp.json()
        assert isinstance(data, dict)

    def test_snapshot_has_required_keys(self):
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics/snapshot")
        data = resp.json()
        for key in ("ts", "dashboards_count"):
            assert key in data, f"Missing key: {key}"

    def test_snapshot_ts_is_iso_string(self):
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics/snapshot")
        ts = resp.json().get("ts", "")
        assert "T" in ts or "Z" in ts, f"Unexpected ts format: {ts!r}"

    def test_snapshot_dashboards_count_is_integer(self):
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics/snapshot")
        count = resp.json().get("dashboards_count")
        assert isinstance(count, int)

    def test_snapshot_learning_connector_key_present(self):
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics/snapshot")
        data = resp.json()
        assert "learning_connector" in data

    def test_snapshot_event_backbone_key_present(self):
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics/snapshot")
        data = resp.json()
        assert "event_backbone" in data


# ---------------------------------------------------------------------------
# SSE endpoint (headers / content type)
# ---------------------------------------------------------------------------

class TestLiveMetricsSSE:
    def test_sse_endpoint_returns_200(self):
        """SSE endpoint must be reachable (not 404/500)."""
        client = _make_client()
        # Use stream=True style via requests; TestClient will read first chunk
        with client.stream("GET", "/api/dashboards/live-metrics?interval=1") as r:
            assert r.status_code == 200

    def test_sse_content_type_is_event_stream(self):
        client = _make_client()
        with client.stream("GET", "/api/dashboards/live-metrics?interval=1") as r:
            ct = r.headers.get("content-type", "")
            assert "text/event-stream" in ct

    def test_sse_interval_below_minimum_returns_422(self):
        """interval=0 should fail FastAPI validation (ge=1.0)."""
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics?interval=0")
        assert resp.status_code == 422

    def test_sse_interval_above_maximum_returns_422(self):
        """interval=999 should fail FastAPI validation (le=60.0)."""
        client = _make_client()
        resp = client.get("/api/dashboards/live-metrics?interval=999")
        assert resp.status_code == 422
