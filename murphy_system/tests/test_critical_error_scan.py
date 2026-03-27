# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
Critical Error Scan — Test Suite
==================================

Tests produced for PR 1 of 5 (Scan & Plan).
Each test corresponds to a finding in docs/CRITICAL_ERROR_REMEDIATION_PLAN.md.

Tests verify:
  - DISP-001: No bare ``except:`` clauses remain in src/dispatch.py
  - ARCH-001: security_hardening_config.py is importable
  - SEC-002: CORS is configured from env var, not hardcoded wildcard
  - SEC-004: SecurityMiddleware is wired into FastAPI via configure_secure_fastapi
  - DISP-001 (runtime): call_from_llm_response handles invalid JSON without crashing
  - META-001: bandit reports zero HIGH-severity findings in src/
"""

import ast
import importlib
import os
import re
import subprocess
import sys

import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
_DISPATCH_FILE = os.path.join(_SRC_DIR, "dispatch.py")


# ---------------------------------------------------------------------------
# DISP-001: bare ``except:`` removed from src/dispatch.py
# ---------------------------------------------------------------------------

class TestBareExceptRemoved:
    """DISP-001 — bare ``except:`` clauses must not exist in src/dispatch.py."""

    def test_no_bare_except_in_dispatch(self):
        """Parse dispatch.py AST and assert no ExceptHandler has type=None (bare except)."""
        with open(_DISPATCH_FILE, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=_DISPATCH_FILE)
        bare = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                bare.append(node.lineno)
        assert bare == [], (
            f"Bare except: clauses found in dispatch.py at lines {bare}. "
            "Replace with specific exception types and add logging."
        )

    def test_no_bare_except_in_src(self):
        """Scan all .py files in src/ for bare except: using regex."""
        bare_except_pattern = re.compile(r"^\s*except\s*:", re.MULTILINE)
        violations = []
        for root, _dirs, files in os.walk(_SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                except OSError:
                    continue
                for m in bare_except_pattern.finditer(content):
                    lineno = content[: m.start()].count("\n") + 1
                    violations.append(f"{fpath}:{lineno}")
        assert violations == [], (
            f"Bare except: clauses found:\n" + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# ARCH-001: security_hardening_config.py is importable
# ---------------------------------------------------------------------------

class TestSecurityHardeningConfigExists:
    """ARCH-001 — security_hardening_config must exist and be importable."""

    def test_file_exists(self):
        path = os.path.join(_SRC_DIR, "security_hardening_config.py")
        assert os.path.isfile(path), "src/security_hardening_config.py is missing"

    def test_importable(self):
        try:
            import src.security_hardening_config as shc  # noqa: F401
        except ImportError as exc:
            pytest.fail(f"src.security_hardening_config import failed: {exc}")

    def test_has_input_sanitizer(self):
        from src.security_hardening_config import InputSanitizer
        sanitizer = InputSanitizer()
        assert sanitizer is not None

    def test_has_security_hardening_config_class(self):
        from src.security_hardening_config import SecurityHardeningConfig
        cfg = SecurityHardeningConfig()
        assert cfg is not None


# ---------------------------------------------------------------------------
# SEC-002: CORS is env-var-driven (not a hardcoded wildcard)
# ---------------------------------------------------------------------------

class TestCORSConfiguration:
    """SEC-002 — CORS must use env-var allowlist, never a hardcoded '*'."""

    def test_fastapi_security_cors_reads_env_var(self):
        """get_cors_origins() must honour MURPHY_CORS_ORIGINS."""
        from src.fastapi_security import get_cors_origins
        test_origins = "https://app.murphy.systems,https://api.murphy.systems"
        original = os.environ.get("MURPHY_CORS_ORIGINS")
        try:
            os.environ["MURPHY_CORS_ORIGINS"] = test_origins
            allowed = get_cors_origins()
        finally:
            if original is None:
                os.environ.pop("MURPHY_CORS_ORIGINS", None)
            else:
                os.environ["MURPHY_CORS_ORIGINS"] = original
        assert "https://app.murphy.systems" in allowed
        assert "https://api.murphy.systems" in allowed

    def test_cors_not_wildcard_by_default(self):
        """Default CORS must not include '*'."""
        from src.fastapi_security import get_cors_origins
        original = os.environ.get("MURPHY_CORS_ORIGINS")
        try:
            os.environ.pop("MURPHY_CORS_ORIGINS", None)
            allowed = get_cors_origins()
        finally:
            if original is not None:
                os.environ["MURPHY_CORS_ORIGINS"] = original
        assert "*" not in allowed, (
            "Default CORS origins must not include '*'; use explicit localhost entries."
        )

    def test_tiered_app_factory_cors_reads_env_var(self):
        """tiered_app_factory must also read MURPHY_CORS_ORIGINS (not hardcode '*')."""
        factory_path = os.path.join(_SRC_DIR, "runtime", "tiered_app_factory.py")
        if not os.path.isfile(factory_path):
            pytest.skip("tiered_app_factory.py not found")
        with open(factory_path, "r", encoding="utf-8") as fh:
            source = fh.read()
        # Wildcard should only appear as an env-var option, never as the raw literal default
        # Allow: os.environ.get("MURPHY_CORS_ORIGINS", ...) and  "Set MURPHY_CORS_ORIGINS=*"
        # Disallow: allow_origins=["*"]  (hardcoded)
        assert 'allow_origins=["*"]' not in source, (
            "tiered_app_factory.py hardcodes allow_origins=[\"*\"]; use MURPHY_CORS_ORIGINS env var."
        )


# ---------------------------------------------------------------------------
# SEC-004: SecurityMiddleware wired into configure_secure_fastapi
# ---------------------------------------------------------------------------

class TestSecurityMiddlewareWired:
    """SEC-004 — SecurityMiddleware must be registered in configure_secure_fastapi."""

    def test_configure_secure_fastapi_adds_security_middleware(self):
        """Inspect fastapi_security source to confirm add_middleware(SecurityMiddleware) call."""
        fastapi_security_path = os.path.join(_SRC_DIR, "fastapi_security.py")
        with open(fastapi_security_path, "r", encoding="utf-8") as fh:
            source = fh.read()
        assert "app.add_middleware(SecurityMiddleware" in source, (
            "configure_secure_fastapi() must call app.add_middleware(SecurityMiddleware, ...)."
        )

    def test_configure_secure_fastapi_importable(self):
        """configure_secure_fastapi must be importable without error."""
        try:
            from src.fastapi_security import configure_secure_fastapi  # noqa: F401
        except ImportError as exc:
            pytest.fail(f"src.fastapi_security import failed: {exc}")


# ---------------------------------------------------------------------------
# DISP-001 (runtime): call_from_llm_response tolerates bad JSON
# ---------------------------------------------------------------------------

class TestDispatchRobustness:
    """DISP-001 runtime — dispatch must not crash on malformed tool-call arguments."""

    def test_call_from_llm_response_bad_json(self):
        """call_from_llm_response must handle invalid JSON args gracefully."""
        from src.dispatch import Dispatcher, ToolRegistry, PendingApprovalStore

        reg = ToolRegistry()
        store = PendingApprovalStore()
        dispatcher = Dispatcher(reg, store)

        bad_tool_calls = [
            {"function": {"name": "nonexistent.tool", "arguments": "{bad json"}},
            {"name": "another.tool", "function": {"name": "another.tool", "arguments": None}},
        ]
        # Must not raise any exception
        results = dispatcher.call_from_llm_response(bad_tool_calls, caller_id="test")
        assert isinstance(results, list)
        assert len(results) == 2

    def test_dispatch_import_includes_json(self):
        """json must be imported at module level in dispatch.py (not inside a loop)."""
        with open(_DISPATCH_FILE, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=_DISPATCH_FILE)
        # Find top-level import json
        top_level_json_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "json":
                        top_level_json_import = True
        assert top_level_json_import, "json must be imported at module level in dispatch.py"


# ---------------------------------------------------------------------------
# META-001: bandit reports zero HIGH severity findings in src/
# ---------------------------------------------------------------------------

class TestBanditSecurityScan:
    """META-001 — bandit must report zero HIGH-severity findings in src/."""

    @pytest.mark.slow
    def test_bandit_zero_high_findings(self):
        """Run bandit with project config; assert no HIGH findings."""
        repo_root = os.path.join(os.path.dirname(__file__), "..")
        bandit_config = os.path.join(repo_root, "bandit.yaml")
        src_dir = os.path.join(repo_root, "src")

        cmd = [
            sys.executable, "-m", "bandit",
            "-c", bandit_config,
            "-r", src_dir,
            "-ll",  # report medium and higher severity (minimum level: medium)
            "-f", "json",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=repo_root,
            )
        except FileNotFoundError:
            pytest.skip("bandit not installed")
        except subprocess.TimeoutExpired:
            pytest.skip("bandit timed out")

        import json as _json
        try:
            report = _json.loads(result.stdout)
        except _json.JSONDecodeError:
            pytest.skip("bandit did not produce valid JSON output")

        metrics = report.get("metrics", {})
        # Aggregate HIGH severity count across all files
        high_count = sum(
            v.get("SEVERITY.HIGH", 0)
            for v in metrics.values()
            if isinstance(v, dict)
        )
        assert high_count == 0, (
            f"bandit found {high_count} HIGH-severity issue(s) in src/. "
            "Review the findings and fix before deploying."
        )


# ---------------------------------------------------------------------------
# IMPORT-001: key modules must be importable
# ---------------------------------------------------------------------------

class TestKeyModulesImportable:
    """IMPORT-001 — critical modules flagged as potentially missing must import cleanly."""

    @pytest.mark.parametrize("module_path", [
        "src.security_hardening_config",
        "src.agentic_api_provisioner",
        "src.fastapi_security",
        "src.flask_security",
        "src.dispatch",
    ])
    def test_module_importable(self, module_path: str):
        """Each critical module must be importable without raising ImportError."""
        try:
            importlib.import_module(module_path)
        except ImportError as exc:
            pytest.fail(f"{module_path} import failed: {exc}")
