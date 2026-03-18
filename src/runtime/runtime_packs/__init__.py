"""Murphy System — Runtime Packs package."""
# Copyright © 2020 Inoni Limited Liability Company / Creator: Corey Post / License: BSL 1.1
"""
src/runtime/runtime_packs/__init__.py
Public surface for the runtime packs sub-package.

Import the pack registry and CAPABILITY_TO_PACK mapping from here.

    from src.runtime.runtime_packs import CAPABILITY_TO_PACK, get_default_packs
"""

from src.runtime.runtime_packs.registry import (
    CAPABILITY_TO_PACK,
    get_default_packs,
)

__all__ = ["CAPABILITY_TO_PACK", "get_default_packs"]
