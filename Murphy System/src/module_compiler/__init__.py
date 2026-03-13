"""
Module Compiler System for MFGC-AI

Converts bot capabilities into safe, auditable, deterministic execution modules.

This system:
- Analyzes code without executing it
- Extracts capabilities with I/O schemas
- Classifies determinism
- Generates sandbox profiles
- Provides capability discovery

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

from .compiler import ModuleCompiler
from .models.module_spec import Capability, FailureMode, ModuleSpec, SandboxProfile
from .registry.module_registry import ModuleRegistry

__version__ = "1.0.0"
__all__ = [
    "ModuleCompiler",
    "ModuleSpec",
    "Capability",
    "FailureMode",
    "SandboxProfile",
    "ModuleRegistry",
]
