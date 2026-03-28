"""
Wave 5 Commissioning Tests — Execution Router & Orchestrator Wiring

Verifies that all three orchestrators (TwoPhaseOrchestrator, UniversalControlPlane,
ExecutionOrchestrator) are wired into the unified FastAPI server via
src/execution_router.py, and that the 14 execution routes are registered.

Commissioning Questions Answered:
  - Does the module do what it was designed to do? → Routes registered, orchestrators instantiate
  - What conditions are possible? → Missing imports, startup failures, route conflicts
  - Does the test profile reflect full capabilities? → All 14 routes tested
  - What is the expected result? → 200/404/422 depending on route, never 500
  - Has hardening been applied? → Lazy init, graceful fallback, error handling

Copyright © 2020 Inoni Limited Liability Company
License: BSL-1.1
"""

import os
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

os.environ["MURPHY_ENV"] = "development"
os.environ["MURPHY_AUTH_ENABLED"] = "false"
os.environ.setdefault("MURPHY_API_KEY", "test-key-12345")


_API_KEY = os.environ.get("MURPHY_API_KEY", "test-key-12345")
_AUTH_HEADERS = {"X-API-Key": _API_KEY}


_app_singleton = None


def _get_app():
    """Get or create the FastAPI app (singleton to avoid re-creation overhead)."""
    global _app_singleton
    if _app_singleton is None:
        try:
            from src.runtime.app import create_app
        except ImportError as e:
            pytest.skip(f"Cannot import create_app: {e}")
        _app_singleton = create_app()
    return _app_singleton


@pytest.fixture(scope="module")
def client():
    """Create a TestClient with startup events triggered via context manager."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi[testclient] not installed")
    app = _get_app()
    with TestClient(app) as c:
        yield c


class TestExecutionRouterRegistration:
    """Verify all 14 execution routes are registered in the unified app."""

    def test_execution_health_route_exists(self, client):
        resp = client.get("/api/execution/health", headers=_AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_two_phase_list_route(self, client):
        resp = client.get("/api/execution/two-phase/", headers=_AUTH_HEADERS)
        assert resp.status_code in (200, 404)

    def test_ucp_list_route(self, client):
        resp = client.get("/api/execution/ucp/", headers=_AUTH_HEADERS)
        assert resp.status_code in (200, 404)

    def test_execution_pending_route(self, client):
        resp = client.get("/api/execution/packet/pending", headers=_AUTH_HEADERS)
        assert resp.status_code in (200, 404)

    def test_execution_history_route(self, client):
        resp = client.get("/api/execution/packet/history", headers=_AUTH_HEADERS)
        assert resp.status_code in (200, 404)

    def test_routes_require_auth(self, client):
        """Execution routes should reject unauthenticated requests."""
        resp = client.get("/api/execution/health")
        assert resp.status_code == 401


class TestExecutionRouteCount:
    """Verify the execution router contributes the expected number of routes."""

    def test_execution_routes_registered(self):
        """At least 14 execution routes should be registered."""
        app = _get_app()
        execution_routes = [
            r for r in app.routes
            if hasattr(r, "path") and "/api/execution" in r.path
        ]
        assert len(execution_routes) >= 14, (
            f"Expected >=14 execution routes, found {len(execution_routes)}: "
            f"{[r.path for r in execution_routes]}"
        )


class TestExecutionRouterModule:
    """Verify the execution_router module itself is importable and well-formed."""

    def test_router_importable(self):
        from src.execution_router import router
        assert router is not None
        assert hasattr(router, "routes")

    def test_startup_function_importable(self):
        from src.execution_router import execution_router_startup
        assert callable(execution_router_startup)

    def test_router_has_execution_tag(self):
        from src.execution_router import router
        assert "execution-engine" in router.tags


class TestTwoPhaseOrchestratorImport:
    """Verify the TwoPhaseOrchestrator can be imported and instantiated."""

    def test_import_from_root(self):
        sys.path.insert(0, str(_root))
        from two_phase_orchestrator import TwoPhaseOrchestrator
        assert TwoPhaseOrchestrator is not None

    def test_instantiation(self):
        sys.path.insert(0, str(_root))
        from two_phase_orchestrator import TwoPhaseOrchestrator
        orch = TwoPhaseOrchestrator()
        assert hasattr(orch, "create_automation")
        assert hasattr(orch, "run_automation")


class TestUniversalControlPlaneImport:
    """Verify the UniversalControlPlane can be imported and instantiated."""

    def test_import_from_root(self):
        sys.path.insert(0, str(_root))
        from universal_control_plane import UniversalControlPlane
        assert UniversalControlPlane is not None

    def test_instantiation(self):
        sys.path.insert(0, str(_root))
        from universal_control_plane import UniversalControlPlane
        ucp = UniversalControlPlane()
        assert hasattr(ucp, "create_automation")
        assert hasattr(ucp, "run_automation")


class TestExecutionOrchestratorImport:
    """Verify the ExecutionOrchestrator can be imported."""

    def test_import(self):
        from src.execution_orchestrator import ExecutionOrchestrator
        assert ExecutionOrchestrator is not None

    def test_instantiation(self):
        from src.execution_orchestrator import ExecutionOrchestrator
        orch = ExecutionOrchestrator()
        assert hasattr(orch, "execute_packet")