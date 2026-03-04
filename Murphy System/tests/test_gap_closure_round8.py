"""
Gap-closure tests — Round 8.

Gaps addressed:
25. 127 division-by-zero risks across 72 files: ``/ len(x)`` without guards
    → replaced with ``/ (len(x) or 1)``
26. 160 unbounded ``.append()`` calls across 91 files
    → replaced with ``capped_append(self._xxx, item)``
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")


# ===================================================================
# Gap 25 — every ``/ len(x)`` in src/ is guarded against zero
# ===================================================================
class TestDivisionByZeroGuards:
    """No source file may divide by ``len(x)`` without a zero-guard."""

    def test_no_unguarded_div_by_len(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    s = line.strip()
                    if s.startswith("#"):
                        continue
                    if re.search(r"/\s*len\(", s):
                        context = "".join(lines[max(0, i - 5) : i])
                        guarded = (
                            "or 1" in s
                            or "if len(" in context
                            or "if not" in context
                            or "> 0" in context
                        )
                        if not guarded:
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(f"{rel}:{i}")

        assert violations == [], (
            f"Unguarded / len() found in: {violations}"
        )

    def test_or_1_guard_is_correct(self):
        """Verify the ``(len(x) or 1)`` idiom works at runtime."""
        empty: list = []
        non_empty = [10, 20, 30]

        # Empty list → denominator becomes 1, result is 0
        assert sum(empty) / (len(empty) or 1) == 0.0
        # Non-empty → denominator is the real length
        assert sum(non_empty) / (len(non_empty) or 1) == 20.0


# ===================================================================
# Gap 26 — every self._xxx.append() uses capped_append
# ===================================================================
class TestUnboundedAppendsCapped:
    """No ``self._xxx.append()`` in src/ should be raw; must use ``capped_append``."""

    def test_no_raw_appends_remain(self):
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    content = f.read()
                raw_appends = set(re.findall(r"self\.(_\w+)\.append\(", content))
                for attr in raw_appends:
                    # Already using capped_append for this attr?
                    if f"capped_append(self.{attr}" in content:
                        continue
                    # Using deque (has built-in maxlen)?
                    if f"{attr} = deque(" in content or f"collections.deque(" in content:
                        continue
                    # Manual truncation?
                    if f"self.{attr} = self.{attr}[" in content:
                        continue
                    if f"del self.{attr}[" in content:
                        continue
                    rel = os.path.relpath(fpath, SRC_DIR)
                    violations.append(f"{rel}: {attr}")

        assert violations == [], (
            f"Unbounded .append() still present: {violations}"
        )

    def test_capped_append_trims_at_cap(self):
        """Verify capped_append actually trims when the cap is hit."""
        from thread_safe_operations import capped_append

        data: list = []
        cap = 100
        for i in range(cap + 50):
            capped_append(data, i, max_size=cap)

        # Must never exceed cap (trimming removes oldest 10%)
        assert len(data) <= cap
        # Most recent item is always present
        assert data[-1] == cap + 49

    def test_capped_append_preserves_order(self):
        """After trimming, the most recent items are preserved."""
        from thread_safe_operations import capped_append

        data: list = []
        for i in range(200):
            capped_append(data, i, max_size=100)

        # Last element is definitely 199
        assert data[-1] == 199
        # All elements are in ascending order
        assert data == sorted(data)


# ===================================================================
# Global: syntax validity of all 583 source files
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
# Meta: all prior gap categories still at zero
# ===================================================================
class TestAllPriorGapsClosed:
    """Regression: confirm every category from rounds 3-7 is still at zero."""

    def test_no_bare_excepts(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    for i, line in enumerate(f, 1):
                        assert not re.match(r"^\s*except\s*:", line), (
                            f"Bare except at {fpath}:{i}"
                        )

    def test_no_raw_pickle_load(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        assert "pickle.load(" not in s and "pickle.loads(" not in s, (
                            f"Raw pickle at {fpath}:{i}"
                        )

    def test_no_unsafe_eval(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        if re.search(r"(?<!\w)eval\s*\(", s):
                            if "literal_eval" in s or ".eval()" in s:
                                continue
                            if "security_audit" in fpath:
                                continue
                            if '"""' in s or "'''" in s:
                                continue
                            pytest.fail(f"eval() at {fpath}:{i}")

    def test_all_http_calls_have_timeout(self):
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    content = f.read()
                if "import requests" not in content:
                    continue
                for m in re.finditer(
                    r"(?<![.\w])requests\.(post|get|put|delete|patch|head)\(", content
                ):
                    start = m.start()
                    depth = 1
                    pos = m.end()
                    while pos < len(content) and depth > 0:
                        if content[pos] == "(":
                            depth += 1
                        elif content[pos] == ")":
                            depth -= 1
                        pos += 1
                    call_text = content[start:pos]
                    line = content[:start].count("\n") + 1
                    assert "timeout" in call_text, (
                        f"HTTP call without timeout at {fpath}:{line}"
                    )
