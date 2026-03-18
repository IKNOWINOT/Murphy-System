"""Compatibility bridge for Murphy Core v3.

This additive bridge lets startup and handoff paths prefer the new v3 app
factory with operator surfaces included.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_app() -> FastAPI:
    from src.murphy_core.app_v3 import create_app

    return create_app()


def create_bridge_app(prefer_core_v3: bool = True) -> FastAPI:
    if prefer_core_v3:
        return create_murphy_core_v3_app()

    from src.runtime.murphy_core_bridge_v2 import create_bridge_app as create_v2_bridge

    return create_v2_bridge(prefer_core_v2=True)
