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

# Re-export everything from the runtime package for backward compatibility
from src.runtime._deps import *  # noqa: F401,F403
from src.runtime.living_document import LivingDocument  # noqa: F401
from src.runtime.murphy_system_core import MurphySystem  # noqa: F401
from src.runtime.app import create_app, main  # noqa: F401


if __name__ == "__main__":
    main()
