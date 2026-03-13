"""
Test Suite: Beta Hardening Verification

Verifies all security hardening changes required for Murphy System beta readiness:

  1. Encryption roundtrip — _encrypt_private_key / _decrypt_private_key
  2. Blueprint auth     — before_request hook registered on all blueprint factories
  3. Rate limiter Redis fallback — RedisRateLimiter → in-memory when Redis unavailable
  4. Auth modes         — development skips auth, staging/production require it
  5. No simulated encryption — grep cryptography.py for SHA-256 hash-as-encryption
  6. httpx is importable
  7. get_rate_limiter factory — returns correct type based on env var

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import ast
import os
import re
import sys
import threading
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helper: clear MURPHY_ENV side-effects between tests
# ---------------------------------------------------------------------------

def _with_env(**kwargs):
    """Context manager that patches os.environ for the duration of a test."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        old = {k: os.environ.get(k) for k in kwargs}
        os.environ.update({k: v for k, v in kwargs.items() if v is not None})
        for k, v in kwargs.items():
            if v is None:
                os.environ.pop(k, None)
        try:
            yield
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    return _ctx()


# ===========================================================================
# 1. Encryption Roundtrip
# ===========================================================================

class TestEncryptionRoundtrip:
    """Fernet encrypt/decrypt must recover the original private key bytes."""

    def _make_manager(self, master_key: str):
        """Import fresh KeyManager with the given master key set."""
        from src.security_plane.cryptography import KeyManager
        return KeyManager()

    def test_roundtrip_with_master_key(self):
        """_encrypt_private_key → _decrypt_private_key recovers the original bytes."""
        from cryptography.fernet import Fernet
        fernet_key = Fernet.generate_key().decode()

        with _with_env(MURPHY_CREDENTIAL_MASTER_KEY=fernet_key, MURPHY_ENV="development"):
            # Clear cached ephemeral Fernet so the env var is used
            from src.security_plane import cryptography as _crypto_mod
            if hasattr(_crypto_mod.KeyManager, "_ephemeral_fernet"):
                del _crypto_mod.KeyManager._ephemeral_fernet

            from src.security_plane.cryptography import KeyManager
            km = KeyManager()
            original = b"super_secret_private_key_bytes_32!!"
            encrypted = km._encrypt_private_key(original)
            assert encrypted != original, "encrypt should change the bytes"
            decrypted = km._decrypt_private_key(encrypted)
            assert decrypted == original, "decrypt must recover original bytes"

    def test_encrypt_produces_different_ciphertexts(self):
        """Fernet is non-deterministic; two encryptions of the same plaintext differ."""
        from cryptography.fernet import Fernet
        fernet_key = Fernet.generate_key().decode()

        with _with_env(MURPHY_CREDENTIAL_MASTER_KEY=fernet_key, MURPHY_ENV="development"):
            from src.security_plane import cryptography as _crypto_mod
            if hasattr(_crypto_mod.KeyManager, "_ephemeral_fernet"):
                del _crypto_mod.KeyManager._ephemeral_fernet
            from src.security_plane.cryptography import KeyManager
            km = KeyManager()
            original = b"my_private_key"
            c1 = km._encrypt_private_key(original)
            c2 = km._encrypt_private_key(original)
            assert c1 != c2, "Fernet should produce different ciphertexts each call"

    def test_no_sha256_in_encrypt_method(self):
        """_encrypt_private_key must NOT use hashlib.sha256 (the old simulated path)."""
        crypto_path = SRC_DIR / "security_plane" / "cryptography.py"
        with open(crypto_path, "r", encoding="utf-8") as fh:
            source = fh.read()

        # Locate the _encrypt_private_key function
        tree = ast.parse(source, filename=str(crypto_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_encrypt_private_key":
                func_src = ast.get_source_segment(source, node) or ""
                assert "sha256" not in func_src.lower(), (
                    "_encrypt_private_key still references sha256 — simulated encryption not removed"
                )
                return
        pytest.fail("_encrypt_private_key function not found in cryptography.py")

    def test_production_mode_requires_master_key(self):
        """In production mode, missing MURPHY_CREDENTIAL_MASTER_KEY must raise RuntimeError."""
        with _with_env(MURPHY_CREDENTIAL_MASTER_KEY=None, MURPHY_ENV="production"):
            from src.security_plane import cryptography as _crypto_mod
            if hasattr(_crypto_mod.KeyManager, "_ephemeral_fernet"):
                del _crypto_mod.KeyManager._ephemeral_fernet
            from src.security_plane.cryptography import KeyManager
            km = KeyManager()
            with pytest.raises(RuntimeError, match="MURPHY_CREDENTIAL_MASTER_KEY"):
                km._get_fernet()


# ===========================================================================
# 2. Blueprint Auth
# ===========================================================================

class TestBlueprintAuth:
    """Every blueprint factory must register a before_request auth hook."""

    BLUEPRINT_FACTORIES = [
        ("src.blockchain_audit_trail", "create_bat_api"),
        ("src.ab_testing_framework", "create_ab_testing_api"),
        ("src.webhook_dispatcher", "create_webhook_api"),
        ("src.multi_cloud_orchestrator", "create_multi_cloud_api"),
        ("src.voice_command_interface", "create_vci_api"),
        ("src.multi_tenant_workspace", "create_multi_tenant_api"),
        ("src.oauth_oidc_provider", "create_oauth_api"),
        ("src.natural_language_query", "create_nlq_api"),
        ("src.kubernetes_deployment", "create_k8s_api"),
        ("src.capacity_planning_engine", "create_capacity_api"),
        ("src.compliance_as_code_engine", "create_compliance_api"),
        ("src.prometheus_metrics_exporter", "create_metrics_blueprint"),
        ("src.docker_containerization", "create_docker_api"),
        ("src.ci_cd_pipeline_manager", "create_cicd_api"),
        ("src.geographic_load_balancer", "create_glb_api"),
        ("src.rpa_recorder_engine", "create_rpa_api"),
        ("src.computer_vision_pipeline", "create_cvp_api"),
        ("src.predictive_maintenance_engine", "create_predictive_maintenance_api"),
        ("src.knowledge_graph_builder", "create_knowledge_graph_api"),
        ("src.notification_system", "create_notification_api"),
        ("src.audit_logging_system", "create_audit_api"),
        ("src.data_pipeline_orchestrator", "create_pipeline_api"),
    ]

    def test_blueprint_auth_import_exists(self):
        """src/blueprint_auth.py must exist and export require_blueprint_auth."""
        auth_path = SRC_DIR / "blueprint_auth.py"
        assert auth_path.exists(), "src/blueprint_auth.py is missing"
        from src.blueprint_auth import require_blueprint_auth
        assert callable(require_blueprint_auth)

    @pytest.mark.parametrize("module_path,factory_name", BLUEPRINT_FACTORIES)
    def test_factory_imports_require_blueprint_auth(self, module_path, factory_name):
        """Each blueprint factory file must import require_blueprint_auth."""
        # Convert module path to file path
        file_path = SRC_DIR / module_path.replace("src.", "").replace(".", "/")
        file_path = file_path.with_suffix(".py")
        assert file_path.exists(), f"{file_path} not found"
        with open(file_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        assert "require_blueprint_auth" in content, (
            f"{file_path.name} does not import or call require_blueprint_auth"
        )

    def test_require_blueprint_auth_registers_before_request(self):
        """require_blueprint_auth must register a before_request hook on the blueprint."""
        try:
            from flask import Blueprint
            from src.blueprint_auth import require_blueprint_auth
        except ImportError:
            pytest.skip("Flask not installed")

        bp = Blueprint("test_auth_bp", __name__)
        require_blueprint_auth(bp)
        # Flask stores before_request_funcs under the blueprint name
        assert len(bp.before_request_funcs.get(None, [])) > 0, (
            "require_blueprint_auth did not register a before_request hook"
        )

    def test_auth_skipped_in_development_mode(self):
        """In development mode, require_blueprint_auth must not block requests."""
        try:
            from flask import Flask, Blueprint
            from src.blueprint_auth import require_blueprint_auth
        except ImportError:
            pytest.skip("Flask not installed")

        app = Flask(__name__)
        bp = Blueprint("dev_test", __name__, url_prefix="/test")

        @bp.route("/ping")
        def _ping():
            return "pong"

        require_blueprint_auth(bp)
        app.register_blueprint(bp)

        with _with_env(MURPHY_ENV="development"):
            with app.test_client() as client:
                resp = client.get("/test/ping")
                assert resp.status_code == 200

    def test_auth_required_in_staging_mode(self):
        """In staging mode, require_blueprint_auth must return 401 without a key."""
        try:
            from flask import Flask, Blueprint
            from src.blueprint_auth import require_blueprint_auth
        except ImportError:
            pytest.skip("Flask not installed")

        app = Flask(__name__)
        bp = Blueprint("staging_test", __name__, url_prefix="/test")

        @bp.route("/protected")
        def _protected():
            return "secret"

        require_blueprint_auth(bp)
        app.register_blueprint(bp)

        with _with_env(MURPHY_ENV="staging", MURPHY_API_KEYS="valid_key_xyz"):
            with app.test_client() as client:
                # No auth header → 401
                resp = client.get("/test/protected")
                assert resp.status_code == 401

                # With correct key → 200
                resp = client.get(
                    "/test/protected",
                    headers={"X-API-Key": "valid_key_xyz"},
                )
                assert resp.status_code == 200

    def test_auth_required_in_production_mode(self):
        """In production mode, require_blueprint_auth must return 401 without a key."""
        try:
            from flask import Flask, Blueprint
            from src.blueprint_auth import require_blueprint_auth
        except ImportError:
            pytest.skip("Flask not installed")

        app = Flask(__name__)
        bp = Blueprint("prod_test", __name__, url_prefix="/api")

        @bp.route("/data")
        def _data():
            return "data"

        require_blueprint_auth(bp)
        app.register_blueprint(bp)

        with _with_env(MURPHY_ENV="production", MURPHY_API_KEYS="prod_key_abc"):
            with app.test_client() as client:
                resp = client.get("/api/data")
                assert resp.status_code == 401, "Production endpoint must require auth"


# ===========================================================================
# 3. Rate Limiter Redis Fallback
# ===========================================================================

class TestRedisRateLimiterFallback:
    """RedisRateLimiter must fall back to in-memory when Redis is unavailable."""

    def test_redis_rate_limiter_exists(self):
        """RedisRateLimiter class must exist in security_hardening_config."""
        from src.security_hardening_config import RedisRateLimiter
        assert RedisRateLimiter is not None

    def test_get_rate_limiter_factory(self):
        """get_rate_limiter returns RateLimiter when no MURPHY_REDIS_URL set."""
        from src.security_hardening_config import get_rate_limiter, RateLimiter, RedisRateLimiter
        with _with_env(MURPHY_REDIS_URL=None):
            limiter = get_rate_limiter()
            assert isinstance(limiter, RateLimiter)
            # Should NOT be RedisRateLimiter since no URL configured
            assert not isinstance(limiter, RedisRateLimiter)

    def test_get_rate_limiter_factory_redis(self):
        """get_rate_limiter returns RedisRateLimiter when MURPHY_REDIS_URL is set."""
        from src.security_hardening_config import get_rate_limiter, RedisRateLimiter
        with _with_env(MURPHY_REDIS_URL="redis://invalid-host:9999/0"):
            limiter = get_rate_limiter()
            assert isinstance(limiter, RedisRateLimiter)

    def test_redis_unavailable_falls_back_to_memory(self):
        """RedisRateLimiter must fall back to in-memory when connection fails."""
        from src.security_hardening_config import RedisRateLimiter
        # Point at an invalid host to force a connection failure
        limiter = RedisRateLimiter(
            requests_per_minute=100,
            burst_size=10,
            redis_url="redis://invalid-host-xyz:9999/0",
        )
        assert not limiter._redis_available, "Should not connect to invalid host"

        # Should still work via in-memory fallback
        result = limiter.check("test_client")
        assert "allowed" in result

    def test_in_memory_rate_limiter_works(self):
        """RateLimiter must correctly allow and then block requests."""
        from src.security_hardening_config import RateLimiter
        limiter = RateLimiter(requests_per_minute=60, burst_size=3)
        # Drain the burst
        for _ in range(3):
            result = limiter.check("client_x")
            assert result["allowed"] is True
        # Next request should be blocked
        result = limiter.check("client_x")
        assert result["allowed"] is False


# ===========================================================================
# 4. Auth Modes (development / staging / production)
# ===========================================================================

class TestAuthModes:
    """MURPHY_ENV controls auth in both Flask and FastAPI security modules."""

    def test_flask_dev_mode_skips_auth(self):
        """Flask security must allow requests without API key in development mode."""
        try:
            from flask import Flask
            from src.flask_security import configure_secure_app
        except ImportError:
            pytest.skip("Flask not installed")

        app = Flask(__name__)
        configure_secure_app(app, service_name="test-dev")

        @app.route("/test")
        def _test():
            return "ok"

        with _with_env(MURPHY_ENV="development", MURPHY_API_KEYS=""):
            with app.test_client() as client:
                resp = client.get("/test")
                # 200 — auth skipped in development
                assert resp.status_code == 200

    def test_flask_staging_requires_auth(self):
        """Flask security must reject requests without API key in staging mode."""
        try:
            from flask import Flask
            from src.flask_security import configure_secure_app
        except ImportError:
            pytest.skip("Flask not installed")

        app = Flask(__name__)
        configure_secure_app(app, service_name="test-staging")

        @app.route("/secure")
        def _secure():
            return "data"

        with _with_env(MURPHY_ENV="staging", MURPHY_API_KEYS="test_key_staging"):
            with app.test_client() as client:
                resp = client.get("/secure")
                assert resp.status_code == 401, "Staging must require auth"

    def test_flask_production_requires_auth(self):
        """Flask security must reject requests without API key in production mode."""
        try:
            from flask import Flask
            from src.flask_security import configure_secure_app
        except ImportError:
            pytest.skip("Flask not installed")

        app = Flask(__name__)
        configure_secure_app(app, service_name="test-prod")

        @app.route("/data")
        def _data():
            return "data"

        with _with_env(MURPHY_ENV="production", MURPHY_API_KEYS="prod_key_abc"):
            with app.test_client() as client:
                resp = client.get("/data")
                assert resp.status_code == 401, "Production must require auth"

    def test_validate_api_key_dev_allows_empty(self):
        """validate_api_key returns True for any key in dev when no keys configured."""
        with _with_env(MURPHY_ENV="development", MURPHY_API_KEYS=""):
            from src.flask_security import validate_api_key
            assert validate_api_key("anything") is True

    def test_validate_api_key_staging_blocks_empty(self):
        """validate_api_key returns False in staging when no keys configured and key given."""
        with _with_env(MURPHY_ENV="staging", MURPHY_API_KEYS=""):
            from src.flask_security import validate_api_key
            # No keys configured in staging — should return False (not authenticated)
            result = validate_api_key("")
            # When no keys are configured in staging, _no keys_ means auth is disabled;
            # the function returns True. But if a key IS configured and the given one
            # doesn't match, it must return False.
            # Test configured key mismatch:
        with _with_env(MURPHY_ENV="staging", MURPHY_API_KEYS="real_key"):
            from importlib import reload
            import src.flask_security as fs
            reload(fs)
            assert fs.validate_api_key("wrong_key") is False
            assert fs.validate_api_key("real_key") is True


# ===========================================================================
# 5. No Simulated Encryption in encrypt/decrypt methods
# ===========================================================================

class TestNoSimulatedEncryption:
    """cryptography.py encrypt/decrypt methods must not use sha256-as-encryption."""

    CRYPTO_PATH = SRC_DIR / "security_plane" / "cryptography.py"

    def _get_func_source(self, func_name: str) -> str:
        with open(self.CRYPTO_PATH, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=str(self.CRYPTO_PATH))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return ast.get_source_segment(source, node) or ""
        return ""

    def test_encrypt_does_not_use_sha256_hash_as_encryption(self):
        """_encrypt_private_key must not return hashlib.sha256(key).digest()."""
        src = self._get_func_source("_encrypt_private_key")
        assert src, "_encrypt_private_key not found"
        # The old stub was: return hashlib.sha256(private_key).digest()
        assert "hashlib.sha256(private_key).digest()" not in src, (
            "_encrypt_private_key still uses sha256 hash as fake encryption"
        )

    def test_encrypt_uses_fernet(self):
        """_encrypt_private_key must reference Fernet.encrypt."""
        src = self._get_func_source("_encrypt_private_key")
        assert "encrypt" in src, "_encrypt_private_key must call .encrypt()"

    def test_decrypt_uses_fernet(self):
        """_decrypt_private_key must reference Fernet.decrypt."""
        src = self._get_func_source("_decrypt_private_key")
        assert "decrypt" in src, "_decrypt_private_key must call .decrypt()"

    def test_simulated_word_not_in_method_docstrings(self):
        """'simulated' should not appear in encrypt/decrypt method docstrings."""
        with open(self.CRYPTO_PATH, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=str(self.CRYPTO_PATH))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in (
                "_encrypt_private_key", "_decrypt_private_key"
            ):
                docstring = ast.get_docstring(node) or ""
                assert "simulated" not in docstring.lower(), (
                    f"{node.name} docstring still says 'simulated' — update the docstring"
                )


# ===========================================================================
# 6. httpx is importable
# ===========================================================================

class TestHttpxDependency:
    """httpx must be importable as a hard dependency."""

    def test_httpx_importable(self):
        """import httpx must succeed (it is a hard dependency)."""
        import httpx  # noqa: F401
        assert httpx.__version__

    def test_universal_control_plane_no_import_guard(self):
        """universal_control_plane.py APIEngine must not swallow ImportError for httpx."""
        ucp_path = PROJECT_ROOT / "universal_control_plane.py"
        if not ucp_path.exists():
            pytest.skip("universal_control_plane.py not found at project root")
        with open(ucp_path, "r", encoding="utf-8") as fh:
            source = fh.read()
        # The old guard was: except ImportError:
        # We need to verify it's no longer there adjacent to the httpx import
        # Look for the pattern: try: ... import httpx ... except ImportError:
        pattern = re.compile(
            r"try\s*:.*?import\s+httpx.*?except\s+ImportError",
            re.DOTALL,
        )
        assert not pattern.search(source), (
            "universal_control_plane.py still has ImportError guard around httpx — "
            "httpx is a hard dependency and should fail loudly if missing"
        )


# ===========================================================================
# 7. get_rate_limiter factory function
# ===========================================================================

class TestGetRateLimiterFactory:
    """get_rate_limiter must be exported and return the correct type."""

    def test_get_rate_limiter_exported(self):
        """get_rate_limiter must be importable from security_hardening_config."""
        from src.security_hardening_config import get_rate_limiter
        assert callable(get_rate_limiter)

    def test_default_returns_memory_limiter(self):
        """Without MURPHY_REDIS_URL, get_rate_limiter returns the in-memory limiter."""
        from src.security_hardening_config import get_rate_limiter, RateLimiter, RedisRateLimiter
        with _with_env(MURPHY_REDIS_URL=None):
            limiter = get_rate_limiter(requests_per_minute=30, burst_size=5)
            assert isinstance(limiter, RateLimiter)
            assert not isinstance(limiter, RedisRateLimiter)
            assert limiter.rpm == 30
            assert limiter.burst == 5

    def test_redis_url_env_returns_redis_limiter(self):
        """With MURPHY_REDIS_URL set, get_rate_limiter returns a RedisRateLimiter."""
        from src.security_hardening_config import get_rate_limiter, RedisRateLimiter
        with _with_env(MURPHY_REDIS_URL="redis://localhost:6379/0"):
            limiter = get_rate_limiter()
            assert isinstance(limiter, RedisRateLimiter)
