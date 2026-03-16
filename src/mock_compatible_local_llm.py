"""
Mock-Compatible Local LLM — backward-compatibility shim.

DEPRECATED: Import directly from ``src.local_inference_engine`` instead.
The production implementation now lives in ``local_inference_engine.py``.
This module re-exports ``LocalInferenceEngine`` under the legacy alias
so that existing import paths continue to work.
"""

import warnings as _warnings

_warnings.warn(
    "mock_compatible_local_llm is deprecated — import from src.local_inference_engine instead.",
    DeprecationWarning,
    stacklevel=2,
)
del _warnings

from src.local_inference_engine import LocalInferenceEngine as MockCompatibleLocalLLM  # noqa: F401

__all__ = ["MockCompatibleLocalLLM"]
