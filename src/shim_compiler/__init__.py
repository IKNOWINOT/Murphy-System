"""
Shim Compiler — generates bot shim files from manifests.

Keeps all bot shim implementations in sync with a single source of truth
while preserving each bot's independent deployment.
"""

from .compiler import ShimCompiler
from .schemas import BotManifest, CompileResult, ShimDrift

__all__ = ["ShimCompiler", "BotManifest", "CompileResult", "ShimDrift"]
