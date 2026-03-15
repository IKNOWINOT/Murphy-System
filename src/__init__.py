"""
Deterministic-Gated Generative Chatbot
A Murphy-resistant, internet-connected system
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Corey Post"
__all__: list[str] = ["matrix_bridge"]

# ---------------------------------------------------------------------------
# Matrix Bridge — lazy import so missing matrix-nio doesn't break startup
# ---------------------------------------------------------------------------
try:
    from . import matrix_bridge  # noqa: F401
except Exception:  # pragma: no cover
    import logging as _logging

    _logging.getLogger(__name__).debug(
        "matrix_bridge could not be imported at package init time; "
        "it will be available once dependencies are installed."
    )
