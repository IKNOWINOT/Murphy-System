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
                with open(fpath, encoding='utf-8') as f:
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
                with open(fpath, encoding='utf-8') as f:
                    content = f.read()
                raw_appends = set(re.findall(r"self\.(_\w+)\.append\(", content))
                for attr in raw_appends:
                    # Already using capped_append for this attr?
                    if f"capped_append(self.{attr}" in content:
                        continue
                    # Already using capped_append_paired for this attr?
                    if f"capped_append_paired(self.{attr}" in content:
                        continue
                    # Using deque (has built-in maxlen)?
                    if f"{attr} = deque(" in content or f"collections.deque(" in content:
                        continue
                    # Manual truncation?
                    if f"self.{attr} = self.{attr}[" in content:
                        continue
                    if f"del self.{attr}[" in content:
                        continue
                    # LRU access_order bounded by cache eviction?
                    if attr == "_access_order" and "_evict" in content:
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


class TestCappedAppendPaired:
    """Paired lists must stay synchronised after trimming."""

    def test_paired_lists_stay_in_sync(self):
        from thread_safe_operations import capped_append_paired

        a: list = []
        b: list = []
        cap = 100
        for i in range(cap + 50):
            capped_append_paired(a, i, b, i * 10, max_size=cap)

        # Both lists have exactly the same length
        assert len(a) == len(b)
        # Last elements correspond
        assert a[-1] == cap + 49
        assert b[-1] == (cap + 49) * 10

    def test_paired_never_desync_under_trimming(self):
        from thread_safe_operations import capped_append_paired

        x: list = []
        y: list = []
        z: list = []
        cap = 50
        for i in range(200):
            capped_append_paired(x, i, y, -i, z, i * 2, max_size=cap)

        assert len(x) == len(y) == len(z)
        # Corresponding elements match
        for xi, yi, zi in zip(x, y, z):
            assert yi == -xi
            assert zi == xi * 2

    def test_no_remaining_paired_capped_append_calls(self):
        """Adjacent capped_append on different attrs should use capped_append_paired."""
        violations = []
        for root, _dirs, files in os.walk(SRC_DIR):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split("\n")

                # Strip docstrings to avoid false positives
                in_docstring = False
                executable = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        toggle = stripped[:3]
                        # Single-line docstring
                        if stripped.count(toggle) >= 2:
                            executable.append("")
                            continue
                        in_docstring = not in_docstring
                        executable.append("")
                        continue
                    if in_docstring:
                        executable.append("")
                    else:
                        executable.append(line)

                for i, line in enumerate(executable):
                    if "capped_append(self." not in line:
                        continue
                    if line.strip().startswith("#"):
                        continue
                    m1 = re.search(r"capped_append\(self\.(_\w+)", line)
                    if not m1:
                        continue
                    for j in range(i + 1, min(i + 3, len(executable))):
                        if "capped_append(self." not in executable[j]:
                            continue
                        if executable[j].strip().startswith("#"):
                            continue
                        m2 = re.search(
                            r"capped_append\(self\.(_\w+)", executable[j]
                        )
                        if m2 and m1.group(1) != m2.group(1):
                            rel = os.path.relpath(fpath, SRC_DIR)
                            violations.append(
                                f"{rel}:{i+1} {m1.group(1)} + {m2.group(1)}"
                            )
        assert violations == [], (
            f"Paired capped_append should use capped_append_paired: {violations}"
        )


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
                with open(fpath, encoding='utf-8') as f:
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
                with open(fpath, encoding='utf-8') as f:
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
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        s = line.strip()
                        if s.startswith("#"):
                            continue
                        if re.search(r"(?<!\w)eval\s*\(", s):
                            if "literal_eval" in s or ".eval()" in s:
                                continue
                            if "security_audit" in fpath or "sandbox_quarantine" in fpath:
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
                with open(fpath, encoding='utf-8') as f:
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
