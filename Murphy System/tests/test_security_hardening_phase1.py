"""
Test Suite for Security Hardening Phase 1.2-1.5

Tests:
- Flask security (CORS, auth, rate limiting, health exemptions)
- FastAPI security middleware
- Confidence engine tenant isolation with thread safety
- Execution orchestrator IDOR protection (pause/resume/abort/status)
"""

import os
import pytest
import threading
from datetime import datetime
from unittest.mock import patch

flask = pytest.importorskip("flask", reason="Flask not installed — skipping Flask security tests")

from src.flask_security import (
    get_cors_origins,
    get_configured_api_keys,
    validate_api_key,
    _is_health_endpoint,
    configure_secure_app,
)


# ============================================================================
# FLASK SECURITY TESTS
# ============================================================================


class TestCORSOrigins:
    """Test CORS origin allowlist configuration"""

    def test_default_origins_are_localhost(self):
        """Default origins should be localhost only (dev mode)"""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MURPHY_CORS_ORIGINS", None)
            origins = get_cors_origins()
            assert all("localhost" in o for o in origins)
            assert "*" not in origins

    def test_custom_origins_from_env(self):
        """MURPHY_CORS_ORIGINS env var should override defaults"""
        with patch.dict(os.environ, {"MURPHY_CORS_ORIGINS": "https://example.com,https://app.example.com"}):
            origins = get_cors_origins()
            assert "https://example.com" in origins
            assert "https://app.example.com" in origins
            assert len(origins) == 2

    def test_no_wildcard_in_origins(self):
        """Wildcard '*' should never appear in origin list"""
        origins = get_cors_origins()
        assert "*" not in origins


class TestAPIKeyValidation:
    """Test API key authentication"""

    def test_no_keys_configured_dev_mode_allows(self):
        """In dev mode with no keys configured, requests should be allowed"""
        with patch.dict(os.environ, {"MURPHY_ENV": "development"}, clear=True):
            os.environ.pop("MURPHY_API_KEYS", None)
            assert validate_api_key("anything") is True

    def test_no_keys_configured_prod_mode_denies(self):
        """In production mode with no keys configured, requests should be denied"""
        with patch.dict(os.environ, {"MURPHY_ENV": "production"}, clear=True):
            os.environ.pop("MURPHY_API_KEYS", None)
            assert validate_api_key("anything") is False

    def test_valid_key_accepted(self):
        """Valid API key should be accepted"""
        with patch.dict(os.environ, {"MURPHY_API_KEYS": "key1,key2"}):
            assert validate_api_key("key1") is True
            assert validate_api_key("key2") is True

    def test_invalid_key_rejected(self):
        """Invalid API key should be rejected"""
        with patch.dict(os.environ, {"MURPHY_API_KEYS": "key1,key2"}):
            assert validate_api_key("wrong_key") is False


class TestHealthEndpointExemption:
    """Test health/readiness endpoint exemptions from auth"""

    def test_health_endpoint_exempt(self):
        assert _is_health_endpoint("/health") is True
        assert _is_health_endpoint("/api/health") is True
        assert _is_health_endpoint("/api/health/") is True

    def test_healthz_endpoint_exempt(self):
        assert _is_health_endpoint("/healthz") is True

    def test_ready_endpoint_exempt(self):
        assert _is_health_endpoint("/ready") is True

    def test_metrics_endpoint_exempt(self):
        assert _is_health_endpoint("/metrics") is True

    def test_non_health_endpoint_not_exempt(self):
        assert _is_health_endpoint("/api/data") is False
        assert _is_health_endpoint("/execute") is False


class TestFlaskSecurityIntegration:
    """Test configure_secure_app wires everything correctly"""

    def test_configure_secure_app_returns_app(self):
        """configure_secure_app should return the Flask app"""
        from flask import Flask
        app = Flask(__name__)
        result = configure_secure_app(app, service_name="test-service")
        assert result is app

    def test_production_mode_rejects_unauthenticated(self):
        """In production mode, unauthenticated requests should be rejected"""
        from flask import Flask
        app = Flask(__name__)
        configure_secure_app(app, service_name="test-service")

        @app.route('/api/test')
        def test_endpoint():
            return "ok"

        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            with app.test_client() as client:
                resp = client.get('/api/test')
                assert resp.status_code == 401

    def test_health_endpoint_allowed_without_auth(self):
        """Health endpoints should be accessible without authentication"""
        from flask import Flask
        app = Flask(__name__)
        configure_secure_app(app, service_name="test-service")

        @app.route('/health')
        def health():
            return "ok"

        with patch.dict(os.environ, {"MURPHY_ENV": "production"}):
            with app.test_client() as client:
                resp = client.get('/health')
                assert resp.status_code == 200

    def test_valid_api_key_accepted(self):
        """Valid API key should grant access"""
        from flask import Flask
        app = Flask(__name__)
        configure_secure_app(app, service_name="test-service")

        @app.route('/api/test')
        def test_endpoint():
            return "ok"

        with patch.dict(os.environ, {"MURPHY_API_KEYS": "test-key-123"}):
            with app.test_client() as client:
                resp = client.get('/api/test', headers={"Authorization": "Bearer test-key-123"})
                assert resp.status_code == 200

    def test_security_headers_present(self):
        """Security headers should be present on responses"""
        from flask import Flask
        app = Flask(__name__)
        configure_secure_app(app, service_name="test-service")

        @app.route('/health')
        def health():
            return "ok"

        with app.test_client() as client:
            resp = client.get('/health')
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "DENY"
            assert "Strict-Transport-Security" in resp.headers


# ============================================================================
# FASTAPI SECURITY TESTS
# ============================================================================


class TestFastAPISecurity:
    """Test FastAPI security middleware"""

    @pytest.fixture(autouse=True)
    def _skip_if_no_fastapi(self):
        pytest.importorskip("fastapi")

    def test_configure_secure_fastapi_returns_app(self):
        """configure_secure_fastapi should return the FastAPI app"""
        from fastapi import FastAPI
        from src.fastapi_security import configure_secure_fastapi

        app = FastAPI()
        result = configure_secure_fastapi(app, service_name="test-service")
        assert result is app

    def test_fastapi_health_endpoint_exempt(self):
        """FastAPI health endpoints should not require auth"""
        from src.fastapi_security import _is_health_endpoint

        assert _is_health_endpoint("/health") is True
        assert _is_health_endpoint("/api/health") is True
        assert _is_health_endpoint("/healthz") is True
        assert _is_health_endpoint("/ready") is True
        assert _is_health_endpoint("/metrics") is True
        assert _is_health_endpoint("/api/data") is False

    def test_fastapi_cors_no_wildcard(self):
        """FastAPI CORS should not use wildcard origins"""
        from src.fastapi_security import get_cors_origins

        origins = get_cors_origins()
        assert "*" not in origins

    def test_fastapi_rate_limiter(self):
        """FastAPI rate limiter should work"""
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter(requests_per_minute=60, burst_size=2)
        result1 = limiter.check("test-client")
        assert result1["allowed"] is True
        result2 = limiter.check("test-client")
        assert result2["allowed"] is True
        result3 = limiter.check("test-client")
        assert result3["allowed"] is False

    def test_register_rbac_governance(self):
        """register_rbac_governance should set the global RBAC instance"""
        from src.fastapi_security import register_rbac_governance, _rbac_instance

        class MockRBAC:
            pass

        register_rbac_governance(MockRBAC())
        from src.fastapi_security import _rbac_instance as after
        assert after is not None
        # Clean up
        register_rbac_governance(None)

    def test_require_permission_returns_callable(self):
        """require_permission should return a callable dependency"""
        from src.fastapi_security import require_permission, register_rbac_governance

        dep = require_permission("execute_task")
        assert callable(dep)

        # Without RBAC registered, the dependency should be permissive
        register_rbac_governance(None)

    def test_require_permission_permissive_without_rbac(self):
        """Without RBAC registered, permission check should pass"""
        import asyncio
        from unittest.mock import MagicMock
        from src.fastapi_security import require_permission, register_rbac_governance

        register_rbac_governance(None)  # ensure no RBAC

        dep = require_permission("execute_task")
        mock_request = MagicMock()
        # Should not raise
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(dep(mock_request))
        finally:
            loop.close()


# ============================================================================
# CONFIDENCE ENGINE TENANT ISOLATION TESTS
# ============================================================================


class TestConfidenceEngineTenantIsolation:
    """Test thread-safe tenant isolation in confidence engine"""

    def test_tenant_graph_isolation(self):
        """Different tenants should get separate graphs"""
        from flask import Flask
        app = Flask(__name__)

        with app.test_request_context(headers={"X-Tenant-ID": "tenant-a"}):
            from src.confidence_engine import api_server as ce
            graph_a = ce._get_tenant_graph("tenant-a")
            graph_b = ce._get_tenant_graph("tenant-b")
            assert graph_a is not graph_b

    def test_tenant_trust_model_isolation(self):
        """Different tenants should get separate trust models"""
        from flask import Flask
        app = Flask(__name__)

        with app.test_request_context():
            from src.confidence_engine import api_server as ce
            tm_a = ce._get_tenant_trust_model("tenant-x")
            tm_b = ce._get_tenant_trust_model("tenant-y")
            assert tm_a is not tm_b

    def test_same_tenant_gets_same_graph(self):
        """Same tenant should always get the same graph"""
        from flask import Flask
        app = Flask(__name__)

        with app.test_request_context():
            from src.confidence_engine import api_server as ce
            g1 = ce._get_tenant_graph("tenant-same")
            g2 = ce._get_tenant_graph("tenant-same")
            assert g1 is g2

    def test_thread_safety_of_tenant_creation(self):
        """Concurrent tenant graph creation should not raise errors"""
        from src.confidence_engine import api_server as ce

        errors = []

        def create_tenant(tid):
            try:
                ce._get_tenant_graph(tid)
                ce._get_tenant_trust_model(tid)
                ce._get_tenant_evidence(tid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_tenant, args=(f"t-{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ============================================================================
# EXECUTION ORCHESTRATOR IDOR TESTS
# ============================================================================


class TestExecutionOrchestratorIDOR:
    """Test IDOR protection on execution orchestrator endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client with a registered execution"""
        from src.execution_orchestrator.api import app, executions, execution_owners, execution_locks
        from src.execution_orchestrator.models import ExecutionState, ExecutionStatus

        app.config['TESTING'] = True

        # Register a test execution owned by 'owner-tenant'
        test_state = ExecutionState(
            packet_id="test-pkt-1",
            packet_signature="sig",
            status=ExecutionStatus.RUNNING,
            current_step=0,
            total_steps=3,
            start_time=datetime.now()
        )
        executions["test-pkt-1"] = test_state
        execution_owners["test-pkt-1"] = "owner-tenant"
        execution_locks["test-pkt-1"] = threading.Lock()

        with app.test_client() as c:
            yield c

        # Cleanup
        executions.pop("test-pkt-1", None)
        execution_owners.pop("test-pkt-1", None)
        execution_locks.pop("test-pkt-1", None)

    def test_abort_by_owner_succeeds(self, client):
        """Owner should be able to abort their own execution"""
        resp = client.post('/abort/test-pkt-1', headers={"X-Tenant-ID": "owner-tenant"})
        assert resp.status_code == 200

    def test_abort_by_non_owner_forbidden(self, client):
        """Non-owner should receive 403 when trying to abort"""
        resp = client.post('/abort/test-pkt-1', headers={"X-Tenant-ID": "other-tenant"})
        assert resp.status_code == 403

    def test_pause_by_owner_succeeds(self, client):
        """Owner should be able to pause their own execution"""
        resp = client.post('/pause/test-pkt-1', headers={"X-Tenant-ID": "owner-tenant"})
        assert resp.status_code == 200

    def test_pause_by_non_owner_forbidden(self, client):
        """Non-owner should receive 403 when trying to pause"""
        resp = client.post('/pause/test-pkt-1', headers={"X-Tenant-ID": "other-tenant"})
        assert resp.status_code == 403

    def test_resume_by_non_owner_forbidden(self, client):
        """Non-owner should receive 403 when trying to resume"""
        resp = client.post('/resume/test-pkt-1', headers={"X-Tenant-ID": "other-tenant"})
        assert resp.status_code == 403

    def test_get_status_by_non_owner_forbidden(self, client):
        """Non-owner should receive 403 when querying execution status"""
        resp = client.get('/execution/test-pkt-1', headers={"X-Tenant-ID": "other-tenant"})
        assert resp.status_code == 403

    def test_get_status_by_owner_succeeds(self, client):
        """Owner should be able to query their own execution status"""
        resp = client.get('/execution/test-pkt-1', headers={"X-Tenant-ID": "owner-tenant"})
        assert resp.status_code == 200

    def test_abort_nonexistent_returns_404(self, client):
        """Aborting a nonexistent execution should return 404"""
        resp = client.post('/abort/nonexistent', headers={"X-Tenant-ID": "owner-tenant"})
        assert resp.status_code == 404

    def test_pause_nonexistent_returns_404(self, client):
        """Pausing a nonexistent execution should return 404"""
        resp = client.post('/pause/nonexistent', headers={"X-Tenant-ID": "owner-tenant"})
        assert resp.status_code == 404
