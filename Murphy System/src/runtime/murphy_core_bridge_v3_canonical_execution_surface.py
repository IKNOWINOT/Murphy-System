"""Bridge for the Murphy Core canonical execution surface.

This bridge prefers the canonical execution runtime for all users and
automations, while founder visibility remains an additive privileged overlay.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_canonical_execution_surface_app() -> FastAPI:
    from src.murphy_core.app_v3_canonical_execution_surface import create_app

    return create_app()


def create_bridge_app(prefer_canonical_execution_surface: bool = True) -> FastAPI:
    if prefer_canonical_execution_surface:
        return create_murphy_core_v3_canonical_execution_surface_app()

    from src.runtime.murphy_core_bridge_v3_founder_execution_surface_v3 import create_bridge_app as create_founder_v3_bridge

    return create_founder_v3_bridge(prefer_founder_execution_surface_v3=True)
