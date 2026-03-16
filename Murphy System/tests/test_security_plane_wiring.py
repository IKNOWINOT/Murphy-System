"""
Unit tests for Security Plane ASGI middleware wiring.

Validates that:
- RBACMiddleware, RiskClassificationMiddleware, and DLPScannerMiddleware are
  registered on the FastAPI app by configure_secure_fastapi().
- Each middleware layer intercepts the correct routes and enforces fail-closed.
- Public / health endpoints bypass all checks.
- The correct middleware execution order is used.
"""

import os
import pytest
import json
from unittest.mock import MagicMock, patch

pytest.importorskip("fastapi", reason="FastAPI not installed")
pytest.importorskip("httpx", reason="httpx not installed")

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(configure: bool = True) -> FastAPI:
    """Create a minimal FastAPI app, optionally applying security hardening."""
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/docs_stub")
    def docs_stub():
        return {"docs": True}

    @app.get("/api/data")
    def api_data():
        return {"data": "value"}

    @app.post("/api/execute")
    def api_execute():
        return {"result": "executed"}

    @app.delete("/api/admin/delete")
    def api_admin_delete():
        return {"deleted": True}

    if configure:
        # Run in test mode so auth is skipped (rate limit + auth layer stays permissive)
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            from src.fastapi_security import configure_secure_fastapi
            configure_secure_fastapi(app, service_name="test-security")

    return app


# ---------------------------------------------------------------------------
# Test: middleware is wired by configure_secure_fastapi
# ---------------------------------------------------------------------------

class TestMiddlewareWiring:
    """Security Plane middleware is registered by configure_secure_fastapi."""

    def test_configure_secure_fastapi_wires_security_middleware(self):
        """configure_secure_fastapi registers SecurityMiddleware."""
        from src.fastapi_security import SecurityMiddleware
        app = _make_app(configure=True)
        mw_types = [type(m.cls if hasattr(m, "cls") else m) for m in app.user_middleware]
        mw_names = [
            (m.cls.__name__ if hasattr(m, "cls") else type(m).__name__)
            for m in app.user_middleware
        ]
        assert "SecurityMiddleware" in mw_names, (
            f"SecurityMiddleware not found in middleware stack: {mw_names}"
        )

    def test_configure_secure_fastapi_wires_rbac_middleware(self):
        """configure_secure_fastapi registers RBACMiddleware."""
        app = _make_app(configure=True)
        mw_names = [
            (m.cls.__name__ if hasattr(m, "cls") else type(m).__name__)
            for m in app.user_middleware
        ]
        assert "RBACMiddleware" in mw_names, (
            f"RBACMiddleware not found in middleware stack: {mw_names}"
        )

    def test_configure_secure_fastapi_wires_risk_middleware(self):
        """configure_secure_fastapi registers RiskClassificationMiddleware."""
        app = _make_app(configure=True)
        mw_names = [
            (m.cls.__name__ if hasattr(m, "cls") else type(m).__name__)
            for m in app.user_middleware
        ]
        assert "RiskClassificationMiddleware" in mw_names, (
            f"RiskClassificationMiddleware not found in middleware stack: {mw_names}"
        )

    def test_configure_secure_fastapi_wires_dlp_middleware(self):
        """configure_secure_fastapi registers DLPScannerMiddleware."""
        app = _make_app(configure=True)
        mw_names = [
            (m.cls.__name__ if hasattr(m, "cls") else type(m).__name__)
            for m in app.user_middleware
        ]
        assert "DLPScannerMiddleware" in mw_names, (
            f"DLPScannerMiddleware not found in middleware stack: {mw_names}"
        )

    def test_middleware_order_security_before_rbac(self):
        """SecurityMiddleware must appear after RBACMiddleware in the stack
        (SecurityMiddleware is outermost, so its index is higher in user_middleware list).
        """
        app = _make_app(configure=True)
        mw_names = [
            (m.cls.__name__ if hasattr(m, "cls") else type(m).__name__)
            for m in app.user_middleware
        ]
        # user_middleware is in reverse execution order in Starlette
        # (last-added middleware = first entry = outermost)
        if "SecurityMiddleware" in mw_names and "RBACMiddleware" in mw_names:
            sec_idx = mw_names.index("SecurityMiddleware")
            rbac_idx = mw_names.index("RBACMiddleware")
            # SecurityMiddleware should come before RBACMiddleware in the list
            # (i.e., lower index = outermost = first to receive request)
            assert sec_idx < rbac_idx, (
                f"SecurityMiddleware (idx {sec_idx}) should be outermost "
                f"(before RBACMiddleware idx {rbac_idx})"
            )


# ---------------------------------------------------------------------------
# Test: health endpoints bypass all checks
# ---------------------------------------------------------------------------

class TestPublicEndpointExemptions:
    """Health and docs endpoints must bypass security-plane checks."""

    def test_health_endpoint_allowed_without_auth(self):
        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_api_data_accessible_in_test_mode(self):
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/data")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: RBACMiddleware
# ---------------------------------------------------------------------------

class TestRBACMiddleware:
    """RBACMiddleware enforces role-based access control."""

    def test_rbac_allows_request_in_test_mode_without_user_id(self):
        """In test mode, RBAC is permissive without X-User-ID."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/data")
        assert resp.status_code == 200

    def test_rbac_denies_in_production_without_rbac_instance_registered(self):
        """In production mode with no RBAC instance, access to /api/* is denied (fail-closed)."""
        from src.security_plane.middleware import RBACMiddleware
        # Temporarily clear RBAC instance
        original = RBACMiddleware._rbac_instance
        RBACMiddleware._rbac_instance = None
        try:
            with patch.dict(os.environ, {
                "MURPHY_ENV": "production",
                "MURPHY_API_KEYS": "prod-key",
            }):
                app = _make_app(configure=True)
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get(
                    "/api/data",
                    headers={"X-API-Key": "prod-key"},
                )
            # Should be denied with 503 (RBAC unavailable)
            assert resp.status_code in (401, 403, 503), (
                f"Expected 4xx/503 when RBAC unavailable in production, got {resp.status_code}"
            )
        finally:
            RBACMiddleware._rbac_instance = original

    def test_rbac_allows_health_in_production(self):
        """Health endpoint is exempt from RBAC even in production."""
        from src.security_plane.middleware import RBACMiddleware
        original = RBACMiddleware._rbac_instance
        RBACMiddleware._rbac_instance = None
        try:
            with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
                app = _make_app(configure=True)
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.get("/health")
            assert resp.status_code == 200
        finally:
            RBACMiddleware._rbac_instance = original

    def test_rbac_middleware_resolve_permission_known_path(self):
        """RBACMiddleware._resolve_permission returns a permission for known paths."""
        from src.security_plane.middleware import RBACMiddleware
        perm = RBACMiddleware._resolve_permission("/api/execute")
        assert perm == "execute_task"

    def test_rbac_middleware_resolve_permission_unknown_path(self):
        """RBACMiddleware._resolve_permission returns None for unmapped paths."""
        from src.security_plane.middleware import RBACMiddleware
        perm = RBACMiddleware._resolve_permission("/api/data")
        assert perm is None

    def test_rbac_middleware_with_mocked_rbac_allowed(self):
        """RBACMiddleware grants access when RBAC.check_permission returns True."""
        from src.security_plane.middleware import RBACMiddleware, register_rbac_middleware_governance

        mock_rbac = MagicMock()
        mock_rbac.check_permission.return_value = (True, "granted_by_role:admin")
        original = RBACMiddleware._rbac_instance
        register_rbac_middleware_governance(mock_rbac)

        try:
            with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
                app = _make_app(configure=True)
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.post(
                    "/api/execute",
                    headers={"X-User-ID": "user-123"},
                )
            # execute maps to execute_task — mock returns True → allowed
            assert resp.status_code == 200
        finally:
            RBACMiddleware._rbac_instance = original

    def test_rbac_middleware_with_mocked_rbac_denied(self):
        """RBACMiddleware denies access when RBAC.check_permission returns False."""
        from src.security_plane.middleware import RBACMiddleware, register_rbac_middleware_governance

        mock_rbac = MagicMock()
        mock_rbac.check_permission.return_value = (False, "no_role_grants_permission")
        original = RBACMiddleware._rbac_instance
        register_rbac_middleware_governance(mock_rbac)

        try:
            with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
                app = _make_app(configure=True)
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.post(
                    "/api/execute",
                    headers={"X-User-ID": "user-no-perms"},
                )
            assert resp.status_code == 403
        finally:
            RBACMiddleware._rbac_instance = original


# ---------------------------------------------------------------------------
# Test: RiskClassificationMiddleware
# ---------------------------------------------------------------------------

class TestRiskClassificationMiddleware:
    """RiskClassificationMiddleware classifies request risk levels correctly."""

    def test_risk_middleware_classifies_get_as_low(self):
        """GET /api/data should be classified as low risk."""
        from src.security_plane.middleware import RiskClassificationMiddleware

        mw = RiskClassificationMiddleware.__new__(RiskClassificationMiddleware)
        req = MagicMock()
        req.url.path = "/api/data"
        req.method = "GET"
        req.headers = {}

        risk = mw._classify_risk(req)
        assert risk == RiskClassificationMiddleware.LOW

    def test_risk_middleware_classifies_post_as_medium(self):
        """POST /api/data should be classified as medium risk."""
        from src.security_plane.middleware import RiskClassificationMiddleware

        mw = RiskClassificationMiddleware.__new__(RiskClassificationMiddleware)
        req = MagicMock()
        req.url.path = "/api/data"
        req.method = "POST"
        req.headers = {}

        risk = mw._classify_risk(req)
        assert risk == RiskClassificationMiddleware.MEDIUM

    def test_risk_middleware_classifies_execute_as_high(self):
        """POST /api/execute should be classified as high risk."""
        from src.security_plane.middleware import RiskClassificationMiddleware

        mw = RiskClassificationMiddleware.__new__(RiskClassificationMiddleware)
        req = MagicMock()
        req.url.path = "/api/execute"
        req.method = "POST"
        req.headers = {}

        risk = mw._classify_risk(req)
        assert risk == RiskClassificationMiddleware.HIGH

    def test_risk_middleware_classifies_delete_as_high(self):
        """DELETE requests should be classified as high risk."""
        from src.security_plane.middleware import RiskClassificationMiddleware

        mw = RiskClassificationMiddleware.__new__(RiskClassificationMiddleware)
        req = MagicMock()
        req.url.path = "/api/data"
        req.method = "DELETE"
        req.headers = {}

        risk = mw._classify_risk(req)
        assert risk == RiskClassificationMiddleware.HIGH

    def test_risk_middleware_classifies_admin_delete_as_critical(self):
        """DELETE /api/admin/delete should be classified as critical risk."""
        from src.security_plane.middleware import RiskClassificationMiddleware

        mw = RiskClassificationMiddleware.__new__(RiskClassificationMiddleware)
        req = MagicMock()
        req.url.path = "/api/admin/delete"
        req.method = "DELETE"
        req.headers = {}

        risk = mw._classify_risk(req)
        assert risk == RiskClassificationMiddleware.CRITICAL

    def test_risk_middleware_blocks_critical_requests(self):
        """Critical risk requests must be blocked with 403."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.delete("/api/admin/delete")
        assert resp.status_code == 403
        body = resp.json()
        assert "critical" in body.get("error", "").lower()

    def test_risk_middleware_sets_risk_level_in_state(self):
        """RiskClassificationMiddleware stores risk level in request.state.risk_level."""
        risk_captured = {}

        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = _make_app(configure=False)
            from src.security_plane.middleware import RiskClassificationMiddleware
            from fastapi import Request as _FRequest
            app.add_middleware(RiskClassificationMiddleware)

            @app.get("/api/probe")
            def probe(request: _FRequest):
                risk_captured["level"] = getattr(request.state, "risk_level", None)
                return {"ok": True}

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/probe")

        assert resp.status_code == 200
        assert risk_captured.get("level") == "low"

    def test_risk_middleware_exempts_health_endpoint(self):
        """Health endpoint is exempt from risk classification."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test: DLPScannerMiddleware
# ---------------------------------------------------------------------------

class TestDLPScannerMiddleware:
    """DLPScannerMiddleware scans request/response bodies for sensitive data."""

    def test_dlp_allows_clean_request(self):
        """Requests without sensitive data should pass through."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/data")
        assert resp.status_code == 200

    def test_dlp_allows_health_endpoint(self):
        """Health endpoint is exempt from DLP scanning."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_dlp_scanner_classifies_clean_text_as_public(self):
        """DLPScannerMiddleware classifies non-sensitive request body as PUBLIC."""
        from src.security_plane.middleware import DLPScannerMiddleware, SecurityMiddlewareConfig

        config = SecurityMiddlewareConfig(
            require_authentication=False,
            require_encryption=False,
            enable_audit_logging=False,
            enable_timing_normalization=False,
            enable_dlp=True,
            block_sensitive_data=True,
            enable_anti_surveillance=False,
        )
        dlp_mw = object.__new__(DLPScannerMiddleware)
        from src.security_plane.middleware import DLPMiddleware
        dlp_mw._dlp_config = config
        dlp_mw._dlp = DLPMiddleware(config)

        from src.security_plane.middleware import SecurityContext
        from datetime import datetime, timezone
        ctx = SecurityContext(request_id="test", timestamp=datetime.now(timezone.utc))
        dlp_mw._dlp.classify_data({"body": "Hello world, this is a clean request"}, ctx)
        # Non-sensitive data should NOT set sensitive flag
        assert ctx.sensitive_data_detected is False


# ---------------------------------------------------------------------------
# Test: fail-closed behavior
# ---------------------------------------------------------------------------

class TestFailClosedEnforcement:
    """Security plane middleware must deny requests when checks error."""

    def test_rbac_middleware_fail_closed_on_exception(self):
        """RBACMiddleware must return 403 if RBAC check raises an unexpected exception."""
        from src.security_plane.middleware import RBACMiddleware, register_rbac_middleware_governance

        mock_rbac = MagicMock()
        mock_rbac.check_permission.side_effect = RuntimeError("unexpected DB error")
        original = RBACMiddleware._rbac_instance
        register_rbac_middleware_governance(mock_rbac)

        try:
            with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
                app = _make_app(configure=True)
                client = TestClient(app, raise_server_exceptions=False)
                resp = client.post(
                    "/api/execute",
                    headers={"X-User-ID": "user-error"},
                )
            assert resp.status_code == 403
        finally:
            RBACMiddleware._rbac_instance = original

    def test_risk_middleware_fail_closed_on_exception(self):
        """RiskClassificationMiddleware must return 500 if classification raises."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = FastAPI()

            from src.security_plane.middleware import RiskClassificationMiddleware

            class _BrokenRiskMW(RiskClassificationMiddleware):
                def _classify_risk(self, request):
                    raise RuntimeError("forced classification error")

            app.add_middleware(_BrokenRiskMW)

            @app.get("/api/data")
            def data():
                return {"data": "value"}

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/data")
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Test: register_rbac_governance syncs RBAC instance to middleware
# ---------------------------------------------------------------------------

class TestRBACRegistration:
    """register_rbac_governance propagates to both the Depends layer and the ASGI middleware."""

    def test_register_rbac_governance_syncs_to_middleware(self):
        """Calling register_rbac_governance also sets RBACMiddleware._rbac_instance."""
        from src.fastapi_security import register_rbac_governance
        from src.security_plane.middleware import RBACMiddleware

        mock_rbac = MagicMock()
        register_rbac_governance(mock_rbac)
        assert RBACMiddleware._rbac_instance is mock_rbac

    def test_register_rbac_middleware_governance_standalone(self):
        """register_rbac_middleware_governance sets the RBAC instance on the middleware."""
        from src.security_plane.middleware import RBACMiddleware, register_rbac_middleware_governance

        mock_rbac = MagicMock()
        register_rbac_middleware_governance(mock_rbac)
        assert RBACMiddleware._rbac_instance is mock_rbac


# ---------------------------------------------------------------------------
# Test: configure_secure_fastapi docstring updated
# ---------------------------------------------------------------------------

class TestConfigureSecureDocstring:
    """configure_secure_fastapi docstring must mention all new middleware layers."""

    def test_docstring_mentions_rbac(self):
        from src.fastapi_security import configure_secure_fastapi
        doc = configure_secure_fastapi.__doc__ or ""
        assert "RBAC" in doc or "rbac" in doc.lower()

    def test_docstring_mentions_risk(self):
        from src.fastapi_security import configure_secure_fastapi
        doc = configure_secure_fastapi.__doc__ or ""
        assert "risk" in doc.lower()

    def test_docstring_mentions_dlp(self):
        from src.fastapi_security import configure_secure_fastapi
        doc = configure_secure_fastapi.__doc__ or ""
        assert "DLP" in doc or "dlp" in doc.lower()

    def test_docstring_mentions_fail_closed(self):
        from src.fastapi_security import configure_secure_fastapi
        doc = configure_secure_fastapi.__doc__ or ""
        assert "fail-closed" in doc.lower() or "fail closed" in doc.lower()

    def test_docstring_mentions_per_user_rate_limit(self):
        from src.fastapi_security import configure_secure_fastapi
        doc = configure_secure_fastapi.__doc__ or ""
        assert "per-user" in doc.lower() or "per user" in doc.lower()


# ---------------------------------------------------------------------------
# Test: PerUserRateLimitMiddleware
# ---------------------------------------------------------------------------

class TestPerUserRateLimitMiddleware:
    """PerUserRateLimitMiddleware enforces per-user and per-endpoint-tier rate limits."""

    def test_per_user_rate_limit_middleware_registered(self):
        """configure_secure_fastapi registers PerUserRateLimitMiddleware."""
        app = _make_app(configure=True)
        mw_names = [
            (m.cls.__name__ if hasattr(m, "cls") else type(m).__name__)
            for m in app.user_middleware
        ]
        assert "PerUserRateLimitMiddleware" in mw_names, (
            f"PerUserRateLimitMiddleware not found in middleware stack: {mw_names}"
        )

    def test_per_user_rate_limit_middleware_wired_before_rbac(self):
        """PerUserRateLimitMiddleware must be outermost of the Security Plane layers
        (i.e., lower index than RBACMiddleware in user_middleware list).
        """
        app = _make_app(configure=True)
        mw_names = [
            (m.cls.__name__ if hasattr(m, "cls") else type(m).__name__)
            for m in app.user_middleware
        ]
        if "PerUserRateLimitMiddleware" in mw_names and "RBACMiddleware" in mw_names:
            per_user_idx = mw_names.index("PerUserRateLimitMiddleware")
            rbac_idx = mw_names.index("RBACMiddleware")
            assert per_user_idx < rbac_idx, (
                f"PerUserRateLimitMiddleware (idx {per_user_idx}) should be outermost "
                f"(before RBACMiddleware idx {rbac_idx})"
            )

    def test_per_user_allows_requests_within_limit(self):
        """Requests within the rate limit are allowed."""
        with patch.dict(os.environ, {
            "MURPHY_ENV": "test",
            "MURPHY_USER_RATE_LIMIT_BURST": "5",
            "MURPHY_USER_RATE_LIMIT_RPM": "60",
        }):
            app = _make_app(configure=True)
            client = TestClient(app, raise_server_exceptions=False)
            for _ in range(3):
                resp = client.get("/api/data", headers={"X-User-ID": "user-ok"})
                assert resp.status_code == 200

    def test_per_user_blocks_after_burst_exhausted(self):
        """Requests beyond the burst budget are blocked with 429."""
        with patch.dict(os.environ, {
            "MURPHY_ENV": "test",
            "MURPHY_USER_RATE_LIMIT_RPM": "60",
            "MURPHY_USER_RATE_LIMIT_BURST": "2",
        }):
            from src.security_plane.middleware import PerUserRateLimitMiddleware
            app = FastAPI()
            app.add_middleware(PerUserRateLimitMiddleware)

            @app.get("/api/data")
            def data():
                return {"data": "value"}

            client = TestClient(app, raise_server_exceptions=False)
            r1 = client.get("/api/data", headers={"X-User-ID": "user-burst"})
            r2 = client.get("/api/data", headers={"X-User-ID": "user-burst"})
            r3 = client.get("/api/data", headers={"X-User-ID": "user-burst"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429

    def test_per_user_different_users_have_independent_buckets(self):
        """Different user IDs have independent token buckets."""
        with patch.dict(os.environ, {
            "MURPHY_ENV": "test",
            "MURPHY_USER_RATE_LIMIT_RPM": "60",
            "MURPHY_USER_RATE_LIMIT_BURST": "1",
        }):
            from src.security_plane.middleware import PerUserRateLimitMiddleware
            app = FastAPI()
            app.add_middleware(PerUserRateLimitMiddleware)

            @app.get("/api/data")
            def data():
                return {"data": "value"}

            client = TestClient(app, raise_server_exceptions=False)
            # User A uses up their budget
            client.get("/api/data", headers={"X-User-ID": "user-a"})
            r_a = client.get("/api/data", headers={"X-User-ID": "user-a"})
            # User B should still be allowed
            r_b = client.get("/api/data", headers={"X-User-ID": "user-b"})

        assert r_a.status_code == 429
        assert r_b.status_code == 200

    def test_endpoint_tier_limits_execute_endpoint(self):
        """The /api/execute endpoint tier has its own tighter budget."""
        with patch.dict(os.environ, {
            "MURPHY_ENV": "test",
            "MURPHY_EXEC_RATE_LIMIT_RPM": "10",
            "MURPHY_EXEC_RATE_LIMIT_BURST": "1",
            "MURPHY_USER_RATE_LIMIT_BURST": "100",  # global is generous
        }):
            from src.security_plane.middleware import PerUserRateLimitMiddleware
            app = FastAPI()
            app.add_middleware(PerUserRateLimitMiddleware)

            @app.post("/api/execute")
            def execute():
                return {"result": "ok"}

            client = TestClient(app, raise_server_exceptions=False)
            r1 = client.post("/api/execute", headers={"X-User-ID": "exec-user"})
            r2 = client.post("/api/execute", headers={"X-User-ID": "exec-user"})

        assert r1.status_code == 200
        assert r2.status_code == 429  # tier limit exhausted

    def test_per_user_health_endpoint_exempt(self):
        """Health endpoint bypasses per-user rate limiting."""
        with patch.dict(os.environ, {
            "MURPHY_ENV": "test",
            "MURPHY_USER_RATE_LIMIT_BURST": "0",  # zero budget
            "MURPHY_USER_RATE_LIMIT_RPM": "1",
        }):
            from src.security_plane.middleware import PerUserRateLimitMiddleware
            app = FastAPI()
            app.add_middleware(PerUserRateLimitMiddleware)

            @app.get("/health")
            def health():
                return {"status": "ok"}

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
        assert resp.status_code == 200

    def test_per_user_anonymous_bucket_for_missing_user_id(self):
        """Requests without X-User-ID are grouped into the 'anonymous' bucket."""
        with patch.dict(os.environ, {
            "MURPHY_ENV": "test",
            "MURPHY_USER_RATE_LIMIT_RPM": "60",
            "MURPHY_USER_RATE_LIMIT_BURST": "2",
        }):
            from src.security_plane.middleware import PerUserRateLimitMiddleware
            app = FastAPI()
            app.add_middleware(PerUserRateLimitMiddleware)

            @app.get("/api/data")
            def data():
                return {"data": "value"}

            client = TestClient(app, raise_server_exceptions=False)
            r1 = client.get("/api/data")  # no X-User-ID
            r2 = client.get("/api/data")
            r3 = client.get("/api/data")

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429

    def test_per_user_rate_limit_token_bucket_check(self):
        """PerUserRateLimitMiddleware._check allows up to burst then blocks."""
        from src.security_plane.middleware import PerUserRateLimitMiddleware

        mw = object.__new__(PerUserRateLimitMiddleware)
        mw._global_rpm = 60
        mw._global_burst = 3
        mw._endpoint_tiers = []
        mw._buckets = {}
        import time as _t
        mw._last_cleanup = _t.monotonic()

        r1 = mw._check("user-x:global", rpm=60, burst=3)
        r2 = mw._check("user-x:global", rpm=60, burst=3)
        r3 = mw._check("user-x:global", rpm=60, burst=3)
        r4 = mw._check("user-x:global", rpm=60, burst=3)

        assert r1["allowed"] is True
        assert r2["allowed"] is True
        assert r3["allowed"] is True
        assert r4["allowed"] is False
        assert "retry_after_seconds" in r4

    def test_per_user_fail_closed_on_exception(self):
        """PerUserRateLimitMiddleware must return 429 if an internal error occurs."""
        with patch.dict(os.environ, {"MURPHY_ENV": "test"}):
            app = FastAPI()
            from src.security_plane.middleware import PerUserRateLimitMiddleware

            class _BrokenPerUserMW(PerUserRateLimitMiddleware):
                def _check(self, key, rpm, burst):
                    raise RuntimeError("forced bucket error")

            app.add_middleware(_BrokenPerUserMW)

            @app.get("/api/data")
            def data():
                return {"data": "value"}

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/data", headers={"X-User-ID": "broken-user"})
        assert resp.status_code == 429

    def test_retry_after_seconds_included_in_response(self):
        """429 responses include retry_after_seconds in the body."""
        with patch.dict(os.environ, {
            "MURPHY_ENV": "test",
            "MURPHY_USER_RATE_LIMIT_RPM": "60",
            "MURPHY_USER_RATE_LIMIT_BURST": "1",
        }):
            from src.security_plane.middleware import PerUserRateLimitMiddleware
            app = FastAPI()
            app.add_middleware(PerUserRateLimitMiddleware)

            @app.get("/api/data")
            def data():
                return {"data": "value"}

            client = TestClient(app, raise_server_exceptions=False)
            client.get("/api/data", headers={"X-User-ID": "retry-user"})
            resp = client.get("/api/data", headers={"X-User-ID": "retry-user"})

        assert resp.status_code == 429
        body = resp.json()
        assert "retry_after_seconds" in body
