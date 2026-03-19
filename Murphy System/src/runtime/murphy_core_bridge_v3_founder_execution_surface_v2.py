"""Bridge for the Murphy Core founder execution surface v2.

This bridge prefers the founder/admin visibility surface aligned to runtime
truth v3, making it the canonical production bridge target.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_founder_execution_surface_v2_app() -> FastAPI:
    from src.murphy_core.app_v3_founder_execution_surface_v2 import create_app

    return create_app()


def create_bridge_app(prefer_founder_execution_surface_v2: bool = True) -> FastAPI:
    if prefer_founder_execution_surface_v2:
        return create_murphy_core_v3_founder_execution_surface_v2_app()

    from src.runtime.murphy_core_bridge_v3_founder_execution_surface import create_bridge_app as create_founder_v1_bridge

    return create_founder_v1_bridge(prefer_founder_execution_surface=True)
