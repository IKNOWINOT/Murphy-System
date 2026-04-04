"""
Integration tests for src.module_instance_api (FastAPI endpoints)

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.module_instance_api import register_module_instance_routes
import src.module_instance_api as _api_mod
from src.module_instance_manager import ModuleInstanceManager


@pytest.fixture()
def client():
    """Fresh FastAPI app + TestClient with a reset manager."""
    app = FastAPI()
    register_module_instance_routes(app)
    _api_mod._manager = ModuleInstanceManager()
    return TestClient(app)


def _spawn(client: TestClient, module_type: str = "worker", **overrides):
    """Helper: spawn an instance and return the response JSON."""
    payload = {"module_type": module_type, **overrides}
    resp = client.post("/module-instances/spawn", json=payload)
    return resp


# ── Spawn ────────────────────────────────────────────────────────────────


class TestSpawn:
    def test_successful_spawn(self, client):
        resp = _spawn(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["decision"] == "approved"
        assert "instance" in body
        assert body["instance"]["module_type"] == "worker"
        assert body["instance"]["state"] == "active"

    def test_validation_error_empty_module_type(self, client):
        resp = client.post("/module-instances/spawn", json={"module_type": ""})
        assert resp.status_code == 422

    def test_spawn_denied_when_blacklisted(self, client):
        client.post(
            "/module-instances/types/dangerous/blacklist",
            json={"actor": "admin"},
        )
        resp = _spawn(client, module_type="dangerous")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["decision"] == "denied_blacklist"


# ── List ─────────────────────────────────────────────────────────────────


class TestList:
    def test_list_returns_spawned_instances(self, client):
        _spawn(client, "a")
        _spawn(client, "b")
        resp = client.get("/module-instances/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["count"] == 2

    def test_list_filter_by_module_type(self, client):
        _spawn(client, "alpha")
        _spawn(client, "beta")
        resp = client.get("/module-instances/", params={"module_type": "alpha"})
        body = resp.json()
        assert body["count"] == 1
        assert body["instances"][0]["module_type"] == "alpha"

    def test_list_filter_by_state(self, client):
        r = _spawn(client, "worker")
        iid = r.json()["instance"]["instance_id"]
        client.post(f"/module-instances/{iid}/despawn", json={"actor": "sys"})
        resp = client.get("/module-instances/", params={"state": "despawned"})
        body = resp.json()
        assert body["count"] == 1
        assert body["instances"][0]["state"] == "despawned"


# ── Single instance ──────────────────────────────────────────────────────


class TestGetInstance:
    def test_returns_instance(self, client):
        r = _spawn(client)
        iid = r.json()["instance"]["instance_id"]
        resp = client.get(f"/module-instances/{iid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["instance"]["instance_id"] == iid

    def test_404_for_unknown_id(self, client):
        resp = client.get("/module-instances/nonexistent")
        assert resp.status_code == 404


# ── Despawn ──────────────────────────────────────────────────────────────


class TestDespawn:
    def test_successful_despawn(self, client):
        r = _spawn(client)
        iid = r.json()["instance"]["instance_id"]
        resp = client.post(f"/module-instances/{iid}/despawn", json={"actor": "admin"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["instance_id"] == iid

    def test_404_for_unknown_id(self, client):
        resp = client.post("/module-instances/nope/despawn", json={"actor": "sys"})
        assert resp.status_code == 404


# ── Viability check ──────────────────────────────────────────────────────


class TestViabilityCheck:
    def test_viable_check(self, client):
        resp = client.post(
            "/module-instances/viability/check",
            json={"module_type": "worker"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["viable"] is True
        assert body["result"] == "viable"

    def test_blacklisted_check(self, client):
        client.post(
            "/module-instances/types/bad/blacklist",
            json={"actor": "admin"},
        )
        resp = client.post(
            "/module-instances/viability/check",
            json={"module_type": "bad"},
        )
        body = resp.json()
        assert body["viable"] is False
        assert body["result"] == "blacklisted"


# ── Find viable ──────────────────────────────────────────────────────────


class TestFindViable:
    def test_find_matching_instances(self, client):
        _spawn(client, "svc", capabilities=["gpu"])
        _spawn(client, "svc", capabilities=["cpu"])
        resp = client.post(
            "/module-instances/find-viable",
            json={"module_type": "svc", "required_capabilities": ["gpu"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["count"] == 1


# ── Audit trail ──────────────────────────────────────────────────────────


class TestAuditTrail:
    def test_returns_entries(self, client):
        _spawn(client)
        resp = client.get("/module-instances/audit/trail")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["count"] >= 1
        assert "entries" in body


# ── Config history ───────────────────────────────────────────────────────


class TestConfigHistory:
    def test_returns_config_history(self, client):
        r = _spawn(client)
        iid = r.json()["instance"]["instance_id"]
        resp = client.get(f"/module-instances/{iid}/config-history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["instance_id"] == iid
        assert body["count"] >= 1
        assert "snapshots" in body


# ── Status ───────────────────────────────────────────────────────────────


class TestStatus:
    def test_manager_status(self, client):
        _spawn(client)
        resp = client.get("/module-instances/status/manager")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "total_instances" in body
        assert "by_state" in body

    def test_resource_availability(self, client):
        resp = client.get("/module-instances/status/resources")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "allocated_cpu_cores" in body
        assert "available_memory_mb" in body


# ── Type management ──────────────────────────────────────────────────────


class TestTypeManagement:
    def test_register_new_type(self, client):
        resp = client.post(
            "/module-instances/types/register",
            json={"module_type": "new_svc", "metadata": {"version": "1.0"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["module_type"] == "new_svc"
        assert body["created"] is True

    def test_blacklist_type(self, client):
        resp = client.post(
            "/module-instances/types/evil/blacklist",
            json={"actor": "admin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["blacklisted"] is True
        assert body["module_type"] == "evil"


# ── Bulk despawn ─────────────────────────────────────────────────────────


class TestBulkDespawn:
    def test_bulk_despawn(self, client):
        r1 = _spawn(client, "x")
        r2 = _spawn(client, "y")
        id1 = r1.json()["instance"]["instance_id"]
        id2 = r2.json()["instance"]["instance_id"]
        resp = client.post(
            "/module-instances/bulk/despawn",
            json={"instance_ids": [id1, id2], "actor": "admin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["results"][id1] is True
        assert body["results"][id2] is True


# ── Audit export ─────────────────────────────────────────────────────────


class TestAuditExport:
    def test_export_returns_report(self, client):
        _spawn(client, "audit_worker")
        resp = client.get("/module-instances/audit/export")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "generated_at" in body
        assert "summary" in body
        assert body["summary"]["total_instances"] >= 1
        assert "instances" in body
        assert "audit_log" in body
        assert "config_snapshots" in body


# ── Unblacklist ──────────────────────────────────────────────────────────


class TestUnblacklist:
    def test_unblacklist_type(self, client):
        # Blacklist first
        client.post(
            "/module-instances/types/removeme/blacklist",
            json={"actor": "admin"},
        )
        # Unblacklist
        resp = client.delete("/module-instances/types/removeme/blacklist")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["unblacklisted"] is True

    def test_unblacklist_not_blacklisted(self, client):
        resp = client.delete("/module-instances/types/never_blocked/blacklist")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False


# ── Unregister type ──────────────────────────────────────────────────────


class TestUnregisterType:
    def test_unregister_existing_type(self, client):
        client.post(
            "/module-instances/types/register",
            json={"module_type": "temp_svc"},
        )
        resp = client.delete("/module-instances/types/temp_svc")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["unregistered"] is True

    def test_unregister_nonexistent_returns_404(self, client):
        resp = client.delete("/module-instances/types/ghost")
        assert resp.status_code == 404


# ── List types ───────────────────────────────────────────────────────────


class TestListTypes:
    def test_list_types_returns_registered_and_blacklisted(self, client):
        client.post(
            "/module-instances/types/register",
            json={"module_type": "svc_a"},
        )
        client.post(
            "/module-instances/types/blocked/blacklist",
            json={"actor": "admin"},
        )
        resp = client.get("/module-instances/types")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "svc_a" in body["registered"]
        assert "blocked" in body["blacklisted"]

    def test_list_types_empty(self, client):
        resp = client.get("/module-instances/types")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["registered"] == {}
        assert body["blacklisted"] == []
