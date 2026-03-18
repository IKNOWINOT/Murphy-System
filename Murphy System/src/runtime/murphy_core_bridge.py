"""Compatibility bridge from legacy runtime paths into Murphy Core.

This file lets the existing runtime import path adopt the new canonical
Murphy Core app without immediately deleting the legacy runtime.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_app() -> FastAPI:
    from src.murphy_core.app import create_app

    return create_app()


def create_bridge_app(prefer_core: bool = True) -> FastAPI:
    """Return Murphy Core when preferred, otherwise fall back to legacy runtime.

    This keeps migration explicit and reversible.
    """
    if prefer_core:
        return create_murphy_core_app()

    from src.runtime.app import create_app as create_legacy_app

    return create_legacy_app()
