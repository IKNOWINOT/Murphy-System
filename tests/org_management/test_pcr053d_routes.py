"""PCR-053d — Test suite for org_compiler_routes (HTTP surface).

Uses a FakeApp to exercise idempotency, route registration, and handler
output shape. End-to-end live tests against the running app are exercised
out-of-band by the deploy demo script.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pytest


# ─────────────────────────────────────────────────────────────────────
# FakeApp infrastructure (mirrors what register_executive() expects)
# ─────────────────────────────────────────────────────────────────────


class _State:
    """app.state — attribute bag."""


@dataclass
class FakeApp:
    state: _State = field(default_factory=_State)
    routes: Dict[str, Any] = field(default_factory=dict)

    def get(self, path):
        def deco(fn):
            self.routes[f"GET {path}"] = fn
            return fn
        return deco

    def post(self, path):
        def deco(fn):
            self.routes[f"POST {path}"] = fn
            return fn
        return deco


def _run(coro):
    """Run an async handler synchronously for tests."""
    return asyncio.get_event_loop().run_until_complete(coro) \
        if asyncio.get_event_loop().is_running() is False \
        else asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────


class TestRegistration:
    def test_registration_attaches_singletons(self):
        from src.org_compiler_routes import register_org_compiler
        app = FakeApp()
        status = register_org_compiler(app)
        assert status["compiler"] is True
        assert status["shadow_collector"] is True
        assert status["shadow_agent"] is True
        assert app.state.org_compiler is not None
        assert app.state.shadow_collector is not None
        assert app.state.shadow_agent is not None

    def test_registration_adds_five_routes(self):
        from src.org_compiler_routes import register_org_compiler
        app = FakeApp()
        status = register_org_compiler(app)
        assert "POST /api/org/compile" in status["routes_added"]
        assert "POST /api/org/shadow/observe" in status["routes_added"]
        assert "GET /api/org/proposals" in status["routes_added"]
        assert "GET /api/org/floor/{jurisdiction}/{industry}/{role_family}" in status["routes_added"]
        assert "GET /api/org/health" in status["routes_added"]

    def test_registration_is_idempotent(self):
        from src.org_compiler_routes import register_org_compiler
        app = FakeApp()
        register_org_compiler(app)
        route_count_after_first = len(app.routes)
        # Second call must not re-add routes
        status2 = register_org_compiler(app)
        assert status2["routes_added"] == ["<already-registered>"]
        assert len(app.routes) == route_count_after_first


# ─────────────────────────────────────────────────────────────────────
# Endpoint behavior
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def app():
    """Fresh registered app for each test."""
    from src.org_compiler_routes import register_org_compiler
    a = FakeApp()
    register_org_compiler(a)
    return a


class TestHealthEndpoint:
    def test_health_returns_ok_with_subsystem_status(self, app):
        h = app.routes["GET /api/org/health"]
        res = asyncio.run(h())
        assert res["ok"] is True
        assert res["compiler_attached"] is True
        assert res["shadow_collector_attached"] is True
        assert res["shadow_agent_attached"] is True
        assert res["regulatory_floor_rows"] >= 7   # from PCR-053c


class TestFloorLookupEndpoint:
    def test_known_combination_returns_floor(self, app):
        h = app.routes["GET /api/org/floor/{jurisdiction}/{industry}/{role_family}"]
        res = asyncio.run(h(jurisdiction="US-CA", industry="saas", role_family="sales_rep"))
        assert res["ok"] is True
        assert res["floor"]["min_observation_days"] == 14
        assert res["floor"]["min_distinct_operators"] == 3
        assert res["floor"]["max_decision_ceiling_usd"] == 50_000.0

    def test_missing_combination_returns_404_fail_closed(self, app):
        # PCR-053e-test-fix: handler now returns JSONResponse OR (body, 404)
        # tuple depending on whether fastapi is importable.
        h = app.routes["GET /api/org/floor/{jurisdiction}/{industry}/{role_family}"]
        res = asyncio.run(h(jurisdiction="MARS", industry="interplanetary", role_family="rover"))
        import json as _json
        try:
            from fastapi.responses import JSONResponse
        except Exception:
            JSONResponse = None
        if JSONResponse is not None and isinstance(res, JSONResponse):
            assert res.status_code == 404
            body = _json.loads(bytes(res.body))
        else:
            body, status = res
            assert status == 404
        assert body["fail_closed"] is True
        assert body["ok"] is False

    def test_never_promote_row_exposed(self, app):
        h = app.routes["GET /api/org/floor/{jurisdiction}/{industry}/{role_family}"]
        res = asyncio.run(h(jurisdiction="CH", industry="banking", role_family="compliance_officer"))
        assert res["ok"] is True
        assert res["floor"]["never_promote"] is True


class TestCompileEndpoint:
    def test_compile_returns_role_template_with_pcr053b_fields(self, app):
        h = app.routes["POST /api/org/compile"]
        payload = {
            "org_chart": [
                {"node_id": "n_sales", "role_name": "Sales Rep",
                 "reports_to": None, "team": "sales",
                 "department": "go_to_market", "authority_level": "low"},
            ],
            "sop_data": {"Sales Rep": {"responsibilities": ["qualify", "quote", "close"]}},
            "role_name": "Sales Rep",
        }
        res = asyncio.run(h(payload))
        # may return tuple (body, status) on error or dict on success
        if isinstance(res, tuple):
            pytest.fail(f"expected success, got error tuple: {res}")
        assert res["ok"] is True
        tpl = res["role_template"]
        assert tpl["role_name"] == "Sales Rep"
        # PCR-053b fields must appear in API response
        assert "decision_ceiling_usd" in tpl
        assert "distinct_operators_required" in tpl
        assert "primary_jurisdiction" in tpl
        # Integrity hash exists
        assert len(tpl["integrity_hash"]) == 64

    def test_compile_rejects_missing_role_name(self, app):
        h = app.routes["POST /api/org/compile"]
        res = asyncio.run(h({"org_chart": [], "sop_data": {}}))
        assert isinstance(res, tuple)
        body, status = res
        assert status == 400
        assert "missing role_name" in body["error"]


class TestShadowObserveEndpoint:
    def test_observe_task_records_event(self, app):
        h = app.routes["POST /api/org/shadow/observe"]
        res = asyncio.run(h({
            "kind": "task",
            "role": "Sales Rep",
            "task": "send_quote",
            "metadata": {"deal_size_usd": 5000, "tenant": "inoni"},
        }))
        assert res["ok"] is True
        assert res["kind_recorded"] == "task"
        assert res["totals"]["task_assignments"] >= 1

    def test_observe_rejects_unknown_kind(self, app):
        h = app.routes["POST /api/org/shadow/observe"]
        res = asyncio.run(h({"kind": "weird", "role": "X"}))
        body, status = res
        assert status == 400
        assert "unknown kind" in body["error"]

    def test_observe_rejects_missing_role(self, app):
        h = app.routes["POST /api/org/shadow/observe"]
        res = asyncio.run(h({"kind": "task"}))
        body, status = res
        assert status == 400


class TestProposalsEndpoint:
    def test_proposals_empty_when_no_observations(self, app):
        h = app.routes["GET /api/org/proposals"]
        res = asyncio.run(h())
        assert res["ok"] is True
        assert res["proposals"] == []

    def test_proposals_after_observations_carry_verdict(self, app):
        """Observe a few tasks then list proposals and verify the multi-dim
        N verdict comes back per-dimension."""
        obs = app.routes["POST /api/org/shadow/observe"]
        for i in range(5):
            asyncio.run(obs({
                "kind": "task", "role": "Sales Rep", "task": "send_quote",
                "metadata": {"deal_size_usd": 5000 + i*1000, "operator": f"human_{i%2}"},
            }))
        lst = app.routes["GET /api/org/proposals"]
        res = asyncio.run(lst(jurisdiction="US-CA", industry="saas"))
        assert res["ok"] is True
        assert res["count"] >= 1
        p = res["proposals"][0]
        assert p["role"] == "Sales Rep"
        assert "verdict" in p
        assert "passes" in p["verdict"]
        assert "reasons" in p["verdict"]
        # We only observed for a moment with 2 operators — expect blocking on
        # at least one dimension (either OPERATORS < 3 or TIME < 14d).
        assert p["verdict"]["passes"] is False

    def test_proposals_fail_closed_when_jurisdiction_missing(self, app):
        """Per locked policy: no jurisdiction = verdict.fail_closed=True."""
        obs = app.routes["POST /api/org/shadow/observe"]
        asyncio.run(obs({"kind": "task", "role": "Sales Rep", "task": "send_quote"}))

        lst = app.routes["GET /api/org/proposals"]
        res = asyncio.run(lst(jurisdiction=None, industry="saas"))
        assert res["ok"] is True
        assert any(p["verdict"]["fail_closed"] for p in res["proposals"])
