"""
Murphy System 1.0 - Runtime Entry Point

This module is the thin entry-point for the Murphy System 1.0 runtime.
The implementation has been refactored into the ``src.runtime`` package
(INC-13 / H-04 / L-02) for maintainability.

Backward-compatible: all public symbols are re-exported from the
runtime package so existing callers continue to work.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger("murphy.launcher")

# ── Critical imports (fail-fast with diagnostics) ──────────────────────
_critical_errors: list = []

try:
    from src.runtime.app import create_app, main  # noqa: F401
except ImportError as e:
    _critical_errors.append(f"src.runtime.app: {e}")

try:
    from src.runtime.murphy_system_core import MurphySystem  # noqa: F401
except ImportError as e:
    _critical_errors.append(f"src.runtime.murphy_system_core: {e}")

try:
    from src.runtime.living_document import LivingDocument  # noqa: F401
except ImportError as e:
    _critical_errors.append(f"src.runtime.living_document: {e}")

if _critical_errors:
    _logger.critical("=" * 60)
    _logger.critical("MURPHY SYSTEM LAUNCHER — CRITICAL IMPORT FAILURES")
    for _err in _critical_errors:
        _logger.critical("  ✗ %s", _err)
    _logger.critical("=" * 60)
    _logger.critical("Cannot start. Fix the above imports and retry.")
    sys.exit(1)

# ── Optional bulk re-exports (backward compatibility) ──────────────────
# _deps defines __all__ with 140+ symbols; wildcard is bounded.
try:
    from src.runtime._deps import *  # noqa: F401,F403
    from src.runtime._deps import __all__ as _deps_all
    _logger.info(
        "Murphy System launcher: %d symbols loaded from _deps", len(_deps_all)
    )
except ImportError as e:
    _logger.warning("Optional _deps bulk import failed: %s", e)
    _logger.warning("Core server will still start; some subsystems unavailable.")

# ── Startup ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _logger.info("Murphy System 1.0 — starting via launcher")
    main()