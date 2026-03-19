"""Bridge for the Murphy Core founder execution surface v3.

This bridge prefers the founder/admin visibility surface v3 with capability-
aware gating and subsystem family selection, making it the canonical
production bridge target.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_founder_execution_surface_v3_app() -> FastAPI:
    from src.murphy_core.app_v3_founder_execution_surface_v3 import create_app

    return create_app()


def create_bridge_app(prefer_founder_execution_surface_v3: bool = True) -> FastAPI:
    if prefer_founder_execution_surface_v3:
        return create_murphy_core_v3_founder_execution_surface_v3_app()

    from src.runtime.murphy_core_bridge_v3_founder_execution_surface_v2 import create_bridge_app as create_founder_v2_bridge

    return create_founder_v2_bridge(prefer_founder_execution_surface_v2=True)
