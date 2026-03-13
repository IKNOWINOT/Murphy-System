"""
Document Export package.

Exports the key public classes used by the Murphy System pipeline.
"""

from __future__ import annotations

from .brand_registry import BrandProfile, BrandRegistry
from .export_pipeline import ExportPipeline, ExportResult
from .style_rewriter import DocumentStyleRewriter

# Lazily import the API helpers to avoid a hard FastAPI dependency at import time.
# These names are NOT included in __all__ because they are not unconditionally
# importable — callers should import them directly from .api when needed.
try:
    from .api import ExportRequest, BrandCreateRequest, create_router  # noqa: F401
except ImportError:  # FastAPI not installed
    pass

__all__ = [
    "BrandProfile",
    "BrandRegistry",
    "DocumentStyleRewriter",
    "ExportPipeline",
    "ExportResult",
]
