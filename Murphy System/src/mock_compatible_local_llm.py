"""
Mock-Compatible Local LLM — backward-compatibility shim.

The production implementation now lives in ``local_inference_engine.py``.
This module re-exports ``LocalInferenceEngine`` under the legacy alias
so that existing import paths continue to work.
"""

from src.local_inference_engine import LocalInferenceEngine as MockCompatibleLocalLLM  # noqa: F401

__all__ = ["MockCompatibleLocalLLM"]
