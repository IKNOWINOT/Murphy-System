"""Tests for `GET /api/aionmind/audit` (Phase 2 / D21).

Covers:

* Disabled-by-default state (no env var, no path set) — endpoint
  returns ``{enabled: false, entries: []}`` cleanly without raising.
* Enabled state but file does not yet exist — returns
  ``{enabled: true, entries: []}``.
* Enabled state with a populated JSONL file — returns entries
  newest-first and respects ``limit``.
* ``limit`` clamping into ``[1, 500]``.
* Malformed JSONL lines are skipped, not raised.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def kernel():
    from aionmind.runtime_kernel import AionMindKernel

    return AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)


@pytest.fixture
def client_factory():
    """Build a fresh TestClient sharing one kernel instance with the router."""
    try:
        from fastapi.testclient import TestClient  # noqa: F401
    except Exception:  # pragma: no cover
        pytest.skip("fastapi[testclient] not installed")

    def _build(kernel):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from aionmind import api as aionmind_api

        aionmind_api.init_kernel(kernel)
        app = FastAPI()
        app.include_router(aionmind_api.router)
        return TestClient(app)

    return _build


class TestAuditEndpointDisabled:
    def test_disabled_state_returns_empty_envelope(self, kernel, client_factory):
        client = client_factory(kernel)
        resp = client.get("/api/aionmind/audit")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["enabled"] is False
        assert body["path"] is None
        assert body["entries"] == []
        assert body["count"] == 0
        # limit is still clamped/echoed even when disabled
        assert body["limit"] == 50


class TestAuditEndpointEnabled:
    def test_enabled_with_no_file_yet(self, kernel, client_factory, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        kernel.set_audit_log_path(str(log_path))
        client = client_factory(kernel)
        resp = client.get("/api/aionmind/audit")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["enabled"] is True
        assert body["path"] == str(log_path)
        assert body["entries"] == []
        assert body["count"] == 0

    def test_enabled_with_populated_file_returns_newest_first(
        self, kernel, client_factory, tmp_path
    ):
        log_path = tmp_path / "audit.jsonl"
        # Write three entries oldest-first; endpoint must return newest-first.
        entries = [
            {"ts": 1.0, "actor": "alice@example.com", "task_type": "general", "status": "completed", "auto_approved": True},
            {"ts": 2.0, "actor": "bob@example.com", "task_type": "general", "status": "awaiting_approval", "auto_approved": False},
            {"ts": 3.0, "actor": "carol@example.com", "task_type": "general", "status": "denied", "auto_approved": False},
        ]
        log_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
        kernel.set_audit_log_path(str(log_path))
        client = client_factory(kernel)
        resp = client.get("/api/aionmind/audit")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["enabled"] is True
        assert body["count"] == 3
        # Newest-first ordering
        assert [e["actor"] for e in body["entries"]] == [
            "carol@example.com",
            "bob@example.com",
            "alice@example.com",
        ]

    def test_limit_caps_returned_entries(self, kernel, client_factory, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        lines = [
            json.dumps({"ts": float(i), "actor": f"u{i}@x", "task_type": "general", "status": "completed"})
            for i in range(20)
        ]
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        kernel.set_audit_log_path(str(log_path))
        client = client_factory(kernel)
        resp = client.get("/api/aionmind/audit?limit=5")
        body = resp.json()
        assert body["count"] == 5
        # Newest-first — should be u19, u18, u17, u16, u15
        assert [e["actor"] for e in body["entries"]] == [f"u{i}@x" for i in (19, 18, 17, 16, 15)]

    def test_limit_clamped_below_one_uses_floor(self, kernel, client_factory, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        log_path.write_text(json.dumps({"ts": 1.0, "actor": "a"}) + "\n", encoding="utf-8")
        kernel.set_audit_log_path(str(log_path))
        client = client_factory(kernel)
        resp = client.get("/api/aionmind/audit?limit=0")
        assert resp.status_code == 200
        # Endpoint clamps the *returned* limit field to the floor (1).
        assert resp.json()["limit"] == 1

    def test_limit_clamped_above_ceiling(self, kernel, client_factory, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        kernel.set_audit_log_path(str(log_path))
        client = client_factory(kernel)
        resp = client.get("/api/aionmind/audit?limit=99999")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 500

    def test_malformed_lines_are_skipped(self, kernel, client_factory, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        # Mix of valid and bogus lines; bogus must be silently skipped.
        log_path.write_text(
            "\n".join([
                json.dumps({"ts": 1.0, "actor": "a", "status": "completed"}),
                "not-json-at-all",
                "",
                json.dumps({"ts": 2.0, "actor": "b", "status": "denied"}),
                json.dumps([1, 2, 3]),  # valid JSON but not a dict — must skip
            ]) + "\n",
            encoding="utf-8",
        )
        kernel.set_audit_log_path(str(log_path))
        client = client_factory(kernel)
        resp = client.get("/api/aionmind/audit")
        body = resp.json()
        # Only the two dict entries survive
        assert body["count"] == 2
        assert [e["actor"] for e in body["entries"]] == ["b", "a"]
