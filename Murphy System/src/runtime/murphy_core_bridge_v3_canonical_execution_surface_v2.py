"""Bridge for the Murphy Core canonical execution surface v2.

This bridge prefers the canonical execution runtime aligned to runtime truth v4,
while founder visibility remains an additive privileged overlay.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_canonical_execution_surface_v2_app() -> FastAPI:
    from src.murphy_core.app_v3_canonical_execution_surface_v2 import create_app

    return create_app()


def create_bridge_app(prefer_canonical_execution_surface_v2: bool = True) -> FastAPI:
    if prefer_canonical_execution_surface_v2:
        return create_murphy_core_v3_canonical_execution_surface_v2_app()

    from src.runtime.murphy_core_bridge_v3_canonical_execution_surface import create_bridge_app as create_canonical_v1_bridge

    return create_canonical_v1_bridge(prefer_canonical_execution_surface=True)
