"""Bridge for the Murphy Core canonical execution surface v4.

This bridge prefers the canonical execution runtime aligned to runtime truth v6,
while founder visibility remains an additive privileged overlay.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_canonical_execution_surface_v4_app() -> FastAPI:
    from src.murphy_core.app_v3_canonical_execution_surface_v4 import create_app

    return create_app()


def create_bridge_app(prefer_canonical_execution_surface_v4: bool = True) -> FastAPI:
    if prefer_canonical_execution_surface_v4:
        return create_murphy_core_v3_canonical_execution_surface_v4_app()

    from src.runtime.murphy_core_bridge_v3_canonical_execution_surface_v3 import create_bridge_app as create_canonical_v3_bridge

    return create_canonical_v3_bridge(prefer_canonical_execution_surface_v3=True)
