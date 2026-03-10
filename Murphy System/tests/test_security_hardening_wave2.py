"""
Wave 2 Security Hardening Tests

Tests for:
- W2-01: Tenant isolation in confidence engine
- W2-02: Execution registry IDOR protection
- W2-03: Credential verifier real validation
- W2-04: Secure master key storage
- W2-05: Rate limiting wiring

Run: pytest tests/test_security_hardening_wave2.py -v
"""

import asyncio
import base64
import json
import os
import time
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

flask = pytest.importorskip("flask", reason="Flask not installed — skipping")


# ============================================================================
# W2-01: Tenant Isolation in Confidence Engine
# ============================================================================


class TestTenantIsolationConfidenceEngine:
    """Verify per-tenant graph isolation and TTL eviction."""

    @pytest.fixture(autouse=True)
    def ce_app(self):
        """Return the confidence engine Flask test client with a clean state."""
        from src.confidence_engine import api_server as ce
        ce.app.config["TESTING"] = True
        # Reset tenant state before each test
        with ce._tenant_lock:
            ce._tenant_graphs.clear()
            ce._tenant_trust_models.clear()
            ce._tenant_evidence.clear()
            ce._tenant_last_access.clear()
        with ce.app.test_client() as client:
            yield client, ce

    def test_tenant_isolation_separate_graphs(self, ce_app):
        """Tenant A's artifacts must not appear in Tenant B's graph."""
        client, ce = ce_app
        # Tenant A adds an artifact
        resp_add = client.post(
            "/api/confidence-engine/artifacts/add",
            json={
                "id": "artifact-tenant-a",
                "type": "hypothesis",
                "source": "human",
                "content": "Tenant A only content",
            },
            headers={"X-Tenant-ID": "tenant-a"},
        )
        assert resp_add.status_code == 200, resp_add.get_json()

        # Tenant B's graph should not contain Tenant A's artifact
        resp_graph_b = client.get(
            "/api/confidence-engine/artifacts/graph",
            headers={"X-Tenant-ID": "tenant-b"},
        )
        assert resp_graph_b.status_code == 200
        data_b = resp_graph_b.get_json()
        node_ids = list(data_b.get("graph", {}).get("nodes", {}).keys())
        assert "artifact-tenant-a" not in node_ids, (
            "Tenant B should not see Tenant A's artifact"
        )

    def test_tenant_isolation_no_auth_returns_401(self, ce_app):
        """Requests without X-Tenant-ID header must be rejected with 401."""
        client, _ce = ce_app
        resp = client.get("/api/confidence-engine/artifacts/graph")
        assert resp.status_code == 401

    def test_tenant_graph_ttl_eviction(self, ce_app):
        """A graph idle for >1 hour must be evicted by the cleanup function."""
        _client, ce = ce_app
        tenant_id = "evict-me-tenant"
        # Create graph entry
        with ce._tenant_lock:
            from src.confidence_engine.models import ArtifactGraph
            ce._tenant_graphs[tenant_id] = ArtifactGraph()
            # Backdate last access by 2 hours
            ce._tenant_last_access[tenant_id] = datetime.now(tz=timezone.utc) - timedelta(hours=2)

        evicted = ce.evict_idle_tenants()
        assert evicted >= 1, "Expected at least one eviction"
        assert tenant_id not in ce._tenant_graphs, (
            "Idle tenant graph must be evicted"
        )

    def test_active_tenant_not_evicted(self, ce_app):
        """A recently-accessed tenant graph must survive eviction."""
        _client, ce = ce_app
        tenant_id = "keep-me-tenant"
        with ce._tenant_lock:
            from src.confidence_engine.models import ArtifactGraph
            ce._tenant_graphs[tenant_id] = ArtifactGraph()
            ce._tenant_last_access[tenant_id] = datetime.now(tz=timezone.utc)

        ce.evict_idle_tenants()
        assert tenant_id in ce._tenant_graphs, (
            "Recently-accessed tenant must not be evicted"
        )


# ============================================================================
# W2-02: Execution Registry IDOR Protection
# ============================================================================


class TestExecutionIDOR:
    """Prevent users from aborting/querying other users' executions."""

    @pytest.fixture
    def eo_client(self):
        """Return execution orchestrator test client with a pre-registered execution."""
        from src.execution_orchestrator import api as eo
        from src.execution_orchestrator.models import ExecutionState, ExecutionStatus

        eo.app.config["TESTING"] = True
        packet_id = "idor-wave2-pkt"

        # Reset state
        eo.executions.pop(packet_id, None)
        eo.execution_owners.pop(packet_id, None)

        # Register a running execution owned by "owner-user"
        eo.executions[packet_id] = ExecutionState(
            packet_id=packet_id,
            packet_signature="sig",
            status=ExecutionStatus.RUNNING,
            current_step=0,
            total_steps=1,
            start_time=datetime.now(tz=timezone.utc),
        )
        eo.execution_owners[packet_id] = "owner-user"

        with eo.app.test_client() as client:
            yield client, packet_id

        # Cleanup
        eo.executions.pop(packet_id, None)
        eo.execution_owners.pop(packet_id, None)

    def test_idor_abort_own_execution(self, eo_client):
        """Owner can abort their own execution — 200 OK."""
        client, packet_id = eo_client
        resp = client.post(
            f"/abort/{packet_id}",
            headers={"X-Tenant-ID": "owner-user"},
        )
        assert resp.status_code == 200

    def test_idor_abort_other_user_execution(self, eo_client):
        """Non-owner must receive 403 when trying to abort another user's execution."""
        client, packet_id = eo_client
        resp = client.post(
            f"/abort/{packet_id}",
            headers={"X-Tenant-ID": "attacker-user"},
        )
        assert resp.status_code == 403

    def test_idor_status_only_own(self, eo_client):
        """Non-owner querying execution status must receive 403."""
        client, packet_id = eo_client
        resp = client.get(
            f"/execution/{packet_id}",
            headers={"X-Tenant-ID": "attacker-user"},
        )
        assert resp.status_code == 403

    def test_admin_can_abort_any(self, eo_client):
        """Admin role must be allowed to abort any execution — 200 OK."""
        client, packet_id = eo_client
        resp = client.post(
            f"/abort/{packet_id}",
            headers={"X-Tenant-ID": "admin-user", "X-Role": "admin"},
        )
        assert resp.status_code == 200


# ============================================================================
# W2-03: Credential Verifier Real Validation
# ============================================================================


def _make_jwt(payload: dict) -> str:
    """Create a minimal unsigned JWT (header.payload.signature)."""
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{body}.fakesig"


class TestConfidenceEngineCredentialVerifier:
    """Unit tests for the confidence engine CredentialVerifier."""

    def _make_cred(self, value: str, cred_type: str = "api_key"):
        from src.confidence_engine.credential_verifier import Credential, CredentialType
        type_map = {
            "api_key": CredentialType.API_KEY,
            "oauth_token": CredentialType.OAUTH_TOKEN,
            "jwt_token": CredentialType.JWT_TOKEN,
        }
        return Credential(
            id="cred-1",
            credential_type=type_map[cred_type],
            service_name="test-service",
            credential_value=value,
        )

    def test_api_key_valid_format_passes(self):
        """32-char alphanumeric key must pass the format gate."""
        from src.confidence_engine.credential_verifier import CredentialVerifier, CredentialStore
        verifier = CredentialVerifier(CredentialStore())
        cred = self._make_cred("a" * 32, "api_key")
        result = asyncio.run(
            verifier._verify_api_key(cred)
        )
        assert result is True

    def test_api_key_too_short_fails(self):
        """A 5-char key must fail the format gate."""
        from src.confidence_engine.credential_verifier import CredentialVerifier, CredentialStore
        verifier = CredentialVerifier(CredentialStore())
        cred = self._make_cred("short", "api_key")
        result = asyncio.run(
            verifier._verify_api_key(cred)
        )
        assert result is False

    def test_oauth_token_expired_fails(self):
        """JWT with exp in the past must fail OAuth token verification."""
        from src.confidence_engine.credential_verifier import CredentialVerifier, CredentialStore
        verifier = CredentialVerifier(CredentialStore())
        past_exp = int((datetime.now(tz=timezone.utc) - timedelta(hours=1)).timestamp())
        token = _make_jwt({"sub": "user", "exp": past_exp})
        cred = self._make_cred(token, "oauth_token")
        result = asyncio.run(
            verifier._verify_oauth_token(cred)
        )
        assert result is False

    def test_oauth_token_valid_structure_passes(self):
        """JWT with future exp must pass OAuth token verification."""
        from src.confidence_engine.credential_verifier import CredentialVerifier, CredentialStore
        verifier = CredentialVerifier(CredentialStore())
        future_exp = int((datetime.now(tz=timezone.utc) + timedelta(hours=1)).timestamp())
        token = _make_jwt({"sub": "user", "exp": future_exp})
        cred = self._make_cred(token, "oauth_token")
        result = asyncio.run(
            verifier._verify_oauth_token(cred)
        )
        assert result is True

    def test_jwt_malformed_fails(self):
        """A string without 3 dot-separated parts must fail JWT verification."""
        from src.confidence_engine.credential_verifier import CredentialVerifier, CredentialStore
        verifier = CredentialVerifier(CredentialStore())
        cred = self._make_cred("not.a.valid.jwt.token.extra", "jwt_token")
        result = asyncio.run(
            verifier._verify_jwt_token(cred)
        )
        assert result is False


class TestFreelancerCredentialVerifier:
    """Unit tests for the freelancer validator BBBSource and GenericPublicRecordSource."""

    def _make_cred(self):
        from src.freelancer_validator.models import (
            Credential, CertificationType,
        )
        from datetime import datetime, timezone
        return Credential(
            credential_id="fl-cred-1",
            name="Test Cert",
            credential_type=CertificationType.INDUSTRY_CERTIFICATION,
            issuing_authority="Test Authority",
            country="US",
            issued_date=datetime.now(tz=timezone.utc),
        )

    def test_bbb_source_unavailable_low_confidence(self):
        """When the BBB API is unreachable, confidence must be ≤ 0.3."""
        from src.freelancer_validator.credential_verifier import BBBSource
        import urllib.error

        source = BBBSource()
        cred = self._make_cred()

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            result = asyncio.run(
                source.lookup_credential(cred)
            )

        assert result is not None
        assert result.confidence <= 0.3, (
            f"Expected confidence ≤ 0.3 but got {result.confidence}"
        )

    def test_generic_source_unavailable_low_confidence(self):
        """When the generic registry is unreachable, confidence must be ≤ 0.3."""
        from src.freelancer_validator.credential_verifier import GenericPublicRecordSource

        source = GenericPublicRecordSource()
        source.REGISTRY_URL = "http://fake-registry.example.invalid"
        cred = self._make_cred()

        with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            result = asyncio.run(
                source.lookup_credential(cred)
            )

        assert result is not None
        assert result.confidence <= 0.3, (
            f"Expected confidence ≤ 0.3 but got {result.confidence}"
        )


# ============================================================================
# W2-04: Secure Master Key Storage
# ============================================================================


class TestSecureKeyStorage:
    """Verify the keyring → encrypted file → .env fallback chain."""

    def test_key_stored_in_keyring(self, tmp_path):
        """When keyring is available, the key must be stored there."""
        from src import secure_key_manager as skm

        mock_keyring = MagicMock()
        mock_keyring.set_password = MagicMock()
        mock_keyring.get_password = MagicMock(return_value=None)

        with patch.object(skm, "_keyring", mock_keyring), \
             patch.object(skm, "_KEYRING_AVAILABLE", True):
            backend = skm.store_api_key("TEST_KEY", "super-secret-value", tmp_path / ".env")

        assert backend == "keyring"
        mock_keyring.set_password.assert_called_once_with(
            skm._KEYRING_SERVICE, "TEST_KEY", "super-secret-value"
        )

    def test_key_fallback_to_encrypted_file(self, tmp_path):
        """When keyring raises, the key must be stored in an encrypted file."""
        from src import secure_key_manager as skm

        mock_keyring = MagicMock()
        mock_keyring.set_password = MagicMock(side_effect=Exception("no keyring"))

        with patch.object(skm, "_keyring", mock_keyring), \
             patch.object(skm, "_KEYRING_AVAILABLE", True):
            backend = skm.store_api_key("TEST_KEY", "my-secret", tmp_path / ".env")

        assert backend == "encrypted_file"
        enc_file = tmp_path / ".murphy_keys.enc"
        assert enc_file.exists(), "Encrypted file must be created as fallback"

    def test_key_not_plaintext_in_env(self, tmp_path):
        """After secure storage, the .env file must not contain the raw key value."""
        from src import secure_key_manager as skm

        env_file = tmp_path / ".env"
        env_file.write_text("")
        secret = "super-secret-key-value-12345"

        # Store without keyring (force encrypted file)
        with patch.object(skm, "_KEYRING_AVAILABLE", False):
            skm.store_api_key("MY_KEY", secret, env_file)

        env_content = env_file.read_text()
        assert secret not in env_content, (
            "Raw key value must not appear in .env after secure storage"
        )

    def test_key_retrieval_chain(self, tmp_path):
        """Store in keyring → retrieve → matches; delete from keyring → falls back to encrypted file."""
        from src import secure_key_manager as skm

        stored = {}

        def mock_set(service, name, value):
            stored[(service, name)] = value

        def mock_get(service, name):
            return stored.get((service, name))

        def mock_delete(service, name):
            stored.pop((service, name), None)

        mock_keyring = MagicMock(
            set_password=mock_set,
            get_password=mock_get,
            delete_password=mock_delete,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("")

        with patch.object(skm, "_keyring", mock_keyring), \
             patch.object(skm, "_KEYRING_AVAILABLE", True):
            skm.store_api_key("MY_KEY", "keyring-value", env_file)
            retrieved = skm.retrieve_api_key("MY_KEY", env_file)
            assert retrieved == "keyring-value"

            # Also write to encrypted file (simulate previous backup)
        with patch.object(skm, "_KEYRING_AVAILABLE", False):
            skm.store_api_key("MY_KEY", "enc-file-value", env_file)

        # Delete from keyring and retrieve — should fall back to encrypted file
        with patch.object(skm, "_keyring", mock_keyring), \
             patch.object(skm, "_KEYRING_AVAILABLE", True):
            skm.delete_api_key("MY_KEY", env_file)
            # Keyring now returns None since deleted
            assert mock_get(skm._KEYRING_SERVICE, "MY_KEY") is None
            retrieved_fallback = skm.retrieve_api_key("MY_KEY", env_file)
            assert retrieved_fallback == "enc-file-value"

    def test_migrate_existing_plaintext_keys(self, tmp_path):
        """migrate_keys() must move .env plaintext API keys to secure store."""
        from src import secure_key_manager as skm

        env_file = tmp_path / ".env"
        env_file.write_text(
            "MURPHY_LLM_PROVIDER=groq\n"
            "GROQ_API_KEY=gsk_plaintext123456789\n"
            "APP_PORT=8000\n"
        )

        migrated_store = {}

        def mock_set(service, name, value):
            migrated_store[(service, name)] = value

        mock_keyring = MagicMock(set_password=mock_set)

        with patch.object(skm, "_keyring", mock_keyring), \
             patch.object(skm, "_KEYRING_AVAILABLE", True):
            migrated = skm.migrate_keys(env_file)

        assert "GROQ_API_KEY" in migrated, "GROQ_API_KEY must be migrated"

        env_content = env_file.read_text()
        assert "gsk_plaintext123456789" not in env_content, (
            "Plaintext key must be removed from .env after migration"
        )
        # Non-sensitive values must remain
        assert "MURPHY_LLM_PROVIDER=groq" in env_content
        assert "APP_PORT=8000" in env_content


# ============================================================================
# W2-05: Rate Limiting Wiring
# ============================================================================


class TestRateLimitingWiring:
    """Verify rate limiting is wired and enforces 429 with Retry-After."""

    @pytest.fixture
    def rate_limited_app(self):
        """Create a minimal Flask app secured via configure_secure_app."""
        from flask import Flask, jsonify
        from src.flask_security import configure_secure_app, _FlaskRateLimiter

        test_app = Flask("rate-limit-test")
        configure_secure_app(test_app, service_name="test")

        # Override with a tight limiter for fast testing
        tight_limiter = _FlaskRateLimiter(requests_per_minute=100, burst_size=10)

        @test_app.route("/ping", methods=["GET"])
        def ping():
            return jsonify({"ok": True})

        test_app.config["TESTING"] = False  # Enable rate limiting
        with test_app.test_client() as client:
            yield client, tight_limiter

    def test_rate_limit_under_threshold_passes(self):
        """10 requests well below the threshold must all return 200."""
        from flask import Flask, jsonify
        from src.flask_security import configure_secure_app, _FlaskRateLimiter

        test_app = Flask("rl-under-test")
        limiter = _FlaskRateLimiter(requests_per_minute=100, burst_size=20)

        with patch("src.flask_security._rate_limiter", limiter):
            configure_secure_app(test_app, service_name="test")

            @test_app.route("/ping")
            def ping():
                return jsonify({"ok": True})

            test_app.config["TESTING"] = False
            with test_app.test_client() as client:
                for _ in range(10):
                    resp = client.get("/ping", environ_base={"REMOTE_ADDR": "10.0.0.1"})
                    assert resp.status_code == 200

    def test_rate_limit_exceeded_returns_429(self):
        """Once burst is exhausted, subsequent requests must return 429."""
        from flask import Flask, jsonify
        from src.flask_security import configure_secure_app, _FlaskRateLimiter

        test_app = Flask("rl-exceeded-test")
        # Very tight: 1 rpm, burst=1
        tight_limiter = _FlaskRateLimiter(requests_per_minute=1, burst_size=1)

        with patch("src.flask_security._rate_limiter", tight_limiter):
            configure_secure_app(test_app, service_name="test")

            @test_app.route("/ping")
            def ping():
                return jsonify({"ok": True})

            test_app.config["TESTING"] = False
            with test_app.test_client() as client:
                statuses = []
                for _ in range(5):
                    resp = client.get("/ping", environ_base={"REMOTE_ADDR": "10.0.0.2"})
                    statuses.append(resp.status_code)
                assert 429 in statuses, "Expected at least one 429 after burst exhaustion"

    def test_rate_limit_429_has_retry_after_header(self):
        """429 responses must include the Retry-After HTTP header."""
        from flask import Flask, jsonify
        from src.flask_security import configure_secure_app, _FlaskRateLimiter

        test_app = Flask("rl-header-test")
        tight_limiter = _FlaskRateLimiter(requests_per_minute=1, burst_size=1)

        with patch("src.flask_security._rate_limiter", tight_limiter):
            configure_secure_app(test_app, service_name="test")

            @test_app.route("/ping")
            def ping():
                return jsonify({"ok": True})

            test_app.config["TESTING"] = False
            with test_app.test_client() as client:
                resp_429 = None
                for _ in range(5):
                    resp = client.get("/ping", environ_base={"REMOTE_ADDR": "10.0.0.3"})
                    if resp.status_code == 429:
                        resp_429 = resp
                        break

                assert resp_429 is not None, "Expected a 429 response"
                assert "Retry-After" in resp_429.headers, (
                    "429 response must include the Retry-After header"
                )

    def test_rate_limit_different_ips_independent(self):
        """Requests from different IPs must have independent rate limit buckets."""
        from flask import Flask, jsonify
        from src.flask_security import configure_secure_app, _FlaskRateLimiter

        test_app = Flask("rl-ip-test")
        # Allow 20 per window with burst of 20 per IP
        limiter = _FlaskRateLimiter(requests_per_minute=20, burst_size=20)

        with patch("src.flask_security._rate_limiter", limiter):
            configure_secure_app(test_app, service_name="test")

            @test_app.route("/ping")
            def ping():
                return jsonify({"ok": True})

            test_app.config["TESTING"] = False
            with test_app.test_client() as client:
                for ip in ("10.1.1.1", "10.1.1.2"):
                    for _ in range(10):
                        resp = client.get(
                            "/ping", environ_base={"REMOTE_ADDR": ip}
                        )
                        assert resp.status_code == 200, (
                            f"IP {ip} should not be rate-limited at 10 requests"
                        )

    def test_rate_limit_redis_fallback(self):
        """In-memory limiter must enforce rate limits even when Redis is unavailable."""
        from src.flask_security import _FlaskRateLimiter

        # The in-memory limiter never touches Redis
        limiter = _FlaskRateLimiter(requests_per_minute=2, burst_size=2)
        results = []
        for _ in range(5):
            result = limiter.check("test-ip")
            results.append(result["allowed"])

        assert True in results, "Some requests should be allowed"
        assert False in results, "Some requests should be rate-limited"
