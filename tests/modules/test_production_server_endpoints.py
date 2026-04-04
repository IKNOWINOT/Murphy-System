"""
Integration tests for production server endpoints:
  - POST /api/infrastructure/compare
  - POST /api/matrix/notify

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

try:
    from murphy_production_server import app as _prod_app

    _PROD_APP_AVAILABLE = True
except Exception:
    _PROD_APP_AVAILABLE = False
    _prod_app = None  # type: ignore[assignment]


@pytest.fixture()
def client():
    if not _PROD_APP_AVAILABLE:
        pytest.skip("murphy_production_server not importable")
    return TestClient(_prod_app)


# ── /api/infrastructure/compare ──────────────────────────────────────


class TestInfrastructureCompare:

    def test_infrastructure_compare_returns_comparisons(self, client) -> None:
        resp = client.post("/api/infrastructure/compare")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        comps = body["comparisons"]
        for key in ("postgres", "redis", "prometheus", "grafana", "ollama", "nginx"):
            assert key in comps, f"Missing comparison key: {key}"
            entry = comps[key]
            assert "required_by_hetzner" in entry
            assert "expected_port" in entry
            assert "status" in entry

    def test_infrastructure_compare_hetzner_found(self, client) -> None:
        resp = client.post("/api/infrastructure/compare")
        body = resp.json()
        assert body["hetzner_script_found"] is True

    def test_infrastructure_compare_overall_ready_without_env(
        self, client, monkeypatch
    ) -> None:
        for var in (
            "DATABASE_URL",
            "REDIS_URL",
            "OLLAMA_HOST",
            "SMTP_HOST",
            "GRAFANA_ADMIN_USER",
            "PROMETHEUS_ENABLED",
        ):
            monkeypatch.delenv(var, raising=False)
        resp = client.post("/api/infrastructure/compare")
        body = resp.json()
        assert body["overall_ready"] is False


# ── /api/matrix/notify ───────────────────────────────────────────────


class TestMatrixNotify:

    def test_matrix_notify_missing_config(self, client, monkeypatch) -> None:
        monkeypatch.delenv("MATRIX_HOMESERVER_URL", raising=False)
        monkeypatch.delenv("MATRIX_ACCESS_TOKEN", raising=False)
        resp = client.post(
            "/api/matrix/notify",
            json={"event_type": "hitl_pending", "hitl_id": "test-1"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["success"] is False
        assert "not configured" in body["error"].lower() or "missing" in body["error"].lower()

    def test_matrix_notify_missing_room(self, client, monkeypatch) -> None:
        monkeypatch.setenv("MATRIX_HOMESERVER_URL", "https://matrix.example.com")
        monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")
        monkeypatch.delenv("MATRIX_DEFAULT_ROOM_ID", raising=False)
        resp = client.post(
            "/api/matrix/notify",
            json={"event_type": "hitl_pending"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["success"] is False
        assert "room_id" in body["error"].lower()

    def test_matrix_notify_validation_error(self, client) -> None:
        resp = client.post("/api/matrix/notify", json={})
        assert resp.status_code == 422

    def test_matrix_notify_custom_message(self, client, monkeypatch) -> None:
        monkeypatch.setenv("MATRIX_HOMESERVER_URL", "https://matrix.example.com")
        monkeypatch.setenv("MATRIX_ACCESS_TOKEN", "syt_test_token")
        monkeypatch.setenv("MATRIX_DEFAULT_ROOM_ID", "!default:matrix.org")
        resp = client.post(
            "/api/matrix/notify",
            json={
                "event_type": "hitl_approved",
                "hitl_id": "h-42",
                "room_id": "!test:matrix.org",
                "message": "Custom test message",
            },
        )
        body = resp.json()
        assert body["sent"] is False
        assert body["message_body"] == "Custom test message"


# ── /module-instances/spawn ──────────────────────────────────────────


class TestModuleInstanceSpawn:

    def test_module_instances_spawn_via_production_server(self, client) -> None:
        resp = client.post(
            "/module-instances/spawn",
            json={"module_type": "test-svc"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["decision"] == "approved"
