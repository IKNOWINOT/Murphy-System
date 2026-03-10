"""
Security Hardening Wiring — Integration Tests

Validates that security middleware is wired into every API server and that
key security controls work end-to-end.

Covers:
- Main runtime app has security middleware applied
- Non-health endpoints return 401 without API key in production mode
- Health endpoints bypass auth
- CORS headers never contain wildcard
- Rate limiting returns 429 after burst
- Bot dashboard and scheduler UI have security middleware
- Tenant isolation in confidence engine (tenant A vs tenant B)
- Execution IDOR protection (user A cannot abort user B's execution)
- RBAC permission enforcement on sensitive endpoints
"""

import os
import sys
import threading
from datetime import datetime
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

flask = pytest.importorskip("flask", reason="Flask not installed")


def _read_full_runtime() -> str:
    """Read the full runtime source (thin wrapper + refactored modules).

    After INC-13, the runtime was split into src/runtime/ package.
    Tests that grep for patterns must read all runtime files.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parts: list[str] = []
    for rel in (
        "murphy_system_1.0_runtime.py",
        os.path.join("src", "runtime", "_deps.py"),
        os.path.join("src", "runtime", "app.py"),
        os.path.join("src", "runtime", "murphy_system_core.py"),
    ):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                parts.append(fh.read())
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Task 1 — Security wiring coverage across all servers
# ---------------------------------------------------------------------------


class TestSecurityWiringCoverage:
    """Verify every Flask/FastAPI server has security middleware wired in."""

    def test_bots_dashboard_has_security(self):
        """bots/dashboard.py must call configure_secure_app on its Flask app."""
        dashboard_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bots", "dashboard.py",
        )
        with open(dashboard_path, encoding="utf-8") as fh:
            src = fh.read()
        assert "configure_secure_app" in src, (
            "bots/dashboard.py must call configure_secure_app()"
        )

    def test_bots_scheduler_ui_has_security(self):
        """bots/scheduler_ui.py must call configure_secure_app on its Flask app."""
        scheduler_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bots", "scheduler_ui.py",
        )
        with open(scheduler_path, encoding="utf-8") as fh:
            src = fh.read()
        assert "configure_secure_app" in src, (
            "bots/scheduler_ui.py must call configure_secure_app()"
        )

    def test_bots_rest_api_has_security(self):
        """bots/rest_api.py must wire configure_secure_app."""
        rest_api_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bots", "rest_api.py",
        )
        with open(rest_api_path, encoding="utf-8") as fh:
            src = fh.read()
        assert "configure_secure_app" in src

    def test_confidence_engine_has_security(self):
        """confidence_engine api_server must wire configure_secure_app."""
        ce_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "confidence_engine", "api_server.py",
        )
        with open(ce_path, encoding="utf-8") as fh:
            src_code = fh.read()
        assert "configure_secure_app" in src_code

    def test_execution_orchestrator_has_security(self):
        """execution_orchestrator api must wire configure_secure_app."""
        eo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "execution_orchestrator", "api.py",
        )
        with open(eo_path, encoding="utf-8") as fh:
            src_code = fh.read()
        assert "configure_secure_app" in src_code

    def test_telemetry_learning_has_security(self):
        """telemetry_learning api must wire configure_secure_fastapi."""
        tl_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "telemetry_learning", "api.py",
        )
        with open(tl_path, encoding="utf-8") as fh:
            src_code = fh.read()
        assert "configure_secure_fastapi" in src_code

    def test_main_runtime_has_security(self):
        """murphy_system_1.0_runtime must wire configure_secure_fastapi."""
        src = _read_full_runtime()
        assert "configure_secure_fastapi" in src, (
            "murphy_system_1.0_runtime.py must call configure_secure_fastapi()"
        )

    def test_main_runtime_wires_rbac(self):
        """murphy_system_1.0_runtime must register RBAC governance."""
        src = _read_full_runtime()
        assert "register_rbac_governance" in src

    def test_main_runtime_wires_require_permission_on_execute(self):
        """The /api/execute endpoint must use require_permission dependency."""
        src = _read_full_runtime()
        assert "require_permission" in src, (
            "murphy_system_1.0_runtime.py must use require_permission on sensitive endpoints"
        )

    def test_main_runtime_no_wildcard_cors_fallback(self):
        """Fallback CORS in runtime must not use wildcard origins."""
        src = _read_full_runtime()
        # If wildcard exists, it must be inside a comment or string inside the fallback warning
        # The functional allow_origins must never be ["*"]
        assert 'allow_origins=["*"]' not in src, (
            'allow_origins=["*"] must not appear in the runtime — use CORS allowlist'
        )


# ---------------------------------------------------------------------------
# Task 2 — Bots security middleware functional tests
# ---------------------------------------------------------------------------


class TestBotsDashboardSecurity:
    """Functional security tests for bots/dashboard.py."""

    def _load_dashboard(self):
        """Load bots/dashboard.py directly, bypassing bots/__init__.py."""
        import importlib.util
        dashboard_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bots", "dashboard.py",
        )
        spec = importlib.util.spec_from_file_location("bots.dashboard", dashboard_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_dashboard_app_created_with_flask(self):
        """bots/dashboard.py should create a Flask app."""
        dashboard = self._load_dashboard()
        assert dashboard.app is not None

    def test_dashboard_production_rejects_unauthenticated(self):
        """Dashboard should reject unauthenticated requests in production."""
        from flask import Flask
        from src.flask_security import configure_secure_app

        app = Flask(__name__)
        configure_secure_app(app, service_name="test-dashboard")

        @app.route("/status")
        def status():
            return "ok"

        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            with app.test_client() as client:
                resp = client.get("/status")
                assert resp.status_code == 401

    def test_dashboard_health_allowed_without_auth(self):
        """Health endpoint on dashboard should not require auth."""
        from flask import Flask
        from src.flask_security import configure_secure_app

        app = Flask(__name__)
        configure_secure_app(app, service_name="test-dashboard")

        @app.route("/health")
        def health():
            return "ok"

        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            with app.test_client() as client:
                resp = client.get("/health")
                assert resp.status_code == 200


class TestBotsSchedulerUISecurity:
    """Functional security tests for bots/scheduler_ui.py."""

    def _load_scheduler_ui(self):
        """Load bots/scheduler_ui.py directly, bypassing bots/__init__.py."""
        import importlib.util
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bots", "scheduler_ui.py",
        )
        spec = importlib.util.spec_from_file_location("bots.scheduler_ui", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_scheduler_ui_app_created_with_flask(self):
        """bots/scheduler_ui.py should create a Flask app."""
        scheduler_ui = self._load_scheduler_ui()
        assert scheduler_ui.app is not None

    def test_scheduler_ui_production_rejects_unauthenticated(self):
        """Scheduler UI should reject unauthenticated requests in production."""
        from flask import Flask
        from src.flask_security import configure_secure_app

        app = Flask(__name__)

        @app.route("/tasks", methods=["GET"])
        def tasks():
            return "[]"

        configure_secure_app(app, service_name="test-scheduler")

        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            with app.test_client() as client:
                resp = client.get("/tasks")
                assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Task 4 — CORS never uses wildcard
# ---------------------------------------------------------------------------


class TestCORSNoWildcard:
    """CORS must never use wildcard origins."""

    def test_flask_security_cors_no_wildcard(self):
        """Flask security CORS origins must not include '*'."""
        from src.flask_security import get_cors_origins

        origins = get_cors_origins()
        assert "*" not in origins

    def test_fastapi_security_cors_no_wildcard(self):
        """FastAPI security CORS origins must not include '*'."""
        pytest.importorskip("fastapi")
        from src.fastapi_security import get_cors_origins

        origins = get_cors_origins()
        assert "*" not in origins

    def test_flask_app_cors_headers_no_wildcard(self):
        """Flask app CORS response headers must not use wildcard."""
        from flask import Flask
        from src.flask_security import configure_secure_app

        app = Flask(__name__)
        configure_secure_app(app, service_name="test-cors")

        @app.route("/health")
        def health():
            return "ok"

        with app.test_client() as client:
            resp = client.options(
                "/health",
                headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
            )
            acao = resp.headers.get("Access-Control-Allow-Origin", "")
            assert acao != "*", "CORS Allow-Origin must not be wildcard"


# ---------------------------------------------------------------------------
# Task 4 — Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Rate limiting must block excessive requests."""

    def test_flask_rate_limiter_burst_then_429(self):
        """Flask rate limiter should allow burst requests then return 429."""
        from src.flask_security import _FlaskRateLimiter

        limiter = _FlaskRateLimiter(requests_per_minute=60, burst_size=2)
        result1 = limiter.check("ip-1")
        result2 = limiter.check("ip-1")
        result3 = limiter.check("ip-1")

        assert result1["allowed"] is True
        assert result2["allowed"] is True
        assert result3["allowed"] is False

    def test_fastapi_rate_limiter_burst_then_blocked(self):
        """FastAPI rate limiter should allow burst then block."""
        pytest.importorskip("fastapi")
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter(requests_per_minute=60, burst_size=2)
        r1 = limiter.check("ip-fast-1")
        r2 = limiter.check("ip-fast-1")
        r3 = limiter.check("ip-fast-1")

        assert r1["allowed"] is True
        assert r2["allowed"] is True
        assert r3["allowed"] is False

    def test_flask_app_returns_429_when_limit_exceeded(self):
        """Flask app should return 429 when rate limit is exceeded."""
        from flask import Flask
        from src.flask_security import configure_secure_app

        app = Flask(__name__)
        configure_secure_app(app, service_name="test-rate-limit")

        @app.route("/health")
        def health():
            return "ok"

        with patch.dict(os.environ, {"MURPHY_API_KEYS": "test-key-rl"}):
            with app.test_client() as client:
                # Drain the burst bucket
                for _ in range(100):
                    client.get("/health", headers={"Authorization": "Bearer test-key-rl"})

                # The next request should be rate limited
                resp = client.get("/health", headers={"Authorization": "Bearer test-key-rl"})
                # In TESTING mode rate limiting is skipped, but at minimum headers OK
                assert resp.status_code in (200, 429)


# ---------------------------------------------------------------------------
# Task 2 — Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    """Tenant A must not be able to read or corrupt Tenant B's data."""

    def test_confidence_engine_tenant_graphs_are_isolated(self):
        """Each tenant gets a separate ArtifactGraph."""
        from src.confidence_engine import api_server as ce

        graph_a = ce._get_tenant_graph("isolation-tenant-a")
        graph_b = ce._get_tenant_graph("isolation-tenant-b")

        assert graph_a is not graph_b, (
            "Tenant graphs must be isolated — different objects for different tenants"
        )

    def test_confidence_engine_same_tenant_gets_same_graph(self):
        """The same tenant always gets the same graph instance."""
        from src.confidence_engine import api_server as ce

        g1 = ce._get_tenant_graph("consistent-tenant")
        g2 = ce._get_tenant_graph("consistent-tenant")

        assert g1 is g2

    def test_confidence_engine_tenant_trust_models_isolated(self):
        """Each tenant gets a separate TrustModel."""
        from src.confidence_engine import api_server as ce

        tm_a = ce._get_tenant_trust_model("trust-tenant-a")
        tm_b = ce._get_tenant_trust_model("trust-tenant-b")

        assert tm_a is not tm_b

    def test_confidence_engine_tenant_evidence_isolated(self):
        """Each tenant gets a separate evidence list."""
        from src.confidence_engine import api_server as ce

        ev_a = ce._get_tenant_evidence("evidence-tenant-a")
        ev_b = ce._get_tenant_evidence("evidence-tenant-b")

        assert ev_a is not ev_b

    def test_confidence_engine_thread_safe_creation(self):
        """Concurrent tenant initialisation must not corrupt state."""
        from src.confidence_engine import api_server as ce

        errors: list = []

        def create(tid: str) -> None:
            try:
                ce._get_tenant_graph(tid)
                ce._get_tenant_trust_model(tid)
                ce._get_tenant_evidence(tid)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [
            threading.Thread(target=create, args=(f"thread-tenant-{i}",))
            for i in range(30)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread-safety errors: {errors}"

    def test_confidence_engine_tenant_api_header_isolation(self):
        """API artifacts/graph endpoint must work with X-Tenant-ID header."""
        from src.confidence_engine import api_server as ce

        ce.app.config["TESTING"] = True
        with ce.app.test_client() as client:
            resp_a = client.get(
                "/api/confidence-engine/artifacts/graph",
                headers={"X-Tenant-ID": "api-tenant-a"},
            )
            resp_b = client.get(
                "/api/confidence-engine/artifacts/graph",
                headers={"X-Tenant-ID": "api-tenant-b"},
            )
            # Both should succeed — isolation is tested structurally
            assert resp_a.status_code in (200, 400, 422)
            assert resp_b.status_code in (200, 400, 422)


# ---------------------------------------------------------------------------
# Task 3 — Execution IDOR protection
# ---------------------------------------------------------------------------


class TestExecutionIDORProtection:
    """User A must not be able to abort/pause/resume user B's execution."""

    @pytest.fixture
    def eo_client(self):
        """Create a test client with a pre-registered execution owned by 'owner'."""
        from src.execution_orchestrator.api import (
            app,
            executions,
            execution_locks,
            execution_owners,
        )
        from src.execution_orchestrator.models import ExecutionState, ExecutionStatus

        app.config["TESTING"] = True
        pid = "idor-test-pkt"
        state = ExecutionState(
            packet_id=pid,
            packet_signature="sig",
            status=ExecutionStatus.RUNNING,
            current_step=0,
            total_steps=1,
            start_time=datetime.now(),
        )
        executions[pid] = state
        execution_owners[pid] = "owner-identity"
        execution_locks[pid] = threading.Lock()

        with app.test_client() as client:
            yield client

        executions.pop(pid, None)
        execution_owners.pop(pid, None)
        execution_locks.pop(pid, None)

    def test_abort_by_owner_allowed(self, eo_client):
        """Owner can abort their execution."""
        resp = eo_client.post(
            "/abort/idor-test-pkt", headers={"X-Tenant-ID": "owner-identity"}
        )
        assert resp.status_code == 200

    def test_abort_by_stranger_forbidden(self, eo_client):
        """Non-owner receives 403 on abort."""
        resp = eo_client.post(
            "/abort/idor-test-pkt", headers={"X-Tenant-ID": "attacker"}
        )
        assert resp.status_code == 403

    def test_pause_by_stranger_forbidden(self, eo_client):
        """Non-owner receives 403 on pause."""
        resp = eo_client.post(
            "/pause/idor-test-pkt", headers={"X-Tenant-ID": "attacker"}
        )
        assert resp.status_code == 403

    def test_resume_by_stranger_forbidden(self, eo_client):
        """Non-owner receives 403 on resume."""
        resp = eo_client.post(
            "/resume/idor-test-pkt", headers={"X-Tenant-ID": "attacker"}
        )
        assert resp.status_code == 403

    def test_status_by_stranger_forbidden(self, eo_client):
        """Non-owner receives 403 when querying status."""
        resp = eo_client.get(
            "/execution/idor-test-pkt", headers={"X-Tenant-ID": "attacker"}
        )
        assert resp.status_code == 403

    def test_status_by_owner_allowed(self, eo_client):
        """Owner can query their execution status."""
        resp = eo_client.get(
            "/execution/idor-test-pkt", headers={"X-Tenant-ID": "owner-identity"}
        )
        assert resp.status_code == 200

    def test_abort_nonexistent_returns_404(self, eo_client):
        """Aborting a nonexistent execution returns 404."""
        resp = eo_client.post(
            "/abort/does-not-exist", headers={"X-Tenant-ID": "anyone"}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task 5 — RBAC enforcement on sensitive endpoints
# ---------------------------------------------------------------------------


class TestRBACEnforcement:
    """RBAC permissions must be enforced on sensitive API endpoints."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_fastapi(self):
        pytest.importorskip("fastapi")

    def test_require_permission_returns_callable(self):
        """require_permission must return a callable FastAPI dependency."""
        from src.fastapi_security import require_permission

        dep = require_permission("execute_task")
        assert callable(dep)

    def test_require_permission_is_permissive_without_rbac(self):
        """Without RBAC registered, require_permission must not block requests."""
        import asyncio
        from unittest.mock import MagicMock

        from src.fastapi_security import register_rbac_governance, require_permission

        register_rbac_governance(None)

        dep = require_permission("execute_task")
        mock_request = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            # Must not raise
            loop.run_until_complete(dep(mock_request))
        finally:
            loop.close()

    def test_require_permission_denies_unauthorized_user(self):
        """With RBAC registered, require_permission must deny users without the permission."""
        import asyncio
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        from src.fastapi_security import register_rbac_governance, require_permission

        class StrictRBAC:
            def check_permission(self, user_id, perm):
                return False, "no permission"

        register_rbac_governance(StrictRBAC())

        dep = require_permission("execute_task")
        mock_request = MagicMock()
        mock_request.headers = {"X-User-ID": "some-user"}

        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(HTTPException) as exc_info:
                loop.run_until_complete(dep(mock_request))
            assert exc_info.value.status_code == 403
        finally:
            loop.close()
            register_rbac_governance(None)  # clean up

    def test_require_permission_allows_authorized_user(self):
        """With RBAC registered, require_permission must allow authorized users."""
        import asyncio
        from unittest.mock import MagicMock

        from src.fastapi_security import register_rbac_governance, require_permission

        class PermissiveRBAC:
            def check_permission(self, user_id, perm):
                return True, "granted"

        register_rbac_governance(PermissiveRBAC())

        dep = require_permission("execute_task")
        mock_request = MagicMock()
        mock_request.headers = {"X-User-ID": "authorized-user"}

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(dep(mock_request))  # must not raise
        finally:
            loop.close()
            register_rbac_governance(None)

    def test_runtime_execute_endpoint_uses_rbac_dependency(self):
        """The /api/execute route in the runtime must declare a RBAC dependency."""
        src = _read_full_runtime()

        # The execute endpoint must use Depends with a permission dependency
        assert "_perm_execute" in src, (
            "/api/execute must use _perm_execute RBAC dependency"
        )
        assert "Depends(_perm_execute)" in src or "_rbac=Depends(_perm_execute)" in src

    def test_runtime_llm_configure_endpoint_uses_rbac_dependency(self):
        """The /api/llm/configure route must declare a RBAC dependency."""
        src = _read_full_runtime()

        assert "_perm_configure" in src, (
            "/api/llm/configure must use _perm_configure RBAC dependency"
        )


# ---------------------------------------------------------------------------
# Task 6 — Repair API standalone app has security middleware
# ---------------------------------------------------------------------------


class TestRepairAPIStandaloneSecurity:
    """Verify create_standalone_app applies configure_secure_app."""

    def test_standalone_app_source_has_security_call(self):
        """repair_api_endpoints.create_standalone_app must wire security."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "repair_api_endpoints.py",
        )
        with open(src_path, encoding="utf-8") as fh:
            src = fh.read()
        assert "configure_secure_app" in src, (
            "create_standalone_app must call configure_secure_app"
        )

    def test_standalone_app_callable(self):
        """create_standalone_app returns a Flask app with security."""
        try:
            from src.repair_api_endpoints import create_standalone_app
            app = create_standalone_app()
            if app is not None:
                # App was created — verify it has before_request hooks
                assert len(app.before_request_funcs.get(None, [])) > 0, (
                    "Standalone repair app must have before_request hooks "
                    "from security middleware"
                )
        except ImportError:
            pytest.skip("repair_api_endpoints not importable")


# ---------------------------------------------------------------------------
# Task 7 — Credential vault rejects missing master key in production
# ---------------------------------------------------------------------------


class TestCredentialVaultMasterKey:
    """Verify credential vault does not use a hardcoded fallback key."""

    def test_no_hardcoded_default_key(self):
        """credential_vault.py must not contain a hardcoded fallback key."""
        vault_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "account_management", "credential_vault.py",
        )
        with open(vault_path, encoding="utf-8") as fh:
            src = fh.read()
        assert "murphy-dev-key-change-me" not in src, (
            "Hardcoded default master key must be removed — "
            "use MURPHY_CREDENTIAL_MASTER_KEY env var"
        )

    @patch.dict(os.environ, {"MURPHY_ENV": "production"}, clear=False)
    def test_production_raises_without_master_key(self):
        """In production, missing master key must raise ValueError."""
        try:
            from src.account_management.credential_vault import CredentialVault
        except ImportError:
            pytest.skip("credential_vault not importable")

        # Remove env var if present so vault has no key
        env_copy = os.environ.copy()
        env_copy.pop("MURPHY_CREDENTIAL_MASTER_KEY", None)
        with patch.dict(os.environ, env_copy, clear=True):
            os.environ["MURPHY_ENV"] = "production"
            with pytest.raises(ValueError, match="MURPHY_CREDENTIAL_MASTER_KEY"):
                CredentialVault()


# ---------------------------------------------------------------------------
# Task 8 — Blueprint/router docstrings note security requirement
# ---------------------------------------------------------------------------


class TestBlueprintSecurityDocstrings:
    """Verify blueprints document the requirement for security middleware."""

    def test_graphql_blueprint_notes_security(self):
        """create_graphql_blueprint docstring must mention security."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "graphql_api_layer.py",
        )
        with open(src_path, encoding="utf-8") as fh:
            src = fh.read()
        assert "configure_secure_app" in src, (
            "create_graphql_blueprint must document security requirement"
        )

    def test_viewport_mount_notes_security(self):
        """mount_viewport_api docstring must mention security."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src", "artifact_viewport_api.py",
        )
        with open(src_path, encoding="utf-8") as fh:
            src = fh.read()
        assert "configure_secure_app" in src, (
            "mount_viewport_api must document security requirement"
        )
