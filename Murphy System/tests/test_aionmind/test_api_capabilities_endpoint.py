"""Smoke tests for the AionMind FastAPI router (Phase 2 / F38 + D22).

* GET /api/aionmind/status → ``capabilities_registered`` ≥
  ``EXPECTED_MIN_CAPABILITIES`` and ``bridge_counts`` is non-empty.
* GET /api/aionmind/capabilities → returns the full capability list.
* GET /api/aionmind/capabilities?provider=automations → filters.
"""

from __future__ import annotations

import pytest

# Minimum capabilities expected after kernel boot with all Phase-2
# subsystem bridges loaded. Sum of:
#   automations(6) + hitl(4) + boards(5) + founder(3)
# + production(5) + integration_bus(1) + document(4) = 28
EXPECTED_MIN_CAPABILITIES = 28


@pytest.fixture(scope="module")
def client():
    try:
        from fastapi.testclient import TestClient
    except Exception:  # pragma: no cover
        pytest.skip("fastapi[testclient] not installed")
    from fastapi import FastAPI
    from aionmind import api as aionmind_api
    from aionmind.runtime_kernel import AionMindKernel

    kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=False)
    aionmind_api.init_kernel(kernel)
    app = FastAPI()
    app.include_router(aionmind_api.router)
    with TestClient(app) as c:
        yield c


class TestStatusEndpoint:
    def test_status_capabilities_count_meets_minimum(self, client):
        resp = client.get("/api/aionmind/status")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["capabilities_registered"] >= EXPECTED_MIN_CAPABILITIES
        assert isinstance(body.get("bridge_counts"), dict)
        assert body["bridge_counts"], "expected non-empty bridge_counts"


class TestCapabilitiesEndpoint:
    def test_capabilities_endpoint_lists_all(self, client):
        resp = client.get("/api/aionmind/capabilities")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["count"] >= EXPECTED_MIN_CAPABILITIES
        ids = {c["capability_id"] for c in body["capabilities"]}
        # Sample a few that must exist after Phase-2 bridge load.
        assert "automations.workflows.execute" in ids
        assert "hitl.decide" in ids
        assert "boards.create" in ids
        assert "founder.password.rotate" in ids
        assert "integration_bus.process" in ids

    def test_capabilities_endpoint_filters_by_provider(self, client):
        resp = client.get(
            "/api/aionmind/capabilities", params={"provider": "automations"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["count"] >= 1
        for cap in body["capabilities"]:
            assert cap["provider"] == "automations"

    def test_capabilities_endpoint_filters_by_tag(self, client):
        resp = client.get(
            "/api/aionmind/capabilities", params={"tag": "delete"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # automations.workflows.delete + boards.delete + production.proposals.delete
        ids = {c["capability_id"] for c in body["capabilities"]}
        assert "automations.workflows.delete" in ids
