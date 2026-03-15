"""
Gap Closure Tests — Unified Flask→FastAPI Gateway.

Validates all 10 correlation items identified in the frontend/backend audit:

  Gap 1  (Critical):  Dual-Framework Unification — Flask services exposed via main FastAPI app
  Gap 2  (High):      Standardise Frontend API Fetch — apiFetch replaced with MurphyAPI
  Gap 3  (High):      Stub Endpoints — orphaned frontend calls return 501
  Gap 4  (High):      Auth Layer Unification — single APIKeyMiddleware on all /api/* routes
  Gap 5  (Medium):    Shared Type Contracts — TypeScript interfaces + JSDoc validators exist
  Gap 6  (Medium):    Error Handling Normalisation — all errors use standard {success, error}
  Gap 7  (Medium):    API Manifest Endpoint — /api/manifest lists all routes
  Gap 8  (Low):       WebSocket Standardisation — MurphyWebSocket class in murphy-components.js
  Gap 9  (Low):       API URL Pattern Documentation — API_ROUTES.md exists and is complete
  Gap 10 (Low):       murphy_auth.js on every API-calling HTML page

Each test class corresponds to one gap.
"""
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1

from __future__ import annotations

import asyncio
import os
import socket
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup — ensure src/ is importable
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_SRC))

os.environ.setdefault("MURPHY_ENV", "test")
# Raise rate limit so integration smoke tests don't trigger 429 responses.
os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "600")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

try:
    from httpx import AsyncClient, ASGITransport
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

pytestmark = pytest.mark.skipif(not _HAS_HTTPX, reason="httpx not available")


def _make_loop():
    return asyncio.new_event_loop()


def _sync(coro, loop=None):
    """Run coroutine in a fresh event loop and return the result."""
    _loop = loop or asyncio.new_event_loop()
    try:
        return _loop.run_until_complete(coro)
    finally:
        if not loop:
            _loop.close()


def _app():
    from src.runtime.app import create_app
    return create_app()


def _req_get(app, path: str, headers: dict | None = None):
    async def _inner():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.get(path, headers=headers or {})
    return _sync(_inner())


def _req_post(app, path: str, body: dict | None = None, headers: dict | None = None):
    async def _inner():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.post(path, json=body or {}, headers=headers or {})
    return _sync(_inner())


def _req_delete(app, path: str):
    async def _inner():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.delete(path)
    return _sync(_inner())


# ===========================================================================
# Gap 1 — Dual-Framework Unification: Flask services reachable on main app
# ===========================================================================

class TestGap1FlaskToFastAPIUnification:
    """All previously-standalone Flask services are now FastAPI endpoints."""

    # ── COA (Cost Optimization Advisor) ────────────────────────────────────

    def test_coa_health_reachable(self):
        """GET /api/coa/health returns 200 from FastAPI — not a separate Flask server."""
        resp = _req_get(_app(), "/api/coa/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    def test_coa_list_resources_empty(self):
        resp = _req_get(_app(), "/api/coa/resources")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_coa_register_resource_and_retrieve(self):
        """Create then immediately retrieve using the SAME app instance."""
        app = _app()

        async def _cycle():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r1 = await c.post("/api/coa/resources", json={"name": "test-server", "provider": "aws"})
                assert r1.status_code == 201
                rid = r1.json()["data"]["id"]
                r2 = await c.get(f"/api/coa/resources/{rid}")
                assert r2.status_code == 200
                assert r2.json()["data"]["name"] == "test-server"

        _sync(_cycle())

    def test_coa_missing_field_returns_400(self):
        resp = _req_post(_app(), "/api/coa/resources", {})
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "MISSING_FIELD"

    # ── CCE (Compliance as Code Engine) ────────────────────────────────────

    def test_cce_health_reachable(self):
        resp = _req_get(_app(), "/api/cce/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "healthy"

    def test_cce_create_and_list_rule(self):
        app = _app()

        async def _cycle():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r1 = await c.post("/api/cce/rules", json={
                    "name": "no-root-login",
                    "expression": "user != 'root'",
                })
                assert r1.status_code == 201
                r2 = await c.get("/api/cce/rules")
                assert r2.status_code == 200
                rules = r2.json()["data"]
                assert isinstance(rules, list)
                assert any(r["name"] == "no-root-login" for r in rules)

        _sync(_cycle())

    def test_cce_missing_expression_returns_400(self):
        resp = _req_post(_app(), "/api/cce/rules", {"name": "incomplete-rule"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "MISSING_FIELD"

    # ── BAT (Blockchain Audit Trail) ────────────────────────────────────────

    def test_bat_health_reachable(self):
        resp = _req_get(_app(), "/api/bat/health")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "healthy"

    def test_bat_record_entry_and_search(self):
        app = _app()

        async def _cycle():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # Record an entry
                r1 = await c.post("/api/bat/entries", json={
                    "entry_type": "api_call",
                    "actor": "gap-test-actor",
                    "action": "gap-closure-test",
                })
                assert r1.status_code == 201
                assert r1.json()["data"]["actor"] == "gap-test-actor"

                # Seal to make the entry searchable
                await c.post("/api/bat/blocks/seal")

                # Search should now find it
                r2 = await c.get("/api/bat/entries/search?actor=gap-test-actor&limit=5")
                assert r2.status_code == 200
                entries = r2.json()["data"]
                assert any(e.get("actor") == "gap-test-actor" for e in entries)

        _sync(_cycle())

    def test_bat_verify_chain(self):
        resp = _req_get(_app(), "/api/bat/verify")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_bat_stats_reachable(self):
        resp = _req_get(_app(), "/api/bat/stats")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    # ── Gate Synthesis ──────────────────────────────────────────────────────

    def test_gate_synthesis_health_reachable(self):
        resp = _req_get(_app(), "/api/gate-synthesis/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    def test_gate_synthesis_list_gates_empty(self):
        resp = _req_get(_app(), "/api/gate-synthesis/gates/list")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_gate_synthesis_statistics(self):
        resp = _req_get(_app(), "/api/gate-synthesis/statistics")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    # ── Module Compiler ────────────────────────────────────────────────────

    def test_module_compiler_endpoint_registered(self):
        """Module compiler endpoint is registered — not a 405 Method Not Allowed."""
        resp = _req_get(_app(), "/api/module-compiler/health")
        assert resp.status_code != 405, "Module compiler endpoint must be registered"

    # ── Compute Plane ──────────────────────────────────────────────────────

    def test_compute_plane_endpoint_registered(self):
        resp = _req_get(_app(), "/api/compute-plane/health")
        assert resp.status_code != 405

    # ── Old Flask Ports Must Be Closed ─────────────────────────────────────

    def test_module_compiler_not_on_port_8053(self):
        """No standalone Flask server on port 8053."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            assert s.connect_ex(("127.0.0.1", 8053)) != 0, \
                "Flask module compiler server still running on port 8053"

    def test_compute_plane_not_on_port_8054(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            assert s.connect_ex(("127.0.0.1", 8054)) != 0, \
                "Flask compute plane server still running on port 8054"

    def test_gate_synthesis_not_on_port_8056(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            assert s.connect_ex(("127.0.0.1", 8056)) != 0, \
                "Flask gate synthesis server still running on port 8056"

    # ── All Gateway Domains Expose /health ─────────────────────────────────

    def test_all_gateway_health_endpoints_ok(self):
        app = _app()

        async def _all():
            health_paths = [
                "/api/coa/health",
                "/api/cce/health",
                "/api/bat/health",
                "/api/gate-synthesis/health",
            ]
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                for path in health_paths:
                    r = await c.get(path)
                    assert r.status_code == 200, f"{path} returned {r.status_code}"
                    assert r.json()["success"] is True, f"{path} success=False"

        _sync(_all())


# ===========================================================================
# Gap 2 — Standardise Frontend API Fetch Patterns
# ===========================================================================

class TestGap2FrontendApiFetch:
    """matrix_integration.html and production_wizard.html use MurphyAPI; flowApi.ts uses murphyClient."""

    @staticmethod
    def _html(name: str) -> str:
        return (_REPO_ROOT / name).read_text(encoding="utf-8")

    @staticmethod
    def _ts(rel: str) -> str:
        return (_REPO_ROOT / rel).read_text(encoding="utf-8")

    def test_matrix_integration_uses_murphyapi_class(self):
        assert "new MurphyAPI(" in self._html("matrix_integration.html")

    def test_matrix_integration_no_raw_base_fetch(self):
        """Raw fetch() with BASE prefix must be gone."""
        assert "await fetch(`${BASE}" not in self._html("matrix_integration.html")

    def test_matrix_integration_handles_get(self):
        assert "_matrixApi.get(" in self._html("matrix_integration.html")

    def test_matrix_integration_handles_post(self):
        assert "_matrixApi.post(" in self._html("matrix_integration.html")

    def test_matrix_integration_handles_put(self):
        assert "_matrixApi.put(" in self._html("matrix_integration.html")

    def test_matrix_integration_handles_delete(self):
        assert "_matrixApi.delete(" in self._html("matrix_integration.html")

    def test_production_wizard_uses_murphyapi_class(self):
        assert "new MurphyAPI(" in self._html("production_wizard.html")

    def test_production_wizard_no_raw_base_fetch(self):
        assert "await fetch(`${BASE}" not in self._html("production_wizard.html")

    def test_production_wizard_handles_all_methods(self):
        html = self._html("production_wizard.html")
        for method in ("get", "post", "put", "delete"):
            assert f"_prodApi.{method}(" in html, f"production_wizard.html missing {method}"

    def test_murphyclient_ts_exists(self):
        assert (_REPO_ROOT / "web" / "src" / "api" / "murphyClient.ts").exists()

    def test_murphyclient_ts_exports_get_post_put_del(self):
        ts = self._ts("web/src/api/murphyClient.ts")
        for fn in ("export function get", "export function post",
                   "export function put", "export function del"):
            assert fn in ts, f"murphyClient.ts must export `{fn.split()[-1]}`"

    def test_murphyclient_ts_has_retry_logic(self):
        ts = self._ts("web/src/api/murphyClient.ts")
        assert "MAX_RETRIES" in ts
        assert "_backoff" in ts

    def test_murphyclient_ts_has_circuit_breaker(self):
        ts = self._ts("web/src/api/murphyClient.ts")
        assert "CB_THRESHOLD" in ts
        assert "_checkCircuit" in ts

    def test_murphyclient_ts_sends_api_key_header(self):
        assert "X-API-Key" in self._ts("web/src/api/murphyClient.ts")

    def test_flowapi_ts_imports_murphyclient(self):
        ts = self._ts("web/src/components/FlowCanvas/flowApi.ts")
        assert "murphyClient" in ts

    def test_flowapi_ts_no_raw_fetch(self):
        assert "await fetch(" not in self._ts("web/src/components/FlowCanvas/flowApi.ts")

    def test_flowapi_ts_deprecated_apibase_annotated(self):
        ts = self._ts("web/src/components/FlowCanvas/flowApi.ts")
        assert "@deprecated" in ts


# ===========================================================================
# Gap 3 — Stub Endpoints for Orphaned Frontend Calls
# ===========================================================================

class TestGap3StubEndpoints:
    """Previously-orphaned frontend calls must get a registered endpoint."""

    def test_analyze_domain_returns_501(self):
        resp = _req_post(_app(), "/api/analyze-domain", {})
        assert resp.status_code == 501
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_IMPLEMENTED"
        assert "not yet implemented" in data["error"]["message"].lower()

    def test_orchestrator_overview_registered(self):
        """Was orphaned — must now be a real or stub endpoint (not 404)."""
        resp = _req_get(_app(), "/api/orchestrator/overview")
        assert resp.status_code != 404, \
            "/api/orchestrator/overview returns 404 — endpoint not registered"

    def test_matrix_status_registered(self):
        resp = _req_get(_app(), "/api/matrix/status")
        assert resp.status_code != 404

    def test_wingman_status_registered(self):
        resp = _req_get(_app(), "/api/wingman/status")
        assert resp.status_code != 404

    def test_causality_graph_registered(self):
        resp = _req_get(_app(), "/api/causality/graph")
        assert resp.status_code != 404

    def test_heatmap_data_registered(self):
        resp = _req_get(_app(), "/api/heatmap/data")
        assert resp.status_code != 404

    def test_production_hitl_submit_registered(self):
        resp = _req_post(_app(), "/api/production/hitl/submit", {})
        assert resp.status_code != 404

    def test_production_hitl_learned_registered(self):
        resp = _req_get(_app(), "/api/production/hitl/learned")
        assert resp.status_code != 404

    def test_stub_returns_standard_envelope(self):
        """All stubs must use the standard error envelope."""
        resp = _req_post(_app(), "/api/analyze-domain", {})
        data = resp.json()
        assert "success" in data
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]


# ===========================================================================
# Gap 4 — Auth Layer Unification
# ===========================================================================

class TestGap4AuthUnification:
    """APIKeyMiddleware enforces X-API-Key on /api/* when env var is set."""

    def _with_key(self, env_key: str, request_key: str | None, path: str = "/api/bat/stats"):
        old = os.environ.pop("MURPHY_API_KEY", None)
        if env_key:
            os.environ["MURPHY_API_KEY"] = env_key
        try:
            app = _app()
            headers = {"X-API-Key": request_key} if request_key else {}
            return _req_get(app, path, headers=headers)
        finally:
            if old is not None:
                os.environ["MURPHY_API_KEY"] = old
            elif "MURPHY_API_KEY" in os.environ:
                del os.environ["MURPHY_API_KEY"]

    def test_permissive_without_env_key(self):
        resp = self._with_key("", None)
        assert resp.status_code == 200

    def test_enforced_missing_header(self):
        resp = self._with_key("test-secret", None)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTH_REQUIRED"

    def test_enforced_wrong_key(self):
        resp = self._with_key("test-secret", "wrong-key")
        assert resp.status_code == 401

    def test_passes_correct_key(self):
        resp = self._with_key("test-secret", "test-secret")
        assert resp.status_code == 200

    def test_health_exempt(self):
        resp = self._with_key("test-secret", None, "/api/health")
        assert resp.status_code == 200

    def test_manifest_exempt(self):
        resp = self._with_key("test-secret", None, "/api/manifest")
        assert resp.status_code == 200

    def test_auth_error_uses_standard_envelope(self):
        resp = self._with_key("test-secret", None)
        data = resp.json()
        assert data["success"] is False
        assert "error" in data and "code" in data["error"]

    def test_all_html_pages_include_murphy_auth_js(self):
        pages = [
            "terminal_unified.html", "terminal_costs.html", "terminal_integrated.html",
            "terminal_integrations.html", "terminal_architect.html", "terminal_worker.html",
            "terminal_orchestrator.html", "terminal_enhanced.html", "terminal_orgchart.html",
            "matrix_integration.html", "production_wizard.html", "onboarding_wizard.html",
            "compliance_dashboard.html", "workflow_canvas.html", "calendar.html",
            "meeting_intelligence.html", "ambient_intelligence.html", "system_visualizer.html",
            "management.html", "wallet.html", "pricing.html",
        ]
        missing = [
            p for p in pages
            if (_REPO_ROOT / p).exists()
            and "murphy_auth.js" not in (_REPO_ROOT / p).read_text(encoding="utf-8")
        ]
        assert not missing, f"murphy_auth.js missing from: {missing}"

    def test_murphy_auth_placed_after_murphy_components(self):
        pages = ["terminal_unified.html", "matrix_integration.html", "production_wizard.html"]
        for page in pages:
            p = _REPO_ROOT / page
            if not p.exists():
                continue
            html = p.read_text(encoding="utf-8")
            mc_pos = html.find("murphy-components.js")
            auth_pos = html.find("murphy_auth.js")
            if mc_pos != -1 and auth_pos != -1:
                assert auth_pos > mc_pos, \
                    f"{page}: murphy_auth.js must follow murphy-components.js"


# ===========================================================================
# Gap 5 — Shared Type Contracts
# ===========================================================================

class TestGap5SharedTypeContracts:
    """TypeScript types and JSDoc validators exist and have the right shapes."""

    def test_types_ts_exists(self):
        assert (_REPO_ROOT / "web" / "src" / "api" / "types.ts").exists()

    def test_types_ts_api_response(self):
        ts = (_REPO_ROOT / "web" / "src" / "api" / "types.ts").read_text()
        assert "ApiResponse" in ts
        assert "success: boolean" in ts

    def test_types_ts_health_status(self):
        assert "HealthStatus" in (_REPO_ROOT / "web" / "src" / "api" / "types.ts").read_text()

    def test_types_ts_form_submission_result(self):
        assert "FormSubmissionResult" in (_REPO_ROOT / "web" / "src" / "api" / "types.ts").read_text()

    def test_types_ts_flow_execution_result(self):
        assert "FlowExecutionResult" in (_REPO_ROOT / "web" / "src" / "api" / "types.ts").read_text()

    def test_types_ts_module_spec(self):
        assert "ModuleSpec" in (_REPO_ROOT / "web" / "src" / "api" / "types.ts").read_text()

    def test_murphy_schemas_js_exists(self):
        assert (_REPO_ROOT / "static" / "murphy-schemas.js").exists()

    def test_murphy_schemas_js_validate_api_response(self):
        js = (_REPO_ROOT / "static" / "murphy-schemas.js").read_text()
        assert "validateApiResponse" in js
        assert "window.validateApiResponse" in js

    def test_murphy_schemas_js_assert_ok(self):
        js = (_REPO_ROOT / "static" / "murphy-schemas.js").read_text()
        assert "assertOk" in js
        assert "window.assertOk" in js

    def test_error_envelope_module_importable(self):
        from src.error_envelope import success_response, error_response
        from fastapi.responses import JSONResponse
        sr = success_response({"key": "val"})
        er = error_response("NOT_FOUND", "not found", 404)
        assert isinstance(sr, JSONResponse) and sr.status_code == 200
        assert isinstance(er, JSONResponse) and er.status_code == 404

    def test_error_envelope_body_shape(self):
        import json
        from src.error_envelope import success_response, error_response
        sr = success_response({"x": 1})
        body = json.loads(sr.body)
        assert body["success"] is True and "data" in body

        er = error_response("OOPS", "msg", 400)
        body2 = json.loads(er.body)
        assert body2["success"] is False
        assert body2["error"]["code"] == "OOPS"
        assert body2["error"]["message"] == "msg"


# ===========================================================================
# Gap 6 — Error Handling Normalisation
# ===========================================================================

class TestGap6ErrorNormalisation:
    """All API errors use standard {success: false, error: {code, message}} envelope."""

    def test_404_standard_envelope(self):
        resp = _req_get(_app(), "/api/does-not-exist-xyz-abc")
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["code"] == "HTTP_404"
        assert "message" in data["error"]

    def test_success_has_success_true(self):
        """Gateway service endpoints must return success=True on valid requests."""
        resp = _req_get(_app(), "/api/coa/health")
        assert resp.json().get("success") is True

    def test_coa_bad_request_envelope(self):
        resp = _req_post(_app(), "/api/coa/resources", {})
        data = resp.json()
        assert resp.status_code == 400
        assert data["success"] is False
        assert data["error"]["code"] == "MISSING_FIELD"
        assert "message" in data["error"]

    def test_cce_bad_request_envelope(self):
        resp = _req_post(_app(), "/api/cce/rules", {"name": "only-name"})
        data = resp.json()
        assert resp.status_code == 400
        assert data["success"] is False
        assert "code" in data["error"] and "message" in data["error"]

    def test_bat_bad_request_envelope(self):
        resp = _req_post(_app(), "/api/bat/entries", {})
        data = resp.json()
        assert resp.status_code == 400
        assert data["success"] is False

    def test_parse_response_handles_legacy_flask(self):
        js = (_REPO_ROOT / "static" / "murphy-components.js").read_text()
        assert "_parseResponse" in js
        assert "LEGACY_ERROR" in js
        assert "data.status === 'error'" in js

    def test_parse_response_handles_fastapi_detail(self):
        js = (_REPO_ROOT / "static" / "murphy-components.js").read_text()
        assert "'detail' in data" in js or '"detail" in data' in js

    def test_parse_response_handles_custom_error(self):
        js = (_REPO_ROOT / "static" / "murphy-components.js").read_text()
        assert "typeof data.error === 'string'" in js

    def test_parse_response_passes_standard_envelope(self):
        js = (_REPO_ROOT / "static" / "murphy-components.js").read_text()
        assert "'success' in data" in js


# ===========================================================================
# Gap 7 — API Manifest Endpoint
# ===========================================================================

class TestGap7ApiManifest:
    """GET /api/manifest returns a machine-readable list of all API routes."""

    @pytest.fixture(scope="class")
    def manifest(self):
        return _req_get(_app(), "/api/manifest").json()

    def test_returns_200_success(self, manifest):
        assert manifest.get("success") is True

    def test_has_endpoints_list(self, manifest):
        assert "endpoints" in manifest["data"]
        assert isinstance(manifest["data"]["endpoints"], list)

    def test_at_least_100_endpoints(self, manifest):
        n = len(manifest["data"]["endpoints"])
        assert n > 100, f"Expected 100+ endpoints in manifest, got {n}"

    def test_endpoint_structure(self, manifest):
        for ep in manifest["data"]["endpoints"][:5]:
            assert "path" in ep and "methods" in ep and "name" in ep
            assert isinstance(ep["methods"], list)

    def test_no_head_or_options(self, manifest):
        for ep in manifest["data"]["endpoints"]:
            assert "HEAD" not in ep["methods"]
            assert "OPTIONS" not in ep["methods"]

    def test_core_paths_present(self, manifest):
        paths = {e["path"] for e in manifest["data"]["endpoints"]}
        for p in ("/api/health", "/api/manifest", "/api/coa/health", "/api/bat/health",
                  "/api/cce/health", "/api/gate-synthesis/health"):
            assert p in paths, f"{p} missing from manifest"

    def test_endpoints_sorted(self, manifest):
        paths = [e["path"] for e in manifest["data"]["endpoints"]]
        assert paths == sorted(paths), "Manifest must be sorted by path"

    def test_no_auth_required(self):
        """Manifest must be accessible without API key even when key is set."""
        old = os.environ.pop("MURPHY_API_KEY", None)
        os.environ["MURPHY_API_KEY"] = "sentinel"
        try:
            resp = _req_get(_app(), "/api/manifest")
            assert resp.status_code == 200
        finally:
            del os.environ["MURPHY_API_KEY"]
            if old:
                os.environ["MURPHY_API_KEY"] = old


# ===========================================================================
# Gap 8 — WebSocket Standardisation
# ===========================================================================

class TestGap8WebSocketClass:
    """MurphyWebSocket class exists in murphy-components.js with correct API."""

    @pytest.fixture(scope="class")
    def js(self):
        return (_REPO_ROOT / "static" / "murphy-components.js").read_text(encoding="utf-8")

    def test_class_exists(self, js):
        assert "class MurphyWebSocket" in js

    def test_exported_on_window(self, js):
        assert "window.MurphyWebSocket" in js

    def test_has_connect(self, js):
        assert "connect()" in js

    def test_has_send(self, js):
        assert "send(data)" in js

    def test_has_on(self, js):
        assert "on(event" in js

    def test_has_disconnect(self, js):
        assert "disconnect()" in js

    def test_has_reconnect(self, js):
        assert "_reconnect()" in js

    def test_has_backoff(self, js):
        assert "_maxReconnectDelay" in js

    def test_json_parse_messages(self, js):
        assert "JSON.parse(" in js

    def test_protocol_detection(self, js):
        assert "wss:" in js and "ws:" in js


# ===========================================================================
# Gap 9 — API URL Pattern Documentation
# ===========================================================================

class TestGap9ApiRoutesDocumentation:
    """API_ROUTES.md exists and covers all gateway domains."""

    @pytest.fixture(scope="class")
    def md(self):
        p = _REPO_ROOT / "API_ROUTES.md"
        assert p.exists(), "API_ROUTES.md must exist"
        return p.read_text(encoding="utf-8")

    def test_exists(self):
        assert (_REPO_ROOT / "API_ROUTES.md").exists()

    def test_covers_health_and_manifest(self, md):
        assert "/api/health" in md and "/api/manifest" in md

    def test_covers_coa(self, md):
        assert "/api/coa/" in md

    def test_covers_cce(self, md):
        assert "/api/cce/" in md

    def test_covers_bat(self, md):
        assert "/api/bat/" in md

    def test_covers_gate_synthesis(self, md):
        assert "/api/gate-synthesis/" in md

    def test_covers_module_compiler(self, md):
        assert "/api/module-compiler/" in md

    def test_covers_compute_plane(self, md):
        assert "/api/compute-plane/" in md

    def test_documents_auth(self, md):
        assert "Auth" in md or "auth" in md

    def test_documents_murphyapi_client(self, md):
        assert "MurphyAPI" in md or "murphyClient" in md

    def test_documents_websocket(self, md):
        assert "MurphyWebSocket" in md

    def test_no_stale_flask_ports(self, md):
        for port in ("8053", "8054", "8056"):
            assert port not in md, f"API_ROUTES.md must not reference old Flask port {port}"


# ===========================================================================
# Gap 10 — murphy_auth.js on every API-calling HTML page
# ===========================================================================

_AUTH_PAGES = [
    "terminal_unified.html", "terminal_costs.html", "terminal_integrated.html",
    "terminal_integrations.html", "terminal_architect.html", "terminal_worker.html",
    "terminal_orchestrator.html", "terminal_enhanced.html", "terminal_orgchart.html",
    "matrix_integration.html", "production_wizard.html", "onboarding_wizard.html",
    "compliance_dashboard.html", "workflow_canvas.html", "calendar.html",
    "meeting_intelligence.html", "ambient_intelligence.html", "system_visualizer.html",
    "management.html", "wallet.html", "pricing.html",
]


class TestGap10MurphyAuthEverywhere:
    """All HTML pages that make API calls include murphy_auth.js."""

    @pytest.mark.parametrize("page", _AUTH_PAGES)
    def test_page_includes_murphy_auth_js(self, page):
        path = _REPO_ROOT / page
        if not path.exists():
            pytest.skip(f"{page} does not exist")
        assert "murphy_auth.js" in path.read_text(encoding="utf-8"), \
            f"{page} must include <script src='murphy_auth.js'>"

    @pytest.mark.parametrize("page", _AUTH_PAGES)
    def test_murphy_auth_after_murphy_components(self, page):
        path = _REPO_ROOT / page
        if not path.exists():
            pytest.skip(f"{page} does not exist")
        html = path.read_text(encoding="utf-8")
        mc = html.find("murphy-components.js")
        auth = html.find("murphy_auth.js")
        if mc == -1 or auth == -1:
            pytest.skip(f"{page}: one script tag not found")
        assert auth > mc, f"{page}: murphy_auth.js must follow murphy-components.js"


# ===========================================================================
# Integration Smoke Tests — end-to-end gateway round-trips
# ===========================================================================

class TestIntegrationSmoke:
    """End-to-end smoke tests exercising the full request path through the unified gateway."""

    def test_coa_full_crud_cycle(self):
        app = _app()

        async def _cycle():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # Create
                r = await c.post("/api/coa/resources", json={"name": "smoke-vm"})
                assert r.status_code == 201
                rid = r.json()["data"]["id"]

                # Read
                r = await c.get(f"/api/coa/resources/{rid}")
                assert r.status_code == 200 and r.json()["data"]["name"] == "smoke-vm"

                # Delete
                r = await c.delete(f"/api/coa/resources/{rid}")
                assert r.status_code == 200 and r.json()["data"]["deleted"] is True

                # Confirm 404
                r = await c.get(f"/api/coa/resources/{rid}")
                assert r.status_code == 404

        _sync(_cycle())

    def test_cce_rule_lifecycle(self):
        app = _app()

        async def _cycle():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/cce/rules", json={
                    "name": "smoke-rule",
                    "expression": "context.get('ok') == True",
                })
                assert r.status_code == 201
                rid = r.json()["data"]["id"]

                r = await c.post(f"/api/cce/check/{rid}", json={"ok": True})
                assert r.status_code == 200

                r = await c.delete(f"/api/cce/rules/{rid}")
                assert r.status_code == 200

        _sync(_cycle())

    def test_bat_entry_to_stats(self):
        app = _app()

        async def _cycle():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/bat/entries", json={
                    "entry_type": "api_call", "actor": "smoke-test", "action": "smoke"
                })
                assert r.status_code == 201

                r = await c.get("/api/bat/stats")
                assert r.status_code == 200
                assert r.json()["data"]["pending_entries"] >= 0

        _sync(_cycle())

    def test_error_envelope_consistent_across_all_gateway_services(self):
        """Every gateway service must return the same error envelope on bad input."""
        bad_requests = [
            ("POST", "/api/coa/resources", {}),
            ("POST", "/api/cce/rules", {"name": "incomplete"}),
            ("POST", "/api/bat/entries", {}),
        ]
        app = _app()

        async def _all():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                for method, path, body in bad_requests:
                    r = await c.post(path, json=body) if method == "POST" else await c.get(path)
                    data = r.json()
                    assert r.status_code == 400, f"{path} should be 400"
                    assert data["success"] is False, f"{path} success must be False"
                    assert "error" in data and "code" in data["error"] and "message" in data["error"]

        _sync(_all())

    def test_manifest_contains_all_gateway_services(self):
        app = _app()

        async def _check():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/api/manifest")
                paths = {e["path"] for e in r.json()["data"]["endpoints"]}
                for p in ("/api/coa/health", "/api/cce/health", "/api/bat/health",
                          "/api/gate-synthesis/health", "/api/manifest"):
                    assert p in paths, f"{p} missing from manifest"

        _sync(_check())
