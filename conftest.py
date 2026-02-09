"""
Pytest configuration to ensure Murphy System modules are importable.
"""

from __future__ import annotations

import sys
from pathlib import Path

MURPHY_ROOT = Path(__file__).parent / "Murphy System"
if MURPHY_ROOT.exists():
    sys.path.insert(0, str(MURPHY_ROOT))
    tests_dir = MURPHY_ROOT / "tests"
    if tests_dir.exists():
        sys.path.insert(0, str(tests_dir))
    integrated_dir = MURPHY_ROOT / "murphy_integrated"
    if integrated_dir.exists():
        sys.path.insert(0, str(integrated_dir))
