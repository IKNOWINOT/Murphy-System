"""
Defensive Import Audit — ensures all thread_safe_operations imports
use the try/except ImportError pattern to prevent startup crashes.

This test prevents regression: any new bare 'from thread_safe_operations import'
without a try/except fallback will fail this test.
"""
import os
import pytest

SRC_ROOT = os.path.join(os.path.dirname(__file__), '..', 'src')


def _find_bare_thread_safe_imports():
    """Find .py files that import thread_safe_operations without try/except."""
    bare_imports = []
    for dirpath, _, filenames in os.walk(SRC_ROOT):
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            filepath = os.path.join(dirpath, fn)
            # Skip thread_safe_operations.py itself — it defines the functions
            if fn == 'thread_safe_operations.py':
                continue
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # Skip files that don't import from thread_safe_operations at all
            if 'from thread_safe_operations import' not in content:
                continue
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'from thread_safe_operations import' not in line:
                    continue
                # Look backward up to 3 lines for a bare 'try:' statement
                found_try = False
                for j in range(max(0, i - 3), i):
                    if lines[j].strip() == 'try:':
                        found_try = True
                        break
                if not found_try:
                    rel = os.path.relpath(filepath, SRC_ROOT)
                    bare_imports.append(f"{rel}:{i + 1}")
    return bare_imports


def test_no_bare_thread_safe_imports():
    """All thread_safe_operations imports MUST use try/except ImportError fallback."""
    bare = _find_bare_thread_safe_imports()
    assert bare == [], (
        f"Found {len(bare)} bare thread_safe_operations import(s) "
        "(no try/except fallback) in:\n"
        + "\n".join(f"  - {b}" for b in bare)
        + "\n\nWrap each import in:\n"
        "  try:\n"
        "      from thread_safe_operations import capped_append\n"
        "  except ImportError:\n"
        "      def capped_append(target_list, item, max_size=10_000): ...\n"
    )
