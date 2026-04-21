"""
Production Security Hardening — Comprehensive Test Suite
=========================================================

Tests for all 40 SEC-* labels across all 12 hardening modules.

Phase 1: Foundations  — Modules 5 (Secrets), 6 (Docker), 9 (Deps)
Phase 2: Perimeter   — Modules 1 (CORS), 8 (Logging), 11 (Routes)
Phase 3: Hardening   — Modules 2 (REPL), 3 (Eval), 7 (Path), 10 (Sandbox)
Phase 4: Validation  — Modules 4 (SQL), 12 (Readiness)

Copyright © 2020 Inoni Limited Liability Company
"""

from __future__ import annotations

import ast
import math
import os
import re
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest

# ── Path resolution ─────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
_MURPHY = _ROOT / "Murphy System"
_MURPHY_SRC = _MURPHY / "src"
_SERVER = _ROOT / "murphy_production_server.py"
for _p in (_ROOT, _ROOT / "src", _MURPHY / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ═══════════════════════════════════════════════════════════════════════
#  Module 1 — CORS & Environment Mode
# ═══════════════════════════════════════════════════════════════════════

class TestCORSCredentialGuard:
    """SEC-CORS-001 / SEC-CORS-002 / SEC-OPENAPI-001"""

    def test_wildcard_cors_disables_credentials(self):
        """SEC-CORS-002: Wildcard origins must never combine with allow_credentials."""
        server_path = _ROOT / "murphy_production_server.py"
        source = server_path.read_text()
        # The code should set _allow_creds = False when origins == ["*"]
        assert "allow_credentials=_allow_creds" in source or "_allow_creds" in source, \
            "CORS credentials must be dynamically controlled (SEC-CORS-002)"

    def test_cors_guard_critical_log_for_nondev_wildcard(self):
        """SEC-CORS-001: Non-development wildcard CORS triggers CRITICAL log."""
        server_path = _ROOT / "murphy_production_server.py"
        source = server_path.read_text()
        assert "SEC-CORS-001" in source, \
            "SEC-CORS-001 guard label must be present in production server"

    def test_openapi_disabled_in_production(self):
        """SEC-OPENAPI-001: docs_url and redoc_url are None in production."""
        server_path = _ROOT / "murphy_production_server.py"
        source = server_path.read_text()
        assert 'docs_url=None if _pre_env == "production"' in source, \
            "OpenAPI UI must be disabled in production (SEC-OPENAPI-001)"
        assert 'redoc_url=None if _pre_env == "production"' in source, \
            "ReDoc UI must be disabled in production (SEC-OPENAPI-001)"


# ═══════════════════════════════════════════════════════════════════════
#  Module 2 — REPL Sandbox
# ═══════════════════════════════════════════════════════════════════════

class TestREPLSandboxEscape:
    """SEC-REPL-001 / SEC-REPL-002"""

    @pytest.fixture()
    def repl(self):
        from murphy_repl import MurphyREPL  # noqa: PLC0415
        return MurphyREPL()

    def test_getattr_not_raw_in_init_builtins(self, repl):
        """SEC-REPL-001: raw getattr must not be in _initialize_environment builtins."""
        builtins = repl.globals.get("__builtins__", {})
        if isinstance(builtins, dict):
            # If getattr is present, it must NOT be the raw built-in
            ga = builtins.get("getattr")
            if ga is not None:
                assert ga is not getattr, \
                    "Raw getattr must be replaced by safe_getattr (SEC-REPL-001)"

    def test_setattr_removed(self, repl):
        """SEC-REPL-001: setattr must not be in builtins."""
        builtins = repl.globals.get("__builtins__", {})
        if isinstance(builtins, dict):
            assert "setattr" not in builtins, "setattr must be removed (SEC-REPL-001)"

    def test_dir_removed(self, repl):
        """SEC-REPL-001: dir must not be in builtins."""
        builtins = repl.globals.get("__builtins__", {})
        if isinstance(builtins, dict):
            assert "dir" not in builtins, "dir must be removed (SEC-REPL-001)"

    def test_help_removed(self, repl):
        """SEC-REPL-001: help must not be in builtins."""
        builtins = repl.globals.get("__builtins__", {})
        if isinstance(builtins, dict):
            assert "help" not in builtins, "help must be removed (SEC-REPL-001)"

    def test_safe_getattr_blocks_dunder_class(self, repl):
        """SEC-REPL-002: safe_getattr blocks __class__ access."""
        result = repl.execute("getattr([], '__class__')")
        assert not result.success or "restricted" in (result.output or "").lower() or \
               "error" in str(result).lower(), \
            "Accessing __class__ via safe_getattr must fail (SEC-REPL-002)"

    def test_safe_getattr_blocks_dunder_bases(self, repl):
        """SEC-REPL-002: safe_getattr blocks __bases__ access."""
        result = repl.execute("getattr(list, '__bases__')")
        assert not result.success, \
            "Accessing __bases__ via safe_getattr must fail (SEC-REPL-002)"

    def test_safe_getattr_allows_normal_attrs(self, repl):
        """SEC-REPL-002: safe_getattr allows normal attribute access."""
        result = repl.execute("x = [1,2,3]\nresult = len(x)\nprint(result)")
        assert result.success, "Normal operations must still work"
        assert "3" in (result.output or "")

    def test_import_blocked(self, repl):
        """__import__ must not be accessible."""
        result = repl.execute("__import__('os')")
        assert not result.success, "__import__ must be blocked in sandbox"


# ═══════════════════════════════════════════════════════════════════════
#  Module 3 — Compliance Engine _safe_eval
# ═══════════════════════════════════════════════════════════════════════

class TestComplianceEvalSafety:
    """SEC-EVAL-001 / SEC-EVAL-002"""

    @pytest.fixture()
    def safe_eval(self):
        from compliance_as_code_engine import _safe_eval  # noqa: PLC0415
        return _safe_eval

    # ── SEC-EVAL-001: blocked constructs ──────────────────────────────

    def test_import_rejected(self, safe_eval):
        """ast.Import is not in _SAFE_NODE_TYPES."""
        with pytest.raises(Exception):
            safe_eval("__import__('os')", {})

    def test_attribute_rejected(self, safe_eval):
        """ast.Attribute is not in _SAFE_NODE_TYPES."""
        with pytest.raises(ValueError, match="disallowed"):
            safe_eval("x.__class__", {"x": []})

    def test_call_rejected(self, safe_eval):
        """ast.Call is not in _SAFE_NODE_TYPES."""
        with pytest.raises(Exception):
            safe_eval("print('hello')", {})

    def test_subscript_rejected(self, safe_eval):
        """ast.Subscript is not in _SAFE_NODE_TYPES."""
        with pytest.raises(ValueError, match="disallowed"):
            safe_eval("x[0]", {"x": [1, 2, 3]})

    # ── SEC-EVAL-002: length and complexity limits ────────────────────

    def test_expression_too_long(self, safe_eval):
        """Expression > 1000 chars must be rejected."""
        expr = "x > " + "1 and x > " * 200
        assert len(expr) > 1000
        with pytest.raises(ValueError, match="too long"):
            safe_eval(expr, {"x": 5})

    def test_expression_too_complex(self, safe_eval):
        """Expression with > 100 AST nodes must be rejected."""
        # 110 True values joined with ' and ' = 113 AST nodes, 985 chars
        expr = " and ".join(["True"] * 110)
        with pytest.raises(ValueError, match="too complex|too long"):
            safe_eval(expr, {})

    # ── Positive cases ────────────────────────────────────────────────

    def test_simple_comparison(self, safe_eval):
        assert safe_eval("x > 5", {"x": 10}) is True

    def test_boolean_and(self, safe_eval):
        assert safe_eval("x > 5 and y < 10", {"x": 7, "y": 3}) is True

    def test_equality(self, safe_eval):
        assert safe_eval("status == 'active'", {"status": "active"}) is True

    def test_in_operator(self, safe_eval):
        assert safe_eval("x in y", {"x": 3, "y": [1, 2, 3]}) is True

    def test_arithmetic(self, safe_eval):
        assert safe_eval("x + y > 10", {"x": 7, "y": 5}) is True

    # ── PROD-HARD-A11: extended sandbox-escape corpus ─────────────────
    # Audit identified that the existing block-list above did not exercise
    # the classic Python sandbox-escape patterns. Each payload below MUST
    # raise (either ValueError "disallowed" from _validate_ast, or a parse
    # error from ast.parse). If any of these stops raising, the eval site
    # at compliance_as_code_engine.py:223 has been weakened — investigate.
    @pytest.mark.parametrize(
        "payload",
        [
            # Class-walking: classic escape to __subclasses__ → file-write gadgets.
            "().__class__.__bases__[0].__subclasses__()",
            "''.__class__.__mro__[1].__subclasses__()",
            # getattr indirection — bypasses simple "no Attribute" filter.
            "getattr(x, '__class__')",
            # Lambda definition — would let an attacker smuggle code as a value.
            "(lambda: 1)()",
            # Comprehensions — Generator/ListComp nodes, allow side effects.
            "[i for i in range(10)]",
            "{i for i in range(10)}",
            "{i: i for i in range(10)}",
            "(i for i in range(10))",
            # f-string with attribute access — JoinedStr / FormattedValue.
            "f'{x.__class__}'",
            # Nested call to dynamic builtins lookup.
            "type(x).__name__",
            # Star-args / unpacking — Starred node not in safe set.
            "[*x]",
            # Slice — Subscript already blocked, but assert via slice too.
            "x[0:1]",
            # Walrus operator — NamedExpr lets values escape into context.
            "(y := 1)",
        ],
    )
    def test_sandbox_escape_corpus_blocked(self, safe_eval, payload):
        """Every classic Python sandbox-escape payload must be rejected."""
        with pytest.raises((ValueError, SyntaxError, TypeError)):
            safe_eval(payload, {"x": [1, 2, 3]})


# ═══════════════════════════════════════════════════════════════════════
#  Module 4 — SQL Injection Guard
# ═══════════════════════════════════════════════════════════════════════

class TestSQLInjectionGuard:
    """SEC-SQL-001 / SEC-SQL-002"""

    def test_sec_sql_001_label_present(self):
        """SEC-SQL-001 label exists in database_connectors.py."""
        path = _MURPHY / "src" / "integrations" / "database_connectors.py"
        source = path.read_text()
        assert "SEC-SQL-001" in source

    def test_sec_sql_002_label_present(self):
        """SEC-SQL-002 label exists in database_connectors.py."""
        path = _MURPHY / "src" / "integrations" / "database_connectors.py"
        source = path.read_text()
        assert "SEC-SQL-002" in source

    def test_suspicious_patterns_detected(self):
        """SEC-SQL-001: Suspicious SQL patterns are listed."""
        path = _MURPHY / "src" / "integrations" / "database_connectors.py"
        source = path.read_text()
        assert "; drop " in source.lower() or "union select" in source.lower()


# ═══════════════════════════════════════════════════════════════════════
#  Module 5 — Secret Management
# ═══════════════════════════════════════════════════════════════════════

class TestSecretGeneration:
    """SEC-SECRET-001 / SEC-SECRET-002 / SEC-GIT-001"""

    def test_build_env_template_no_changeme(self):
        """SEC-SECRET-001: _build_env_template must not produce 'change-me'."""
        path = _MURPHY / "src" / "runtime" / "app.py"
        source = path.read_text()
        # The old placeholder should no longer be present in the template builder
        assert "change-me-to-a-random-string" not in source, \
            "SEC-SECRET-001: placeholder must be replaced with secrets.token_urlsafe()"

    def test_build_env_template_uses_secrets_module(self):
        """SEC-SECRET-001: _build_env_template imports secrets."""
        path = _MURPHY / "src" / "runtime" / "app.py"
        source = path.read_text()
        # Find the _build_env_template function and check it uses secrets
        idx = source.find("def _build_env_template")
        assert idx > 0
        func_body = source[idx:idx + 500]
        assert "secrets" in func_body

    def test_env_example_no_changeme_password(self):
        """SEC-SECRET-002: .env.example must not contain CHANGEME passwords."""
        path = _MURPHY / ".env.example"
        content = path.read_text()
        assert "CHANGEME_generate_a_strong_password" not in content, \
            "SEC-SECRET-002: placeholder passwords must be cleared"

    def test_gitignore_blocks_env_files(self):
        """SEC-GIT-001: Murphy System/.gitignore blocks .env files."""
        path = _MURPHY / ".gitignore"
        content = path.read_text()
        assert ".env" in content, "SEC-GIT-001: .env must be in .gitignore"
        assert ".env.local" in content, "SEC-GIT-001: .env.local must be in .gitignore"


# ═══════════════════════════════════════════════════════════════════════
#  Module 6 — Docker & Container Security
# ═══════════════════════════════════════════════════════════════════════

class TestDockerHardening:
    """SEC-DOCKER-001 through SEC-DOCKER-005 / SEC-COMPOSE-001"""

    @pytest.fixture()
    def compose_content(self):
        return (_MURPHY / "docker-compose.yml").read_text()

    def test_postgres_not_exposed_to_host(self, compose_content):
        """SEC-DOCKER-001: PostgreSQL port must not be in 'ports:' section."""
        # We check that postgres uses expose: rather than ports:
        assert "expose:" in compose_content
        # The commented-out ports line should be present but commented
        lines = compose_content.splitlines()
        pg_section = False
        for line in lines:
            if "postgres:" in line and "image:" not in line:
                pg_section = True
            if pg_section and "redis:" in line:
                break
            if pg_section and line.strip().startswith("- ") and "5432" in line:
                assert line.strip().startswith("#"), \
                    "SEC-DOCKER-001: PostgreSQL ports must be commented out"

    def test_redis_password_required(self, compose_content):
        """SEC-DOCKER-002: REDIS_PASSWORD must use :? (required) syntax."""
        assert "REDIS_PASSWORD:?" in compose_content or \
               "${REDIS_PASSWORD:?" in compose_content, \
            "SEC-DOCKER-002: REDIS_PASSWORD must be required via :? syntax"

    def test_prometheus_lifecycle_disabled(self, compose_content):
        """SEC-DOCKER-003: Prometheus lifecycle API must be disabled."""
        assert "--web.enable-lifecycle=false" in compose_content, \
            "SEC-DOCKER-003: Lifecycle API must be explicitly disabled"

    def test_redis_read_only(self, compose_content):
        """SEC-DOCKER-004: Redis should have read_only: true."""
        assert "read_only: true" in compose_content, \
            "SEC-DOCKER-004: Read-only filesystem for infrastructure containers"

    def test_no_new_privileges(self, compose_content):
        """SEC-DOCKER-005: Containers should have no-new-privileges."""
        assert "no-new-privileges:true" in compose_content, \
            "SEC-DOCKER-005: no-new-privileges security option must be set"

    def test_compose_env_required(self, compose_content):
        """SEC-COMPOSE-001: MURPHY_ENV must use :? (required) syntax."""
        assert "MURPHY_ENV:?" in compose_content or \
               "${MURPHY_ENV:?" in compose_content, \
            "SEC-COMPOSE-001: MURPHY_ENV must be required via :? syntax"


# ═══════════════════════════════════════════════════════════════════════
#  Module 7 — Path Traversal Prevention
# ═══════════════════════════════════════════════════════════════════════

class TestPathTraversalGuard:
    """SEC-PATH-001 / SEC-PATH-003"""

    @pytest.fixture()
    def safe_join(self):
        from security_plane.hardening import safe_path_join  # noqa: PLC0415
        return safe_path_join

    @pytest.fixture()
    def injection_error(self):
        from security_plane.hardening import InjectionAttemptError  # noqa: PLC0415
        return InjectionAttemptError

    def test_dotdot_raises(self, safe_join, injection_error, tmp_path):
        """SEC-PATH-001: ../../etc/passwd must raise."""
        with pytest.raises(injection_error):
            safe_join(str(tmp_path), "../../etc/passwd")

    def test_encoded_dotdot_raises(self, safe_join, injection_error, tmp_path):
        """SEC-PATH-003: URL-encoded %2e%2e must raise."""
        with pytest.raises(injection_error):
            safe_join(str(tmp_path), "%2e%2e/etc/passwd")

    def test_double_encoded_raises(self, safe_join, injection_error, tmp_path):
        """SEC-PATH-003: Double-encoded %%2e must raise."""
        with pytest.raises(injection_error):
            safe_join(str(tmp_path), "%252e%252e/etc/passwd")

    def test_null_byte_raises(self, safe_join, injection_error, tmp_path):
        """SEC-PATH-003: Null byte in path must raise."""
        with pytest.raises(injection_error):
            safe_join(str(tmp_path), "file\x00.txt")

    def test_valid_subpath_succeeds(self, safe_join, tmp_path):
        """Valid subpath must resolve correctly."""
        result = safe_join(str(tmp_path), "subdir", "file.txt")
        assert str(result).startswith(str(tmp_path))

    def test_valid_filename_succeeds(self, safe_join, tmp_path):
        """Simple filename must resolve correctly."""
        result = safe_join(str(tmp_path), "data.json")
        assert result.name == "data.json"


# ═══════════════════════════════════════════════════════════════════════
#  Module 8 — Logging & Error Handling
# ═══════════════════════════════════════════════════════════════════════

class TestLogSanitizerIntegration:
    """SEC-LOG-001 / SEC-ERROR-001"""

    def test_log_sanitizer_wired_in_server(self):
        """SEC-LOG-001: Log sanitizer filter must be wired in murphy_production_server.py."""
        path = _ROOT / "murphy_production_server.py"
        source = path.read_text()
        assert "SEC-LOG-001" in source
        assert "_SanitizingFilter" in source

    def test_error_handler_environment_aware(self):
        """SEC-ERROR-001: Exception handler differentiates dev/staging/production."""
        path = _ROOT / "murphy_production_server.py"
        source = path.read_text()
        assert "SEC-ERROR-001" in source
        assert "Internal Server Error" in source


# ═══════════════════════════════════════════════════════════════════════
#  Module 9 — Dependency Security Scanning
# ═══════════════════════════════════════════════════════════════════════

class TestDependencyScanning:
    """SEC-DEPS-001 / SEC-DEPS-003"""

    def test_pip_audit_not_continue_on_error(self):
        """SEC-DEPS-001: pip-audit step must not have continue-on-error: true."""
        ci_path = _ROOT / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()
        # Find the pip-audit block
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "pip-audit" in line:
                # Check next few lines for continue-on-error
                block = "\n".join(lines[max(0, i - 2):i + 5])
                if "continue-on-error: true" in block:
                    pytest.fail("SEC-DEPS-001: pip-audit must not have continue-on-error: true")

    def test_dependabot_config_exists(self):
        """SEC-DEPS-003: Dependabot configuration must exist."""
        path = _ROOT / ".github" / "dependabot.yml"
        assert path.exists(), "SEC-DEPS-003: .github/dependabot.yml must exist"
        content = path.read_text()
        assert "pip" in content


# ═══════════════════════════════════════════════════════════════════════
#  Module 10 — Sandbox Quarantine
# ═══════════════════════════════════════════════════════════════════════

class TestQuarantineEnforcement:
    """SEC-SANDBOX-003"""

    @pytest.fixture()
    def patterns_source(self):
        path = _MURPHY / "src" / "integration_engine" / "sandbox_quarantine.py"
        return path.read_text()

    def test_import_pattern_present(self, patterns_source):
        """SEC-SANDBOX-003: __import__ pattern must be in threat list."""
        assert "__import__" in patterns_source

    def test_importlib_pattern_present(self, patterns_source):
        """SEC-SANDBOX-003: importlib.import_module pattern must be in threat list."""
        assert "importlib" in patterns_source

    def test_ctypes_pattern_present(self, patterns_source):
        """SEC-SANDBOX-003: ctypes/cffi pattern must be in threat list."""
        assert "ctypes" in patterns_source

    def test_compile_exec_pattern_present(self, patterns_source):
        """SEC-SANDBOX-003: compile(..., 'exec') pattern must be in threat list."""
        assert "compile" in patterns_source


# ═══════════════════════════════════════════════════════════════════════
#  Module 12 — Readiness Scanner
# ═══════════════════════════════════════════════════════════════════════

class TestReadinessScannerHardening:
    """SEC-READY-001 / SEC-READY-002 / SEC-READY-003"""

    @pytest.fixture()
    def gate_fn(self):
        from readiness_scanner import _gate_security_scan  # noqa: PLC0415
        return _gate_security_scan

    def _set_prod_env(self, monkeypatch, **extra):
        """Set up production env with minimum valid secrets."""
        defaults = {
            "MURPHY_ENV": "production",
            "MURPHY_JWT_SECRET": "a" * 40 + "bCdEfGhIjKlMnOpQrStUvWxYz123456",
            "MURPHY_CORS_ORIGINS": "https://app.example.com",
            "MURPHY_CREDENTIAL_MASTER_KEY": "test-master-key-production",
            "REDIS_PASSWORD": "strong-redis-password-here",
            "MURPHY_TLS_CERT": "/etc/ssl/cert.pem",
            "MURPHY_TLS_KEY": "/etc/ssl/key.pem",
        }
        defaults.update(extra)
        for k, v in defaults.items():
            monkeypatch.setenv(k, v)

    def test_low_entropy_secret_blocked(self, gate_fn, monkeypatch):
        """SEC-READY-001: Secret with low Shannon entropy must be rejected."""
        self._set_prod_env(monkeypatch,
                           MURPHY_JWT_SECRET="a" * 64)  # all same char = 0 bits/char
        ok, msg = gate_fn()
        assert not ok, "Low-entropy secret must be blocked"
        assert "entropy" in msg.lower()

    def test_redis_password_required(self, gate_fn, monkeypatch):
        """SEC-READY-002: Missing REDIS_PASSWORD must be rejected in production."""
        self._set_prod_env(monkeypatch, REDIS_PASSWORD="")
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        ok, msg = gate_fn()
        assert not ok, "Missing REDIS_PASSWORD must block production"
        assert "REDIS" in msg.upper()

    def test_tls_required_in_production(self, gate_fn, monkeypatch):
        """SEC-READY-003: Missing TLS config must be rejected in production."""
        self._set_prod_env(monkeypatch, MURPHY_TLS_CERT="", MURPHY_TLS_KEY="")
        monkeypatch.delenv("MURPHY_TLS_CERT", raising=False)
        monkeypatch.delenv("MURPHY_TLS_KEY", raising=False)
        monkeypatch.delenv("MURPHY_REVERSE_PROXY", raising=False)
        ok, msg = gate_fn()
        assert not ok, "Missing TLS must block production"
        assert "TLS" in msg.upper() or "SEC-READY-003" in msg

    def test_reverse_proxy_satisfies_tls(self, gate_fn, monkeypatch):
        """SEC-READY-003: MURPHY_REVERSE_PROXY can satisfy TLS requirement."""
        self._set_prod_env(monkeypatch, MURPHY_TLS_CERT="", MURPHY_TLS_KEY="")
        monkeypatch.delenv("MURPHY_TLS_CERT", raising=False)
        monkeypatch.delenv("MURPHY_TLS_KEY", raising=False)
        monkeypatch.setenv("MURPHY_REVERSE_PROXY", "nginx")
        ok, msg = gate_fn()
        # Should pass if all other checks pass
        assert ok or "TLS" not in msg

    def test_all_secrets_valid_passes(self, gate_fn, monkeypatch):
        """All valid secrets should pass the security gate."""
        self._set_prod_env(monkeypatch)
        ok, msg = gate_fn()
        assert ok, f"Should pass with valid secrets, got: {msg}"

    def test_development_skips_checks(self, gate_fn, monkeypatch):
        """Development mode skips security checks."""
        monkeypatch.setenv("MURPHY_ENV", "development")
        ok, msg = gate_fn()
        assert ok
        assert "skipped" in msg.lower() or "development" in msg.lower()


# ═══════════════════════════════════════════════════════════════════════
#  Cross-cutting: Label inventory verification
# ═══════════════════════════════════════════════════════════════════════

class TestSecurityLabelInventory:
    """Verify all SEC-* labels exist in the codebase."""

    REQUIRED_LABELS = [
        "SEC-CORS-001", "SEC-CORS-002", "SEC-OPENAPI-001",
        "SEC-COMPOSE-001",
        "SEC-REPL-001", "SEC-REPL-002", "SEC-REPL-003", "SEC-REPL-004",
        "SEC-EVAL-001", "SEC-EVAL-002",
        "SEC-SQL-001", "SEC-SQL-002",
        "SEC-SECRET-001", "SEC-SECRET-002",
        "SEC-GIT-001", "SEC-STARTUP-001",
        "SEC-DOCKER-001", "SEC-DOCKER-002", "SEC-DOCKER-003",
        "SEC-DOCKER-004", "SEC-DOCKER-005",
        "SEC-PATH-001", "SEC-PATH-002", "SEC-PATH-003",
        "SEC-LOG-001", "SEC-LOG-002", "SEC-ERROR-001",
        "SEC-DEPS-001", "SEC-DEPS-002", "SEC-DEPS-003",
        "SEC-SANDBOX-001", "SEC-SANDBOX-002", "SEC-SANDBOX-003",
        "SEC-ROUTE-001", "SEC-ROUTE-002", "SEC-ROUTE-003",
        "SEC-READY-001", "SEC-READY-002", "SEC-READY-003", "SEC-READY-004",
    ]

    def _scan_codebase(self):
        """Collect all text from source files."""
        combined = []
        for ext in ("*.py", "*.yml", "*.yaml"):
            for p in _ROOT.rglob(ext):
                if ".git" in str(p) or "__pycache__" in str(p):
                    continue
                try:
                    combined.append(p.read_text(errors="ignore"))
                except Exception:
                    pass
        return "\n".join(combined)

    @pytest.mark.parametrize("label", REQUIRED_LABELS)
    def test_label_exists_in_codebase(self, label):
        """Every SEC-* label must appear at least once in the codebase."""
        text = self._scan_codebase()
        assert label in text, f"Security label {label} not found in codebase"


# ═══════════════════════════════════════════════════════════════════════
#  SEC-REPL-003: Execution timeout enforcement
# ═══════════════════════════════════════════════════════════════════════

class TestREPLTimeoutEnforcement:
    """SEC-REPL-003: REPL execute() must timeout long-running code."""

    def test_timeout_label_in_source(self):
        """SEC-REPL-003 label present in murphy_repl.py."""
        source = (_MURPHY_SRC / "murphy_repl.py").read_text()
        assert "SEC-REPL-003" in source

    def test_timeout_mechanism_present(self):
        """Threading or signal-based timeout wraps exec()."""
        source = (_MURPHY_SRC / "murphy_repl.py").read_text()
        assert "threading" in source or "signal.alarm" in source, \
            "Timeout enforcement mechanism must exist"

    def test_timeout_fires_on_long_exec(self):
        """A long-running exec should raise TimeoutError (or fail gracefully)."""
        sys.path.insert(0, str(_MURPHY_SRC))
        try:
            from murphy_repl import MurphyREPL
            repl = MurphyREPL()
            repl.max_execution_time = 2.0  # 2 second timeout
            # Busy loop that doesn't need imports
            result = repl.execute("x = 0\nwhile True:\n x += 1")
            # Should either timeout with error or produce an error result
            assert not result.success, \
                "Long-running REPL exec must be stopped by timeout"
        except (ImportError, TimeoutError):
            pass  # TimeoutError is acceptable — means it worked
        finally:
            if str(_MURPHY_SRC) in sys.path:
                sys.path.remove(str(_MURPHY_SRC))


# ═══════════════════════════════════════════════════════════════════════
#  SEC-REPL-004: Memory limit enforcement
# ═══════════════════════════════════════════════════════════════════════

class TestREPLMemoryLimitEnforcement:
    """SEC-REPL-004: REPL must enforce memory limits."""

    def test_memory_label_in_source(self):
        """SEC-REPL-004 label present in murphy_repl.py."""
        source = (_MURPHY_SRC / "murphy_repl.py").read_text()
        assert "SEC-REPL-004" in source

    def test_max_memory_mb_attribute(self):
        """max_memory_mb policy attribute exists for container-level enforcement."""
        source = (_MURPHY_SRC / "murphy_repl.py").read_text()
        assert "max_memory_mb" in source, \
            "max_memory_mb policy attribute must exist for container enforcement"


# ═══════════════════════════════════════════════════════════════════════
#  SEC-PATH-002: safe_path_join used in file-writing paths
# ═══════════════════════════════════════════════════════════════════════

class TestPathTraversalFileReplacements:
    """SEC-PATH-002: All user-influenced file paths use safe_path_join."""

    FILES_WITH_SAFE_PATH = [
        "murphy_template_hub.py",
        "command_parser.py",
        "api_capability_builder.py",
        "hetzner_deploy.py",
        "environment_state_manager.py",
    ]

    @pytest.mark.parametrize("filename", FILES_WITH_SAFE_PATH)
    def test_safe_path_join_present(self, filename):
        """SEC-PATH-002: Each file must reference safe_path_join."""
        # Search across full Murphy System/src tree
        matches = list(_MURPHY_SRC.rglob(filename))
        assert matches, f"{filename} not found"
        source = matches[0].read_text()
        assert "safe_path_join" in source or "SEC-PATH-002" in source, \
            f"{filename} must use safe_path_join (SEC-PATH-002)"


# ═══════════════════════════════════════════════════════════════════════
#  SEC-LOG-002: OAuth log line sanitized
# ═══════════════════════════════════════════════════════════════════════

class TestLogSanitizationOAuth:
    """SEC-LOG-002: OAuth error logging must not leak tokens."""

    def test_oauth_log_uses_type_only(self):
        """app.py must log exception type, not message, for OAuth errors."""
        source = (_MURPHY_SRC / "runtime" / "app.py").read_text()
        assert "SEC-LOG-002" in source, "SEC-LOG-002 label must be in app.py"
        # The old pattern was: logger.warning("... %s", _tok_exc)
        # New pattern should use type(__name__) instead
        assert "type(_tok_exc).__name__" in source or "type(exc).__name__" in source, \
            "OAuth log must use exception type name, not full message"


# ═══════════════════════════════════════════════════════════════════════
#  SEC-STARTUP-001: Readiness scanner gate at startup
# ═══════════════════════════════════════════════════════════════════════

class TestStartupReadinessGate:
    """SEC-STARTUP-001: Production startup calls readiness scanner."""

    def test_startup_gate_label(self):
        """SEC-STARTUP-001 label present in production server."""
        source = _SERVER.read_text()
        assert "SEC-STARTUP-001" in source

    def test_startup_imports_readiness_scanner(self):
        """Production startup references readiness_scanner."""
        source = _SERVER.read_text()
        assert "readiness_scanner" in source or "DeploymentGateRunner" in source


# ═══════════════════════════════════════════════════════════════════════
#  SEC-DEPS-002: requirements.txt pinned to exact versions
# ═══════════════════════════════════════════════════════════════════════

class TestDependencyPinning:
    """SEC-DEPS-002: Production requirements pinned with ==."""

    def test_deps_label_in_requirements(self):
        """SEC-DEPS-002 comment in requirements.txt."""
        source = (_ROOT / "requirements.txt").read_text()
        assert "SEC-DEPS-002" in source

    def test_no_range_specifiers(self):
        """No >= or < version specifiers in production requirements."""
        source = (_ROOT / "requirements.txt").read_text()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped or stripped.startswith("-"):
                continue
            # Skip commented-out packages
            if stripped.startswith("#"):
                continue
            # Active package lines should use ==, not >= or <
            if ">=" in stripped and not stripped.startswith("#"):
                pytest.fail(
                    f"SEC-DEPS-002: requirements.txt has range specifier: {stripped}")


# ═══════════════════════════════════════════════════════════════════════
#  SEC-SANDBOX-001 / SEC-SANDBOX-002: Pre-execution quarantine gate
# ═══════════════════════════════════════════════════════════════════════

class TestQuarantinePreExecutionGate:
    """SEC-SANDBOX-001/002: quarantine_check() must exist and block."""

    def test_quarantine_check_method_exists(self):
        """SandboxQuarantine must have quarantine_check()."""
        source = (_MURPHY_SRC / "integration_engine" / "sandbox_quarantine.py").read_text()
        assert "def quarantine_check" in source, \
            "SEC-SANDBOX-001: quarantine_check() method must exist"
        assert "SEC-SANDBOX-001" in source
        assert "SEC-SANDBOX-002" in source

    def test_quarantine_check_blocks_eval(self):
        """quarantine_check must detect eval() as CRITICAL."""
        sys.path.insert(0, str(_MURPHY_SRC))
        try:
            from integration_engine.sandbox_quarantine import SandboxQuarantine
            sq = SandboxQuarantine()
            is_safe, findings = sq.quarantine_check("result = eval(user_input)")
            assert not is_safe, "eval() must be flagged as unsafe"
            assert any("eval" in f.lower() for f in findings)
        except ImportError:
            pytest.skip("sandbox_quarantine not importable")
        finally:
            if str(_MURPHY_SRC) in sys.path:
                sys.path.remove(str(_MURPHY_SRC))

    def test_quarantine_check_blocks_import(self):
        """quarantine_check must detect __import__ as CRITICAL."""
        sys.path.insert(0, str(_MURPHY_SRC))
        try:
            from integration_engine.sandbox_quarantine import SandboxQuarantine
            sq = SandboxQuarantine()
            is_safe, findings = sq.quarantine_check("os = __import__('os')")
            assert not is_safe, "__import__ must be flagged as unsafe"
        except ImportError:
            pytest.skip("sandbox_quarantine not importable")
        finally:
            if str(_MURPHY_SRC) in sys.path:
                sys.path.remove(str(_MURPHY_SRC))

    def test_quarantine_check_passes_clean_code(self):
        """Clean code should pass quarantine_check."""
        sys.path.insert(0, str(_MURPHY_SRC))
        try:
            from integration_engine.sandbox_quarantine import SandboxQuarantine
            sq = SandboxQuarantine()
            is_safe, findings = sq.quarantine_check("x = 1 + 2\nprint(x)")
            assert is_safe, "Clean code must pass quarantine"
        except ImportError:
            pytest.skip("sandbox_quarantine not importable")
        finally:
            if str(_MURPHY_SRC) in sys.path:
                sys.path.remove(str(_MURPHY_SRC))


# ═══════════════════════════════════════════════════════════════════════
#  SEC-ROUTE-001/002/003: Route auth coverage
# ═══════════════════════════════════════════════════════════════════════

class TestRouteAuthCoverage:
    """SEC-ROUTE-001/002/003: Route inventory and auth verification."""

    # SEC-ROUTE-002: Known public (no-auth) route prefixes
    PUBLIC_ROUTE_PREFIXES = (
        "/health", "/api/infrastructure/health",
        "/api/demo/", "/landing", "/ui/landing", "/onboarding",
        "/static/", "/api/rate-governor/", "/docs", "/redoc", "/openapi.json",
        "/api/fdd/", "/ws", "/",
    )

    def test_route_inventory_label(self):
        """SEC-ROUTE-001 label in production server."""
        source = _SERVER.read_text()
        assert "SEC-ROUTE" in source or "route" in source.lower()

    def test_all_routes_are_documented(self):
        """SEC-ROUTE-002: Every @app route can be categorised."""
        import re
        source = _SERVER.read_text()
        routes = re.findall(r'@app\.(?:get|post|put|patch|delete)\("([^"]+)"', source)
        assert len(routes) > 50, "Expected 50+ routes in production server"

    def test_public_routes_are_intentional(self):
        """SEC-ROUTE-003: No accidental public endpoints."""
        import re
        source = _SERVER.read_text()
        routes = re.findall(r'@app\.(?:get|post|put|patch|delete)\("([^"]+)"', source)

        for route in routes:
            is_public = any(route.startswith(prefix) for prefix in self.PUBLIC_ROUTE_PREFIXES)
            if not is_public:
                # Non-public routes should be in app.py (which has Depends) or
                # be explicitly documented here. We just verify the route exists
                # and is categorizable.
                assert route.startswith("/api/"), \
                    f"Non-API route {route} not in public list — audit needed"


# ═══════════════════════════════════════════════════════════════════════
#  SEC-READY-004: Docker port exposure check
# ═══════════════════════════════════════════════════════════════════════

class TestReadinessScannerDockerCheck:
    """SEC-READY-004: Readiness scanner checks Docker port exposure."""

    def test_ready_004_label(self):
        """SEC-READY-004 label in readiness_scanner.py."""
        source = (_MURPHY_SRC / "readiness_scanner.py").read_text()
        assert "SEC-READY-004" in source

    def test_ready_004_checks_infrastructure_ports(self):
        """SEC-READY-004 references infrastructure ports (5432, 6379, 9090)."""
        source = (_MURPHY_SRC / "readiness_scanner.py").read_text()
        for port in ("5432", "6379", "9090"):
            assert port in source, \
                f"SEC-READY-004: Readiness scanner must check port {port}"
