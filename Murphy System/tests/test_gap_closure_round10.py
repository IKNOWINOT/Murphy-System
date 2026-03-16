"""
Gap-closure tests — Round 10.

Gaps addressed:
32. 26 silent exception swallows across 18 files: ``except Exception: pass``
    → replaced with ``except Exception as exc:`` + ``logger.debug(...)``
33. 44 ``except Exception:`` without ``as`` clause → added ``as exc``
34. Logging sensitive data in provider_adapter.py: exception text that
    may contain tokens → log only ``type(exc).__name__``
35. 2 syntax errors from import placement inside multi-line imports → fixed
36. 5 unreachable code blocks after return statements → removed dead code
37. 2 duplicate method definitions (get_system_state) → removed shadowed dups
38. 1 deeply nested try (depth=3) in compute_plane/service.py → extracted helper
"""

import ast
import os
import re

import pytest


SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


# ===================================================================
# Gap 32 — no more silent exception swallows
# ===================================================================
class TestNoSilentExceptionSwallows:
    """Every ``except Exception`` must log before pass/continue."""

    def test_no_silent_swallows_in_src(self):
        """AST-verified: no except Exception with body == [pass] or [continue]."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        if (
                            node.type
                            and isinstance(node.type, ast.Name)
                            and node.type.id == "Exception"
                        ):
                            if len(node.body) == 1 and isinstance(
                                node.body[0], (ast.Pass, ast.Continue)
                            ):
                                rel = os.path.relpath(fpath, SRC_DIR)
                                violations.append(f"{rel}:{node.lineno}")
        assert violations == [], (
            f"Silent exception swallows remain: {violations}"
        )

    def test_exception_handlers_have_as_clause(self):
        """Every ``except Exception`` must capture the exception (``as exc``)
        so it can be logged."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        # Match except Exception: (without 'as')
                        if re.match(r"except\s+Exception\s*:", s):
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{i}")
        assert violations == [], (
            f"except Exception without 'as' clause: {violations}"
        )


# ===================================================================
# Gap 33 — no sensitive data in log messages
# ===================================================================
class TestNoSensitiveDataInLogs:
    """Log statements must not include raw secret/token/password values."""

    def test_no_sensitive_data_logged(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        if re.search(
                            r"(?:logger|logging)\.\w+\(.*"
                            r"(?:password|secret|api_key|apikey|auth_token)",
                            s,
                            re.I,
                        ):
                            # Allow safe patterns
                            if any(
                                safe in s.lower()
                                for safe in [
                                    "redact",
                                    "mask",
                                    "sanitiz",
                                    "type(exc).__name__",
                                    "provider.value",
                                    "token_type",
                                ]
                            ):
                                continue
                            # Allow "token refresh failed" with only exception type
                            if "token" in s.lower() and "type(" in s:
                                continue
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{i}")
        assert violations == [], (
            f"Sensitive data in log statements: {violations}"
        )

    def test_provider_adapter_logs_exception_type_only(self):
        """provider_adapter.py must log type(exc).__name__, not str(exc)."""
        fpath = os.path.join(SRC_DIR, "auar", "provider_adapter.py")
        with open(fpath, encoding='utf-8') as f:
            content = f.read()
        assert "type(exc).__name__" in content, (
            "provider_adapter should log exception type, not full message"
        )


# ===================================================================
# Gap 34 — syntax validity of all source files
# ===================================================================
class TestSyntaxValidity:
    """Every .py file in src/ must be syntactically valid."""

    def test_all_source_files_compile(self):
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
                    rel = os.path.relpath(fpath, SRC_DIR)
                    errors.append(rel)
        assert errors == [], f"Syntax errors in: {errors}"


# ===================================================================
# Meta: all prior categories still at zero
# ===================================================================
class TestAllPriorGapsClosed:
    """Regression: every category from rounds 3-9 is still clean."""

    def test_no_bare_excepts(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        assert not re.match(r"^\s*except\s*:", line), (
                            f"Bare except at {fpath}:{i}"
                        )

    def test_no_production_asserts(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py") or "test" in fname.lower():
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assert):
                        rel = os.path.relpath(fpath, SRC_DIR)
                        pytest.fail(f"assert at {rel}:{node.lineno}")

    def test_no_wildcard_imports(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        assert not re.match(
                            r"from\s+\S+\s+import\s+\*", s
                        ), f"Wildcard import at {fpath}:{i}"

    def test_no_mutable_default_args(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for default in node.args.defaults + node.args.kw_defaults:
                            if default is None:
                                continue
                            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                                rel = os.path.relpath(fpath, SRC_DIR)
                                pytest.fail(
                                    f"Mutable default at {rel}:{node.lineno} "
                                    f"def {node.name}()"
                                )


# ===================================================================
# Gap 36 — no unreachable code after return/raise
# ===================================================================
class TestNoUnreachableCode:
    """No statements after return/raise within the same block."""

    def test_no_unreachable_code(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        body = node.body
                        for idx, stmt in enumerate(body[:-1]):
                            if isinstance(stmt, (ast.Return, ast.Raise)):
                                ns = body[idx + 1]
                                if not isinstance(
                                    ns,
                                    (
                                        ast.FunctionDef,
                                        ast.AsyncFunctionDef,
                                        ast.ClassDef,
                                    ),
                                ):
                                    rel = os.path.relpath(fpath, SRC_DIR)
                                    violations.append(
                                        f"{rel}:{ns.lineno}"
                                    )
        assert violations == [], (
            f"Unreachable code found: {violations}"
        )


# ===================================================================
# Gap 37 — no duplicate method definitions in same class
# ===================================================================
class TestNoDuplicateMethods:
    """Each class must define each method name exactly once."""

    def test_no_duplicate_methods(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        methods = {}
                        for child in node.body:
                            if isinstance(
                                child,
                                (ast.FunctionDef, ast.AsyncFunctionDef),
                            ):
                                if child.name in methods:
                                    rel = os.path.relpath(fpath, SRC_DIR)
                                    violations.append(
                                        f"{rel}:{child.lineno} "
                                        f"{node.name}.{child.name}()"
                                    )
                                else:
                                    methods[child.name] = child.lineno
        assert violations == [], (
            f"Duplicate methods: {violations}"
        )


# ===================================================================
# Gap 38 — no deeply nested try (>= 3 levels)
# ===================================================================
class TestNoDeeplyNestedTry:
    """Try/except blocks should not nest 3+ levels deep."""

    def test_no_triple_nested_try(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue

                def check(node, depth=0):
                    if isinstance(node, ast.Try):
                        depth += 1
                        if depth >= 3:
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(
                                f"{rel}:{node.lineno} depth={depth}"
                            )
                            return
                    for child in ast.iter_child_nodes(node):
                        check(child, depth)

                check(tree)
        assert violations == [], (
            f"Deeply nested try: {violations}"
        )


# ===================================================================
# Gap 39 — consistent exception variable naming (exc, not e)
# ===================================================================
class TestConsistentExceptionNaming:
    """All except handlers should use 'exc' as the variable name."""

    def test_no_except_as_e(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        if node.name == "e":
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{node.lineno}")
        assert violations == [], (
            f"'except ... as e:' should use 'exc': {violations[:10]}"
        )
