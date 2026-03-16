"""
Test Suite: Code Hardening — Recursive Fix Verification

Verifies the code quality improvements:
  - CODE-001: print→logger in _deps.py
  - CODE-002: Bare except cleanup in MFM endpoints
  - MFM-001: MFM endpoints log errors properly
  - Blueprint stub accepts constructor arguments

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"



# ---------------------------------------------------------------------------
# CODE-001: No print() in _deps.py — must use logger.warning()
# ---------------------------------------------------------------------------

class TestDepsLoggerUsage:
    """CODE-001: _deps.py must use logger, not print, for warnings."""

    def test_no_print_calls_in_deps(self) -> None:
        """Verify _deps.py has zero print() calls."""
        deps_path = SRC_DIR / "runtime" / "_deps.py"
        assert deps_path.exists(), f"Missing {deps_path}"

        with open(deps_path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=str(deps_path))

        print_calls: List[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Catch print(...)
                if isinstance(func, ast.Name) and func.id == "print":
                    print_calls.append(node.lineno)

        assert len(print_calls) == 0, (
            f"Found {len(print_calls)} print() call(s) in _deps.py at lines: "
            f"{print_calls}. Use logger.warning() instead."
        )

    def test_logger_defined_before_first_import_block(self) -> None:
        """Verify logger is defined early enough to be used in all except blocks."""
        deps_path = SRC_DIR / "runtime" / "_deps.py"
        with open(deps_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # logger must be defined before the first logger.warning call
        logger_def = content.find("logger = logging.getLogger")
        first_use = content.find("logger.warning(")
        assert logger_def != -1, "logger not defined in _deps.py"
        assert first_use != -1, "No logger.warning() calls found in _deps.py"
        assert logger_def < first_use, (
            "logger is defined after first usage — move logger definition earlier"
        )

    def test_import_warnings_use_logger(self) -> None:
        """Verify import except blocks use logger.warning, not print."""
        deps_path = SRC_DIR / "runtime" / "_deps.py"
        with open(deps_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # Count logger.warning calls in the file (should be many)
        logger_warnings = len(re.findall(r"logger\.warning\(", content))
        assert logger_warnings >= 40, (
            f"Expected ≥40 logger.warning() calls, found {logger_warnings}"
        )


# ---------------------------------------------------------------------------
# CODE-002 / MFM-001: MFM endpoints use specific exceptions + logging
# ---------------------------------------------------------------------------

class TestMFMEndpointExceptionHandling:
    """CODE-002/MFM-001: MFM endpoints must use specific exception types."""

    @pytest.fixture
    def app_ast(self) -> ast.Module:
        app_path = SRC_DIR / "runtime" / "app.py"
        with open(app_path, "r", encoding="utf-8") as fh:
            return ast.parse(fh.read(), filename=str(app_path))

    @pytest.fixture
    def app_source(self) -> str:
        app_path = SRC_DIR / "runtime" / "app.py"
        with open(app_path, "r", encoding="utf-8") as fh:
            return fh.read()

    def test_mfm_endpoints_no_bare_except_exception(self, app_source: str) -> None:
        """MFM endpoint section must not have bare 'except Exception:' without logging."""
        # Extract MFM section
        mfm_start = app_source.find("# ==================== MFM (Murphy Foundation Model)")
        mfm_end = app_source.find("return app", mfm_start)
        assert mfm_start != -1, "MFM section not found in app.py"
        assert mfm_end != -1, "return app not found after MFM section"

        mfm_section = app_source[mfm_start:mfm_end]

        # Check: no bare "except Exception:" without logger call on the next few lines
        lines = mfm_section.splitlines()
        violations: List[Tuple[int, str]] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("except Exception") and ":" in stripped:
                # Check if the next 3 lines contain logger
                context = "\n".join(lines[i:i + 4])
                if "logger." not in context:
                    violations.append((i, stripped))

        assert len(violations) == 0, (
            f"Found {len(violations)} bare except Exception without logging "
            f"in MFM section: {violations}"
        )

    def test_mfm_endpoints_use_importerror_specifically(self, app_source: str) -> None:
        """MFM endpoints must catch ImportError separately for missing modules."""
        mfm_start = app_source.find("# ==================== MFM (Murphy Foundation Model)")
        mfm_end = app_source.find("return app", mfm_start)
        mfm_section = app_source[mfm_start:mfm_end]

        # Count ImportError catches in MFM section (should be present for lazy imports)
        import_error_catches = len(re.findall(r"except ImportError", mfm_section))
        assert import_error_catches >= 4, (
            f"Expected ≥4 'except ImportError' in MFM section, found {import_error_catches}. "
            f"MFM endpoints with lazy imports must catch ImportError specifically."
        )

    def test_mfm_endpoints_log_errors(self, app_source: str) -> None:
        """MFM endpoints must use logger.exception or logger.warning for errors."""
        mfm_start = app_source.find("# ==================== MFM (Murphy Foundation Model)")
        mfm_end = app_source.find("return app", mfm_start)
        mfm_section = app_source[mfm_start:mfm_end]

        logger_calls = (
            len(re.findall(r"logger\.exception\(", mfm_section))
            + len(re.findall(r"logger\.warning\(", mfm_section))
            + len(re.findall(r"logger\.error\(", mfm_section))
        )
        assert logger_calls >= 8, (
            f"Expected ≥8 logger calls in MFM section, found {logger_calls}. "
            f"Each except block should log the error."
        )


# ---------------------------------------------------------------------------
# Blueprint stub fix
# ---------------------------------------------------------------------------

class TestBlueprintStub:
    """Verify the Flask Blueprint fallback stub accepts constructor arguments."""

    def test_blueprint_stub_accepts_args(self) -> None:
        """When Flask is unavailable, the Blueprint stub must accept positional args."""
        from src.ab_testing_framework import create_ab_testing_api, ABTestingEngine
        engine = ABTestingEngine()
        # This should NOT raise TypeError
        bp = create_ab_testing_api(engine)
        assert bp is not None
