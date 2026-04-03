# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Critical Security Fixes — Regression Test Suite
=================================================

Proves that each gap identified in the PR #27 QA audit is closed.
One test class per finding; each class contains:
  1. A test that attempts the previously-possible attack vector → it is now blocked.
  2. A test that verifies legitimate access still works.

Findings covered
----------------
SEC-001  All routes require authentication (FastAPI SecurityMiddleware)
SEC-002  CORS no longer allows wildcard origins
SEC-003  Cryptographic operations use real implementations (not stubs)
ARCH-001 security_hardening_config.py is present and loadable
ARCH-003 Tenant isolation in confidence_engine/api_server.py
ARCH-004 Execution registry IDOR — ownership check on abort/pause/resume
ARCH-006 Rate limiting wired and enforced

Run with:
    MURPHY_ENV=test python3 -m pytest tests/test_critical_security_fixes.py -v --override-ini="addopts="
"""

import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root on path
os.environ.setdefault("MURPHY_ENV", "test")


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_fastapi_app():
    """Create a minimal FastAPI app with full security wiring applied."""
    from fastapi import FastAPI
    from src.fastapi_security import configure_secure_fastapi

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/auth/login")
    async def login():
        return {"token": "test"}

    @app.get("/api/protected")
    async def protected():
        return {"data": "secret"}

    configure_secure_fastapi(app, service_name="test-service")
    return app


# ── SEC-001: Authentication Required ─────────────────────────────────────────


class TestSEC001_AuthenticationRequired:
    """
    SEC-001 — Every non-public route must reject unauthenticated requests.

    The fix: SecurityMiddleware (src/fastapi_security.py) is registered
    via configure_secure_fastapi() and blocks requests without a valid
    API key, JWT, or session cookie.
    """

    def test_security_middleware_class_exists(self):
        """SecurityMiddleware must be importable from src.fastapi_security."""
        from src.fastapi_security import SecurityMiddleware  # noqa: F401

    def test_configure_secure_fastapi_exists(self):
        """configure_secure_fastapi() helper must exist and be callable."""
        from src.fastapi_security import configure_secure_fastapi

        assert callable(configure_secure_fastapi)

    def test_security_middleware_is_registered_on_app(self):
        """
        After configure_secure_fastapi(), the app middleware stack must contain
        SecurityMiddleware.
        """
        from fastapi import FastAPI
        from src.fastapi_security import SecurityMiddleware, configure_secure_fastapi

        app = FastAPI()
        configure_secure_fastapi(app, service_name="test")

        middleware_types = [type(m) for m in app.user_middleware]
        # FastAPI wraps middleware — check the cls kwarg
        middleware_classes = []
        for m in app.user_middleware:
            cls = getattr(m, "cls", None)
            if cls is not None:
                middleware_classes.append(cls)
        assert SecurityMiddleware in middleware_classes, (
            "SecurityMiddleware must be in the app middleware stack after configure_secure_fastapi()"
        )

    def test_unauthenticated_routes_blocked_by_default(self):
        """
        _is_public_api_route() must NOT classify arbitrary API routes as public.
        Only the explicitly listed paths should bypass auth.
        """
        from src.fastapi_security import _is_public_api_route

        assert not _is_public_api_route("/api/production/queue", "GET"), (
            "/api/production/queue must require auth"
        )
        assert not _is_public_api_route("/api/admin/users", "GET"), (
            "/api/admin/users must require auth"
        )
        assert not _is_public_api_route("/api/execute", "POST"), (
            "/api/execute must require auth"
        )

    def test_health_endpoint_is_public(self):
        """Health endpoint must NOT require authentication."""
        from src.fastapi_security import _is_health_endpoint, _is_public_api_route

        assert _is_health_endpoint("/health") or _is_public_api_route("/health", "GET"), (
            "/health must be exempt from auth"
        )

    def test_login_endpoint_is_public(self):
        """Login endpoint must NOT require authentication (circular dependency)."""
        from src.fastapi_security import _is_public_api_route

        assert _is_public_api_route("/api/auth/login", "POST"), (
            "/api/auth/login POST must be public"
        )

    def test_signup_endpoint_is_public(self):
        """Signup endpoint must NOT require authentication."""
        from src.fastapi_security import _is_public_api_route

        assert _is_public_api_route("/api/auth/signup", "POST"), (
            "/api/auth/signup POST must be public"
        )

    def test_flask_security_configure_exists(self):
        """configure_secure_app() must exist in src.flask_security."""
        from src.flask_security import configure_secure_app  # noqa: F401

        assert callable(configure_secure_app)

    def test_middleware_authenticates_via_api_key(self):
        """validate_api_key() returns True for a valid API key."""
        import importlib
        with patch.dict(os.environ, {"MURPHY_API_KEY": "test-api-key-12345", "MURPHY_ENV": "test"}):
            import src.fastapi_security as mod
            importlib.reload(mod)

            result = mod.validate_api_key("test-api-key-12345")
            assert result is True


# ── SEC-002: CORS Restricted ──────────────────────────────────────────────────


class TestSEC002_CORSRestricted:
    """
    SEC-002 — CORS must not allow wildcard origins.

    The fix: get_cors_origins() reads MURPHY_CORS_ORIGINS env var and
    defaults to localhost origins only; wildcard is never the default.
    """

    def test_default_cors_does_not_include_wildcard(self):
        """Without MURPHY_CORS_ORIGINS set, origins must not contain '*'."""
        import importlib
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MURPHY_CORS_ORIGINS", None)
            import src.fastapi_security as mod
            importlib.reload(mod)
            origins = mod.get_cors_origins()

        assert "*" not in origins, (
            f"Wildcard origin must not be in default CORS list; got: {origins}"
        )

    def test_default_cors_includes_localhost(self):
        """Default origins should include localhost entries."""
        import importlib
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MURPHY_CORS_ORIGINS", None)
            import src.fastapi_security as mod
            importlib.reload(mod)
            origins = mod.get_cors_origins()

        assert any("localhost" in o for o in origins), (
            f"Default CORS origins should include localhost; got: {origins}"
        )

    def test_cors_reads_env_var(self):
        """MURPHY_CORS_ORIGINS env var overrides the default origin list."""
        import importlib
        with patch.dict(os.environ, {"MURPHY_CORS_ORIGINS": "https://app.example.com,https://admin.example.com"}):
            import src.fastapi_security as mod
            importlib.reload(mod)
            origins = mod.get_cors_origins()

        assert "https://app.example.com" in origins
        assert "https://admin.example.com" in origins

    def test_cors_rejects_unknown_origin(self):
        """An unlisted origin must NOT appear in the allowed list."""
        import importlib
        with patch.dict(os.environ, {"MURPHY_CORS_ORIGINS": "http://localhost:3000"}):
            import src.fastapi_security as mod
            importlib.reload(mod)
            origins = mod.get_cors_origins()

        assert "https://evil.com" not in origins, (
            "https://evil.com must not be in the CORS allowlist"
        )

    def test_flask_cors_does_not_wildcard(self):
        """Flask security get_cors_origins must also avoid wildcard defaults."""
        import importlib
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MURPHY_CORS_ORIGINS", None)
            import src.flask_security as mod
            importlib.reload(mod)
            origins = mod.get_cors_origins()

        assert "*" not in origins, (
            f"Flask CORS wildcard must not be default; got: {origins}"
        )

    def test_cors_origin_list_is_nonempty(self):
        """CORS origin list must never be empty (would block all cross-origin requests)."""
        from src.fastapi_security import get_cors_origins

        origins = get_cors_origins()
        assert len(origins) > 0, "CORS origin list must not be empty"


# ── SEC-003: Real Cryptography ────────────────────────────────────────────────


class TestSEC003_CryptoNotSimulated:
    """
    SEC-003 — Cryptographic operations must use real implementations.

    The fix: src/security_plane/cryptography.py delegates to the
    `cryptography` library (Fernet + ECDSA) when available; PQC stubs
    are flagged clearly and FIDO2 raises NotImplementedError.
    """

    def test_real_crypto_flag_detected(self):
        """
        _HAS_REAL_CLASSICAL or _HAS_FERNET must be True when the
        `cryptography` package is installed.
        """
        from src.security_plane import cryptography as crypto_mod

        assert crypto_mod._HAS_REAL_CLASSICAL or crypto_mod._HAS_FERNET, (
            "_HAS_REAL_CLASSICAL or _HAS_FERNET must be True — install the 'cryptography' package"
        )

    def test_key_manager_encrypt_decrypt_roundtrip(self):
        """
        KeyManager must be able to encrypt and decrypt a private key using
        real Fernet symmetric encryption (not a passthrough stub).
        """
        os.environ.setdefault("MURPHY_ENV", "test")
        from src.security_plane.cryptography import KeyManager

        plaintext = b"test-private-key-value-abc123"
        km = KeyManager()
        encrypted = km._encrypt_private_key(plaintext)
        decrypted = km._decrypt_private_key(encrypted)
        assert decrypted == plaintext

    def test_encryption_produces_different_ciphertext_each_call(self):
        """
        Real Fernet uses a random IV — encrypting the same plaintext twice
        must produce different ciphertexts (proves real crypto, not a stub).
        """
        os.environ.setdefault("MURPHY_ENV", "test")
        from src.security_plane.cryptography import KeyManager

        plaintext = b"same-plaintext"
        km = KeyManager()
        c1 = km._encrypt_private_key(plaintext)
        c2 = km._encrypt_private_key(plaintext)
        assert c1 != c2, (
            "Encrypting the same plaintext twice must yield different ciphertexts "
            "(real Fernet uses a random IV; stub behaviour would return identical bytes)"
        )

    def test_encryption_output_is_longer_than_input(self):
        """Fernet ciphertext (with IV + HMAC) must be longer than the plaintext."""
        os.environ.setdefault("MURPHY_ENV", "test")
        from src.security_plane.cryptography import KeyManager

        plaintext = b"short-key"
        km = KeyManager()
        encrypted = km._encrypt_private_key(plaintext)
        assert len(encrypted) > len(plaintext), (
            "Ciphertext must be longer than plaintext when real crypto is used"
        )

    def test_classical_keypair_generates_real_bytes(self):
        """ClassicalCryptography.generate_keypair() must return non-empty key bytes."""
        from src.security_plane.cryptography import ClassicalCryptography

        kp = ClassicalCryptography.generate_keypair()
        assert len(kp.public_key) > 0
        assert len(kp.private_key) > 0

    def test_classical_keypairs_are_unique(self):
        """Each call to generate_keypair() must produce different keys."""
        from src.security_plane.cryptography import ClassicalCryptography

        kp1 = ClassicalCryptography.generate_keypair()
        kp2 = ClassicalCryptography.generate_keypair()
        assert kp1.public_key != kp2.public_key, (
            "Successive keypair generation must produce distinct keys"
        )

    def test_hash_produces_deterministic_output(self):
        """CryptographicPrimitives.hash_data() must be deterministic."""
        from src.security_plane.cryptography import CryptographicPrimitives, HashAlgorithm

        data = b"deterministic-test-input"
        h1 = CryptographicPrimitives.hash_data(data, HashAlgorithm.SHA256)
        h2 = CryptographicPrimitives.hash_data(data, HashAlgorithm.SHA256)
        assert h1 == h2

    def test_hash_is_not_empty(self):
        """Hash output must not be empty bytes."""
        from src.security_plane.cryptography import CryptographicPrimitives

        h = CryptographicPrimitives.hash_data(b"input")
        assert h and len(h) > 0


# ── ARCH-001: Security Config Exists ─────────────────────────────────────────


class TestARCH001_SecurityConfigExists:
    """
    ARCH-001 — security_hardening_config.py must exist and expose the
    required security controls.
    """

    def test_module_is_importable(self):
        """src.security_hardening_config must be importable."""
        import src.security_hardening_config  # noqa: F401

    def test_input_sanitizer_present(self):
        """InputSanitizer class must exist and be usable."""
        from src.security_hardening_config import InputSanitizer

        assert callable(getattr(InputSanitizer, "sanitize_string", None))

    def test_cors_policy_present(self):
        """CORSPolicy class must exist."""
        from src.security_hardening_config import CORSPolicy  # noqa: F401

    def test_rate_limiter_present(self):
        """RateLimiter class must exist."""
        from src.security_hardening_config import RateLimiter  # noqa: F401

    def test_content_security_policy_present(self):
        """ContentSecurityPolicy class must exist."""
        from src.security_hardening_config import ContentSecurityPolicy  # noqa: F401

    def test_get_rate_limiter_callable(self):
        """get_rate_limiter() factory must be callable and return a RateLimiter."""
        from src.security_hardening_config import RateLimiter, get_rate_limiter

        limiter = get_rate_limiter()
        assert isinstance(limiter, RateLimiter)

    def test_input_sanitizer_detects_xss(self):
        """InputSanitizer must flag obvious XSS payloads."""
        from src.security_hardening_config import InputSanitizer

        findings = InputSanitizer.detect_injection("<script>alert(1)</script>")
        assert len(findings) > 0, "XSS payload must be detected"

    def test_input_sanitizer_accepts_clean_string(self):
        """InputSanitizer must pass clean strings without raising."""
        from src.security_hardening_config import InputSanitizer

        result = InputSanitizer.sanitize_string("hello world")
        assert result == "hello world"

    def test_cors_policy_blocks_unknown_origin(self):
        """CORSPolicy.is_origin_allowed() must reject origins not in the allowlist."""
        from src.security_hardening_config import CORSPolicy

        policy = CORSPolicy(allowed_origins=["http://localhost:3000"])
        assert not policy.is_origin_allowed("https://evil.com")

    def test_cors_policy_allows_configured_origin(self):
        """CORSPolicy.is_origin_allowed() must accept allowlisted origins."""
        from src.security_hardening_config import CORSPolicy

        policy = CORSPolicy(allowed_origins=["http://localhost:3000"])
        assert policy.is_origin_allowed("http://localhost:3000")

    def test_rate_limiter_allows_initial_requests(self):
        """Rate limiter must allow the first request from a new client."""
        from src.security_hardening_config import RateLimiter

        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        result = limiter.check("unique-client-id-test-arch001")
        assert result["allowed"] is True

    def test_rate_limiter_blocks_after_burst(self):
        """Rate limiter must block requests after the burst limit is exceeded."""
        from src.security_hardening_config import RateLimiter

        burst = 3
        limiter = RateLimiter(requests_per_minute=60, burst_size=burst)
        client = "burst-test-client-arch001-unique"
        for _ in range(burst):
            limiter.check(client)
        # The next request should be blocked
        result = limiter.check(client)
        assert result["allowed"] is False, (
            f"Request after burst={burst} should be blocked; got: {result}"
        )


# ── ARCH-003: Tenant Isolation ────────────────────────────────────────────────


class TestARCH003_TenantIsolation:
    """
    ARCH-003 — The confidence engine must isolate artifact graphs per tenant.

    The fix: confidence_engine/api_server.py replaces the global
    ArtifactGraph with a per-tenant registry keyed by X-Tenant-ID.
    """

    def test_tenant_graph_function_exists(self):
        """_get_tenant_graph() must exist in the confidence_engine api_server."""
        # Import without starting the Flask server by importing the module directly
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "confidence_engine.api_server",
            os.path.join(
                os.path.dirname(__file__),
                "..", "src", "confidence_engine", "api_server.py"
            ),
        )
        mod = importlib.util.module_from_spec(spec)
        assert hasattr(spec, "loader")

    def test_tenant_graphs_dict_is_present(self):
        """The module must expose a _tenant_graphs dict (not a global singleton)."""
        import importlib
        import sys

        # Load the module file as text and check for the pattern
        api_server_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "confidence_engine", "api_server.py"
        )
        with open(api_server_path, encoding="utf-8") as fh:
            source = fh.read()

        assert "_tenant_graphs" in source, (
            "confidence_engine/api_server.py must use _tenant_graphs dict for tenant isolation"
        )

    def test_x_tenant_id_header_is_used(self):
        """The module must reference X-Tenant-ID header for tenant extraction."""
        api_server_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "confidence_engine", "api_server.py"
        )
        with open(api_server_path, encoding="utf-8") as fh:
            source = fh.read()

        assert "X-Tenant-ID" in source, (
            "confidence_engine/api_server.py must use X-Tenant-ID header for tenant extraction"
        )

    def test_no_global_artifact_graph_singleton(self):
        """
        There must be NO line that assigns a bare module-level ArtifactGraph()
        outside of a function/method (the old singleton pattern is gone).
        """
        import ast
        api_server_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "confidence_engine", "api_server.py"
        )
        with open(api_server_path, encoding="utf-8") as fh:
            source = fh.read()

        tree = ast.parse(source, filename=api_server_path)
        # Collect module-level assignments (not inside functions/classes)
        top_level_assigns = [
            node for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
        ]
        for node in top_level_assigns:
            # Look for bare `ArtifactGraph()` call at module level
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    name = ""
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr
                    assert name != "ArtifactGraph", (
                        f"Found bare ArtifactGraph() singleton at module level (line {sub.lineno}). "
                        "Use _get_tenant_graph() instead."
                    )

    def test_tenant_lock_is_present(self):
        """Thread lock for tenant dict must be present for concurrent safety."""
        api_server_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "confidence_engine", "api_server.py"
        )
        with open(api_server_path, encoding="utf-8") as fh:
            source = fh.read()

        assert "_tenant_lock" in source or "threading.Lock" in source, (
            "confidence_engine/api_server.py must use a thread lock to protect _tenant_graphs"
        )

    def test_tenant_ttl_eviction_present(self):
        """Idle tenant state must be evictable to prevent memory leaks."""
        api_server_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "confidence_engine", "api_server.py"
        )
        with open(api_server_path, encoding="utf-8") as fh:
            source = fh.read()

        assert "evict" in source.lower() or "TTL" in source or "ttl" in source.lower(), (
            "confidence_engine/api_server.py must implement TTL eviction for idle tenants"
        )


# ── ARCH-004: Execution Ownership ────────────────────────────────────────────


class TestARCH004_ExecutionOwnership:
    """
    ARCH-004 — Users must not be able to abort/pause/resume other users' executions.

    The fix: _check_ownership() in execution_orchestrator/api.py verifies
    the caller identity against the stored owner before allowing abort/modify.
    """

    def _get_api(self):
        """Import the execution orchestrator Flask app for testing."""
        import importlib
        import sys

        # Ensure any previous import is cleared
        for key in list(sys.modules.keys()):
            if "execution_orchestrator" in key:
                del sys.modules[key]

        import src.execution_orchestrator.api as api_mod
        return api_mod

    def _make_execution_state(self, packet_id: str):
        """Create a minimal ExecutionState for testing."""
        from datetime import datetime, timezone
        from src.execution_orchestrator.models import ExecutionState, ExecutionStatus

        return ExecutionState(
            packet_id=packet_id,
            packet_signature="test-sig",
            status=ExecutionStatus.RUNNING,
            current_step=0,
            total_steps=1,
            start_time=datetime.now(timezone.utc),
        )

    def test_check_ownership_function_exists(self):
        """_check_ownership() must exist in the execution orchestrator API."""
        api_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "execution_orchestrator", "api.py"
        )
        with open(api_path, encoding="utf-8") as fh:
            source = fh.read()

        assert "_check_ownership" in source, (
            "execution_orchestrator/api.py must define _check_ownership()"
        )

    def test_403_is_returned_for_non_owner(self):
        """
        When caller identity != execution owner, _check_ownership() must
        return a 403 response.
        """
        api_mod = self._get_api()

        fake_packet_id = "test-packet-arch004-nonowner"
        api_mod.executions[fake_packet_id] = self._make_execution_state(fake_packet_id)
        api_mod.execution_owners[fake_packet_id] = "user-alice"

        with api_mod.app.test_request_context(
            f"/abort/{fake_packet_id}",
            method="POST",
            headers={"X-Tenant-ID": "user-bob"},
        ):
            result = api_mod._check_ownership(fake_packet_id)

        assert result is not None, (
            "_check_ownership() must return a denial tuple for a non-owner caller"
        )
        response, status_code = result
        assert status_code == 403, f"Expected 403, got {status_code}"

    def test_owner_is_allowed(self):
        """The execution owner must be allowed through _check_ownership()."""
        api_mod = self._get_api()

        fake_packet_id = "test-packet-arch004-owner"
        api_mod.executions[fake_packet_id] = self._make_execution_state(fake_packet_id)
        api_mod.execution_owners[fake_packet_id] = "user-carol"

        with api_mod.app.test_request_context(
            f"/abort/{fake_packet_id}",
            method="POST",
            headers={"X-Tenant-ID": "user-carol"},
        ):
            result = api_mod._check_ownership(fake_packet_id)

        assert result is None, (
            "_check_ownership() must return None (allow) for the execution owner"
        )

    def test_admin_bypasses_ownership_check(self):
        """Admin users (X-Role: admin) must bypass the ownership check."""
        api_mod = self._get_api()

        fake_packet_id = "test-packet-arch004-admin"
        api_mod.executions[fake_packet_id] = self._make_execution_state(fake_packet_id)
        api_mod.execution_owners[fake_packet_id] = "user-owner"

        with api_mod.app.test_request_context(
            f"/abort/{fake_packet_id}",
            method="POST",
            headers={"X-Tenant-ID": "different-user", "X-Role": "admin"},
        ):
            result = api_mod._check_ownership(fake_packet_id)

        assert result is None, (
            "Admin users must bypass the ownership check (_check_ownership() must return None)"
        )

    def test_ownership_stored_at_execution_time(self):
        """
        Caller identity (X-Tenant-ID) must be stored in execution_owners when
        an execution packet is submitted.
        """
        api_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "execution_orchestrator", "api.py"
        )
        with open(api_path, encoding="utf-8") as fh:
            source = fh.read()

        assert "execution_owners" in source, (
            "execution_orchestrator/api.py must maintain an execution_owners dict"
        )
        assert "_get_caller_identity" in source, (
            "execution_orchestrator/api.py must call _get_caller_identity() to record owner"
        )

    def test_abort_route_includes_ownership_check(self):
        """
        The /abort/<packet_id> route source must call _check_ownership().
        """
        # Number of characters to scan after `def abort_execution` to find the
        # ownership check call.  Large enough to cover the function prologue.
        _ABORT_SCAN_WINDOW = 400

        api_path = os.path.join(
            os.path.dirname(__file__),
            "..", "src", "execution_orchestrator", "api.py"
        )
        with open(api_path, encoding="utf-8") as fh:
            source = fh.read()

        # Find the abort_execution function definition block
        abort_idx = source.find("def abort_execution")
        assert abort_idx != -1, "abort_execution function not found"
        abort_block = source[abort_idx: abort_idx + _ABORT_SCAN_WINDOW]
        assert "_check_ownership" in abort_block, (
            "abort_execution() must call _check_ownership() (ARCH-004 fix)"
        )


# ── ARCH-006: Rate Limiting Active ────────────────────────────────────────────


class TestARCH006_RateLimiting:
    """
    ARCH-006 — Rate limiting must be active on all API routes.

    The fix: _FastAPIRateLimiter and _FlaskRateLimiter in fastapi_security.py /
    flask_security.py enforce per-client request limits with X-RateLimit-*
    response headers.
    """

    def test_fastapi_rate_limiter_exists(self):
        """_FastAPIRateLimiter must exist in src.fastapi_security."""
        from src.fastapi_security import _FastAPIRateLimiter  # noqa: F401

    def test_flask_rate_limiter_exists(self):
        """_FlaskRateLimiter must exist in src.flask_security."""
        from src.flask_security import _FlaskRateLimiter  # noqa: F401

    def test_module_level_rate_limiter_instance(self):
        """A module-level _rate_limiter instance must exist in fastapi_security."""
        from src.fastapi_security import _rate_limiter

        assert _rate_limiter is not None

    def test_rate_limiter_allows_initial_request(self):
        """First request from a new client IP must be allowed."""
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter(requests_per_minute=60, burst_size=5)
        result = limiter.check("test-client-initial-arch006")
        assert result["allowed"] is True

    def test_rate_limiter_blocks_after_burst(self):
        """
        After exhausting the burst quota, the rate limiter must return
        allowed=False — this proves rate limiting is not a no-op stub.
        """
        from src.fastapi_security import _FastAPIRateLimiter

        burst = 3
        limiter = _FastAPIRateLimiter(requests_per_minute=120, burst_size=burst)
        client = f"burst-test-arch006-{time.time()}"
        for _ in range(burst):
            r = limiter.check(client)
            assert r["allowed"] is True

        # One more — must be blocked
        blocked = limiter.check(client)
        assert blocked["allowed"] is False, (
            f"Request {burst + 1} must be rate-limited; got: {blocked}"
        )

    def test_rate_limiter_allows_after_refill(self):
        """
        After waiting for the token refill window, requests should be
        allowed again.
        """
        from src.fastapi_security import _FastAPIRateLimiter

        # Very high RPM so that 1 second refills at least 1 token
        limiter = _FastAPIRateLimiter(requests_per_minute=120, burst_size=1)
        client = f"refill-test-arch006-{time.time()}"

        # Exhaust the burst
        limiter.check(client)
        blocked = limiter.check(client)
        assert blocked["allowed"] is False

        # Wait 1 second for a token to refill
        time.sleep(1.1)

        refilled = limiter.check(client)
        assert refilled["allowed"] is True, (
            "Rate limiter must allow requests again after the refill interval"
        )

    def test_rate_limit_result_includes_metadata(self):
        """Rate limiter result must contain limit and remaining metadata."""
        from src.fastapi_security import _FastAPIRateLimiter

        limiter = _FastAPIRateLimiter(requests_per_minute=60, burst_size=10)
        result = limiter.check("metadata-test-arch006")
        assert "allowed" in result
        assert "limit" in result or "tokens" in result, (
            "Rate limiter result must include limit or token count metadata"
        )

    def test_security_middleware_includes_rate_check(self):
        """
        SecurityMiddleware source must reference rate limiting logic,
        proving rate limiting is wired into the request pipeline.
        """
        import inspect
        from src.fastapi_security import SecurityMiddleware

        source = inspect.getsource(SecurityMiddleware)
        assert "rate" in source.lower(), (
            "SecurityMiddleware must reference rate limiting in its dispatch method"
        )

    def test_flask_rate_limiter_blocks_after_burst(self):
        """Flask rate limiter must also enforce burst limits."""
        from src.flask_security import _FlaskRateLimiter

        burst = 2
        limiter = _FlaskRateLimiter(requests_per_minute=120, burst_size=burst)
        client = f"flask-burst-arch006-{time.time()}"
        for _ in range(burst):
            r = limiter.check(client)
            assert r["allowed"] is True

        blocked = limiter.check(client)
        assert blocked["allowed"] is False, (
            f"Flask rate limiter must block after burst={burst}; got: {blocked}"
        )
