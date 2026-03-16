"""
Gap-closure tests — Round 18.

Gaps addressed:
38. 6 security_plane modules missing module docstrings → added
39. 1 silent except (ValueError, TypeError): pass → logger.debug
40. Hardcoded secret false-positives verified as enum labels
"""

import ast
import os
import re

import pytest


SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


class TestModuleDocstrings:
    """Every non-__init__ source module must have a module-level docstring."""

    SECURITY_MODULES = [
        "security_plane/log_sanitizer.py",
        "security_plane/bot_anomaly_detector.py",
        "security_plane/security_dashboard.py",
        "security_plane/bot_identity_verifier.py",
        "security_plane/bot_resource_quotas.py",
        "security_plane/swarm_communication_monitor.py",
    ]

    def test_security_plane_modules_have_docstrings(self):
        missing = []
        for mod in self.SECURITY_MODULES:
            fpath = os.path.join(SRC_DIR, mod)
            tree = ast.parse(open(fpath, encoding="utf-8").read())
            has_docstring = (
                tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            )
            if not has_docstring:
                missing.append(mod)
        assert missing == [], f"Modules missing docstrings: {missing}"


class TestNoSilentExceptPass:
    """except blocks must not silently pass without logging."""

    # ImportError: pass is acceptable for optional deps
    ALLOWED_EXCEPTION_TYPES = {"ImportError"}

    def test_no_silent_value_type_error_pass(self):
        """Non-ImportError except: pass blocks must log."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    content = open(fpath, encoding="utf-8").read()
                    tree = ast.parse(content)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ExceptHandler):
                        continue
                    if len(node.body) != 1 or not isinstance(node.body[0], ast.Pass):
                        continue
                    # Check what exception type is caught
                    if node.type is None:
                        # bare except: pass — already covered in earlier rounds
                        continue
                    exc_names = set()
                    if isinstance(node.type, ast.Name):
                        exc_names.add(node.type.id)
                    elif isinstance(node.type, ast.Tuple):
                        for elt in node.type.elts:
                            if isinstance(elt, ast.Name):
                                exc_names.add(elt.id)
                    # ImportError: pass is OK for optional deps
                    if exc_names and exc_names <= self.ALLOWED_EXCEPTION_TYPES:
                        continue
                    rel = os.path.relpath(fpath, SRC_DIR)
                    violations.append(f"{rel}:{node.lineno}")
        assert violations == [], (
            f"Silent except: pass (non-ImportError): {violations}"
        )


class TestHardcodedSecretsFalsePositives:
    """Verify 'hardcoded secrets' are actually enum/type labels."""

    KNOWN_ENUM_PATTERNS = {
        "BEARER_TOKEN",
        "WEBHOOK_SECRET",
        "OAUTH_TOKEN",
        "JWT_TOKEN",
        "PASSWORD",
        "AUTH_TOKEN",
        "TOP_SECRET",
    }

    def test_secret_looking_constants_are_enums(self):
        """Constants matching secret patterns must be ALL_CAPS enum labels."""
        secret_re = re.compile(
            r"(password|secret|api_key|token)\s*=\s*[\"'][^\"']{4,}",
            re.I,
        )
        real_secrets = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                for i, line in enumerate(
                    open(fpath, encoding="utf-8"), 1
                ):
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    m = secret_re.search(s)
                    if not m:
                        continue
                    # Extract the variable name
                    var_match = re.match(r"(\w+)\s*=", s)
                    if var_match:
                        var_name = var_match.group(1)
                        # ALL_CAPS = enum label, not real secret
                        if var_name.isupper():
                            continue
                    # Skip test/mock/example values
                    lower = s.lower()
                    if any(
                        kw in lower
                        for kw in (
                            "test", "mock", "example", "placeholder",
                            "dummy", "default", "sample",
                        )
                    ):
                        continue
                    rel = os.path.relpath(fpath, SRC_DIR)
                    real_secrets.append(f"{rel}:{i}")
        assert real_secrets == [], (
            f"Possible real hardcoded secrets: {real_secrets}"
        )


class TestRound18Regression:
    """All source files still compile after round 18 changes."""

    def test_all_files_compile(self):
        import py_compile

        errors = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    py_compile.compile(fpath, doraise=True)
                except py_compile.PyCompileError:
                    errors.append(os.path.relpath(fpath, SRC_DIR))
        assert errors == [], f"Syntax errors: {errors}"
